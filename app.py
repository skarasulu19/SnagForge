#!/usr/bin/env python3
"""SnagForge: an independent open-source Linux capture workbench."""
import io
import shutil
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
from PIL import Image
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QImage, QTransform
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox, QToolBar, QColorDialog,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QInputDialog, QListWidget,
    QSplitter, QAbstractItemView)
from editor import Canvas, RegionDialog
from workers import CaptureWorker, Recorder
from media import stitch

CAPTURES=Path.home()/'Pictures'/'SnagForge'

def pil_image(image):
    from PySide6.QtCore import QBuffer, QIODevice
    buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer,'PNG')
    return Image.open(io.BytesIO(bytes(buffer.data()))).copy()

def qt_image(image):
    raw=image.convert('RGBA').tobytes()
    return QImage(raw,image.width,image.height,image.width*4,QImage.Format.Format_RGBA8888).copy()

def button(label,fn,layout):
    b=QPushButton(label);b.clicked.connect(fn);layout.addWidget(b);return b

class ScrollDialog(QDialog):
    def __init__(self,parent):
        super().__init__(parent)
        self.main=parent;self.sections=[];self.result_image=None
        self.setWindowTitle('Scrolling capture · guided stitching');self.resize(600,490)
        layout=QVBoxLayout(self)
        description=QLabel('1. Capture a section of the page.\n2. Scroll down, keeping some overlap.\n3. Capture the next section with the same area.\n4. Set overlap in image pixels, then stitch.\n\nUse a constant scroll distance. Trim sticky headers/footers below.\nDifferent overlap distances require separate stitches.')
        description.setWordWrap(True);layout.addWidget(description)
        self.list=QListWidget();layout.addWidget(self.list)
        row=QHBoxLayout();layout.addLayout(row)
        self.capture_button=button('Capture section',self.capture,row)
        button('Import sections',self.import_sections,row)
        button('Remove last',self.remove,row)
        self.overlap=QSpinBox();self.overlap.setRange(0,20000);self.overlap.setValue(120)
        self.top=QSpinBox();self.top.setRange(0,20000)
        self.bottom=QSpinBox();self.bottom.setRange(0,20000)
        for title,widget in [('Overlap (px)',self.overlap),('Trim header (px)',self.top),('Trim footer (px)',self.bottom)]:
            line=QHBoxLayout();line.addWidget(QLabel(title));line.addWidget(widget);layout.addLayout(line)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton('Stitch into editor',QDialogButtonBox.ButtonRole.AcceptRole).clicked.connect(self.finish)
        buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def add(self,image):
        self.sections.append(image.copy());self.list.addItem(f'Section {len(self.sections)} · {image.width()} × {image.height()}')
    def remove(self):
        if self.sections:
            self.sections.pop();self.list.takeItem(self.list.count()-1)
    def import_sections(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Import sections in top-to-bottom order','','Images (*.png *.jpg *.jpeg *.webp)')
        for path in paths:
            im=QImage(path)
            if not im.isNull():self.add(im)
    def capture(self):
        self.hide();self.main.hide();self.capture_button.setEnabled(False)
        QTimer.singleShot(500,self.begin)
    def begin(self):
        self.worker=CaptureWorker()
        self.worker.image.connect(self.receive)
        self.worker.error.connect(self.main.error)
        self.worker.finished.connect(self.restore)
        self.worker.start()
    def restore(self):
        self.main.show();self.show();self.raise_();self.capture_button.setEnabled(True)
    def receive(self,path):
        self.restore()
        image=QImage(path)
        if image.isNull():return
        chooser=RegionDialog(image,self)
        if chooser.exec():self.add(image.copy(chooser.region) if chooser.region else image)
    def finish(self):
        try:
            result=stitch([pil_image(x) for x in self.sections],self.overlap.value(),self.top.value(),self.bottom.value())
            self.result_image=qt_image(result);self.accept()
        except Exception as e:self.main.error(str(e))
    def reject(self):
        if getattr(self,'worker',None) and self.worker.isRunning():return
        super().reject()

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('SnagForge · Capture. Annotate. Explain.');self.resize(1360,860)
        self.recorder=None;self.capture_worker=None;self.busy=False;self.dirty=False
        self.recording_since=None
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root)
        header=QHBoxLayout();layout.addLayout(header)
        brand=QLabel('SNAGFORGE');brand.setObjectName('brand');header.addWidget(brand)
        tag=QLabel('CAPTURE. ANNOTATE. EXPLAIN.');tag.setObjectName('muted');header.addWidget(tag)
        header.addStretch();self.capture_btn=button('＋ New capture',self.capture,header)
        button('Open image',self.open_image,header);button('Paste',self.paste,header)
        button('Export image',self.save,header)
        controls=QHBoxLayout();layout.addLayout(controls)
        self.mode=QComboBox();self.mode.addItems(['MP4 video','MP3 audio']);controls.addWidget(self.mode)
        self.audio=QComboBox();self.audio.addItems(['None','Microphone','System audio']);controls.addWidget(self.audio)
        self.region=QCheckBox('Select region');self.region.setChecked(True);controls.addWidget(self.region)
        controls.addWidget(QLabel('Delay (s)'));self.delay=QSpinBox();self.delay.setRange(0,30);controls.addWidget(self.delay)
        self.record_btn=button('● Record',self.record,controls)
        self.stop_btn=button('■ Stop & save',self.stop,controls);self.stop_btn.setEnabled(False)
        controls.addStretch();button('Scrolling capture',self.scrolling,controls)
        splitter=QSplitter();layout.addWidget(splitter,1)
        sidebar=QWidget();side=QVBoxLayout(sidebar);side.setContentsMargins(0,8,8,0)
        side.addWidget(QLabel('ANNOTATE'))
        self.tool=QComboBox();self.tool.addItems(['Arrow','Pen','Line','Rectangle','Ellipse','Text','Step','Highlight','Pixelate','Redact','Spotlight','Crop'])
        side.addWidget(self.tool)
        button('Annotation color',self.pick_color,side)
        side.addWidget(QLabel('Stroke / text size'))
        self.stroke=QSpinBox();self.stroke.setRange(1,30);self.stroke.setValue(5);side.addWidget(self.stroke)
        button('Undo · Ctrl+Z',lambda:self.canvas.undo(),side)
        button('Redo · Ctrl+Shift+Z',lambda:self.canvas.redo(),side)
        button('Copy image',self.copy,side)
        button('Rotate 90°',self.rotate,side)
        button('Resize image',self.resize_image,side)
        button('Extract text (OCR)',self.ocr,side)
        side.addSpacing(16);side.addWidget(QLabel('RECENT EXPORTS'))
        self.recent=QListWidget();self.recent.itemDoubleClicked.connect(self.open_recent);side.addWidget(self.recent,1)
        button('Open captures folder',self.open_folder,side)
        button('User manual',self.manual,side)
        sidebar.setMinimumWidth(220);sidebar.setMaximumWidth(280)
        self.canvas=Canvas();splitter.addWidget(sidebar);splitter.addWidget(self.canvas);splitter.setStretchFactor(1,1)
        self.tool.currentTextChanged.connect(lambda t:setattr(self.canvas,'tool',t))
        self.stroke.valueChanged.connect(lambda n:setattr(self.canvas,'stroke_width',n))
        self.canvas.changed.connect(self.changed)
        self.statusBar().showMessage('Ready · Local files · Ubuntu / Wayland capture via desktop portals')
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(1000)
        for key,fn in [('Ctrl+O',self.open_image),('Ctrl+S',self.save),('Ctrl+C',self.copy),('Ctrl+V',self.paste),('Ctrl+Z',self.canvas.undo),('Ctrl+Shift+Z',self.canvas.redo),('Ctrl+N',self.capture)]:
            action=QAction(self);action.setShortcut(key);action.triggered.connect(fn);self.addAction(action)
        self.refresh_recent()

    def error(self,message):
        QMessageBox.warning(self,'SnagForge',message)
    def changed(self):
        self.dirty=True
        im=self.canvas.image
        self.statusBar().showMessage(f'{im.width():,} × {im.height():,} px · {self.tool.currentText()} · Drag to annotate')
    def can_replace(self):
        if not self.dirty:return True
        answer=QMessageBox.question(self,'Unsaved image','Export the current image before replacing it?',
            QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)
        if answer==QMessageBox.StandardButton.Save:return self.save()
        return answer==QMessageBox.StandardButton.Discard
    def load_image(self,image):
        if image.isNull():self.error('This image could not be opened.');return
        self.canvas.load(image);self.dirty=True
    def open_image(self):
        if not self.can_replace():return
        path,_=QFileDialog.getOpenFileName(self,'Open image','','Images (*.png *.jpg *.jpeg *.webp *.bmp)')
        if path:self.load_image(QImage(path))
    def paste(self):
        image=QApplication.clipboard().image()
        if image.isNull():self.error('The clipboard does not contain an image.');return
        if self.can_replace():self.load_image(image)
    def copy(self):
        if not self.canvas.image.isNull():
            QApplication.clipboard().setImage(self.canvas.image);self.statusBar().showMessage('Image copied to clipboard')
    def pick_color(self):
        color=QColorDialog.getColor(self.canvas.color,self)
        if color.isValid():self.canvas.color=color
    def rotate(self):
        if not self.canvas.image.isNull():self.canvas.commit(self.canvas.image.transformed(QTransform().rotate(90)))
    def resize_image(self):
        if self.canvas.image.isNull():return
        width,ok=QInputDialog.getInt(self,'Resize image','New width (aspect ratio is preserved):',self.canvas.image.width(),1,20000)
        if ok:self.canvas.commit(self.canvas.image.scaledToWidth(width,Qt.TransformationMode.SmoothTransformation))
    def save(self):
        if self.canvas.image.isNull():return False
        CAPTURES.mkdir(parents=True,exist_ok=True)
        path,selected=QFileDialog.getSaveFileName(self,'Export image',str(CAPTURES/f'capture-{datetime.now():%Y%m%d-%H%M%S}.png'),'PNG (*.png);;JPEG (*.jpg);;WebP (*.webp)')
        if not path:return False
        if not Path(path).suffix:path += '.jpg' if 'JPEG' in selected else '.webp' if 'WebP' in selected else '.png'
        if not self.canvas.image.save(path):self.error('Could not save the image. Check the filename and folder permissions.');return False
        self.dirty=False;self.statusBar().showMessage(f'Exported {path}');self.refresh_recent();return True
    def capture(self):
        if self.busy or not self.can_replace():return
        self.busy=True;self.capture_btn.setEnabled(False);self.hide()
        QTimer.singleShot(max(450,self.delay.value()*1000),self.begin_capture)
    def begin_capture(self):
        self.capture_worker=CaptureWorker()
        self.capture_worker.image.connect(self.received_capture)
        self.capture_worker.error.connect(self.error)
        self.capture_worker.finished.connect(self.end_capture)
        self.capture_worker.start()
    def end_capture(self):
        self.show();self.raise_();self.busy=False;self.capture_btn.setEnabled(True)
    def received_capture(self,path):
        self.show();self.raise_()
        image=QImage(path)
        if image.isNull():self.error('Screenshot could not be read.');return
        chooser=RegionDialog(image,self)
        if chooser.exec():self.load_image(image.copy(chooser.region) if chooser.region else image)
    def scrolling(self):
        if self.busy or not self.can_replace():return
        self.busy=True
        dialog=ScrollDialog(self)
        if dialog.exec() and dialog.result_image is not None:self.load_image(dialog.result_image)
        self.busy=False
    def record(self):
        if self.recorder and self.recorder.isRunning():return
        if self.busy:return
        mode=self.mode.currentText();audio=self.audio.currentText()
        if mode=='MP3 audio' and audio=='None':self.error('Choose Microphone or System audio for MP3.');return
        if not shutil.which('gst-launch-1.0'):self.error('Install GStreamer first: see README.md.');return
        CAPTURES.mkdir(parents=True,exist_ok=True)
        suffix='mp3' if mode=='MP3 audio' else 'mp4'
        path,_=QFileDialog.getSaveFileName(self,'Save recording',str(CAPTURES/f'recording-{datetime.now():%Y%m%d-%H%M%S}.{suffix}'),f'{suffix.upper()} (*.{suffix})')
        if not path:return
        if not path.lower().endswith('.'+suffix):path+='.'+suffix
        self.recorder=Recorder(path,mode,audio,self.region.isChecked())
        self.recorder.preview.connect(self.video_region)
        self.recorder.started.connect(self.recording_started)
        self.recorder.saved.connect(self.recording_saved)
        self.recorder.error.connect(self.error)
        self.recorder.finished.connect(self.recording_finished)
        self.busy=True;self.record_btn.setEnabled(False);self.capture_btn.setEnabled(False);self.stop_btn.setEnabled(True)
        self.statusBar().showMessage('Preparing capture · approve the desktop picker, then select a region')
        self.showMinimized()
        QTimer.singleShot(max(450,self.delay.value()*1000),self.recorder.start)
    def video_region(self,path):
        self.showNormal();self.raise_()
        image=QImage(path)
        if image.isNull():
            self.recorder.cancelled=True;self.recorder.selection_ready.set();return
        chooser=RegionDialog(image,self)
        if chooser.exec():
            rect=chooser.region or image.rect()
            # Even width/height for H.264 4:2:0. Preserve selected origin.
            width=rect.width()//2*2;height=rect.height()//2*2
            if width<2 or height<2:self.recorder.cancelled=True
            else:self.recorder.crop=(rect.x(),rect.y(),image.width()-rect.x()-width,image.height()-rect.y()-height)
        else:self.recorder.cancelled=True
        self.recorder.selection_ready.set()
        if not self.recorder.cancelled:self.showMinimized()
    def recording_started(self):
        self.recording_since=time.monotonic();self.tick()
    def tick(self):
        if self.recording_since is not None:
            elapsed=int(time.monotonic()-self.recording_since)
            self.statusBar().showMessage(f'● Recording {elapsed//60:02}:{elapsed%60:02} · Restore SnagForge and press Stop & save')
    def stop(self):
        if self.recorder:
            self.recorder.stop_event.set();self.stop_btn.setEnabled(False)
            self.statusBar().showMessage('Finalizing recording… keep SnagForge open')
    def recording_saved(self,path):
        self.refresh_recent();QMessageBox.information(self,'Recording saved',path)
    def recording_finished(self):
        self.recording_since=None;self.busy=False;self.record_btn.setEnabled(True)
        self.capture_btn.setEnabled(True);self.stop_btn.setEnabled(False);self.showNormal();self.raise_()
        self.statusBar().showMessage('Ready · Recording finished or cancelled')
    def refresh_recent(self):
        self.recent.clear()
        if CAPTURES.exists():
            paths=sorted((p for p in CAPTURES.iterdir() if p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.mp4','.mp3')),key=lambda p:p.stat().st_mtime,reverse=True)
            for path in paths[:80]:
                self.recent.addItem(path.name)
                self.recent.item(self.recent.count()-1).setData(Qt.ItemDataRole.UserRole,str(path))
    def open_recent(self,item):
        path=Path(item.data(Qt.ItemDataRole.UserRole))
        if path.suffix.lower() in ('.mp4','.mp3'):QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        elif self.can_replace():self.load_image(QImage(str(path)))
    def open_folder(self):
        CAPTURES.mkdir(parents=True,exist_ok=True);QDesktopServices.openUrl(QUrl.fromLocalFile(str(CAPTURES)))
    def manual(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(__file__).parent/'docs'/'MANUAL.html')))
    def ocr(self):
        if self.canvas.image.isNull():return
        if not shutil.which('tesseract'):self.error('Install OCR with: sudo apt install tesseract-ocr');return
        import tempfile
        try:
            with tempfile.TemporaryDirectory(prefix='snagforge-ocr-') as folder:
                path=str(Path(folder)/'image.png');self.canvas.image.save(path)
                result=subprocess.run(['tesseract',path,'stdout'],capture_output=True,text=True,timeout=40)
                if result.returncode:raise RuntimeError(result.stderr)
            text,ok=QInputDialog.getMultiLineText(self,'Extracted text','Review and copy recognized text:',result.stdout)
            if ok:QApplication.clipboard().setText(text)
        except Exception as e:self.error(str(e))
    def closeEvent(self,event):
        if self.busy:
            self.error('Finish or cancel the active capture first. For recording, press Stop & save and wait for finalization.')
            event.ignore();return
        if not self.can_replace():event.ignore();return
        event.accept()

STYLE='''
QMainWindow,QDialog { background:#191f2d; color:#e5edf7; }
QWidget { font-family:"DejaVu Sans"; font-size:13px; color:#e5edf7; }
QLabel#brand { font-size:23px; font-weight:800; color:#64dfcb; padding:12px 0; }
QLabel#muted { color:#8fa0b8; font-size:10px; padding-left:14px; }
QPushButton { background:#2b3548; border:1px solid #3b4860; border-radius:7px; padding:9px 12px; }
QPushButton:hover { background:#38465d; border-color:#64dfcb; }
QPushButton:disabled { color:#69788e; background:#202838; }
QComboBox,QSpinBox { background:#252f42; border:1px solid #3b4860; padding:7px; border-radius:5px; }
QListWidget { background:#141b29; border:1px solid #303c52; border-radius:6px; }
QStatusBar { background:#111723; color:#8fa0b8; padding:5px; }
QSplitter::handle { background:#303c52; width:1px; }
'''

def main():
    app=QApplication(sys.argv);app.setApplicationName('SnagForge');app.setDesktopFileName('snagforge')
    app.setStyle('Fusion');app.setStyleSheet(STYLE)
    window=Window();window.show()
    if len(sys.argv)>1 and Path(sys.argv[1]).is_file():window.load_image(QImage(sys.argv[1]))
    return app.exec()

if __name__=='__main__':sys.exit(main())
