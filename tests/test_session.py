"""Selection stays in the existing window; duplicate launches reuse it."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import socket
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from PySide6.QtTest import QTest
from app import Window
from instance import InstanceGuard
from web_shell import EngineWindow

app=QApplication.instance() or QApplication([])


class SessionTests(unittest.TestCase):
    def test_process_lock_excludes_a_second_python_process(self):
        code="""import sys
from PySide6.QtCore import QCoreApplication, QLockFile
app=QCoreApplication([]);app.setApplicationName('SnagForge')
lock=QLockFile(sys.argv[1]);lock.setStaleLockTime(0)
print(lock.tryLock(0),flush=True)
sys.stdin.read()
"""
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/'snagforge-session.lock')
            first=subprocess.Popen([sys.executable,'-c',code,path],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(first.stdout.readline().strip(),'True')
                second=subprocess.run([sys.executable,'-c',code,path],input='',capture_output=True,text=True,timeout=5,check=True)
                self.assertEqual(second.stdout.strip(),'False')
            finally:first.communicate(input='',timeout=5)

    def test_second_launch_activates_existing_window(self):
        try:
            probe=socket.socket(socket.AF_UNIX);probe.close()
        except PermissionError:
            self.skipTest('Runtime forbids local sockets; run this integration check on the desktop.')
        with tempfile.TemporaryDirectory() as directory:
            first=InstanceGuard(directory=directory)
            window=QMainWindow();first.set_window(window)
            self.assertTrue(first.primary)
            try:
                second=InstanceGuard(directory=directory)
                self.assertFalse(second.primary)
                app.processEvents()
                self.assertTrue(window.isVisible())
            finally:window.close();first.close()
            replacement=InstanceGuard(directory=directory)
            self.assertTrue(replacement.primary);replacement.close()

    def test_process_lock_blocks_a_duplicate_when_activation_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory, patch('instance.QLocalServer.listen',return_value=True):
            first=InstanceGuard(directory=directory)
            try:
                with patch('instance.QLocalSocket.connectToServer'), patch('instance.QLocalSocket.waitForConnected',return_value=False):
                    with self.assertRaisesRegex(RuntimeError,'already running'):
                        InstanceGuard(directory=directory)
            finally:first.close()

    def test_region_uses_same_native_and_angular_window(self):
        for angular in (False,True):
            with self.subTest(angular=angular), tempfile.TemporaryDirectory() as directory:
                engine=EngineWindow() if angular else Window()
                host=QMainWindow() if angular else engine
                if angular:
                    host.setCentralWidget(QWidget());engine.shell=host
                original=host.centralWidget();host.show();app.processEvents()
                engine.recorder=SimpleNamespace(cancelled=False,crop=None,selection_ready=threading.Event())
                image=QImage(800,600,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white)
                path=str(Path(directory)/'preview.png');image.save(path)
                try:
                    with patch.object(engine,'showMinimized') as minimize:
                        engine.video_region(path);app.processEvents()
                        chooser=engine.region_chooser
                        self.assertFalse(chooser.isWindow())
                        self.assertIs(chooser.window(),host)
                        self.assertIs(host.centralWidget(),chooser)
                        self.assertFalse(original.isVisible())
                        self.assertFalse(engine.recorder.selection_ready.is_set())
                        QTest.mousePress(chooser.selector,Qt.MouseButton.LeftButton,pos=QPoint(120,120))
                        QTest.mouseRelease(chooser.selector,Qt.MouseButton.LeftButton,pos=QPoint(350,300))
                        locked=chooser.region
                        QTest.mouseMove(chooser.selector,QPoint(500,350))
                        QTest.mouseClick(chooser.confirm_button,Qt.MouseButton.LeftButton)
                        self.assertIs(host.centralWidget(),original)
                        self.assertTrue(original.isVisible())
                        self.assertTrue(engine.recorder.selection_ready.is_set())
                        left,top,right,bottom=engine.recorder.crop
                        self.assertEqual((left,top),(locked.x(),locked.y()))
                        self.assertLessEqual(abs(800-left-right-locked.width()),1)
                        minimize.assert_called_once()
                finally:
                    engine.timer.stop();engine.busy=False;host.close()
                    if angular:engine.shell=None;engine.close()

    def test_cancel_restores_workspace_without_starting_encoder(self):
        with tempfile.TemporaryDirectory() as directory:
            engine=Window();engine.show();original=engine.centralWidget()
            engine.recorder=SimpleNamespace(cancelled=False,crop=None,selection_ready=threading.Event())
            image=QImage(800,600,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white)
            path=str(Path(directory)/'preview.png');image.save(path)
            try:
                engine.video_region(path)
                engine.region_chooser.reject()
                self.assertIs(engine.centralWidget(),original)
                self.assertTrue(engine.recorder.cancelled)
                self.assertTrue(engine.recorder.selection_ready.is_set())
                self.assertIsNone(engine.recorder.crop)
            finally:engine.timer.stop();engine.close()


if __name__=='__main__':unittest.main()
