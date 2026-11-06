import io
import math
import platform
from datetime import datetime
from PIL import Image as PillowImage, ImageFilter
from PySide6.QtCore import Qt, QPointF, QRect, QRectF, Signal, QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF, QFont
from PySide6.QtWidgets import QWidget, QInputDialog, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDialogButtonBox, QPushButton

def blur_image(image,radius):
    """Apply a real Gaussian blur to a QImage using the local Pillow dependency."""
    encoded=QBuffer();encoded.open(QIODevice.OpenModeFlag.WriteOnly);image.save(encoded,'PNG')
    source=PillowImage.open(io.BytesIO(bytes(encoded.data()))).convert('RGBA')
    output=io.BytesIO();source.filter(ImageFilter.GaussianBlur(radius)).save(output,'PNG')
    return QImage.fromData(output.getvalue())

class Canvas(QWidget):
    changed = Signal()
    selected = Signal(QRect)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self.tool = 'Arrow'
        self.color = QColor('#f97356')
        self.stroke_width = 5
        self.history, self.future = [], []
        self.points = []
        self.dragging = False
        self.number = 1
        self.setMinimumSize(480, 300)
        self.setMouseTracking(True)

    def load(self, image):
        self.image = image.convertToFormat(QImage.Format.Format_ARGB32)
        self.history, self.future = [], []
        self.number = 1
        self.changed.emit()
        self.update()

    def commit(self, image):
        self.history.append(self.image.copy())
        self.history = self.history[-20:]
        self.future.clear()
        self.image = image
        self.changed.emit()
        self.update()

    def undo(self):
        if self.history:
            self.future.append(self.image.copy())
            self.image = self.history.pop()
            self.changed.emit()
            self.update()

    def redo(self):
        if self.future:
            self.history.append(self.image.copy())
            self.image = self.future.pop()
            self.changed.emit()
            self.update()

    def geometry_image(self):
        if self.image.isNull():
            return QRectF()
        scale = min((self.width()-32)/self.image.width(), (self.height()-32)/self.image.height())
        w,h = self.image.width()*scale, self.image.height()*scale
        return QRectF((self.width()-w)/2, (self.height()-h)/2, w,h)

    def image_point(self, p):
        r = self.geometry_image()
        return QPointF(max(0,min(self.image.width()-1,(p.x()-r.x())*self.image.width()/r.width())),
                       max(0,min(self.image.height()-1,(p.y()-r.y())*self.image.height()/r.height())))

    def paintEvent(self, e):
        p=QPainter(self)
        p.fillRect(self.rect(), QColor('#111723'))
        if self.image.isNull():
            p.setPen(QColor('#a5b2c7'))
            p.setFont(QFont('Sans', 16))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       'Capture something worth explaining.\n\nNew capture · Open image · Paste from clipboard')
            return
        r=self.geometry_image()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(r,self.image)
        if self.dragging:
            preview=self.image.copy()
            if self.tool in ('Crop','Select','Pixelate','Blur','Redact','Spotlight','Magnify'):
                p.setPen(QPen(QColor('#59d5ca'),2,Qt.PenStyle.DashLine))
                a,b=self.points[0],self.points[-1]
                factor=r.width()/self.image.width()
                p.drawRect(QRectF(QPointF(r.x()+a.x()*factor,r.y()+a.y()*factor),
                                      QPointF(r.x()+b.x()*factor,r.y()+b.y()*factor)).normalized())
            else:
                self.draw_annotation(preview)
                p.drawImage(r,preview)

    def mousePressEvent(self,e):
        if self.image.isNull() or e.button()!=Qt.MouseButton.LeftButton:
            return
        if not self.geometry_image().contains(e.position()):
            return
        self.points=[self.image_point(e.position())]
        self.dragging=True

    def mouseMoveEvent(self,e):
        if self.dragging:
            self.points.append(self.image_point(e.position()))
            self.update()

    def mouseReleaseEvent(self,e):
        if not self.dragging:
            return
        self.points.append(self.image_point(e.position()))
        self.dragging=False
        rect=QRectF(self.points[0],self.points[-1]).normalized().toAlignedRect().intersected(self.image.rect())
        if self.tool=='Select':
            if rect.width()>1 and rect.height()>1:
                self.selected.emit(rect)
        elif self.tool=='Crop':
            if rect.width()>1 and rect.height()>1:
                self.commit(self.image.copy(rect))
        elif self.tool in ('Pixelate','Blur','Redact','Spotlight'):
            if rect.width()>1 and rect.height()>1:
                result=self.image.copy()
                p=QPainter(result)
                if self.tool=='Pixelate':
                    part=self.image.copy(rect)
                    part=part.scaled(max(1,rect.width()//16),max(1,rect.height()//16),
                                     Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
                    p.drawImage(rect,part.scaled(rect.size()))
                elif self.tool=='Blur':
                    p.drawImage(rect,blur_image(self.image.copy(rect),max(3,self.stroke_width)))
                elif self.tool=='Redact':
                    p.fillRect(rect,Qt.GlobalColor.black)
                else:
                    p.fillRect(result.rect(),QColor(0,0,0,170))
                    p.drawImage(rect,self.image.copy(rect))
                p.end()
                self.commit(result)
        else:
            text=None
            if self.tool in ('Text','Callout'):
                text,ok=QInputDialog.getMultiLineText(self,'Text annotation','Text:')
                if not ok or not text:
                    self.update()
                    return
            result=self.image.copy()
            self.draw_annotation(result,text)
            if self.tool=='Step':
                self.number+=1
            self.commit(result)
        self.update()

    def draw_annotation(self,result,text=None):
        p=QPainter(result)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(self.color,self.stroke_width,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        a,b=self.points[0],self.points[-1]
        rect=QRectF(a,b).normalized()
        if self.tool=='Pen':
            p.drawPolyline(QPolygonF(self.points))
        elif self.tool in ('Arrow','Line'):
            p.drawLine(a,b)
            if self.tool=='Arrow':
                angle=math.atan2(b.y()-a.y(),b.x()-a.x())
                size=max(16,self.stroke_width*4)
                p.setBrush(self.color)
                p.drawPolygon(QPolygonF([b,QPointF(b.x()-size*math.cos(angle-.5),b.y()-size*math.sin(angle-.5)),
                                         QPointF(b.x()-size*math.cos(angle+.5),b.y()-size*math.sin(angle+.5))]))
        elif self.tool=='Rectangle': p.drawRect(rect)
        elif self.tool=='Ellipse': p.drawEllipse(rect)
        elif self.tool=='Highlight': p.fillRect(rect,QColor(255,221,60,100))
        elif self.tool=='Callout' and text:
            box=rect if rect.width()>80 and rect.height()>45 else QRectF(a.x(),a.y(),260,100)
            p.setPen(QPen(self.color,max(2,self.stroke_width//2)));p.setBrush(self.color)
            p.drawRoundedRect(box,14,14)
            tail=QPolygonF([QPointF(box.left()+30,box.bottom()),QPointF(box.left()+50,box.bottom()),QPointF(box.left()+28,box.bottom()+24)])
            p.drawPolygon(tail);p.setPen(Qt.GlobalColor.white)
            f=QFont('Sans');f.setPixelSize(max(17,self.stroke_width*4));f.setBold(True);p.setFont(f)
            p.drawText(box.adjusted(16,10,-16,-10),Qt.AlignmentFlag.AlignCenter|Qt.TextFlag.TextWordWrap,text)
        elif self.tool=='Stamp':
            radius=max(22,self.stroke_width*5);p.setBrush(self.color);p.setPen(Qt.PenStyle.NoPen);p.drawEllipse(a,radius,radius)
            p.setPen(QPen(Qt.GlobalColor.white,max(4,radius//7),Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
            p.drawLine(QPointF(a.x()-radius*.45,a.y()),QPointF(a.x()-radius*.1,a.y()+radius*.35))
            p.drawLine(QPointF(a.x()-radius*.1,a.y()+radius*.35),QPointF(a.x()+radius*.5,a.y()-radius*.4))
        elif self.tool=='Magnify' and rect.width()>3 and rect.height()>3:
            inner=QRect(rect.center().x()-max(1,rect.width()//4),rect.center().y()-max(1,rect.height()//4),max(2,rect.width()//2),max(2,rect.height()//2)).intersected(self.image.rect())
            enlarged=self.image.copy(inner).scaled(max(2,int(rect.width())),max(2,int(rect.height())),Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
            p.drawImage(rect,enlarged);p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(self.color,max(3,self.stroke_width)));p.drawRoundedRect(rect,12,12)
        elif self.tool=='Capture Info':
            box=rect if rect.width()>220 and rect.height()>55 else QRectF(a.x(),a.y(),390,82)
            box=box.intersected(QRectF(result.rect()))
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(16,24,39,225));p.drawRoundedRect(box,10,10)
            p.setPen(Qt.GlobalColor.white);f=QFont('Sans');f.setPixelSize(max(14,self.stroke_width*3));f.setBold(True);p.setFont(f)
            info=f'Ubuntu · {platform.release()}   •   {datetime.now():%Y-%m-%d %H:%M}\n{result.width()} × {result.height()} px   •   SnagForge'
            p.drawText(box.adjusted(14,9,-14,-9),Qt.AlignmentFlag.AlignVCenter|Qt.TextFlag.TextWordWrap,info)
        elif self.tool=='Step':
            radius=max(18,self.stroke_width*4)
            p.setBrush(self.color)
            p.drawEllipse(a,radius,radius)
            p.setPen(Qt.GlobalColor.white)
            f=QFont('Sans');f.setPixelSize(radius);f.setBold(True);p.setFont(f)
            p.drawText(QRectF(a.x()-radius,a.y()-radius,radius*2,radius*2),Qt.AlignmentFlag.AlignCenter,str(self.number))
        elif self.tool=='Text' and text:
            f=QFont('Sans');f.setPixelSize(max(20,self.stroke_width*5));p.setFont(f)
            p.drawText(QRectF(a.x(),a.y(),max(100,result.width()-a.x()),max(100,result.height()-a.y())),text)
        p.end()

class RegionSelector(QWidget):
    """Full-screen, portal-safe marquee selector for a captured source frame."""
    selected = Signal(QRect)
    confirmed = Signal(QRect)
    full_source = Signal()
    cancelled = Signal()
    selection_started = Signal()

    def __init__(self,image,parent=None):
        super().__init__(parent)
        self.image=image.convertToFormat(QImage.Format.Format_ARGB32)
        self.start=None;self.end=None;self.pointer=None
        self.dragging=False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def image_rect(self):
        if self.image.isNull():return QRectF()
        scale=min(self.width()/self.image.width(),self.height()/self.image.height())
        width,height=self.image.width()*scale,self.image.height()*scale
        return QRectF((self.width()-width)/2,(self.height()-height)/2,width,height)

    def image_point(self,point):
        target=self.image_rect()
        if target.isEmpty():return QPointF()
        return QPointF(
            max(0,min(self.image.width(),(point.x()-target.x())*self.image.width()/target.width())),
            max(0,min(self.image.height(),(point.y()-target.y())*self.image.height()/target.height())))

    def selection(self):
        if self.start is None or self.end is None:return QRect()
        first,last=self.image_point(self.start),self.image_point(self.end)
        left,top=math.floor(min(first.x(),last.x())),math.floor(min(first.y(),last.y()))
        right,bottom=math.ceil(max(first.x(),last.x())),math.ceil(max(first.y(),last.y()))
        return QRect(left,top,max(0,right-left),max(0,bottom-top)).intersected(self.image.rect())

    def target_rect(self,source):
        target=self.image_rect();scale=target.width()/self.image.width()
        return QRectF(target.x()+source.x()*scale,target.y()+source.y()*scale,
                      source.width()*scale,source.height()*scale)

    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor('#080d18'))
        target=self.image_rect()
        if target.isEmpty():return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(target,self.image)
        source=self.selection()
        if not source.isEmpty():
            painter.fillRect(target,QColor(4,8,18,145))
            destination=self.target_rect(source)
            painter.drawImage(destination,self.image,QRectF(source))
            painter.setPen(QPen(QColor('#8f7cff'),3))
            painter.drawRect(destination)
            label=f'{source.width():,} × {source.height():,}'
            metrics=painter.fontMetrics();label_width=metrics.horizontalAdvance(label)+24
            label_box=QRectF(destination.x(),max(12,destination.y()-38),label_width,28)
            painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#7864ef'))
            painter.drawRoundedRect(label_box,6,6)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(label_box,Qt.AlignmentFlag.AlignCenter,label)
        if self.pointer is not None and (self.dragging or source.isEmpty()) and target.contains(self.pointer):
            painter.setPen(QPen(QColor(255,255,255,125),1,Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(target.left(),self.pointer.y()),QPointF(target.right(),self.pointer.y()))
            painter.drawLine(QPointF(self.pointer.x(),target.top()),QPointF(self.pointer.x(),target.bottom()))
        hint=('RELEASE TO SET AREA' if self.dragging else
              'AREA SET   •   ENTER: CONFIRM   •   DRAG AGAIN TO REDRAW' if not source.isEmpty() else
              'DRAG TO SELECT   •   ENTER: FULL SOURCE')+'   •   ESC: CANCEL'
        metrics=painter.fontMetrics();width=metrics.horizontalAdvance(hint)+38
        box=QRectF((self.width()-width)/2,20,width,38)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(17,24,39,225))
        painter.drawRoundedRect(box,10,10);painter.setPen(Qt.GlobalColor.white)
        painter.drawText(box,Qt.AlignmentFlag.AlignCenter,hint)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.RightButton:
            self.cancelled.emit();return
        if event.button()!=Qt.MouseButton.LeftButton or not self.image_rect().contains(event.position()):return
        self.dragging=True
        self.start=event.position();self.end=event.position();self.pointer=event.position()
        self.selection_started.emit()
        # Qt implicitly grabs the mouse for the widget receiving the press.
        # Explicit grabs are unsupported on some Wayland compositors.
        self.setFocus(Qt.FocusReason.MouseFocusReason);self.update()

    def mouseMoveEvent(self,event):
        self.pointer=event.position()
        if self.dragging:self.end=event.position()
        self.update()

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or not self.dragging:return
        self.dragging=False
        self.end=event.position();region=self.selection();self.update()
        if region.width()>1 and region.height()>1:self.selected.emit(region)
        else:self.start=None;self.end=None

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:self.cancelled.emit()
        elif event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            if self.dragging:return
            region=self.selection()
            if region.width()>1 and region.height()>1:self.confirmed.emit(region)
            else:self.full_source.emit()
        else:super().keyPressEvent(event)

class RegionDialog(QDialog):
    def __init__(self,image,parent=None,confirm_text='Use selected area'):
        super().__init__(parent)
        self.setWindowTitle('SnagForge · Select desktop region')
        # Keep the selector with its owning app rather than adding another
        # task-switcher entry while the user is trying to choose an area.
        self.setWindowFlags(Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowState(self.windowState()|Qt.WindowState.WindowFullScreen)
        self.region=None
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        self.selector=RegionSelector(image,self);self.canvas=self.selector
        self.selector.selected.connect(self.preview_selection)
        self.selector.selection_started.connect(self.begin_selection)
        self.selector.confirmed.connect(self.choose)
        self.selector.full_source.connect(self.accept)
        self.selector.cancelled.connect(self.reject)
        layout.addWidget(self.selector,1)
        actions=QHBoxLayout();actions.setContentsMargins(18,12,18,12);actions.setSpacing(10)
        hint=QLabel('Drag, release to set the box, then confirm.');hint.setStyleSheet('color:#64748b;')
        actions.addWidget(hint);actions.addStretch()
        cancel=QPushButton('Cancel');cancel.clicked.connect(self.reject);actions.addWidget(cancel)
        full=QPushButton('Use full source');full.clicked.connect(self.use_full_source);actions.addWidget(full)
        self.confirm_button=QPushButton(confirm_text);self.confirm_button.setEnabled(False)
        self.confirm_button.setObjectName('primary')
        self.confirm_button.clicked.connect(self.confirm_selection);actions.addWidget(self.confirm_button)
        layout.addLayout(actions)
    def showEvent(self,event):
        super().showEvent(event)
        self.raise_();self.activateWindow()
        if self.windowHandle():self.windowHandle().requestActivate()
        self.selector.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
    def begin_selection(self):
        self.region=None;self.confirm_button.setEnabled(False)
        self.confirm_button.setText(self.confirm_button.text().split('  ·  ')[0])
    def choose(self,rect):
        self.region=rect
        self.accept()
    def preview_selection(self,rect):
        self.region=rect;self.confirm_button.setEnabled(True)
        self.confirm_button.setText(self.confirm_button.text().split('  ·  ')[0]+f'  ·  {rect.width()} × {rect.height()}')
    def confirm_selection(self):
        if self.region and self.region.width()>1 and self.region.height()>1:self.accept()
    def use_full_source(self):
        self.region=None;self.accept()

