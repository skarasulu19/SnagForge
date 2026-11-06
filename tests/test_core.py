import asyncio
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtTest import QTest
from editor import Canvas, RegionDialog, RegionSelector
from media import pipeline, recording_crop, stitch
from portal import Portal, Cancelled
from workers import recording_output_ok
from dbus_next import Message, MessageType, Variant

app=QApplication.instance() or QApplication([])

class EditorTests(unittest.TestCase):
    def setUp(self):
        self.canvas=Canvas();self.canvas.resize(800,600);self.canvas.show()
        im=QImage(400,300,QImage.Format.Format_ARGB32);im.fill(Qt.GlobalColor.white);self.canvas.load(im)
        app.processEvents()
    def test_annotations_crop_and_history(self):
        for tool in ['Arrow','Pen','Rectangle','Ellipse','Highlight','Step','Stamp','Redact','Pixelate','Blur','Spotlight','Magnify','Capture Info']:
            self.canvas.tool=tool
            QTest.mousePress(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center())
            QTest.mouseMove(self.canvas,self.canvas.rect().center()+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(90,70))
            QTest.mouseRelease(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center()+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(90,70))
            self.assertTrue(self.canvas.history,tool)
        self.canvas.tool='Callout'
        with patch('editor.QInputDialog.getMultiLineText',return_value=('Review this',True)):
            QTest.mousePress(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center())
            QTest.mouseRelease(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center()+QPoint(100,65))
        self.assertTrue(self.canvas.history)
        before=self.canvas.image.copy();self.canvas.undo();self.canvas.redo();self.assertEqual(before,self.canvas.image)
        self.canvas.tool='Crop'
        QTest.mousePress(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center())
        QTest.mouseRelease(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center()+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(90,70))
        self.assertLess(self.canvas.image.width(),400)
        self.canvas.undo();self.assertEqual(self.canvas.image.width(),400)
    def test_selection_mapping(self):
        rect=self.canvas.geometry_image();point=self.canvas.image_point(rect.center())
        self.assertAlmostEqual(point.x(),200);self.assertAlmostEqual(point.y(),150)
    def test_redact_is_opaque(self):
        self.canvas.tool='Redact'
        QTest.mousePress(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center())
        QTest.mouseRelease(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center()+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(90,70))
        self.assertEqual(self.canvas.image.pixelColor(210,160).name(),'#000000')

class RegionSelectorTests(unittest.TestCase):
    def setUp(self):
        image=QImage(1600,900,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white)
        self.selector=RegionSelector(image);self.selector.resize(800,600);self.selector.show();app.processEvents()
    def tearDown(self):self.selector.close()
    def test_marquee_maps_overlay_to_source_pixels(self):
        regions=[];self.selector.selected.connect(regions.append)
        QTest.mousePress(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(100,100))
        QTest.mouseMove(self.selector,QPoint(500,400))
        QTest.mouseRelease(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(500,400))
        QTest.mousePress(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(500,400))
        QTest.mouseMove(self.selector,QPoint(100,100))
        QTest.mouseRelease(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(100,100))
        self.assertEqual(regions,[QRect(200,50,800,600),QRect(200,50,800,600)])
    def test_enter_chooses_full_source_and_escape_cancels(self):
        events=[];self.selector.full_source.connect(lambda:events.append('full'))
        self.selector.cancelled.connect(lambda:events.append('cancel'))
        QTest.keyClick(self.selector,Qt.Key.Key_Return);QTest.keyClick(self.selector,Qt.Key.Key_Escape)
        QTest.mouseClick(self.selector,Qt.MouseButton.RightButton,pos=QPoint(300,300))
        self.assertEqual(events,['full','cancel','cancel'])
    def test_release_locks_marquee_while_pointer_moves_to_confirm(self):
        regions=[];self.selector.selected.connect(regions.append)
        QTest.mousePress(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(100,100))
        QTest.mouseMove(self.selector,QPoint(500,400))
        QTest.mouseRelease(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(500,400))
        locked=self.selector.selection()
        QTest.mouseMove(self.selector,QPoint(750,550))
        QTest.mouseMove(self.selector,QPoint(30,80))
        self.assertEqual(self.selector.selection(),locked)
        self.assertEqual(regions,[locked])
        confirmed=[];self.selector.confirmed.connect(confirmed.append)
        QTest.keyClick(self.selector,Qt.Key.Key_Return)
        self.assertEqual(confirmed,[locked])
    def test_redraw_requires_another_press_and_release(self):
        QTest.mousePress(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(100,100))
        QTest.mouseRelease(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(500,400))
        QTest.mousePress(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(200,200))
        QTest.mouseMove(self.selector,QPoint(400,350))
        confirmed=[];self.selector.confirmed.connect(confirmed.append)
        QTest.keyClick(self.selector,Qt.Key.Key_Return)
        self.assertEqual(confirmed,[])
        QTest.mouseRelease(self.selector,Qt.MouseButton.LeftButton,pos=QPoint(400,350))
        self.assertEqual(self.selector.selection(),QRect(400,250,400,300))
    def test_confirm_button_uses_locked_box_and_disables_during_redraw(self):
        image=QImage(800,600,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white)
        dialog=RegionDialog(image,confirm_text='Record selected area');dialog.show();app.processEvents()
        try:
            selector=dialog.selector
            QTest.mousePress(selector,Qt.MouseButton.LeftButton,pos=QPoint(100,100))
            QTest.mouseRelease(selector,Qt.MouseButton.LeftButton,pos=QPoint(400,300))
            self.assertTrue(dialog.confirm_button.isEnabled())
            QTest.mousePress(selector,Qt.MouseButton.LeftButton,pos=QPoint(150,150))
            self.assertFalse(dialog.confirm_button.isEnabled());self.assertIsNone(dialog.region)
            QTest.mouseRelease(selector,Qt.MouseButton.LeftButton,pos=QPoint(350,300))
            locked=selector.selection()
            QTest.mouseMove(selector,QPoint(500,350))
            QTest.mouseClick(dialog.confirm_button,Qt.MouseButton.LeftButton)
            self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
            self.assertEqual(dialog.region,locked)
        finally:dialog.close()
    def test_region_dialog_waits_for_explicit_confirmation(self):
        image=QImage(800,600,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white)
        dialog=RegionDialog(image,confirm_text='Record selected area')
        dialog.preview_selection(QRect(50,60,320,240))
        self.assertEqual(dialog.result(),0);self.assertTrue(dialog.confirm_button.isEnabled())
        dialog.confirm_selection();self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)

class MediaTests(unittest.TestCase):
    def test_stitch_continuity(self):
        source=Image.new('RGB',(20,180))
        for y in range(180):
            for x in range(20):source.putpixel((x,y),(y,x,0))
        out=stitch([source.crop((0,0,20,100)),source.crop((0,80,20,180))],20)
        self.assertEqual(out.tobytes(),source.tobytes())
    def test_invalid_stitch(self):
        with self.assertRaises(ValueError):stitch([Image.new('RGB',(4,4)),Image.new('RGB',(5,4))],1)
        with self.assertRaises(ValueError):stitch([Image.new('RGB',(4,4))]*2,4)
    def test_pipeline_crop_audio_and_safe_path(self):
        args=pipeline('/tmp/space name;$(bad).mp4','MP4 video',9,42,(10,20,30,40),'Microphone')
        self.assertIn('left=10',args);self.assertIn('bottom=40',args)
        self.assertIn('avenc_aac',args);self.assertIn('mp4mux',args)
        self.assertIn('location="/tmp/space name;$(bad).mp4"',args)
        with self.assertRaises(ValueError):pipeline('/tmp/x.mp3','MP3 audio')
        self.assertIn('lamemp3enc',pipeline('/tmp/x.mp3','MP3 audio',audio='Microphone'))
    def test_recording_marquee_maps_to_even_crop_margins(self):
        self.assertEqual(recording_crop(1920,1080,(101,53,801,601)),(101,53,1019,427))
        with self.assertRaises(ValueError):recording_crop(1920,1080,(10,10,1,1))
    def test_user_stopped_finalized_recording_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'capture.mp4';path.write_bytes(b'x'*256)
            self.assertTrue(recording_output_ok(path,-2,'',True))
            self.assertFalse(recording_output_ok(path,-2,'ERROR encoder failed',True))

class FakeBus:
    unique_name=':1.23'
    def add_message_handler(self,fn):self.handler=fn
    def remove_message_handler(self,fn):self.handler=None
    async def call(self,msg):
        if msg.member in ('AddMatch','RemoveMatch'):
            return Message(message_type=MessageType.METHOD_RETURN,reply_serial=1)
        token=msg.body[-1]['handle_token'].value
        self.handler(Message(message_type=MessageType.SIGNAL,
            path='/org/freedesktop/portal/desktop/request/1_23/'+token,
            interface='org.freedesktop.portal.Request',member='Response',signature='ua{sv}',
            body=[self.code,{'uri':Variant('s','file:///tmp/test.png')}]))
        return Message(message_type=MessageType.METHOD_RETURN,reply_serial=1)

class MissingSessionBus:
    """A portal bus whose compositor already removed the session object."""
    def __init__(self):self.disconnected=False
    async def call(self,msg):
        return Message(message_type=MessageType.ERROR,reply_serial=1,
            error_name='org.freedesktop.DBus.Error.UnknownMethod',signature='s',
            body=['Object does not exist at the session path'])
    def disconnect(self):self.disconnected=True

class PortalTests(unittest.TestCase):
    def test_response_before_method_reply_is_not_lost(self):
        async def run():
            p=Portal();p.bus=FakeBus();p.bus.code=0
            self.assertEqual(await p.screenshot(),'file:///tmp/test.png')
            self.assertIsNone(p.bus.handler)
        asyncio.run(run())
    def test_cancellation(self):
        async def run():
            p=Portal();p.bus=FakeBus();p.bus.code=1
            with self.assertRaises(Cancelled):await p.screenshot()
        asyncio.run(run())
    def test_close_is_safe_when_compositor_already_removed_session(self):
        async def run():
            p=Portal();p.bus=MissingSessionBus();p.session='/missing/session'
            await p.close()
            self.assertIsNone(p.session)
            self.assertIsNone(p.bus)
        asyncio.run(run())
    def test_close_is_idempotent(self):
        async def run():
            p=Portal();bus=MissingSessionBus();p.bus=bus;p.session='/missing/session'
            await p.close();await p.close()
            self.assertTrue(bus.disconnected)
        asyncio.run(run())

if __name__=='__main__':unittest.main()


