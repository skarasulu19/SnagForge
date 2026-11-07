import asyncio
import os
import signal
import subprocess
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse, unquote
from PySide6.QtCore import QThread, Signal
from portal import Portal, Cancelled
from media import pipeline, gst_string

FINALIZE_GRACE_SECONDS=8
TERMINATE_GRACE_SECONDS=3

def _mp4_has_playable_boxes(path):
    """Check the MP4 initialization and media boxes without reading a huge file."""
    target=Path(path)
    size=target.stat().st_size
    with target.open('rb') as stream:
        head=stream.read(min(size,2*1024*1024))
        tail=b''
        if size>len(head):
            stream.seek(max(0,size-2*1024*1024))
            tail=stream.read()
    sample=head+tail
    return b'ftyp' in sample and b'moov' in sample and (b'moof' in sample or b'mdat' in sample)

def recording_output_ok(path,returncode,details,stopped):
    """Accept playable user-stopped output even when gst-launch needed forcing down."""
    target=Path(path)
    if not target.is_file() or target.stat().st_size<128:
        return False
    if target.suffix.lower()=='.mp4' and not _mp4_has_playable_boxes(target):
        return False
    # SIGINT/SIGTERM are expected after Stop. Encoder errors remain fatal when
    # the pipeline ended by itself, but must not discard playable fragments.
    return stopped or (not returncode and 'ERROR' not in details)

def _signal_group(process, sig):
    """Signal the recorder's private process group, falling back to the child."""
    try:
        os.killpg(process.pid,sig)
    except (AttributeError,ProcessLookupError):
        try:
            process.send_signal(sig)
        except ProcessLookupError:
            pass

async def finalize_process(process):
    """Request EOS, then bound shutdown without trapping the application UI."""
    _signal_group(process,signal.SIGINT)  # gst-launch -e converts this to EOS.
    try:
        await asyncio.to_thread(process.wait,FINALIZE_GRACE_SECONDS)
        return False
    except subprocess.TimeoutExpired:
        _signal_group(process,signal.SIGTERM)
        try:
            await asyncio.to_thread(process.wait,TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            _signal_group(process,signal.SIGKILL)
            await asyncio.to_thread(process.wait)
        return True

class CaptureWorker(QThread):
    image = Signal(str)
    error = Signal(str)
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
            portal=await Portal().connect()
            uri=await portal.screenshot()
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
    started = Signal()
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
                portal=await Portal().connect()
                node=await portal.screencast()
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
                                await asyncio.to_thread(preview_process.wait,20)
                            except subprocess.TimeoutExpired:
                                preview_process.kill()
                                await asyncio.to_thread(preview_process.wait)
                                raise RuntimeError('The selected screen produced no preview. Try full-source recording.')
                            finally:
                                os.close(fd);fd=None
                            if preview_process.returncode:
                                preview_log.seek(0)
                                raise RuntimeError(preview_log.read().decode(errors='replace')[-2500:])
                        if not Path(path).is_file() or Path(path).stat().st_size<128:
                            raise RuntimeError('The selected desktop source did not produce a marquee preview.')
                        self.preview.emit(path)
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
                                         stdout=log,stderr=subprocess.STDOUT,
                                         start_new_session=True)
                # Catch immediate startup/plugin errors before showing Recording.
                await asyncio.sleep(.7)
                if process.poll() is None:
                    self.started.emit()
                while process.poll() is None and not self.stop_event.is_set():
                    await asyncio.sleep(.1)
                stopped=self.stop_event.is_set()
                forced_shutdown=False
                if process.poll() is None:
                    forced_shutdown=await finalize_process(process)
                log.seek(0)
                details=log.read().decode(errors='replace')[-3500:]
                if not recording_output_ok(self.path,process.returncode,details,stopped):
                    if forced_shutdown:
                        raise RuntimeError('The encoder stopped responding and did not leave a playable recording.')
                    raise RuntimeError('Recording failed.\n'+details)
                if not stopped:
                    raise RuntimeError('Capture ended unexpectedly; check the saved file before using it.\n'+details)
                self.saved.emit(self.path)
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
