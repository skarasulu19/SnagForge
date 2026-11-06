"""Desktop tray quick actions shared by the Angular and native interfaces."""
from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from ui import application_icon


class TrayController(QObject):
    def __init__(self,window,engine,app):
        super().__init__(window)
        self.window=window;self.engine=engine;self.app=app;self.quitting=False
        self.exit_requested=False
        self.icon=QSystemTrayIcon(application_icon(),self)
        window.setWindowIcon(self.icon.icon())
        self.icon.setToolTip('SnagForge — Capture. Annotate. Explain.')
        self.menu=QMenu(window)
        self.open_action=self.menu.addAction('Open SnagForge',self.open)
        self.menu.addSeparator()
        self.capture_action=self.menu.addAction('Take screenshot',self.screenshot)
        self.area_action=self.menu.addAction('Record selected area',lambda:self.record(True))
        self.full_action=self.menu.addAction('Record full screen / window',lambda:self.record(False))
        self.stop_action=self.menu.addAction('Stop & save',self.stop)
        self.menu.addSeparator()
        self.menu.addAction('Quit SnagForge',self.quit)
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self.activated)
        self.timer=QTimer(self);self.timer.timeout.connect(self.update_actions);self.timer.start(500)
        self.update_actions()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.app.setQuitOnLastWindowClosed(False);self.icon.show()

    def update_actions(self):
        busy=self.engine.busy or self.quitting
        for action in (self.capture_action,self.area_action,self.full_action):action.setEnabled(not busy)
        self.stop_action.setEnabled(not self.quitting and self.engine.busy and not self.engine.stopping)
        self.stop_action.setText('Stop & save' if self.engine.recording_since is not None else 'Cancel capture')

    def open(self):
        if self.window.isMinimized():self.window.showNormal()
        else:self.window.show()
        self.window.raise_();self.window.activateWindow()
        if self.window.windowHandle():self.window.windowHandle().requestActivate()

    def activated(self,reason):
        if reason==QSystemTrayIcon.ActivationReason.Trigger:self.menu.popup(QCursor.pos())
        elif reason==QSystemTrayIcon.ActivationReason.DoubleClick:self.open()

    def screenshot(self):
        if not self.quitting and not self.engine.busy:self.engine.capture()

    def record(self,region):
        if self.engine.busy or self.quitting:return
        self.engine.mode.setCurrentText('MP4 video');self.engine.region.setChecked(region)
        # Area selection is embedded in the existing host; keep it available.
        if region:self.open()
        self.engine.record()

    def stop(self):
        self.engine.stop()

    def hide_on_close(self):
        if self.quitting or not QSystemTrayIcon.isSystemTrayAvailable():return False
        self.app.setQuitOnLastWindowClosed(False)
        self.icon.show();self.window.hide();return True

    def quit(self):
        if self.quitting:return
        if not self.engine.can_replace():return
        self.quitting=True;self.update_actions()
        # Connect before Stop to avoid losing a fast completion signal.
        for worker in (self.engine.recorder,self.engine.capture_worker):
            if worker and worker.isRunning():worker.finished.connect(self.finish_quit)
        if self.engine.busy:self.engine.stop()
        self.finish_quit()

    def finish_quit(self):
        if self.exit_requested:return
        if any(worker and worker.isRunning() for worker in (self.engine.recorder,self.engine.capture_worker)):return
        self.exit_requested=True
        self.icon.hide();self.app.quit()
