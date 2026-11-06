import asyncio
import os
import signal
import subprocess
import tempfile
import threading
import logging
from pathlib import Path
from urllib.parse import urlparse, unquote
from PySide6.QtCore import QThread, Signal
from portal import Portal, Cancelled
from media import pipeline, gst_string

async def until_stopped(awaitable,stop_event):
    """Let Stop cancel a portal wait instead of waiting for its 180s timeout."""
    task=asyncio.create_task(awaitable)
    try:
        while not task.done():
            if stop_event.is_set():raise Cancelled('Capture stopped')
            await asyncio.wait((task,),timeout=.05)
        result=await task
        if stop_event.is_set():raise Cancelled('Capture stopped')
        return result
    finally:
        if not task.done():
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass

def recording_output_ok(path,returncode,details,stopped):
    """A user-stopped gst-launch may report SIGINT despite a valid finalized file."""
    valid_file=Path(path).is_file() and Path(path).stat().st_size>=128
    return valid_file and 'ERROR' not in details and (not returncode or stopped)

class CaptureWorker(QThread):
    image = Signal(str)
    error = Signal(str)
    def __init__(self):
        super().__init__();self.stop_event=threading.Event()
    def run(self):
        try:
            asyncio.run(self.capture())
        except Exception as e:
            # Exceptions must never cross QThread.run(), where PySide reports
            # them as a Python override failure and may terminate the process.
            self.error.emit(str(e))
    async def capture(self):
        portal=None
        try:
            portal=Portal();await until_stopped(portal.connect(),self.stop_event)
            uri=await until_stopped(portal.screenshot(),self.stop_event)
            parsed=urlparse(uri)
            if parsed.scheme!='file' or parsed.netloc not in ('','localhost'):
                raise RuntimeError('The screenshot portal returned an unsupported URI.')
            self.image.emit(unquote(parsed.path))
        except Cancelled:
            pass
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if portal:
                await portal.close()

class Recorder(QThread):
    preview = Signal(str)
    # QThread.started is emitted when the worker thread starts, before portal
    # permission or encoding. Never reuse it to mean recording is active.
    recording_active = Signal()
    saved = Signal(str)
    error = Signal(str)
    def __init__(self,path,mode,audio,region):
        super().__init__()
        self.path,self.mode,self.audio,self.region=path,mode,audio,region
        self.stop_event=threading.Event()
        self.selection_ready=threading.Event()
        self.crop=None
        self.cancelled=False

    def run(self):
        try:
            asyncio.run(self.record())
        except Exception as e:
            # record() handles operational failures itself; this is the final
            # guard for shutdown/cleanup errors at the Qt thread boundary.
            self.error.emit(str(e))

    async def record(self):
        portal=None
        fd=None
        process=None
        try:
            node=None
            if self.mode!='MP3 audio':
                portal=Portal();await until_stopped(portal.connect(),self.stop_event)
                logging.info('Recorder: waiting for desktop permission')
                node=await until_stopped(portal.screencast(),self.stop_event)
                if self.region:
                    with tempfile.TemporaryDirectory(prefix='snagforge-preview-') as tmp:
                        fd=await portal.remote()
                        path=str(Path(tmp)/'preview.png')
                        cmd=['gst-launch-1.0','-q','-e','pipewiresrc',f'fd={fd}',f'path={node}',
                             'do-timestamp=true','num-buffers=1','!','videoconvert','!',
                             'pngenc','snapshot=true','!','filesink','location='+gst_string(path)]
                        # A preview must not block the UI or leak its child on timeout.
                        with tempfile.TemporaryFile() as preview_log:
                            preview_process=subprocess.Popen(cmd,pass_fds=(fd,),stdout=preview_log,stderr=subprocess.STDOUT)
                            try:
                                await until_stopped(asyncio.to_thread(preview_process.wait,20),self.stop_event)
                            except subprocess.TimeoutExpired:
                                preview_process.kill()
                                await asyncio.to_thread(preview_process.wait)
                                raise RuntimeError('The selected screen produced no preview. Try full-source recording.')
                            finally:
                                if preview_process.poll() is None:
                                    preview_process.kill()
                                    await asyncio.to_thread(preview_process.wait)
                                os.close(fd);fd=None
                            if preview_process.returncode:
                                preview_log.seek(0)
                                raise RuntimeError(preview_log.read().decode(errors='replace')[-2500:])
                        if not Path(path).is_file() or Path(path).stat().st_size<128:
                            raise RuntimeError('The selected desktop source did not produce a marquee preview.')
                        self.preview.emit(path)
                        logging.info('Recorder: waiting for selected area')
                        while not self.selection_ready.is_set():
                            if self.stop_event.is_set():
                                return
                            await asyncio.sleep(.1)
                        if self.cancelled:
                            return
                fd=await portal.remote()
            if self.stop_event.is_set():
                return
            cmd=pipeline(self.path,self.mode,fd,node,self.crop,self.audio)
            with tempfile.TemporaryFile() as log:
                process=subprocess.Popen(cmd,pass_fds=(fd,) if fd is not None else (),
                                         stdout=log,stderr=subprocess.STDOUT)
                # Catch immediate startup/plugin errors before showing Recording.
                await asyncio.sleep(.7)
                if process.poll() is None and not self.stop_event.is_set():
                    logging.info('Recorder: encoder active (PID %s)',process.pid)
                    self.recording_active.emit()
                while process.poll() is None and not self.stop_event.is_set():
                    await asyncio.sleep(.1)
                stopped=self.stop_event.is_set()
                if process.poll() is None:
                    logging.info('Recorder: stopping encoder')
                    process.send_signal(signal.SIGINT)  # gst-launch -e writes EOS/trailer.
                    try:
                        await asyncio.to_thread(process.wait,20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        await asyncio.to_thread(process.wait)
                        raise RuntimeError('Encoder could not finalize in 20 seconds. The recording may be incomplete.')
                log.seek(0)
                details=log.read().decode(errors='replace')[-3500:]
                if not recording_output_ok(self.path,process.returncode,details,stopped):
                    raise RuntimeError('Recording failed.\n'+details)
                if not stopped:
                    raise RuntimeError('Capture ended unexpectedly; check the saved file before using it.\n'+details)
                self.saved.emit(self.path)
                logging.info('Recorder: saved')
        except Cancelled:
            pass
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if process and process.poll() is None:
                process.kill()
                await asyncio.to_thread(process.wait)
            if fd is not None:
                os.close(fd)
            if portal:
                await portal.close()
            logging.info('Recorder: session released')

