import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication,QMainWindow
from tray import TrayController

app=QApplication.instance() or QApplication([])


class TrayTests(unittest.TestCase):
    def setUp(self):
        self.window=QMainWindow();self.engine=Mock(busy=False,recorder=None)
        self.available=patch('tray.QSystemTrayIcon.isSystemTrayAvailable',return_value=False);self.available.start()
        self.tray=TrayController(self.window,self.engine,app)
        self.engine.region_chooser=None
        self.previous_quit=app.quitOnLastWindowClosed()
    def tearDown(self):
        self.tray.timer.stop();self.tray.icon.hide();self.window.close()
        app.setQuitOnLastWindowClosed(self.previous_quit);self.available.stop()
    def test_quick_actions_start_capture_without_editor_navigation(self):
        self.tray.capture_action.trigger();self.engine.capture.assert_called_once()
        self.tray.area_action.trigger();self.engine.mode.setCurrentText.assert_called_with('MP4 video')
        self.engine.region.setChecked.assert_called_with(True);self.engine.record.assert_called_once()
        self.tray.full_action.trigger();self.engine.region.setChecked.assert_called_with(False)
    def test_busy_state_blocks_new_capture_and_exposes_stop(self):
        self.engine.busy=True;self.engine.recorder=object();self.tray.update_actions()
        self.assertFalse(self.tray.capture_action.isEnabled());self.assertFalse(self.tray.area_action.isEnabled())
        self.assertTrue(self.tray.stop_action.isEnabled());self.tray.stop_action.trigger()
        self.engine.stop.assert_called_once();self.tray.record(True);self.engine.record.assert_not_called()
    def test_close_hides_only_when_tray_is_available(self):
        self.window.show();self.assertFalse(self.tray.hide_on_close());self.assertTrue(self.window.isVisible())
        with patch('tray.QSystemTrayIcon.isSystemTrayAvailable',return_value=True),patch.object(self.tray.icon,'show'):
            self.assertTrue(self.tray.hide_on_close());self.assertFalse(self.window.isVisible())
    def test_quit_during_recording_requires_stop_and_save(self):
        self.engine.busy=True
        with patch.object(app,'quit') as quit:
            self.tray.quit();quit.assert_not_called();self.engine.error.assert_called_once()
