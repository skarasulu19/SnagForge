"""Keep native and web launchers in one desktop session per user."""
from pathlib import Path
from PySide6.QtCore import QObject, QLockFile, QStandardPaths
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class InstanceGuard(QObject):
    def __init__(self,parent=None,directory=None):
        super().__init__(parent)
        root=Path(directory or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation))
        root.mkdir(parents=True,exist_ok=True)
        self.address=str(root/'snagforge-session')
        self.lock=QLockFile(self.address+'.lock');self.lock.setStaleLockTime(0)
        self.server=None;self.window=None
        self.primary=self.lock.tryLock(0)
        if not self.primary:
            socket=QLocalSocket();socket.connectToServer(self.address)
            if not socket.waitForConnected(1500):
                raise RuntimeError('SnagForge is already running but cannot be reached. Close its existing session and try again.')
            socket.disconnectFromServer()
            return
        # Only the holder of the process lock may remove a stale socket.
        QLocalServer.removeServer(self.address)
        self.server=QLocalServer(self)
        self.server.newConnection.connect(self.activate)
        if not self.server.listen(self.address):
            self.lock.unlock();raise RuntimeError(self.server.errorString())

    def set_window(self,window):
        self.window=window

    def activate(self):
        while self.server.hasPendingConnections():
            connection=self.server.nextPendingConnection()
            connection.disconnectFromServer();connection.deleteLater()
        if self.window:
            if self.window.isMinimized():self.window.showNormal()
            else:self.window.show()
            self.window.raise_();self.window.activateWindow()
            if self.window.windowHandle():self.window.windowHandle().requestActivate()

    def close(self):
        if self.primary:
            self.server.close();self.lock.unlock();self.primary=False
