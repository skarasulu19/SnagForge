"""Native Qt visual components for SnagForge's capture studio."""
from PySide6.QtCore import Qt, QByteArray, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton, QLabel, QVBoxLayout, QWidget, QDialog

PATHS = {
    'capture': '<path d="M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3M3 16v3a2 2 0 0 0 2 2h3m8 0h3a2 2 0 0 0 2-2v-3"/><rect x="7" y="7" width="10" height="10" rx="2"/>',
    'video': '<rect x="3" y="5" width="13" height="14" rx="3"/><path d="m16 10 5-3v10l-5-3"/>',
    'scroll': '<rect x="5" y="2" width="14" height="20" rx="3"/><path d="M9 7h6M9 11h6m-6 4h6m-5 3 2 2 2-2"/>',
    'folder': '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 9h18"/>',
    'image': '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
    'paste': '<rect x="5" y="4" width="14" height="18" rx="2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M9 11h6m-6 4h6"/>',
    'export': '<path d="M12 15V3m-4 4 4-4 4 4M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/>',
    'copy': '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    'undo': '<path d="m8 4-5 5 5 5M3 9h10a7 7 0 0 1 0 14"/>',
    'redo': '<path d="m16 4 5 5-5 5m5-5H11a7 7 0 0 0 0 14"/>',
    'Arrow': '<path d="M4 20 20 4M8 4h12v12"/>',
    'Pen': '<path d="m4 16-1 5 5-1L21 7l-4-4Zm10-10 4 4"/>',
    'Line': '<path d="M4 20 20 4"/>',
    'Rectangle': '<rect x="3" y="5" width="18" height="14" rx="1"/>',
    'Ellipse': '<ellipse cx="12" cy="12" rx="9" ry="7"/>',
    'Text': '<path d="M4 4h16M12 4v16m-4 0h8"/>',
    'Callout': '<path d="M4 4h16v12H9l-5 4v-4H4z"/><path d="M8 8h8m-8 4h5"/>',
    'Stamp': '<circle cx="12" cy="12" r="9"/><path d="m7 12 3 3 7-7"/>',
    'Magnify': '<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M10 7v6m-3-3h6"/>',
    'Capture Info': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 8h10M7 12h7m-7 4h4"/>',
    'Step': '<circle cx="12" cy="12" r="9"/><path d="m10 9 2-2v10m-2 0h4"/>',
    'Highlight': '<path d="m7 15 8-12 6 4-8 12-6-4Zm0 0-4 5h8"/>',
    'Pixelate': '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
    'Blur': '<path d="M8 5h.01M12 4h.01M16 6h.01M6 10h.01M11 9h.01M17 11h.01M5 15h.01M10 16h.01M15 15h.01M19 17h.01M8 20h.01M14 20h.01" stroke-width="3"/>',
    'Redact': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M6 9h12m-12 3h12m-12 3h12"/>',
    'Spotlight': '<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5m-10-15v4m-3 2h4"/>',
    'Crop': '<path d="M6 2v16h16M2 6h16v16"/>',
    'rotate': '<path d="M20 10a8 8 0 1 0-1 8M20 3v7h-7"/>',
    'resize': '<path d="M9 3H3v6m12 12h6v-6M3 3l7 7m11 11-7-7"/>',
    'frame': '<rect x="5" y="4" width="15" height="15" rx="2"/><path d="M2 8v13h14M8 8h9v8H8z"/>',
    'ocr': '<path d="M7 3H3v4m14-4h4v4M3 17v4h4m14-4v4h-4M7 8h10m-5 0v9m-3 0h6"/>',
    'pin': '<path d="m8 3 13 13-5 1-3 4-2-8-8-2 5-3ZM3 21l7-7"/>',
    'help': '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3v1"/>',
    'shield': '<path d="m12 2 9 4v6c0 5-9 10-9 10S3 17 3 12V6Zm-4 10 3 3 5-6"/>',
    'stop': '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    'record': '<circle cx="12" cy="12" r="7" fill="currentColor"/>',
}

def icon(name, color='#888888', size=20):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" color="{color}" stroke="{color}" stroke-width="1.7" '
           'stroke-linecap="round" stroke-linejoin="round">' + PATHS[name] + '</svg>')
    pixmap=QPixmap(size*2,size*2);pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap);QSvgRenderer(QByteArray(svg.encode())).render(painter);painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)

def action_button(text, name, callback, kind='secondary', color='#7a7a7a'):
    control=QPushButton(text);control.setObjectName(kind)
    control.setIcon(icon(name,color));control.setIconSize(QSize(19,19))
    control.setCursor(Qt.CursorShape.PointingHandCursor)
    control.setAccessibleName(text);control.clicked.connect(callback)
    return control

def caption(text):
    label=QLabel(text);label.setObjectName('caption');return label

def field(text, control):
    wrapper=QWidget();layout=QVBoxLayout(wrapper)
    layout.setContentsMargins(0,0,0,0);layout.setSpacing(7)
    layout.addWidget(caption(text));layout.addWidget(control)
    return wrapper

class ReferenceWindow(QDialog):
    """A separate image reference; topmost is a compositor-dependent hint."""
    def __init__(self,image,parent=None):
        super().__init__(parent,Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.source=image.copy();self.setWindowTitle('SnagForge · Pinned reference')
        self.resize(min(850,image.width()+32),min(650,image.height()+32))
        self.label=QLabel();self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout=QVBoxLayout(self);layout.addWidget(self.label)
        self.refresh()
    def refresh(self):
        self.label.setPixmap(QPixmap.fromImage(self.source).scaled(
            max(1,self.width()-32),max(1,self.height()-32),
            Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def resizeEvent(self,event):
        super().resizeEvent(event);self.refresh()

STYLE = '''
QMainWindow,QDialog { background:#f7f7f7; }
QWidget { font-family:"DejaVu Sans"; font-size:12px; color:#383838; }
QWidget#sidebar { background:#1c1c1c; border-right:1px solid #2a2a2a; }
QWidget#sidebar QLabel { color:#b8b8b8; }
QLabel#brand { font-size:22px; font-weight:800; color:#f9f9f9; }
QLabel#logo { background:#f3a268; border-radius:13px; padding:10px; }
QLabel#sideCaption { color:#727272; font-size:9px; font-weight:700; letter-spacing:2px; }
QLabel#sideSub { color:#838383; font-size:10px; }
QLabel#title { font-size:24px; font-weight:800; color:#282828; }
QLabel#subtitle { font-size:11px; color:#979797; }
QLabel#caption { color:#a6a6a6; font-size:9px; font-weight:700; letter-spacing:1px; }
QLabel#chip { background:#eaf7f2; color:#258f73; border:1px solid #d1eee3; border-radius:9px; padding:5px 10px; font-size:9px; font-weight:700; }
QLabel#alpha { background:#323232; color:#f7c29d; border:1px solid #454545; border-radius:5px; padding:3px 7px; font-size:9px; }
QLabel#sectionTitle { font-size:13px; font-weight:700; color:#3f3f3f; }
QLabel#filename { font-size:12px; font-weight:700; color:#3f3f3f; }
QLabel#canvasInfo { color:#9a9a9a; font-size:10px; }
QFrame#editorCard,QFrame#recordCard,QFrame#inspector { background:#ffffff; border:1px solid #e8e8e8; border-radius:12px; }
QFrame#toolbar { background:#ffffff; border:0; border-bottom:1px solid #eeeeee; border-top-left-radius:12px; border-top-right-radius:12px; }
QFrame#imageHeader { background:#ffffff; border:0; }
QPushButton { border:1px solid #e7e7e7; border-radius:7px; background:#ffffff; padding:9px 13px; font-weight:600; }
QPushButton:hover { background:#fef6f0; border-color:#f6cbad; color:#df8d53; }
QPushButton:pressed { background:#fdede1; }
QPushButton:disabled { background:#f6f6f6; border-color:#ececec; color:#c3c3c3; }
QPushButton#primary { background:#ee9c61; border-color:#ee9c61; color:white; padding:11px 18px; }
QPushButton#primary:hover { background:#df8c50; border-color:#df8c50; }
QPushButton#primary:disabled { background:#f4cdb2; border-color:#f4cdb2; }
QPushButton#export { background:#282828; border-color:#282828; color:#ffffff; padding:11px 18px; }
QPushButton#export:hover { background:#424242; }
QPushButton#nav { background:transparent; border:1px solid transparent; color:#b6b6b6; text-align:left; padding:11px 14px; }
QPushButton#nav:hover { background:#2c2c2c; color:#fafafa; }
QPushButton#activeNav { background:#333333; border:1px solid #564132; color:#fad6bd; text-align:left; padding:11px 14px; }
QPushButton#quiet { border:0; background:transparent; color:#949494; font-size:11px; }
QPushButton#quiet:hover { background:#f0f0f0; color:#d18650; }
QPushButton#sideQuiet { border:0; background:transparent; text-align:left; color:#a1a1a1; }
QPushButton#sideQuiet:hover { background:#2b2b2b; }
QPushButton#swatch { border:2px solid #ffffff; border-radius:10px; padding:0; }
QToolButton { background:transparent; border:1px solid transparent; border-radius:7px; padding:7px; }
QToolButton:hover { background:#fef5ee; border-color:#f8e0cf; }
QToolButton:checked { background:#fdf1e8; border-color:#fadbc5; }
QComboBox,QSpinBox { background:#f9f9f9; border:1px solid #e6e6e6; padding:8px 10px; border-radius:7px; min-height:17px; }
QComboBox:hover,QSpinBox:hover { border-color:#f0c1a0; }
QComboBox QAbstractItemView { background:#ffffff; selection-background-color:#fdf2eb; selection-color:#df8c50; }
QComboBox::drop-down { border:0; width:20px; }
QCheckBox { color:#8a8a8a; spacing:7px; }
QCheckBox::indicator { width:15px; height:15px; border:1px solid #d8d8d8; border-radius:4px; background:#ffffff; }
QCheckBox::indicator:checked { background:#efa068; border:4px solid #fce8da; }
QListWidget { border:0; background:transparent; outline:none; color:#aeaeae; font-size:10px; }
QListWidget::item { padding:9px 3px; border-bottom:1px solid #2a2a2a; }
QListWidget::item:selected { background:#383838; color:#fbe3d2; border-radius:6px; }
QListWidget::item:hover { background:#2a2a2a; }
QScrollBar:vertical { background:transparent; width:5px; margin:0; }
QScrollBar::handle:vertical { background:#dddddd; border-radius:2px; min-height:24px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QStatusBar { background:#f7f7f7; border:0; color:#a2a2a2; padding:4px 14px; font-size:10px; }
QStatusBar::item { border:0; }
QToolTip { background:#282828; color:#ffffff; border:0; border-radius:4px; padding:6px; }
QDialog QLabel { color:#6a6a6a; }
QLineEdit,QTextEdit,QPlainTextEdit { background:#ffffff; color:#383838; border:1px solid #e4e4e4; border-radius:5px; padding:6px; }
'''

