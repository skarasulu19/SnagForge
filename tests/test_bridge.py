"""Native bridge checks use synthetic images; no screen or audio is captured."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from PySide6.QtCore import QUrl
from web_shell import decode_image,encode_image,DesktopBridge,EngineWindow,LocalPage,ROOT

app=QApplication.instance() or QApplication([])

class BridgeTests(unittest.TestCase):
    def test_image_roundtrip_preserves_pixels(self):
        image=QImage(31,17,QImage.Format.Format_ARGB32);image.fill(QColor('#8672ee'))
        result=decode_image(encode_image(image))
        self.assertEqual(result.size(),image.size())
        self.assertEqual(result.pixelColor(10,10).name(),'#8672ee')
    def test_image_rejects_non_image_and_invalid_base64(self):
        for data in ('file:///etc/passwd','data:text/html;base64,SGVsbG8=','data:image/png;base64,not-valid!'):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    decode_image(data)
    def test_frontend_sync_does_not_echo_a_capture(self):
        engine=EngineWindow();bridge=DesktopBridge(engine);events=[]
        bridge.imageReady.connect(events.append)
        image=QImage(16,16,QImage.Format.Format_ARGB32);image.fill(QColor('white'))
        bridge.syncImage(encode_image(image))
        self.assertFalse(engine.canvas.image.isNull())
        self.assertTrue(engine.dirty)
        self.assertEqual(events,[])
        engine.dirty=False;bridge.timer.stop();engine.close()
    def test_navigation_does_not_expose_bridge_to_other_content(self):
        allowed=QUrl.fromLocalFile(str(ROOT/'frontend/dist/index.html'))
        self.assertTrue(LocalPage.acceptNavigationRequest(None,allowed,None,True))
        for url in ('https://example.com','file:///tmp/untrusted.html','data:text/html,hello'):
            self.assertFalse(LocalPage.acceptNavigationRequest(None,QUrl(url),None,True))
    def test_native_recorder_exposes_marquee_action(self):
        engine=EngineWindow()
        self.assertEqual(engine.record_btn.text(),'Select area & record')
        engine.region.setChecked(False)
        self.assertEqual(engine.record_btn.text(),'Record full source')
        engine.mode.setCurrentText('MP3 audio')
        self.assertEqual(engine.record_btn.text(),'Start audio recording')
        self.assertFalse(engine.region.isEnabled())
        engine.timer.stop();engine.close()

if __name__=='__main__':unittest.main()
