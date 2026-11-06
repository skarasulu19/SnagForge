import math
from PySide6.QtCore import Qt, QPointF, QRect, QRectF, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF, QFont
from PySide6.QtWidgets import QWidget, QInputDialog, QDialog, QVBoxLayout, QLabel, QDialogButtonBox

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
            if self.tool in ('Crop','Select','Pixelate','Redact','Spotlight'):
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
        elif self.tool in ('Pixelate','Redact','Spotlight'):
            if rect.width()>1 and rect.height()>1:
                result=self.image.copy()
                p=QPainter(result)
                if self.tool=='Pixelate':
                    part=self.image.copy(rect)
                    part=part.scaled(max(1,rect.width()//16),max(1,rect.height()//16),
                                     Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
                    p.drawImage(rect,part.scaled(rect.size()))
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

class RegionDialog(QDialog):
    def __init__(self,image,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select capture area — drag a rectangle')
        self.resize(1100,750)
        self.region=None
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Drag over the image to choose an area. Full source keeps the entire screen/window.'))
        self.canvas=Canvas();self.canvas.load(image);self.canvas.tool='Select'
        self.canvas.selected.connect(self.choose)
        layout.addWidget(self.canvas,1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        full=buttons.addButton('Full source',QDialogButtonBox.ButtonRole.AcceptRole)
        full.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def choose(self,rect):
        self.region=rect
        self.accept()
