import io
import math
from PIL import Image as PillowImage, ImageFilter
from PySide6.QtCore import Qt, QPointF, QRect, QRectF, Signal, QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF, QFont
from PySide6.QtWidgets import QWidget, QInputDialog, QDialog, QVBoxLayout, QLabel, QDialogButtonBox

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
            if self.tool in ('Crop','Select','Pixelate','Blur','Redact','Spotlight'):
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
            if self.tool=='Text':
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
    full_source = Signal()
    cancelled = Signal()

    def __init__(self,image,parent=None):
        super().__init__(parent)
        self.image=image.convertToFormat(QImage.Format.Format_ARGB32)
        self.start=None;self.end=None;self.pointer=None
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
        if self.pointer is not None and target.contains(self.pointer):
            painter.setPen(QPen(QColor(255,255,255,125),1,Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(target.left(),self.pointer.y()),QPointF(target.right(),self.pointer.y()))
            painter.drawLine(QPointF(self.pointer.x(),target.top()),QPointF(self.pointer.x(),target.bottom()))
        hint='DRAG TO SELECT   •   ENTER: FULL SOURCE   •   ESC: CANCEL'
        metrics=painter.fontMetrics();width=metrics.horizontalAdvance(hint)+38
        box=QRectF((self.width()-width)/2,20,width,38)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(17,24,39,225))
        painter.drawRoundedRect(box,10,10);painter.setPen(Qt.GlobalColor.white)
        painter.drawText(box,Qt.AlignmentFlag.AlignCenter,hint)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.RightButton:
            self.cancelled.emit();return
        if event.button()!=Qt.MouseButton.LeftButton or not self.image_rect().contains(event.position()):return
        self.start=event.position();self.end=event.position();self.pointer=event.position();self.update()

    def mouseMoveEvent(self,event):
        self.pointer=event.position()
        if self.start is not None:self.end=event.position()
        self.update()

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or self.start is None:return
        self.end=event.position();region=self.selection();self.update()
        if region.width()>1 and region.height()>1:self.selected.emit(region)
        else:self.start=None;self.end=None

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:self.cancelled.emit()
        elif event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.full_source.emit()
        else:super().keyPressEvent(event)

class RegionDialog(QDialog):
    def __init__(self,image,parent=None):
        super().__init__(parent)
        self.setWindowTitle('SnagForge · Select desktop region')
        self.setWindowFlags(Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowState(self.windowState()|Qt.WindowState.WindowFullScreen)
        self.region=None
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0)
        self.selector=RegionSelector(image,self);self.canvas=self.selector
        self.selector.selected.connect(self.choose)
        self.selector.full_source.connect(self.accept)
        self.selector.cancelled.connect(self.reject)
        layout.addWidget(self.selector)
    def showEvent(self,event):
        super().showEvent(event);self.selector.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
    def choose(self,rect):
        self.region=rect
        self.accept()
