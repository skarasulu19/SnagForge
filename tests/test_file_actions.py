import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QMessageBox
from app import Window

app=QApplication.instance() or QApplication([])


class FileActionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.captures=self.root/'captures';self.captures.mkdir()
        self.patch=patch('app.CAPTURES',self.captures);self.patch.start()
        self.engine=Window();self.file=self.captures/'test clip.mp4';self.file.write_bytes(b'test video')
    def tearDown(self):
        self.engine.timer.stop();self.engine.close();self.patch.stop();self.temp.cleanup()
    def test_copy_returns_absolute_path_without_modifying_video(self):
        self.assertTrue(self.engine.copy_capture_path(self.file.name))
        self.assertEqual(app.clipboard().text(),str(self.file.resolve()))
        self.assertEqual(self.file.read_bytes(),b'test video')
    def test_outside_paths_and_symlinks_are_rejected(self):
        outside=self.root/'outside.mp4';outside.write_bytes(b'private')
        (self.captures/'link.mp4').symlink_to(outside)
        for name in ('../outside.mp4',str(outside),'link.mp4','missing.mp4'):
            with self.subTest(name=name),self.assertRaises(ValueError):self.engine.capture_path(name)
    def test_cancel_delete_keeps_file(self):
        with patch('app.QMessageBox.question',return_value=QMessageBox.StandardButton.No),patch('app.QFile.moveToTrash') as trash:
            self.assertFalse(self.engine.delete_capture(self.file.name));trash.assert_not_called()
        self.assertTrue(self.file.exists())
    def test_confirm_delete_moves_to_trash_and_refreshes(self):
        destination=self.root/'trashed.mp4'
        def trash(path):Path(path).rename(destination);return True
        with patch('app.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes),patch('app.QFile.moveToTrash',side_effect=trash):
            self.assertTrue(self.engine.delete_capture(self.file.name))
        self.assertFalse(self.file.exists());self.assertEqual(destination.read_bytes(),b'test video')
        self.assertEqual(self.engine.recent.count(),0)
    def test_trash_failure_preserves_file_and_reports_error(self):
        with patch('app.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes),patch('app.QFile.moveToTrash',return_value=False),patch.object(self.engine,'error') as error:
            self.assertFalse(self.engine.delete_capture(self.file.name));error.assert_called_once()
        self.assertTrue(self.file.exists())
    def test_active_capture_cannot_be_deleted(self):
        self.engine.busy=True
        with patch.object(self.engine,'error') as error,patch('app.QFile.moveToTrash') as trash:
            self.assertFalse(self.engine.delete_capture(self.file.name));error.assert_called_once();trash.assert_not_called()
        self.engine.busy=False;self.assertTrue(self.file.exists())
