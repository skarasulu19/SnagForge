import asyncio
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from editor import Canvas, RegionDialog, RegionSelector
from media import pipeline, recording_crop, stitch
from portal import Portal, Cancelled
from dbus_next import Message, MessageType, Variant

app=QApplication.instance() or QApplication([])

class EditorTests(unittest.TestCase):
    def setUp(self):
        self.canvas=Canvas();self.canvas.resize(800,600);self.canvas.show()
        im=QImage(400,300,QImage.Format.Format_ARGB32);im.fill(Qt.GlobalColor.white);self.canvas.load(im)
        app.processEvents()
    def test_annotations_crop_and_history(self):
        for tool in ['Arrow','Pen','Rectangle','Ellipse','Highlight','Step','Redact','Pixelate','Blur','Spotlight']:
            self.canvas.tool=tool
            QTest.mousePress(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center())
            QTest.mouseMove(self.canvas,self.canvas.rect().center()+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(90,70))
            QTest.mouseRelease(self.canvas,Qt.MouseButton.LeftButton,pos=self.canvas.rect().center()+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(90,70))
            self.assertTrue(self.canvas.history,tool)
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

