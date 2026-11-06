"""Offline Angular desktop shell with a narrowly scoped native capture bridge."""
import base64
import json
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QImage
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from app import Window, CAPTURES, configure_application_identity

ROOT=Path(__file__).resolve().parent

def decode_image(data):
    if not isinstance(data,str) or len(data)>140_000_000:
        raise ValueError('Image payload is too large.')
    header,encoded=data.split(',',1)
    if header not in ('data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'):
        raise ValueError('Unsupported image format.')
    image=QImage.fromData(base64.b64decode(encoded,validate=True))
    if image.isNull() or image.width()*image.height()>100_000_000:
        raise ValueError('Invalid image or image exceeds 100 megapixels.')
    return image

def encode_image(image):
    from PySide6.QtCore import QBuffer,QIODevice
    buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG')
    return 'data:image/png;base64,'+base64.b64encode(bytes(buffer.data())).decode('ascii')

class EngineWindow(Window):
    """Reuse tested capture workers and dialogs behind the Angular window."""
    shell=None
    def show(self):
        if self.shell:self.shell.show()
    def showNormal(self):
        if self.shell:self.shell.showNormal()
    def showMinimized(self):
        if self.shell:self.shell.showMinimized()
    def hide(self):
        if self.shell:self.shell.hide()
    def raise_(self):
        if self.shell:self.shell.raise_()

class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self,url,navigation_type,is_main_frame):
        # Never expose the native bridge to remote pages or arbitrary local files.
        if url.scheme()=='file':
            return Path(url.toLocalFile()).resolve()==ROOT/'frontend/dist/index.html'
        return url.scheme() in ('qrc','about')

class DesktopBridge(QObject):
    imageReady=Signal(str)
    stateChanged=Signal(str)
    def __init__(self,engine,parent=None):
        super().__init__(parent);self.engine=engine;self.syncing=False;self.workflow='editor'
        engine.canvas.changed.connect(self.image_changed)
        self.timer=QTimer(self);self.timer.timeout.connect(self.notify);self.timer.start(700)

    def notify(self,message=''):
        elapsed=0 if self.engine.recording_since is None else int(time.monotonic()-self.engine.recording_since)
        self.stateChanged.emit(json.dumps({'busy':self.engine.busy,'recording':self.engine.recording_since is not None,
            'elapsed':f'{elapsed//60:02}:{elapsed%60:02}','message':message}))

    def image_changed(self):
        if self.syncing or self.engine.canvas.image.isNull():return
        self.imageReady.emit(encode_image(self.engine.canvas.image))
        workflow=self.workflow;self.workflow='editor'
        if workflow in ('copy','save-copy'):
            self.engine.copy()
            if workflow=='save-copy':self.engine.save()
            self.notify('Screenshot copied to clipboard.')

    def set_image(self,data):
        image=decode_image(data);self.syncing=True
        try:self.engine.load_image(image)
        finally:self.syncing=False

    @Slot(str)
    def syncImage(self,data):
        try:self.set_image(data)
        except Exception as error:self.notify(str(error))

    @Slot(str,int)
    def capture(self,workflow,delay=0):
        self.workflow=workflow if workflow in ('editor','copy','save-copy') else 'editor'
        self.engine.delay.setValue(max(0,min(30,delay)))
        self.engine.capture();self.notify()

    @Slot()
    def scrolling(self):
        self.workflow='editor';self.engine.scrolling();self.notify()

    @Slot()
    def paste(self):self.engine.paste()

    @Slot(str,str,result=bool)
    def saveImage(self,data,format):
        try:
            self.set_image(data)
            formats={'png':('PNG','png'),'jpg':('JPEG','jpg'),'webp':('WebP','webp')}
            label,suffix=formats.get(format,formats['png']);CAPTURES.mkdir(parents=True,exist_ok=True)
            destination=CAPTURES/f'capture-{datetime.now():%Y%m%d-%H%M%S}.{suffix}'
            path,_=QFileDialog.getSaveFileName(self.engine.shell,'Export image',str(destination),f'{label} (*.{suffix})')
            if not path:return False
            if not Path(path).suffix:path+='.'+suffix
            if not self.engine.canvas.image.save(path,label):raise ValueError('Could not save the image.')
            self.engine.dirty=False;self.engine.refresh_recent();self.notify('Image exported.');return True
        except Exception as error:self.notify(str(error));return False

    @Slot(str)
    def copyImage(self,data):
        try:self.set_image(data);self.engine.copy()
        except Exception as error:self.notify(str(error))

    @Slot(str)
    def pinImage(self,data):
        try:self.set_image(data);self.engine.pin_image()
        except Exception as error:self.notify(str(error))

    @Slot(str)
    def recognizeText(self,data):
        try:self.set_image(data);self.engine.ocr()
        except Exception as error:self.notify(str(error))

    @Slot(str)
    def record(self,config):
        try:
            config=json.loads(config)
            if config.get('mode') not in ('MP4 video','MP3 audio'):raise ValueError('Invalid recording format.')
            if config.get('audio') not in ('None','Microphone','System audio'):raise ValueError('Invalid audio source.')
            self.engine.mode.setCurrentText(config['mode']);self.engine.audio.setCurrentText(config['audio'])
            self.engine.region.setChecked(bool(config.get('region',True)))
            self.engine.delay.setValue(max(0,min(30,int(config.get('delay',0)))))
            self.engine.record();self.notify()
        except Exception as error:self.notify(str(error))

    @Slot()
    def stop(self):self.engine.stop();self.notify()

    @Slot(result=str)
    def listRecent(self):
        items=[]
        if CAPTURES.is_dir():
            try:
                files=sorted((p for p in CAPTURES.iterdir() if p.is_file() and p.suffix.lower() in
                    ('.png','.jpg','.jpeg','.webp','.mp4','.mp3')),key=lambda p:p.stat().st_mtime,reverse=True)
                for p in files[:80]:
                    items.append({'name':p.name,'kind':'recording' if p.suffix.lower() in ('.mp4','.mp3') else 'image',
                        'modified':datetime.fromtimestamp(p.stat().st_mtime).strftime('%d %b · %H:%M')})
            except OSError:pass
        return json.dumps(items)

    @Slot(str)
    def openRecent(self,name):
        path=(CAPTURES/name).resolve()
        if path.parent!=CAPTURES.resolve() or not path.is_file():return
        if path.suffix.lower() in ('.mp4','.mp3'):QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        elif path.suffix.lower() in ('.png','.jpg','.jpeg','.webp') and self.engine.can_replace():self.engine.load_image(QImage(str(path)))

    @Slot()
    def openFolder(self):self.engine.open_folder()

    @Slot(str)
    def copyPath(self,name):
        if self.engine.copy_capture_path(name):self.notify('File path copied to clipboard.')

    @Slot(str)
    def deleteRecent(self,name):
        if self.engine.delete_capture(name):self.notify('Capture moved to Trash.')

    @Slot()
    def manual(self):self.engine.manual()

class DesktopWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('SnagForge · Capture studio');self.resize(1520,960)
        self.setMinimumSize(1000,760)
        self.engine=EngineWindow();self.engine.shell=self
        self.view=QWebEngineView(self);self.setCentralWidget(self.view)
        self.page=LocalPage(self.view);self.view.setPage(self.page)
        settings=self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,False)
        self.channel=QWebChannel(self.page);self.bridge=DesktopBridge(self.engine,self)
        self.channel.registerObject('bridge',self.bridge);self.page.setWebChannel(self.channel)
        self.view.load(QUrl.fromLocalFile(str(ROOT/'frontend/dist/index.html')))
    def closeEvent(self,event):
        if getattr(self,'tray_controller',None) and self.tray_controller.hide_on_close():
            event.ignore();return
        if self.engine.busy:
            self.engine.error('Stop the active recording and wait for it to finish before closing.');event.ignore();return
        if not self.engine.can_replace():event.ignore();return
        for pin in list(self.engine.pins):pin.close()
        event.accept()

def run(guard=None):
    configure_application_identity()
    app=QApplication.instance() or QApplication([])
    window=DesktopWindow();window.show()
    if guard:guard.set_window(window)
    from tray import TrayController
    window.tray_controller=TrayController(window,window.engine,app)
    return app.exec()

