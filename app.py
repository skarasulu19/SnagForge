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
from PySide6.QtGui import QAction, QColor, QDesktopServices, QImage, QPainter, QTransform
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox, QToolBar, QColorDialog,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QInputDialog, QListWidget,
    QSplitter, QAbstractItemView, QFrame, QToolButton, QButtonGroup, QGridLayout)
from editor import Canvas, RegionDialog
from workers import CaptureWorker, Recorder
from media import stitch
from ui import STYLE, icon, action_button, caption, field, ReferenceWindow

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
        self.setWindowTitle('SnagForge · Capture studio');self.resize(1520,940)
        self.setMinimumSize(1250,790)
        self.recorder=None;self.capture_worker=None;self.busy=False;self.dirty=False
        self.recording_since=None;self.pins=[]
        root=QWidget();self.setCentralWidget(root)
        shell=QHBoxLayout(root);shell.setContentsMargins(0,0,0,0);shell.setSpacing(0)
        sidebar=QWidget();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(222)
        shell.addWidget(sidebar)
        side=QVBoxLayout(sidebar);side.setContentsMargins(20,26,18,18);side.setSpacing(9)
        brandrow=QHBoxLayout();brandrow.setSpacing(10)
        logo=QLabel();logo.setObjectName('logo');logo.setPixmap(icon('capture','#ffffff',23).pixmap(23,23));brandrow.addWidget(logo)
        brandcol=QVBoxLayout();brandcol.setSpacing(3)
        brand=QLabel('SnagForge');brand.setObjectName('brand');brandcol.addWidget(brand)
        sub=QLabel('CAPTURE. CREATE. SHARE.');sub.setObjectName('sideSub');brandcol.addWidget(sub)
        brandrow.addLayout(brandcol);side.addLayout(brandrow);side.addSpacing(28)
        label=QLabel('WORKSPACE');label.setObjectName('sideCaption');side.addWidget(label);side.addSpacing(3)
        side.addWidget(action_button('  Image editor','image',lambda:self.canvas.setFocus(),'activeNav','#b6a6ff'))
        side.addWidget(action_button('  Screen recorder','video',self.focus_recording,'nav','#8190ac'))
        side.addWidget(action_button('  Scrolling capture','scroll',self.scrolling,'nav','#8190ac'))
        side.addWidget(action_button('  Capture folder','folder',self.open_folder,'nav','#8190ac'))
        side.addSpacing(26)
        recentrow=QHBoxLayout();label=QLabel('RECENT EXPORTS');label.setObjectName('sideCaption');recentrow.addWidget(label);recentrow.addStretch()
        self.recent_count=QLabel('0');self.recent_count.setObjectName('sideSub');recentrow.addWidget(self.recent_count);side.addLayout(recentrow)
        self.recent=QListWidget();self.recent.setWordWrap(True);self.recent.itemDoubleClicked.connect(self.open_recent)
        side.addWidget(self.recent,1)
        self.recent_empty=QLabel('Your exported captures\nwill appear here.');self.recent_empty.setObjectName('sideSub');side.addWidget(self.recent_empty)
        side.addSpacing(14)
        privacy=QLabel('●  Local by default');privacy.setStyleSheet('color:#73c5ac;font-size:11px;padding:10px 0;');side.addWidget(privacy)
        side.addWidget(action_button('  Help & user manual','help',self.manual,'sideQuiet','#8292ae'))
        foot=QHBoxLayout();version=QLabel('v0.2.1');version.setObjectName('sideSub');foot.addWidget(version)
        alpha=QLabel('ALPHA');alpha.setObjectName('alpha');foot.addWidget(alpha);foot.addStretch();side.addLayout(foot)

        workspace=QWidget();shell.addWidget(workspace,1)
        layout=QVBoxLayout(workspace);layout.setContentsMargins(28,25,28,6);layout.setSpacing(18)
        top=QHBoxLayout();titles=QVBoxLayout();titles.setSpacing(5)
        title=QLabel('Capture studio');title.setObjectName('title');titles.addWidget(title)
        subtitle=QLabel('A little clarity goes a long way.');subtitle.setObjectName('subtitle');titles.addWidget(subtitle);top.addLayout(titles);top.addStretch()
        self.capture_btn=action_button('New capture','capture',self.capture,'primary','#ffffff');top.addWidget(self.capture_btn)
        top.addWidget(action_button('Export image','export',self.save,'export','#ffffff'));layout.addLayout(top)

        editorrow=QHBoxLayout();editorrow.setSpacing(16);layout.addLayout(editorrow,1)
        card=QFrame();card.setObjectName('editorCard');editorrow.addWidget(card,1)
        cardlayout=QVBoxLayout(card);cardlayout.setContentsMargins(0,0,0,0);cardlayout.setSpacing(0)
        imagehead=QFrame();imagehead.setObjectName('imageHeader');ih=QHBoxLayout(imagehead);ih.setContentsMargins(16,14,16,12)
        nameicon=QLabel();nameicon.setPixmap(icon('image','#8e83bd',17).pixmap(17,17));ih.addWidget(nameicon)
        self.image_title=QLabel('Untitled capture');self.image_title.setObjectName('filename');ih.addWidget(self.image_title);ih.addStretch()
        chip=QLabel('LOCAL WORKSPACE');chip.setObjectName('chip');ih.addWidget(chip);cardlayout.addWidget(imagehead)
        toolbar=QFrame();toolbar.setObjectName('toolbar');tools=QHBoxLayout(toolbar);tools.setContentsMargins(10,4,10,10);tools.setSpacing(3)
        self.tool=QComboBox();names=['Arrow','Pen','Line','Rectangle','Ellipse','Text','Step','Highlight','Pixelate','Blur','Redact','Spotlight','Crop'];self.tool.addItems(names);self.tool.hide()
        self.tool_group=QButtonGroup(self);self.tool_buttons={}
        for name in names:
            control=QToolButton();control.setIcon(icon(name));control.setCheckable(True)
            control.setToolTip(name);control.setAccessibleName(name);control.setFixedSize(34,35)
            control.setCursor(Qt.CursorShape.PointingHandCursor)
            control.clicked.connect(lambda checked=False,n=name:self.tool.setCurrentText(n))
            self.tool_group.addButton(control);self.tool_buttons[name]=control;tools.addWidget(control)
        self.tool_buttons['Arrow'].setChecked(True);tools.addStretch()
        for text,name,fn in [('Undo','undo',lambda:self.canvas.undo()),('Redo','redo',lambda:self.canvas.redo())]:
            control=QToolButton();control.setIcon(icon(name));control.setToolTip(text);control.setAccessibleName(text);control.clicked.connect(fn);tools.addWidget(control)
        cardlayout.addWidget(toolbar)
        self.canvas=Canvas();cardlayout.addWidget(self.canvas,1)
        canvasfoot=QHBoxLayout();canvasfoot.setContentsMargins(16,9,16,11)
        self.image_info=QLabel('No image loaded');self.image_info.setObjectName('canvasInfo');canvasfoot.addWidget(self.image_info);canvasfoot.addStretch()
        fit=QLabel('Fit to workspace');fit.setObjectName('canvasInfo');canvasfoot.addWidget(fit);cardlayout.addLayout(canvasfoot)

        inspector=QFrame();inspector.setObjectName('inspector');inspector.setFixedWidth(204);editorrow.addWidget(inspector)
        props=QVBoxLayout(inspector);props.setContentsMargins(17,18,17,16);props.setSpacing(12)
        label=QLabel('Tool properties');label.setObjectName('sectionTitle');props.addWidget(label)
        self.active_tool=QLabel('ARROW');self.active_tool.setObjectName('caption');props.addWidget(self.active_tool);props.addSpacing(8)
        props.addWidget(caption('COLOR'))
        swatches=QHBoxLayout();swatches.setSpacing(5);self.color_buttons=[]
        for color in ['#7561ee','#ff7759','#38b997','#f4b846','#26334a']:
            control=QPushButton();control.setObjectName('swatch');control.setFixedSize(25,25)
            control.setToolTip(color);control.setAccessibleName('Color '+color)
            control.setStyleSheet('background:'+color+';');control.clicked.connect(lambda checked=False,c=color:self.set_color(QColor(c)))
            swatches.addWidget(control);self.color_buttons.append(control)
        props.addLayout(swatches)
        self.color_btn=action_button('Custom color','image',self.pick_color,'quiet');props.addWidget(self.color_btn)
        self.stroke=QSpinBox();self.stroke.setRange(1,30);self.stroke.setValue(5);self.stroke.setSuffix(' px')
        props.addWidget(field('STROKE / TEXT SIZE',self.stroke));props.addSpacing(16)
        label=QLabel('Quick actions');label.setObjectName('sectionTitle');props.addWidget(label)
        for text,name,fn in [('Copy image','copy',self.copy),('Pin reference','pin',self.pin_image),('Rotate 90°','rotate',self.rotate),('Resize image','resize',self.resize_image),('Border & shadow','frame',self.add_frame),('Extract text','ocr',self.ocr)]:
            control=action_button(text,name,fn,'quiet');control.setStyleSheet('text-align:left;');props.addWidget(control)
        props.addStretch()
        tips=QLabel('GOOD TO KNOW\n\nDrag on the image to annotate.\nCtrl+Z brings you back.');tips.setWordWrap(True);tips.setStyleSheet('color:#9aa5b5;font-size:10px;line-height:1.5;');props.addWidget(tips)

        recordcard=QFrame();recordcard.setObjectName('recordCard');self.record_card=recordcard
        rl=QVBoxLayout(recordcard);rl.setContentsMargins(18,15,18,16);rl.setSpacing(13)
        rh=QHBoxLayout();recordicon=QLabel();recordicon.setPixmap(icon('video','#8a7de0',18).pixmap(18,18));rh.addWidget(recordicon)
        label=QLabel('Screen & audio recording');label.setObjectName('sectionTitle');rh.addWidget(label);rh.addStretch()
        self.record_badge=QLabel('READY');self.record_badge.setObjectName('caption');rh.addWidget(self.record_badge);rl.addLayout(rh)
        controls=QHBoxLayout();controls.setSpacing(14)
        self.mode=QComboBox();self.mode.addItems(['MP4 video','MP3 audio']);self.mode.setMinimumWidth(130);controls.addWidget(field('FORMAT',self.mode),1)
        self.audio=QComboBox();self.audio.addItems(['None','Microphone','System audio']);self.audio.setMinimumWidth(140);controls.addWidget(field('AUDIO SOURCE',self.audio),1)
        self.delay=QSpinBox();self.delay.setRange(0,30);self.delay.setSuffix(' sec');controls.addWidget(field('START DELAY',self.delay))
        self.region=QCheckBox('Select region');self.region.setChecked(True);controls.addWidget(self.region)
        self.record_btn=action_button('Record','record',self.record,'primary','#ffffff');controls.addWidget(self.record_btn)
        self.stop_btn=action_button('Stop & save','stop',self.stop);self.stop_btn.setEnabled(False);controls.addWidget(self.stop_btn)
        rl.addLayout(controls);layout.addWidget(recordcard)
        bottom=QHBoxLayout();bottom.setSpacing(8)
        bottom.addWidget(action_button('Open image','image',self.open_image,'quiet'));bottom.addWidget(action_button('Paste image','paste',self.paste,'quiet'));bottom.addStretch()
        notice=QLabel('Ubuntu / Wayland  ·  Desktop recording validation pending');notice.setObjectName('canvasInfo');bottom.addWidget(notice);layout.addLayout(bottom)
        self.tool.currentTextChanged.connect(self.select_tool)
        self.stroke.valueChanged.connect(lambda n:setattr(self.canvas,'stroke_width',n))
        self.canvas.changed.connect(self.changed);self.set_color(QColor('#7561ee'))
        self.statusBar().showMessage('Ready to capture something worth explaining.')
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(1000)
        for key,fn in [('Ctrl+O',self.open_image),('Ctrl+S',self.save),('Ctrl+C',self.copy),('Ctrl+V',self.paste),('Ctrl+Z',self.canvas.undo),('Ctrl+Shift+Z',self.canvas.redo),('Ctrl+N',self.capture)]:
            action=QAction(self);action.setShortcut(key);action.triggered.connect(fn);self.addAction(action)
        self.refresh_recent()

    def select_tool(self,name):
        self.canvas.tool=name;self.active_tool.setText(name.upper());self.tool_buttons[name].setChecked(True)
    def set_color(self,color):
        self.canvas.color=color;self.color_btn.setText(color.name().upper())
    def focus_recording(self):
        self.mode.setFocus();self.statusBar().showMessage('Choose a format and audio source, then press Record.')
    def pin_image(self):
        if self.canvas.image.isNull():return
        pin=ReferenceWindow(self.canvas.image,self);self.pins.append(pin)
        pin.finished.connect(lambda result,p=pin:self.pins.remove(p) if p in self.pins else None)
        pin.show()

    def error(self,message):
        QMessageBox.warning(self,'SnagForge',message)
    def changed(self):
        self.dirty=True
        im=self.canvas.image
        self.image_info.setText(f'{im.width():,} × {im.height():,} px  ·  Unsaved changes')
        self.image_title.setText('Untitled capture')
        self.statusBar().showMessage(f'{self.tool.currentText()} · Drag on your image to annotate')
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
        if color.isValid():self.set_color(color)
    def rotate(self):
        if not self.canvas.image.isNull():self.canvas.commit(self.canvas.image.transformed(QTransform().rotate(90)))
    def resize_image(self):
        if self.canvas.image.isNull():return
        width,ok=QInputDialog.getInt(self,'Resize image','New width (aspect ratio is preserved):',self.canvas.image.width(),1,20000)
        if ok:self.canvas.commit(self.canvas.image.scaledToWidth(width,Qt.TransformationMode.SmoothTransformation))
    def add_frame(self):
        if self.canvas.image.isNull():return
        source=self.canvas.image;margin=32
        result=QImage(source.width()+margin*2,source.height()+margin*2,QImage.Format.Format_ARGB32)
        result.fill(QColor('#eef1f7'));painter=QPainter(result)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(21,31,49,55))
        painter.drawRoundedRect(margin+8,margin+8,source.width(),source.height(),8,8)
        painter.drawImage(margin,margin,source);painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor('#d8deea'));painter.drawRect(margin,margin,source.width()-1,source.height()-1)
        painter.end();self.canvas.commit(result)
    def save(self):
        if self.canvas.image.isNull():return False
        CAPTURES.mkdir(parents=True,exist_ok=True)
        path,selected=QFileDialog.getSaveFileName(self,'Export image',str(CAPTURES/f'capture-{datetime.now():%Y%m%d-%H%M%S}.png'),'PNG (*.png);;JPEG (*.jpg);;WebP (*.webp)')
        if not path:return False
        if not Path(path).suffix:path += '.jpg' if 'JPEG' in selected else '.webp' if 'WebP' in selected else '.png'
        if not self.canvas.image.save(path):self.error('Could not save the image. Check the filename and folder permissions.');return False
        self.dirty=False;self.image_title.setText(Path(path).name);self.image_info.setText(f'{self.canvas.image.width():,} × {self.canvas.image.height():,} px  ·  Saved');self.statusBar().showMessage(f'Exported {path}');self.refresh_recent();return True
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
        self.recording_since=time.monotonic();self.record_badge.setText('RECORDING');self.tick()
    def tick(self):
        if self.recording_since is not None:
            elapsed=int(time.monotonic()-self.recording_since)
            self.record_badge.setText(f'RECORDING  {elapsed//60:02}:{elapsed%60:02}')
            self.statusBar().showMessage(f'● Recording {elapsed//60:02}:{elapsed%60:02} · Restore SnagForge and press Stop & save')
    def stop(self):
        if self.recorder:
            self.recorder.stop_event.set();self.stop_btn.setEnabled(False)
            self.statusBar().showMessage('Finalizing recording… keep SnagForge open')
    def recording_saved(self,path):
        self.refresh_recent();QMessageBox.information(self,'Recording saved',path)
    def recording_finished(self):
        self.recording_since=None;self.record_badge.setText('READY');self.busy=False;self.record_btn.setEnabled(True)
        self.capture_btn.setEnabled(True);self.stop_btn.setEnabled(False);self.showNormal();self.raise_()
        self.statusBar().showMessage('Ready · Recording finished or cancelled')
    def refresh_recent(self):
        self.recent.clear()
        if CAPTURES.exists():
            paths=sorted((p for p in CAPTURES.iterdir() if p.is_file() and p.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.mp4','.mp3')),key=lambda p:p.stat().st_mtime,reverse=True)
            for path in paths[:80]:
                self.recent.addItem(path.name)
                self.recent.item(self.recent.count()-1).setData(Qt.ItemDataRole.UserRole,str(path))
        self.recent_count.setText(str(self.recent.count()))
        self.recent_empty.setVisible(self.recent.count()==0)
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


def main():
    if '--native' not in sys.argv and (Path(__file__).parent/'frontend'/'dist'/'index.html').is_file():
        from web_shell import run
        return run()
    app=QApplication(sys.argv);app.setApplicationName('SnagForge');app.setDesktopFileName('snagforge')
    app.setStyle('Fusion');app.setStyleSheet(STYLE)
    window=Window();window.show()
    if len(sys.argv)>1 and Path(sys.argv[1]).is_file():window.load_image(QImage(sys.argv[1]))
    return app.exec()

if __name__=='__main__':sys.exit(main())
