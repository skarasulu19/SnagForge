"""Render the actual Angular desktop window with synthetic data and exercise its bridge.

Run with QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software for headless QA.
This checks the desktop UI, not live GNOME/Wayland screen recording.
"""
import os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer,QPoint,Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from web_shell import DesktopWindow

app=QApplication([]);window=DesktopWindow();window.resize(1520,960);window.show()
out=Path(__file__).parent/'screenshots';out.mkdir(exist_ok=True)

def js(expression,callback=lambda result:None):window.page.runJavaScript(expression,callback)
def fail(message):print('FAIL:',message,flush=True);app.exit(1)
def ready():
 js("JSON.stringify({text:document.querySelector('snagforge-app').innerText})",check_root)
def check_root(data):
 if not data or 'Desktop connected' not in data:return fail('Angular did not connect to the native bridge.')
 js("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('Explore with an example')).click()")
 QTimer.singleShot(800,prepare_annotation)
def prepare_annotation():
 if window.engine.canvas.image.width()!=1200:return fail('Demo image did not reach the native engine.')
 js("document.querySelector('button[aria-label=Rectangle]').click()")
 QTimer.singleShot(100,find_canvas)
def find_canvas():
 js("JSON.stringify((()=>{const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};})())",draw)
def draw(data):
 r=json.loads(data);target=window.view.focusProxy() or window.view
 a=QPoint(round(r['x']+r['w']*.335),round(r['y']+r['h']*.275))
 b=QPoint(round(r['x']+r['w']*.645),round(r['y']+r['h']*.485))
 QTest.mousePress(target,Qt.MouseButton.LeftButton,pos=a)
 QTest.mouseMove(target,b,30)
 QTest.mouseRelease(target,Qt.MouseButton.LeftButton,pos=b)
 QTimer.singleShot(600,check_annotation)
def check_annotation():
 js("JSON.stringify({undo:!document.querySelector('button[aria-label=Undo]').disabled,width:document.querySelector('canvas').width})",after_annotation)
def after_annotation(data):
 data=json.loads(data)
 if not data['undo'] or data['width']!=1200:return fail('Annotation did not update undo history.')
 window.grab().save(str(out/'05-angular-editor.png'))
 js("Array.from(document.querySelectorAll('.quick-actions button')).find(b=>b.textContent.includes('Copy image')).click()")
 QTimer.singleShot(300,check_copy)
def check_copy():
 if app.clipboard().image().width()!=1200:return fail('Copy did not reach the native clipboard.')
 js("document.querySelector('button[aria-label=Undo]').click()")
 QTimer.singleShot(300,check_undo)
def check_undo():
 js("JSON.stringify({undo:document.querySelector('button[aria-label=Undo]').disabled,redo:!document.querySelector('button[aria-label=Redo]').disabled})",after_undo)
def after_undo(data):
 data=json.loads(data)
 if not data['undo'] or not data['redo']:return fail('Undo/redo state is incorrect.')
 js("document.querySelector('button[aria-label=Redo]').click()")
 js("Array.from(document.querySelectorAll('nav button')).find(b=>b.textContent.includes('Screen recorder')).click()")
 QTimer.singleShot(300,recording_view)
def recording_view():
 js("document.querySelector('.toast button')?.click()")
 QTimer.singleShot(100,save_recording_view)
def save_recording_view():
 window.grab().save(str(out/'06-angular-recorder.png'))
 js("Array.from(document.querySelectorAll('nav button')).find(b=>b.textContent.includes('Workflows')).click()")
 QTimer.singleShot(300,workflow_view)
def workflow_view():
 window.grab().save(str(out/'07-angular-workflows.png'))
 print('PASS: Angular desktop startup, native bridge image sync, annotation, native clipboard, undo/redo and three UI screenshots.',flush=True)
 window.engine.dirty=False;app.exit(0)

window.view.loadFinished.connect(lambda ok:QTimer.singleShot(900,ready) if ok else fail('Angular page load failed.'))
QTimer.singleShot(25000,lambda:fail('UI check timed out.'))
sys.exit(app.exec())
