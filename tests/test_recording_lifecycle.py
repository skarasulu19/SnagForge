"""Exercise real Qt worker signals; no desktop or encoder is opened."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import asyncio
import signal
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock
from PySide6.QtWidgets import QApplication
from app import Window,RecordingController
from PySide6.QtGui import QImage
from PySide6.QtCore import Qt
from workers import Recorder
from workers import until_stopped
from portal import Cancelled
import threading

app=QApplication.instance() or QApplication([])


class RecordingLifecycleTests(unittest.TestCase):
    def test_cancel_before_capture_delay_does_not_start_worker(self):
        window=Window();scheduled=[]
        try:
            with patch('app.QTimer.singleShot',side_effect=lambda delay,callback:scheduled.append(callback)),patch('app.CaptureWorker') as worker:
                window.capture();window.stop();scheduled[0]()
                worker.assert_not_called();self.assertFalse(window.busy)
        finally:window.timer.stop();window.close()

    def test_screenshot_stays_busy_until_selection_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            window=Window();window.busy=True;window.capture_in_progress=True
            window.capture_worker=SimpleNamespace(stop_event=threading.Event(),isRunning=lambda:False)
            image=QImage(100,100,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white)
            path=str(Path(directory)/'screen.png');image.save(path)
            def selection():
                window.end_capture();self.assertTrue(window.busy)
                return 0
            try:
                with patch('app.RegionDialog') as dialog:
                    dialog.return_value.exec.side_effect=selection
                    window.received_capture(path)
                self.assertFalse(window.busy);self.assertIsNone(window.screenshot_chooser)
            finally:window.timer.stop();window.close()

    def test_late_screenshot_completion_cannot_unlock_a_new_operation(self):
        window=Window()
        try:
            window.capture_in_progress=True;window.busy=True;window.end_capture()
            self.assertFalse(window.busy)
            window.busy=True
            window.end_capture()
            self.assertTrue(window.busy)
        finally:window.busy=False;window.timer.stop();window.close()

    def test_stop_cancels_an_unanswered_portal_wait(self):
        async def run():
            stop=threading.Event();cancelled=[]
            async def pending():
                try:await asyncio.Future()
                finally:cancelled.append(True)
            task=asyncio.create_task(until_stopped(pending(),stop))
            await asyncio.sleep(.01);stop.set()
            with self.assertRaises(Cancelled):await asyncio.wait_for(task,1)
            self.assertEqual(cancelled,[True])
        asyncio.run(run())

    def test_stopping_at_permission_never_launches_an_encoder(self):
        async def run():
            entered=asyncio.Event();closed=[]
            class PendingPortal:
                async def connect(self):return self
                async def screencast(self):entered.set();await asyncio.Future()
                async def close(self):closed.append(True)
            recorder=Recorder('/tmp/unused.mp4','MP4 video','None',True);active=[]
            recorder.recording_active.connect(lambda:active.append(True))
            with patch('workers.Portal',return_value=PendingPortal()),patch('workers.subprocess.Popen') as launch:
                task=asyncio.create_task(recorder.record());await entered.wait();recorder.stop_event.set()
                await asyncio.wait_for(task,1);launch.assert_not_called()
            self.assertEqual(active,[]);self.assertEqual(closed,[True])
        asyncio.run(run())
    def test_rapid_record_and_capture_actions_schedule_only_one_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            window=Window();scheduled=[];created=[]
            def make_recorder(*args):
                recorder=Recorder(*args)
                async def no_encoder():return
                recorder.record=no_encoder;created.append(recorder);return recorder
            try:
                with patch('app.CAPTURES',Path(directory)),patch('app.shutil.which',return_value='/fake/gst-launch-1.0'),patch('app.Recorder',side_effect=make_recorder),patch('app.QTimer.singleShot',side_effect=lambda delay,callback:scheduled.append(callback)),patch('app.RecordingController') as controller:
                    for _ in range(10):window.record();window.capture()
                    self.assertEqual(len(created),1);self.assertEqual(len(scheduled),1)
                    self.assertTrue(window.busy)
                    scheduled[0]();self.assertTrue(created[0].wait(2000));app.processEvents()
                    controller.assert_not_called()
                    self.assertFalse(window.busy);self.assertIsNone(window.record_controller)
            finally:window.timer.stop();window.close()

    def run_worker(self,recording=False):
        recorder=Recorder('/tmp/unused.mp4','MP4 video','None',True)
        events=[]
        recorder.started.connect(lambda:events.append('thread'))
        recorder.recording_active.connect(lambda:events.append('recording'))
        async def fake_capture():
            if recording:recorder.recording_active.emit()
        recorder.record=fake_capture
        recorder.start()
        self.assertTrue(recorder.wait(2000),'Test worker did not finish')
        app.processEvents()
        return events

    def test_thread_start_does_not_mean_recording_started(self):
        self.assertEqual(self.run_worker(False),['thread'])

    def test_encoder_notification_is_delivered_exactly_once(self):
        self.assertEqual(self.run_worker(True),['thread','recording'])

    def test_duplicate_active_notification_cannot_orphan_a_timer(self):
        window=Window()
        try:
            window.recording_started();first=window.record_controller
            window.recording_started()
            self.assertIs(window.record_controller,first)
            window.recording_finished();app.processEvents()
            self.assertIsNone(window.record_controller)
            self.assertFalse(first.isVisible())
            self.assertIsNone(window.recording_since)
            self.assertFalse(window.busy);self.assertFalse(window.stop_btn.isEnabled())
        finally:window.timer.stop();window.close()

    def test_stop_during_encoder_warmup_never_shows_recording_timer(self):
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/'warmup.mp3')
            recorder=Recorder(path,'MP3 audio','Microphone',False)
            active=[];saved=[];signals=[]
            recorder.recording_active.connect(lambda:active.append(True))
            recorder.saved.connect(saved.append)
            class Encoder:
                returncode=None
                def poll(self):return self.returncode
                def send_signal(self,sig):
                    signals.append(sig);Path(path).write_bytes(b'x'*256);self.returncode=0
                def wait(self,timeout=None):return self.returncode
            def launch(*args,**kwargs):
                recorder.stop_event.set();return Encoder()
            with patch('workers.pipeline',return_value=['fake-encoder']),patch('workers.subprocess.Popen',side_effect=launch),patch('workers.asyncio.sleep',new=AsyncMock()):
                asyncio.run(recorder.record())
            self.assertEqual(active,[])
            self.assertEqual(signals,[signal.SIGINT]);self.assertEqual(saved,[path])
