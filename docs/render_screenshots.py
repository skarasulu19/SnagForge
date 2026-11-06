"""Reproduce documentation screenshots using real Qt widgets and synthetic sample data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication
from app import Window, ScrollDialog, STYLE
from editor import RegionSelector

out=Path(__file__).parent/'screenshots';out.mkdir(exist_ok=True)
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet(STYLE)
image=QImage(1100,660,QImage.Format.Format_ARGB32);image.fill(QColor('#f4f7fb'))
p=QPainter(image)
def text(x,y,content,size=16,color='#27354a',bold=False):
    f=QFont('DejaVu Sans');f.setPixelSize(size);f.setBold(bold);p.setFont(f);p.setPen(QColor(color));p.drawText(x,y,content)
p.fillRect(0,0,1100,76,QColor('#17243b'))
text(32,46,'PROJECT OVERVIEW',24,'#f4f7fb',True)
text(740,44,'DEMO DATA  /  November 2026',14,'#9fb4d2')
for x,title,value in [(30,'ACTIVE PROJECTS','12'),(390,'TASKS COMPLETE','84%'),(750,'OPEN REVIEWS','03')]:
    p.fillRect(x,106,320,115,QColor('white'));text(x+22,140,title,12,'#71829b');text(x+22,192,value,34,'#173b60',True)
text(32,267,'Release readiness',21,bold=True)
for i,(name,status) in enumerate([('Screenshot editor','Ready for review'),('Screen recording','Desktop validation pending'),('Documentation','Draft complete'),('Scrolling capture','Guided workflow')]):
    y=300+i*66;p.fillRect(30,y,1040,54,QColor('white'));text(48,y+33,name,16);text(680,y+33,status,15,'#397d70')
text(32,626,'Synthetic sample image for SnagForge documentation. No personal information.',13,'#708099')
p.end()
window=Window();window.show();window.load_image(image)
window.canvas.tool='Rectangle';window.canvas.points=[QPointF(376,98),QPointF(724,230)]
result=window.canvas.image.copy();window.canvas.draw_annotation(result);window.canvas.commit(result)
window.canvas.tool='Arrow';window.canvas.points=[QPointF(608,277),QPointF(566,221)]
result=window.canvas.image.copy();window.canvas.draw_annotation(result);window.canvas.commit(result)
window.canvas.tool='Step';window.canvas.points=[QPointF(1013,145),QPointF(1013,145)]
result=window.canvas.image.copy();window.canvas.draw_annotation(result);window.canvas.commit(result)
window.canvas.tool='Arrow';app.processEvents();window.grab().save(str(out/'01-editor.png'))
selection=RegionSelector(image);selection.resize(1100,750);selection.show();app.processEvents()
selection.start=QPointF(180,180);selection.end=QPointF(650,470);selection.pointer=selection.end
selection.update();app.processEvents()
if not selection.grab().save(str(out/'02-region-selection.png')):raise RuntimeError('Could not render region selector')
selection.hide()
scroll=ScrollDialog(window);scroll.add(image);scroll.add(image);scroll.show();app.processEvents();scroll.grab().save(str(out/'03-scrolling-capture.png'));scroll.hide()
# Recording controls shown in their actual idle state: no fake active recording.
window.mode.setCurrentText('MP4 video');window.audio.setCurrentText('System audio');window.region.setChecked(True)
window.statusBar().showMessage('Recording setup · Choose MP4 / MP3, audio source, and capture region')
app.processEvents();window.grab().save(str(out/'04-recording-setup.png'))
window.dirty=False;window.close()
print('Wrote 4 real-widget screenshots to',out)
