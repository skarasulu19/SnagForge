"""Error dialogs restore the owning UI and expose an immediately usable OK."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from app import Window
from web_shell import EngineWindow

app=QApplication.instance() or QApplication([])


class ErrorDialogTests(unittest.TestCase):
    def test_error_restores_minimized_host_and_shows_modal_ok(self):
        for angular in (False,True):
            with self.subTest(angular=angular):
                engine=EngineWindow() if angular else Window()
                host=QMainWindow() if angular else engine
                if angular:engine.shell=host
                host.showMinimized();app.processEvents()
                observed={}
                def inspect_and_dismiss():
                    box=app.activeModalWidget()
                    observed.update(visible=host.isVisible(),minimized=host.isMinimized(),box=box is not None)
                    if isinstance(box,QMessageBox):
                        observed.update(parent=box.parentWidget() is host,message=box.text(),
                                        top=bool(box.windowFlags() & Qt.WindowType.WindowStaysOnTopHint),
                                        modality=box.windowModality(),
                                        default=box.defaultButton() is box.button(QMessageBox.StandardButton.Ok))
                        box.button(QMessageBox.StandardButton.Ok).click()
                QTimer.singleShot(20,inspect_and_dismiss)
                try:
                    engine.error('The selected source produced no preview.')
                    self.assertTrue(observed['visible']);self.assertFalse(observed['minimized'])
                    self.assertTrue(observed['box']);self.assertTrue(observed['parent'])
                    self.assertTrue(observed['top']);self.assertTrue(observed['default'])
                    self.assertEqual(observed['modality'],Qt.WindowModality.ApplicationModal)
                    self.assertEqual(observed['message'],'The selected source produced no preview.')
                finally:
                    engine.timer.stop();host.close()
                    if angular:engine.shell=None;engine.close()


if __name__=='__main__':unittest.main()
