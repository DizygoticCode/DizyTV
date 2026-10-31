"""Native Qt desktop client for Windows, macOS and Linux."""
from __future__ import annotations
import json
import re
import os
import sys
import time
import threading
from pathlib import Path
from zoneinfo import available_timezones

from PySide6.QtCore import Qt, QUrl, QTimer, QTimeZone, QRunnable, QThreadPool, QObject, Signal, QRectF, QEvent, QPoint, QPointF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QDesktopServices, QShortcut, QKeySequence, QCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QCheckBox, QSplitter,
    QTabWidget, QFrame, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QFormLayout, QLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QPlainTextEdit, QFileDialog, QMessageBox, QInputDialog, QMenu, QSlider, QToolButton, QSizePolicy, QAbstractItemView, QProgressBar, QProgressDialog)

from .core import (parse_playlist, parse_xmltv, format_time, stream_url, make_job,
                   check_conflicts, export_backup, restore_backup, MAX_BACKUP, validate_state, normalise_genre, catalogue, match_guide, guide_lookup, guide_suggestions, display_channel_name, channel_section, channel_kind, COUNTRIES, GENRES)
from .network import download
from .sources import (configured_playlists, refresh_catalogue, DEFAULT_GUIDE_URLS,
                      DEFAULT_PLAYLIST_URLS, OPTIONAL_FAST_PLAYLISTS, FAST_GUIDE_BY_PLAYLIST,
                      OPTIONAL_UK_RETRANSMISSIONS, OPTIONAL_SHOW_LOOP_PLAYLISTS, source_label, safe_source_label)
from .storage import Store, atomic_json
from .recorder import ensure_worker
from .engine import ensure_ready, engine_diagnostics, start_playback_session
from .timeshift import RollingTimeshift
from .stream_diagnostics import probe_stream, regional_access_notice
from .global_search import GlobalSearch
from .iptv_directory import DIRECTORY_ROWS, DIRECTORY_TYPES, DIRECTORY_URL, WORLDWIDE_URL, parse_directory, directory_search
from .subtitles import (COLOURS, POSITIONS, FONTS, vlc_subtitle_options,
                        subtitle_tracks, suggested_subtitle, external_subtitle_path)
from .auto_captions import (verify_caption_engine, LocalCaptionWorker, caption_text, PLAYBACK_USER_AGENT,
                            LANGUAGE_MODELS, installed_language_model, install_language_model, remove_language_model,
                            managed_language_model)
from .channel_browser import channel_sort_key, CHANNEL_SORT_MODES
from .caption_sync import CaptionDelayQueue
from .health_history import HealthHistory
from .duplicates import duplicate_groups, independent_candidates
from .system_usage import SystemSampler
from .ui_diagnostics import UiHangMonitor

ASSETS = Path(getattr(sys,'_MEIPASS', Path(__file__).resolve().parent.parent))/'assets'
STYLE = '''
QWidget { background:#151e19; color:#f3ead5; font-size:14px; }
QLabel#brand { font-size:27px; font-weight:800; }
QPushButton { background:#355b43; border:1px solid #54785b; padding:9px 15px; border-radius:7px; }
QPushButton:hover { background:#477552; } QPushButton:disabled { color:#8a938b; }
QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#202d24; padding:8px; border:1px solid #405246; border-radius:5px; }
QListWidget { background:#1a261e; border:0; } QListWidget::item { padding:12px; border-bottom:1px solid #2f4033; }
QListWidget::item:selected { background:#416248; }
QTabWidget::pane { border:1px solid #405246; border-radius:10px; top:0px; }
QTabBar::tab { padding:9px 16px; margin:4px 4px 5px 0; background:#25362b; border:1px solid #405246; border-radius:9px; }
QTabBar::tab:hover { background:#355b43; }
QTabBar::tab:selected { background:#416248; border:1px solid #54785b; font-weight:700; }
QLabel#filterTitle { color:#a8c5ad; }
QTableWidget { gridline-color:#354638; background:#19251d; }
QHeaderView::section { background:#2d4133; padding:8px; border:0; }
QPushButton#tvPrimary { background:#397f51; border:1px solid #64b679; color:white; font-weight:700; }
QPushButton#tvPrimary:hover { background:#4b9963; }
QPushButton#tvDanger { background:#69352f; border:1px solid #b26354; }
QPushButton#tvLive { background:#713b38; border:1px solid #cc7771; font-weight:700; color:#ffe2d4; }
/* Compact media-player rails: never paint the slider's full rectangular widget. */
QSlider#seekBar, QSlider#volumeBar { background:transparent; border:0; padding:0; margin:0; }
QSlider#seekBar::groove:horizontal, QSlider#volumeBar::groove:horizontal {
    height:4px; border:0; border-radius:2px; background:#23352c;
}
QSlider#seekBar::add-page:horizontal, QSlider#volumeBar::add-page:horizontal {
    background:#23352c; border:0; border-radius:2px;
}
QSlider#seekBar::sub-page:horizontal {
    background:#63d89b; border:0; border-radius:2px;
}
QSlider#volumeBar::sub-page:horizontal {
    background:#68bde0; border:0; border-radius:2px;
}
QSlider#seekBar::handle:horizontal, QSlider#volumeBar::handle:horizontal {
    background:#dbffeb; border:2px solid #3b9364; border-radius:7px;
    width:14px; margin:-7px 0;
}
QSlider#seekBar::handle:horizontal:hover, QSlider#volumeBar::handle:horizontal:hover {
    background:#ffffff; border-color:#63d89b;
}
QSlider#seekBar:disabled::sub-page:horizontal, QSlider#volumeBar:disabled::sub-page:horizontal {
    background:#53655b;
}
QSlider#seekBar:disabled::handle:horizontal, QSlider#volumeBar:disabled::handle:horizontal {
    background:#9ca9a1; border-color:#637267;
}
QScrollArea#toolbarScroll, QScrollArea#playerControlScroll { border:0; background:transparent; }
QWidget#playbackControlsRow { background:transparent; border:0; }
'''


THEME_COLORS = {
    'Dark': {
        '#151e19':'#17191f',
        '#f3ead5':'#f1f3f7',
        '#355b43':'#323845',
        '#54785b':'#59616f',
        '#8a938b':'#8d96a4',
        '#477552':'#424a5b',
        '#202d24':'#242932',
        '#405246':'#545d6d',
        '#1a261e':'#1d222b',
        '#2f4033':'#343c47',
        '#416248':'#485d79',
        '#25362b':'#292f3a',
        '#19251d':'#20252e',
        '#354638':'#454f5c',
        '#2d4133':'#333b49',
        '#397f51':'#385e91',
        '#64b679':'#6ea0e1',
        '#4b9963':'#497ab6',
        '#69352f':'#693c45',
        '#b26354':'#bf777e',
        '#713b38':'#8b3e3f',
        '#cc7771':'#f1a29b',
        '#ffe2d4':'#ffe9dc',
        '#355c48':'#66788e',
        '#21392e':'#2d3542',
        '#61bd7c':'#679bdc',
        '#d9f6dd':'#e4edff',
        '#72df99':'#8bb7f2',
        '#6b746d':'#747983',
        '#99a69d':'#a7afbc',
        '#62adca':'#759dbf',
        '#23352c':'#323b4a',
        '#63d89b':'#79aeff',
        '#68bde0':'#85c7f5',
        '#dbffeb':'#edf5ff',
        '#3b9364':'#5e8dce',
        '#53655b':'#687487',
        '#9ca9a1':'#abb6c5',
        '#637267':'#748299',
        '#a8c5ad':'#c1cada',
        '#15221a':'#151922',
        '#253b2b':'#283448',
        '#47654b':'#465267',
        '#95a695':'#bbc1cd',
        '#3c5c42':'#354966',
        '#283e30':'#272f3e',
        '#f4af71':'#f2b875',
        '#304d36':'#303c52',
        '#101713':'#101219',
    },
    'Light': {
        '#151e19':'#f7f9fc',
        '#f3ead5':'#1e293b',
        '#355b43':'#e3e9f2',
        '#54785b':'#a4b2c6',
        '#8a938b':'#8490a2',
        '#477552':'#d3deec',
        '#202d24':'#ffffff',
        '#405246':'#c2ccd9',
        '#1a261e':'#ffffff',
        '#2f4033':'#dee5ed',
        '#416248':'#bfd4ee',
        '#25362b':'#e9eef6',
        '#19251d':'#ffffff',
        '#354638':'#d1dbe7',
        '#2d4133':'#eff3fa',
        '#397f51':'#2d6cc0',
        '#64b679':'#1a569e',
        '#4b9963':'#3d7ed1',
        '#69352f':'#f7dce0',
        '#b26354':'#d67e8a',
        '#713b38':'#fae7e4',
        '#cc7771':'#d76767',
        '#ffe2d4':'#842a27',
        '#355c48':'#a5bfdc',
        '#21392e':'#e8f0fb',
        '#61bd7c':'#3b82d5',
        '#d9f6dd':'#e8f4ff',
        '#72df99':'#4c94e0',
        '#6b746d':'#bcc4cf',
        '#99a69d':'#919cae',
        '#62adca':'#3480a3',
        '#23352c':'#d7e2ef',
        '#63d89b':'#2a76c7',
        '#68bde0':'#3d93bf',
        '#dbffeb':'#ffffff',
        '#3b9364':'#2a76c7',
        '#53655b':'#bac4d0',
        '#9ca9a1':'#bcc8d5',
        '#637267':'#9dacbe',
        '#a8c5ad':'#51657e',
        '#15221a':'#f1f5fb',
        '#253b2b':'#dde7f4',
        '#47654b':'#ccd7e5',
        '#95a695':'#526078',
        '#3c5c42':'#d7e7fb',
        '#283e30':'#e5edf9',
        '#f4af71':'#cf6f17',
        '#304d36':'#dde9fa',
        '#101713':'#e8eef6',
    },
}


def theme_color(color, theme='Green'):
    return THEME_COLORS.get(theme, {}).get(color, color)


def overlay_theme_style(style, theme='Green'):
    """Preserve translucent overlay geometry while changing only its colours."""
    variants={
        'Dark': {
            'rgba(10,35,23,135)':'rgba(21,33,53,165)',
            'rgba(161,213,173,150)':'rgba(148,177,225,160)',
            'rgba(17,70,43,180)':'rgba(40,64,101,205)',
            'rgba(14,40,29,120)':'rgba(21,32,53,165)',
            'rgba(86,205,128,190)':'rgba(109,155,224,200)',
            'rgba(210,255,227,200)':'rgba(212,227,255,210)',
            'rgba(106,227,147,215)':'rgba(132,182,246,220)',
            '#edfff0':'#f2f5ff','#effff0':'#f2f5ff',
        },
        'Light': {
            'rgba(10,35,23,135)':'rgba(232,240,253,213)',
            'rgba(161,213,173,150)':'rgba(58,111,181,180)',
            'rgba(17,70,43,180)':'rgba(202,221,249,230)',
            'rgba(14,40,29,120)':'rgba(206,219,237,200)',
            'rgba(86,205,128,190)':'rgba(57,119,206,220)',
            'rgba(210,255,227,200)':'rgba(34,97,177,220)',
            'rgba(106,227,147,215)':'rgba(85,151,229,230)',
            '#edfff0':'#17263b','#effff0':'#17263b',
        },
    }
    for before,after in variants.get(theme,{}).items():
        style=style.replace(before,after)
    return style


def desktop_style(scale=100, button_size='Normal', theme='Green'):
    """Respect TV DPI while allowing smaller independent UI/controls."""
    scale=max(75,min(150,int(scale)))/100
    pad={'Compact':(4,8),'Normal':(9,15),'Large':(13,20)}.get(button_size,(9,15))
    style=(STYLE.replace('font-size:14px;',f'font-size:{round(14*scale)}px;')
               .replace('font-size:27px;',f'font-size:{round(27*scale)}px;')
               .replace('padding:9px 15px;',f'padding:{round(pad[0]*scale)}px {round(pad[1]*scale)}px;')
               .replace('padding:9px 16px;',f'padding:{round(8*scale)}px {round(14*scale)}px;')
               .replace('QListWidget::item { padding:12px;',f'QListWidget::item {{ padding:{round(9*scale)}px;'))
    colors=THEME_COLORS.get(theme, {})
    converted=re.sub(r'#[0-9a-fA-F]{6}\b',lambda m: colors.get(m.group(),m.group()),style) if colors else style
    return converted+'\n'+modern_desktop_style(theme)



def modern_desktop_style(theme='Green'):
    """Kodi/IPTV-style surfaces shared by desktop Windows and macOS."""
    palettes={
        'Green': ('#101712','#19251d','#26362b','#47654b','#f1f7f1','#a8c4ae','#65dca0','#327b50','#13221a'),
        'Dark': ('#121821','#1b2531','#293544','#50627a','#f1f5fb','#a8bad0','#84b4fa','#456daa','#192231'),
        'Light': ('#f4f7fb','#ffffff','#e9f0f9','#bdcad9','#23364b','#647b91','#2678cb','#225b9b','#eef3fa'),
    }
    bg,surface,raised,border,fg,muted,accent,primary,input_bg=palettes.get(theme,palettes['Green'])
    return f"""
QMainWindow, QDialog, QWidget#appShell {{ background:{bg}; }}
QWidget#appHeader, QWidget#livePage, QWidget#playbackControlsRow {{ background:transparent; border:0; }}
QWidget#appSidebar {{ background:{surface};border:1px solid {border};border-radius:12px; }}
QLabel#brand {{ color:{fg};font-size:24px;font-weight:800; }}
QLabel#channelHeading {{color:{fg};font-weight:700;font-size:16px;}}
QLabel#filterTitle, QLabel#timezoneLabel, QLabel#playbackHint, QLabel#appStatus {{
    color:{muted};font-size:12px;
}}
QPushButton {{ background:{raised};color:{fg};border:1px solid {border};
    border-radius:9px;padding:8px 13px;font-weight:600; }}
QPushButton:hover {{background:{border};border-color:{accent};}}
QPushButton:pressed {{background:{primary};color:white;}}
QPushButton:disabled {{color:{muted};border-color:{raised};}}
QPushButton#tvPrimary {{background:{primary};border-color:{primary};color:white;font-weight:700;}}
QPushButton#tvDanger {{background:{raised};border-color:{border};}}
QPushButton#globalSearch {{background:{input_bg};color:{muted};border-radius:10px;
    border:1px solid {border};text-align:left;padding:10px 14px;}}
QPushButton#globalSearch:hover {{border-color:{accent};color:{fg};}}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background:{input_bg};color:{fg};border:1px solid {border};border-radius:8px;
    padding:7px 9px;selection-background-color:{primary};
}}
QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus {{border-color:{accent};}}
QComboBox::drop-down {{border:0;width:24px;}}
QTabWidget::pane {{background:{surface};border:1px solid {border};border-radius:11px;top:0;}}
QTabBar::tab {{background:transparent;color:{muted};border:0;
    border-bottom:2px solid transparent;border-radius:0;padding:11px 16px;margin-right:4px;}}
QTabBar::tab:hover {{background:{raised};color:{fg};}}
QTabBar::tab:selected {{background:{surface};color:{accent};
    border-bottom:2px solid {accent};font-weight:700;}}
QListWidget,QTreeWidget,QTableWidget {{background:{surface};color:{fg};
    border:1px solid {border};border-radius:8px;alternate-background-color:{input_bg};}}
QListWidget::item {{padding:10px 9px;border-bottom:1px solid {raised};}}
QListWidget::item:selected,QTreeWidget::item:selected {{background:{raised};color:{accent};}}
QListWidget::item:hover,QTreeWidget::item:hover {{background:{raised};}}
QHeaderView::section {{background:{raised};color:{fg};padding:9px;border:0;border-bottom:1px solid {border};}}
QScrollArea#toolbarScroll,QScrollArea#playerControlScroll {{background:transparent;border:0;}}
QScrollArea#toolbarScroll > QWidget > QWidget,QScrollArea#playerControlScroll > QWidget > QWidget {{
    background:transparent;border:0;
}}
QScrollBar:vertical {{width:9px;background:transparent;}}
QScrollBar:horizontal {{height:9px;background:transparent;}}
QScrollBar::handle {{background:{border};border-radius:4px;min-height:25px;min-width:25px;}}
QScrollBar::handle:hover {{background:{muted};}}
QScrollBar::add-line,QScrollBar::sub-line {{width:0;height:0;border:0;}}
QScrollBar::add-page,QScrollBar::sub-page {{background:transparent;}}
QSlider#seekBar,QSlider#volumeBar {{background:transparent;border:0;padding:0;margin:0;}}
QSlider#seekBar::groove:horizontal,QSlider#volumeBar::groove:horizontal {{
    background:{raised};border:0;border-radius:2px;height:4px;}}
QSlider#seekBar::add-page:horizontal,QSlider#volumeBar::add-page:horizontal {{
    background:{raised};border:0;border-radius:2px;}}
QSlider#seekBar::sub-page:horizontal {{background:{accent};border:0;border-radius:2px;}}
QSlider#volumeBar::sub-page:horizontal {{background:#69bbd6;border:0;border-radius:2px;}}
QSlider#seekBar::handle:horizontal,QSlider#volumeBar::handle:horizontal {{
    background:{fg};border:2px solid {accent};width:14px;border-radius:7px;margin:-7px 0;}}
QSlider#seekBar:disabled::handle:horizontal {{background:{muted};border-color:{raised};}}
QWidget#playerControlsStrip {{background:transparent;border:0;}}
QToolButton#mediaScrollArrow {{color:{fg};background:{raised};border:1px solid {border};
    border-radius:8px;padding:0;font-size:21px;font-weight:700;}}
QToolButton#mediaScrollArrow:hover {{border-color:{accent};color:{accent};}}
QToolButton#mediaScrollArrow:disabled {{color:{muted};background:transparent;border-color:{raised};}}
"""



def diagnose_video_output(decoded_audio, decoded_video, displayed_pictures,
                          video_tracks=None, video_size=None):
    """Classify a playing, audible stream without treating VLC Playing as video proof.

    MediaStats counters are advisory, so these are diagnostic hints, not codec
    promises. Inspect only after playback has had time to initialise.
    """
    if decoded_audio <= 0:
        return None
    if video_tracks == 0:
        return ('Audio is playing but VLC reports no video track. '
                'This channel source may be audio-only; try another feed.')
    if displayed_pictures > 0:
        if video_size == (0, 0):
            return ('Video frames are being displayed according to VLC, but no '
                    'video output dimensions are available. Check VLC video '
                    'surface / Windows hardware acceleration.')
        return None
    if decoded_video > 0:
        return ('Audio and video are decoding, but VLC is displaying no video '
                'frames. A decoder count does not prove a usable frame or '
                'keyframe. Check damaged segments, missing keyframes, codec '
                'support and libVLC video output / hardware acceleration.')
    if video_tracks is not None and video_tracks > 0:
        return ('Audio is playing and a video track exists, but VLC is not '
                'decoding video frames. Suspect the codec, damaged source, '
                'or VLC decoder rather than the playback controls.')
    return ('Audio is playing but VLC has not reported video frames. '
            'Check source video tracks, libVLC decoding and Windows video output.')


def detected_zone():
    value = bytes(QTimeZone.systemTimeZoneId()).decode('utf-8')
    return value if value in available_timezones() else 'UTC'


class Signals(QObject):
    success = Signal(object)
    failure = Signal(str)
    progress = Signal(int,int)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__(); self.function = function; self.signals = Signals()
    def run(self):
        try:
            self.signals.success.emit(self.function())
        except Exception as exc:
            self.signals.failure.emit(str(exc))


class CaptionSignals(QObject):
    caption=Signal(int,str)
    finished=Signal(int,str)


class MediaRailSlider(QSlider):
    """Draw the actual TV timeline/volume rail ourselves, not the Windows QSlider.

    QSS groove overrides alone still allowed the platform style to paint two
    full-height grey native grooves in the 0.1.13 installer. This widget owns
    every pixel, including the background, on Windows and macOS.
    """
    BACKGROUNDS={'Green':'#101712','Dark':'#121821','Light':'#f4f7fb'}
    COLOURS={
        'Green':('#2a4434','#65dca0','#70c5dc','#f1f7f1'),
        'Dark':('#293544','#84b4fa','#78c8eb','#f1f5fb'),
        'Light':('#d7e2f0','#2678cb','#358eaf','#ffffff'),
    }

    def __init__(self,orientation=Qt.Horizontal,parent=None):
        super().__init__(orientation,parent)
        self.rail_theme='Green'
        self.setFixedHeight(25)
        self.setMinimumWidth(35)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.setAutoFillBackground(False)

    def set_rail_theme(self,theme):
        self.rail_theme=theme if theme in self.COLOURS else 'Green'
        self.update()

    def _rail_geometry(self):
        left=12.0
        length=max(1.0,float(self.width())-24.0)
        y=self.height()/2.0
        span=self.maximum()-self.minimum()
        fraction=(self.value()-self.minimum())/span if span>0 else 0.0
        return left,length,y,max(0.0,min(1.0,fraction))

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Explicitly cover the whole widget with the SAME surrounding
        # application surface, never the operating system's grey slider plate.
        painter.fillRect(self.rect(),QColor(self.BACKGROUNDS[self.rail_theme]))
        track,seek_colour,volume_colour,thumb=self.COLOURS[self.rail_theme]
        left,length,y,fraction=self._rail_geometry()
        is_volume=self.objectName()=='volumeBar'
        accent=volume_colour if is_volume else seek_colour
        if not self.isEnabled():accent=track
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(track))
        painter.drawRoundedRect(QRectF(left,y-2.0,length,4.0),2.0,2.0)
        if fraction>0:
            painter.setBrush(QColor(accent))
            painter.drawRoundedRect(QRectF(left,y-2.0,max(1.0,length*fraction),4.0),2.0,2.0)
        centre=left+length*fraction
        painter.setBrush(QColor(thumb if self.isEnabled() else '#9aabba'))
        painter.setPen(QColor(accent if self.isEnabled() else track))
        painter.drawEllipse(QPointF(centre,y),6.5,6.5)
        painter.end()

    def _set_from_mouse(self,x):
        left,length,_,_=self._rail_geometry()
        position=max(0.0,min(1.0,(float(x)-left)/length))
        self.setSliderPosition(round(self.minimum()+position*(self.maximum()-self.minimum())))

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and self.isEnabled():
            self.setFocus(Qt.MouseFocusReason)
            self.setSliderDown(True)
            self._set_from_mouse(event.position().x())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.isSliderDown() and event.buttons() & Qt.LeftButton:
            self._set_from_mouse(event.position().x())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton and self.isSliderDown():
            self._set_from_mouse(event.position().x())
            self.setSliderDown(False)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class TimeSeekSlider(MediaRailSlider):
    """Mouse wheel seeks only when directly over the video timeline."""
    seek_requested=Signal(int)
    def __init__(self,orientation=Qt.Horizontal,parent=None):
        super().__init__(orientation,parent)
        self._wheel_degrees=0
        self.setToolTip('Drag to seek or scroll over the timeline: 30 seconds per wheel notch')

    def seek_wheel_delta(self,delta):
        self._wheel_degrees+=delta
        ticks=int(self._wheel_degrees/120)
        if ticks:
            ticks=max(-4,min(4,ticks))
            self._wheel_degrees-=ticks*120
            self.seek_requested.emit(ticks*30000)

    def wheelEvent(self,event):
        if not self.isEnabled():
            event.ignore()
            return
        self.seek_wheel_delta(event.angleDelta().y() or event.angleDelta().x())
        event.accept()


class GuideGrid(QWidget):
    channel_clicked = Signal(object)
    programme_record_requested = Signal(object,object)
    channel_record_requested = Signal(object)
    def __init__(self):
        super().__init__(); self.rows=[]; self.programmes=[]; self.hitboxes=[]; self.zone='auto'; self.start=0
        self.guide_scale=100
        self.theme='Green'
        self._programmes_by_channel={}
    def set_theme(self,theme):
        if theme!=self.theme:
            self.theme=theme
            self.update()

    def geometry_units(self):
        ratio=max(55,min(130,self.guide_scale))/100.0
        return (max(25,int(58*ratio)),max(125,int(210*ratio)),
                max(86,int(180*ratio)),max(8,int(11*ratio)))
    def set_guide_scale(self,value):
        self.guide_scale=max(55,min(130,int(value)))
        self.update_dimensions()
    def update_dimensions(self):
        row,left,hour,font=self.geometry_units()
        self.setMinimumSize(left+6*hour+30,max(230,48+len(self.rows)*row+12))
        self.update()
    def set_data(self,channels,programmes,mappings,zone,start):
        # NO channel cap. The full filtered catalogue stays scrollable; only
        # the rows inside the viewport are painted at any given moment.
        self.rows=list(channels)
        self.programmes=programmes
        self.mappings=mappings
        self.zone=zone; self.start=start
        by_channel={}
        for item in programmes:
            by_channel.setdefault(item['channel'],[]).append(item)
        self._programmes_by_channel=by_channel
        self.update_dimensions()
    def visible_row_range(self,rect):
        height,_,_,_=self.geometry_units()
        first=max(0,(rect.top()-48)//height)
        last=min(len(self.rows),(rect.bottom()-48)//height+2)
        return first,max(first,last)
    def paintEvent(self,event):
        p=QPainter(self)
        visible=event.rect()
        p.setClipRect(visible)
        p.fillRect(visible,QColor(theme_color('#15221a',self.theme)))
        rowheight,left,hour,font=self.geometry_units()
        p.setFont(QFont('Sans Serif',font)); scale=hour/3600
        for i in range(7):
            x=left+i*hour
            p.setPen(QColor(theme_color('#47654b',self.theme))); p.drawLine(x,visible.top(),x,visible.bottom())
            if visible.top()<=48:
                p.setPen(QColor(theme_color('#f3ead5',self.theme))); p.drawText(x+5,30,format_time(self.start+i*3600,self.zone,False,detected_zone()))
        first,last=self.visible_row_range(visible)
        for row in range(first,last):
            ch=self.rows[row]
            y=48+row*rowheight
            p.fillRect(0,y,left,rowheight-3,QColor(theme_color('#253b2b',self.theme)))
            p.setPen(QColor(theme_color('#f3ead5',self.theme))); p.drawText(QRectF(12,y+4,left-20,rowheight-8),Qt.AlignVCenter|Qt.TextWordWrap,display_channel_name(ch['name']))
            key=self.mappings.get(ch['id'],ch['tvg_id'])
            entries=self._programmes_by_channel.get(key,[])
            if not entries:
                p.setPen(QColor(theme_color('#95a695',self.theme))); p.drawText(left+15,y+33,'No guide match — choose Map EPG for this channel')
            for item in entries:
                x=left+max(0,item['start']-self.start)*scale
                width=(min(item['end'],self.start+6*3600)-max(item['start'],self.start))*scale
                rect=QRectF(x+2,y+2,max(0,width-4),rowheight-6)
                fill='#3c5c42' if item['start']<=time.time()<item['end'] else '#283e30'
                p.fillRect(rect,QColor(theme_color(fill,self.theme)))
                p.setPen(QColor(theme_color('#f3ead5',self.theme))); p.drawText(rect.adjusted(8,2,-8,-2),Qt.AlignVCenter|Qt.TextWordWrap,item['title'])

        x=left+(time.time()-self.start)*scale
        if left<=x<=left+6*hour:
            p.setPen(QColor(theme_color('#f4af71',self.theme))); p.drawLine(int(x),40,int(x),self.height())
    def programme_at(self,point,row=None):
        """Determine the programme from its data, not partial paint rectangles.

        Qt repaints narrow dirty rectangles while scrolling; caching hitboxes
        only from paintEvent causes invisible context-menu regressions.
        """
        rowheight,left,hour,_=self.geometry_units()
        if row is None:row=int((point.y()-48)//rowheight)
        if not 0<=row<len(self.rows) or point.x()<left:return None
        channel=self.rows[row]
        key=self.mappings.get(channel['id'],channel['tvg_id'])
        scale=hour/3600
        for item in self._programmes_by_channel.get(key,()):
            span_start=max(item['start'],self.start)
            span_end=min(item['end'],self.start+6*3600)
            if span_end<=span_start:continue
            x=left+(span_start-self.start)*scale
            width=(span_end-span_start)*scale
            rect=QRectF(x+2,48+row*rowheight+2,max(0,width-4),rowheight-6)
            if rect.contains(point):return item
        return None

    def mousePressEvent(self,event):
        # Row identity does not depend on whether this channel has XMLTV data.
        rowheight,_,_,_=self.geometry_units()
        row=int((event.position().y()-48)//rowheight)
        if not (0<=row<len(self.rows)):
            return super().mousePressEvent(event)
        channel=self.rows[row]
        if event.button()==Qt.LeftButton:
            self.channel_clicked.emit(channel)
            event.accept()
            return
        if event.button()==Qt.RightButton:
            # Offer recording only through an explicit menu, never by default click.
            programme=self.programme_at(event.position(),row)
            menu=QMenu(self)
            watch=menu.addAction('▶ Watch channel')
            watch.triggered.connect(lambda checked=False,ch=channel:self.channel_clicked.emit(ch))
            if programme is not None:
                record=menu.addAction('● Record programme…')
                record.triggered.connect(lambda checked=False,ch=channel,p=programme:self.programme_record_requested.emit(ch,p))
            else:
                record=menu.addAction('● Record now…')
                record.triggered.connect(lambda checked=False,ch=channel:self.channel_record_requested.emit(ch))
            # Popup is non-modal: don't stall the EPG event loop while it is open.
            self.context_menu=menu
            menu.popup(event.globalPosition().toPoint())
            event.accept()
            return
        return super().mousePressEvent(event)


class IPTVDirectoryDialog(QDialog):
    """Entire official IPTV-org playlist index, not 1,000 simultaneous downloads."""

    def __init__(self,existing_urls,parent=None):
        super().__init__(parent)
        self.setWindowTitle('IPTV-org public playlist directory')
        self.resize(820,610)
        self.rows=list(DIRECTORY_ROWS)
        self.existing=set(existing_urls)
        self.added_urls=[]
        self.refresh_task=None
        root=QVBoxLayout(self)
        note=QLabel('Browse the complete IPTV-org directory: countries, cities, regions, '
                    'languages and categories. Pick feeds to import; the worldwide index '
                    'covers the complete channel collection with one playlist. '
                    'No new streams are downloaded until you save Settings and refresh channels.',self)
        note.setWordWrap(True);root.addWidget(note)
        top=QHBoxLayout()
        self.kind_filter=QComboBox(self)
        self.kind_filter.setObjectName('iptvDirectoryType')
        self.kind_filter.addItems(DIRECTORY_TYPES)
        self.kind_filter.currentTextChanged.connect(self.populate)
        top.addWidget(self.kind_filter)
        self.query=QLineEdit(self)
        self.query.setObjectName('iptvDirectorySearch')
        self.query.setPlaceholderText('Search country, region, city, language, genre or URL…')
        self.query.textChanged.connect(self.populate)
        top.addWidget(self.query,1)
        root.addLayout(top)
        self.results=QListWidget(self)
        self.results.setObjectName('iptvDirectoryResults')
        self.results.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.results.itemDoubleClicked.connect(lambda _:self.add_selected())
        root.addWidget(self.results,1)
        self.status_label=QLabel('',self)
        self.status_label.setObjectName('iptvDirectoryStatus')
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        buttons=QHBoxLayout()
        add=QPushButton('Add selected playlists',self)
        add.setObjectName('iptvDirectoryAdd')
        add.clicked.connect(self.add_selected)
        buttons.addWidget(add)
        worldwide=QPushButton('Add worldwide index',self)
        worldwide.setObjectName('iptvDirectoryWorldwide')
        worldwide.setToolTip('One playlist containing all channels; no mass per-country downloads')
        worldwide.clicked.connect(self.add_worldwide)
        buttons.addWidget(worldwide)
        refresh=QPushButton('Refresh source directory',self)
        refresh.setObjectName('iptvDirectoryRefresh')
        refresh.clicked.connect(self.refresh_online)
        buttons.addWidget(refresh)
        cancel=QPushButton('Cancel',self)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        root.addLayout(buttons)
        self.populate()

    def populate(self,*_):
        visible=directory_search(self.rows,self.kind_filter.currentText(),self.query.text())
        self.results.clear()
        for kind,name,url,country in visible:
            label=name+((' · '+country) if country else '')+'  —  '+kind
            if url in self.existing:label+='  (already added)'
            item=QListWidgetItem(label)
            item.setData(Qt.UserRole,url)
            item.setToolTip(url)
            self.results.addItem(item)
        self.status_label.setText(f'{len(visible):,} matching sources of {len(self.rows):,} published playlists '
                                  '· select one or several; up to 32 active playlists in Settings')

    def add_selected(self):
        urls=[item.data(Qt.UserRole) for item in self.results.selectedItems()]
        if not urls:
            self.status_label.setText('Select at least one playlist, or choose the worldwide index.')
            return
        combined=list(dict.fromkeys([*self.existing,*urls]))
        if len(combined)>32:
            self.status_label.setText(f'Cannot activate {len(combined)} feeds at once (24 maximum). '
                                      'Select fewer, or use the single worldwide index.')
            return
        self.added_urls=[url for url in urls if url not in self.existing]
        self.accept()

    def add_worldwide(self):
        if WORLDWIDE_URL not in self.existing and len(self.existing)>=24:
            self.status_label.setText('Remove an active feed in Settings before adding the worldwide index.')
            return
        self.added_urls=[WORLDWIDE_URL] if WORLDWIDE_URL not in self.existing else []
        self.accept()

    def refresh_online(self):
        if self.refresh_task is not None:return
        self.status_label.setText('Refreshing directory from IPTV-org …')
        task=Task(lambda:parse_directory(download(DIRECTORY_URL)))
        self.refresh_task=task
        def done(rows):
            self.refresh_task=None
            self.rows=rows
            self.populate()
            self.status_label.setText(f'{len(rows):,} published sources loaded directly from IPTV-org.')
        def failed(error):
            self.refresh_task=None
            self.status_label.setText('Online refresh unavailable ('+error+
                                      '). Bundled directory retained.')
        task.signals.success.connect(done)
        task.signals.failure.connect(failed)
        QThreadPool.globalInstance().start(task)


class Settings(QDialog):
    def __init__(self,state,parent):
        super().__init__(parent); self.setWindowTitle('DizyTV settings'); self.resize(690,640)
        self.original=state['settings'].copy()
        root=QVBoxLayout(self)
        page=QWidget(self); form=QFormLayout(page)
        scroll=QScrollArea(self);scroll.setWidgetResizable(True);scroll.setWidget(page)
        root.addWidget(scroll,1)
        self.playlists=QPlainTextEdit('\n'.join(configured_playlists(self.original)))
        self.playlists.setPlaceholderText('One M3U playlist URL per line; remove a line to disable that source')
        self.playlists.setMaximumHeight(125); form.addRow('Channel playlists',self.playlists)
        add_presets=QPushButton('Add built-in free playlists (keep existing URLs)')
        add_presets.clicked.connect(self.add_free_playlists)
        form.addRow(add_presets)
        add_uk_fast=QPushButton('Add UK FAST playlists + matching guides (Plex / Samsung / Pluto)',self)
        add_uk_fast.setObjectName('addUKFastPlaylists')
        add_uk_fast.setToolTip('Add the three UK FAST M3U sources and their matching XMLTV feeds without deleting your existing sources.')
        add_uk_fast.clicked.connect(self.add_uk_fast_playlists)
        form.addRow(add_uk_fast)
        add_shows=QPushButton('Add 24/7 show / sitcom channels (US FAST sources)',self)
        add_shows.setToolTip('Opt-in public Pluto/Plex/Samsung US feeds; find their series channels under 24/7 Shows & Loops.')
        add_shows.clicked.connect(self.add_show_loop_playlists)
        form.addRow(add_shows)
        add_us=QPushButton('Add optional US FAST channels (Roku and Tubi)',self)
        add_us.setToolTip('US-origin FAST listings may be unavailable outside supported regions; use only where permitted.')
        add_us.clicked.connect(self.add_optional_fast_playlists)
        form.addRow(add_us)
        uk_candidates=QPushButton('Add UK retransmission / +1 candidates (unverified)',self)
        uk_candidates.setToolTip('Optional independent UK sources including E4 and STV+1 candidates. Availability and access vary.')
        uk_candidates.clicked.connect(self.add_uk_retransmissions)
        form.addRow(uk_candidates)
        discover=QPushButton('Browse every IPTV-org country, category and language…',self)
        discover.setObjectName('browseIPTVDirectory')
        discover.clicked.connect(self.browse_iptv_directory)
        form.addRow(discover)
        self.engine=QLineEdit(self.original['engine_url']); form.addRow('Ace engine address',self.engine)
        self.engine_path=QLineEdit(self.original.get('engine_executable',''))
        self.engine_path.setReadOnly(True)
        self.engine_path.setPlaceholderText(
            'Choose start-engine or auto-detect /opt/acestream/start-engine'
            if sys.platform.startswith('linux') else 'Auto-detect from Windows registry / AppData')
        exe_button=QPushButton('Choose Linux engine script' if sys.platform.startswith('linux') else 'Choose installed EXE')
        exe_button.clicked.connect(self.pick_engine_path)
        exe_row=QWidget(); exe_layout=QHBoxLayout(exe_row)
        exe_layout.setContentsMargins(0,0,0,0)
        exe_layout.addWidget(self.engine_path,1); exe_layout.addWidget(exe_button)
        form.addRow('Installed Ace engine',exe_row)
        self.ui_scale=QSpinBox()
        self.ui_scale.setRange(75,150);self.ui_scale.setSingleStep(5)
        self.ui_scale.setSuffix(' %');self.ui_scale.setValue(self.original.get('ui_scale',100))
        form.addRow('Interface scale',self.ui_scale)
        self.button_size=QComboBox()
        for size in ('Compact','Normal','Large'):self.button_size.addItem(size)
        self.button_size.setCurrentText(self.original.get('button_size','Normal'))
        form.addRow('Button size',self.button_size)
        self.theme=QComboBox()
        self.theme.addItems(['Green','Dark','Light'])
        self.theme.setCurrentText(self.original.get('theme','Green'))
        form.addRow('Appearance theme',self.theme)
        self.vlc_decoder=QComboBox()
        self.vlc_decoder.addItems(['Auto','Software'])
        self.vlc_decoder.setCurrentText(self.original.get('vlc_decoder','Auto'))
        self.vlc_decoder.setToolTip('If audio plays but video stays black, try Software. Restart DizyTV after changing this setting.')
        form.addRow('VLC video decoding',self.vlc_decoder)
        self.http_buffer=QSpinBox()
        self.http_buffer.setRange(1000,12000)
        self.http_buffer.setSingleStep(1000)
        self.http_buffer.setSuffix(' ms')
        self.http_buffer.setValue(self.original.get('http_buffer_ms',4000))
        self.http_buffer.setToolTip('Direct HTTP/HLS only. More buffering can reduce stalls but increases live delay. Ace Stream engine playback is unaffected.')
        form.addRow('HTTP/HLS network buffer',self.http_buffer)
        self.guide_scale=QSpinBox()
        self.guide_scale.setRange(55,130);self.guide_scale.setSingleStep(5)
        self.guide_scale.setSuffix(' %');self.guide_scale.setValue(self.original.get('guide_scale',100))
        form.addRow('TV guide density / size',self.guide_scale)
        self.cc_enabled=QCheckBox('Use broadcast subtitles when available')
        self.cc_enabled.setObjectName('subtitleEnabled')
        self.cc_enabled.setChecked(self.original.get('subtitles_enabled',True))
        form.addRow('Subtitles / closed captions',self.cc_enabled)
        self.cc_language=QComboBox()
        self.cc_language.addItems(['Auto','English'])
        self.cc_language.setCurrentText(self.original.get('subtitle_language','Auto'))
        form.addRow('Preferred caption language',self.cc_language)
        self.cc_font=QComboBox()
        self.cc_font.addItems(FONTS)
        self.cc_font.setCurrentText(self.original.get('subtitle_font','Sans'))
        form.addRow('Subtitle text font',self.cc_font)
        self.cc_size=QSpinBox()
        self.cc_size.setObjectName('subtitleSize')
        self.cc_size.setRange(12,64)
        self.cc_size.setSuffix(' px')
        self.cc_size.setValue(self.original.get('subtitle_size',20))
        form.addRow('Subtitle text size',self.cc_size)
        self.cc_colour=QComboBox()
        self.cc_colour.setObjectName('subtitleColour')
        self.cc_colour.addItems(list(COLOURS))
        self.cc_colour.setCurrentText(self.original.get('subtitle_colour','White'))
        form.addRow('Subtitle text colour',self.cc_colour)
        self.cc_position=QComboBox()
        self.cc_position.setObjectName('subtitlePosition')
        self.cc_position.addItems(list(POSITIONS))
        self.cc_position.setCurrentText(self.original.get('subtitle_position','Bottom'))
        form.addRow('Subtitle screen position',self.cc_position)
        hint=QLabel('Text size, font, colour and vertical position apply to newly opened VLC playback. '
                    'Picture-based broadcast captions may ignore these settings. '
                    'Automatic speech-generated subtitles require a separate opt-in recognition engine.')
        hint.setWordWrap(True);form.addRow(hint)
        self.caption_language=QComboBox()
        self.caption_language.setObjectName('captionLanguage')
        self.caption_language.addItems(list(LANGUAGE_MODELS))
        self.caption_language.setCurrentText(self.original.get('auto_caption_language','English (bundled)'))
        form.addRow('Speech transcription language',self.caption_language)
        self.caption_delay=QSpinBox()
        self.caption_delay.setObjectName('autoCaptionDelayMs')
        self.caption_delay.setRange(0,10000)
        self.caption_delay.setSingleStep(250)
        self.caption_delay.setSuffix(' ms')
        self.caption_delay.setValue(self.original.get('auto_caption_delay_ms',0))
        self.caption_delay.setToolTip('0 = show Vosk text as soon as recognised. Positive values delay it to match slower video playback.')
        form.addRow('Vosk subtitle delay',self.caption_delay)
        self.caption_video_delay=QSpinBox()
        self.caption_video_delay.setObjectName('autoCaptionVideoDelayMs')
        self.caption_video_delay.setRange(0,30000)
        self.caption_video_delay.setSingleStep(1000)
        self.caption_video_delay.setSuffix(' ms')
        self.caption_video_delay.setValue(self.original.get('auto_caption_video_delay_ms',0))
        self.caption_video_delay.setToolTip('Delay live VIDEO and AUDIO together via the optional local rolling timeshift buffer.')
        form.addRow('Video delay for Vosk',self.caption_video_delay)
        video_note=QLabel('When recognition appears late, delay the VIDEO and AUDIO together; '
                          'requires “Keep a temporary on-device rolling buffer” below. '
                          'Changes made here take effect on the next channel start; '
                          'for live adjustments use the CC menu. Not supported by all streams.')
        video_note.setWordWrap(True)
        form.addRow(video_note)
        delay_note=QLabel('For captions appearing BEFORE the spoken words, increase the delay. '
                          'For captions appearing AFTER the words, reduce toward 0 ms. '
                          'Vosk cannot show text before recognising the audio; automatic sync '
                          'across separate IPTV stream connections is not reliable.')
        delay_note.setWordWrap(True)
        form.addRow(delay_note)
        preset=QPushButton('Apply recommended Vosk + IPTV buffer settings')
        preset.setObjectName('applyRecommendedVoskBuffer')
        preset.setToolTip('Opt in to a temporary on-device DVR buffer, 5-second video/audio holdback and 20 px captions. Save to keep; all values remain editable.')
        preset.clicked.connect(self.apply_recommended_vosk_settings)
        form.addRow('Recommended profile',preset)
        preset_note=QLabel('Suggested starting point: 20 px subtitle text, 0 ms additional Vosk text delay '
                           'and 5000 ms video/audio delay. This enables the optional rolling on-device '
                           'timeshift buffer (which uses disk space). Your changes are only saved when '
                           'you click Save. Vosk transcription still starts only when requested. '
                           'Not all streams support buffered playback.')
        preset_note.setWordWrap(True)
        form.addRow(preset_note)
        model_actions=QWidget()
        model_actions_layout=QHBoxLayout(model_actions)
        model_actions_layout.setContentsMargins(0,0,0,0)
        self.model_download=QPushButton('Download selected language model')
        self.model_download.clicked.connect(self.download_caption_language)
        self.model_cancel=QPushButton('Cancel download')
        self.model_cancel.setEnabled(False)
        self.model_cancel.clicked.connect(self.cancel_caption_download)
        self.model_remove=QPushButton('Remove downloaded model')
        self.model_remove.clicked.connect(self.remove_caption_language)
        self.model_state=QLabel('')
        self.model_state.setWordWrap(True)
        model_actions_layout.addWidget(self.model_download)
        model_actions_layout.addWidget(self.model_cancel)
        model_actions_layout.addWidget(self.model_remove)
        form.addRow('Optional Vosk languages',model_actions)
        form.addRow('Language model status',self.model_state)
        self.model_progress=QProgressBar()
        self.model_progress.setVisible(False)
        self.model_progress.setRange(0,100)
        form.addRow('Language download progress',self.model_progress)
        self.caption_language.currentTextChanged.connect(self.refresh_caption_language)
        self.refresh_caption_language()
        self.auto_model_path=QLineEdit(self.original.get('auto_caption_model_dir',''))
        self.auto_model_path.setObjectName('autoCaptionModelPath')
        self.auto_model_path.setReadOnly(True)
        self.auto_model_path.setPlaceholderText('Bundled English Vosk model by default (optional override)')
        model_btn=QPushButton('Browse…')
        model_btn.clicked.connect(self.choose_auto_caption_model)
        model_row=QWidget(); model_layout=QHBoxLayout(model_row)
        model_layout.setContentsMargins(0,0,0,0)
        model_layout.addWidget(self.auto_model_path,1)
        model_layout.addWidget(model_btn)
        form.addRow('Offline auto-caption model',model_row)
        self.auto_model_path.textChanged.connect(self.refresh_caption_language)
        self.refresh_caption_language()
        self.auto_ffmpeg_path=QLineEdit(self.original.get('auto_caption_ffmpeg_path',''))
        self.auto_ffmpeg_path.setObjectName('autoCaptionFFmpegPath')
        self.auto_ffmpeg_path.setReadOnly(True)
        self.auto_ffmpeg_path.setPlaceholderText('Bundled FFmpeg by default (optional override)')
        ffmpeg_btn=QPushButton('Browse…')
        ffmpeg_btn.clicked.connect(self.choose_auto_caption_ffmpeg)
        ffmpeg_row=QWidget();ffmpeg_layout=QHBoxLayout(ffmpeg_row)
        ffmpeg_layout.setContentsMargins(0,0,0,0)
        ffmpeg_layout.addWidget(self.auto_ffmpeg_path,1)
        ffmpeg_layout.addWidget(ffmpeg_btn)
        form.addRow('FFmpeg for local speech captions',ffmpeg_row)
        generated=QLabel('Windows includes FFmpeg, Vosk runtime/DLLs and the English speech model. '
                         'Use CC → Generate live subtitles, including for streams without built-in captions. '
                         'Other languages are optional downloads. Uses local CPU/RAM and a second stream connection; '
                         'off by default, no cloud speech service or microphone.')
        generated.setWordWrap(True);form.addRow(generated)
        self.feeds=QPlainTextEdit('\n'.join(self.original['xmltv_urls'])); self.feeds.setPlaceholderText('One XMLTV URL per line'); self.feeds.setMaximumHeight(95); form.addRow('XMLTV sources',self.feeds)
        fast_epg=QPushButton('Add matching UK FAST programme guides')
        fast_epg.setToolTip('Add only the Plex/Samsung/Pluto UK XMLTV sources for playlists currently selected above.')
        fast_epg.clicked.connect(self.add_uk_fast_guides)
        form.addRow(fast_epg)
        self.zone=QComboBox(); self.zone.addItem('Automatic — '+detected_zone(),'auto')
        for z in sorted(available_timezones()): self.zone.addItem(z,z)
        self.zone.setCurrentIndex(max(0,self.zone.findData(self.original['timezone']))); form.addRow('Timezone',self.zone)
        self.offset=QSpinBox(); self.offset.setRange(-1440,1440); self.offset.setSuffix(' minutes'); self.offset.setValue(self.original['epg_offset_minutes']); form.addRow('EPG time correction',self.offset)
        self.before=QSpinBox(); self.after=QSpinBox()
        for w,k in ((self.before,'padding_before'),(self.after,'padding_after')): w.setRange(0,240); w.setValue(self.original[k]); w.setSuffix(' minutes')
        form.addRow('Record before programme',self.before); form.addRow('Record after programme',self.after)
        row=QWidget(); layout=QHBoxLayout(row); layout.setContentsMargins(0,0,0,0)
        self.folder=QLineEdit(self.original['recording_dir']); self.folder.setReadOnly(True); pick=QPushButton('Choose folder'); pick.clicked.connect(self.pick_folder)
        layout.addWidget(self.folder); layout.addWidget(pick); form.addRow('Local recording folder',row)
        self.reserve=QDoubleSpinBox(); self.reserve.setRange(0,10000); self.reserve.setValue(self.original['reserve_bytes']/1024**3); self.reserve.setSuffix(' GiB'); form.addRow('Keep free space',self.reserve)
        self.timeshift_enabled=QCheckBox('Keep a temporary on-device rolling buffer while watching')
        self.timeshift_enabled.setChecked(self.original.get('timeshift_enabled',False))
        form.addRow('Live pause / rewind (opt-in)',self.timeshift_enabled)
        self.timeshift_minutes=QSpinBox()
        self.timeshift_minutes.setRange(1,240)
        self.timeshift_minutes.setValue(self.original.get('timeshift_minutes',30))
        self.timeshift_minutes.setSuffix(' minutes (max 240)')
        form.addRow('Rolling buffer duration',self.timeshift_minutes)
        self.timeshift_limit=QDoubleSpinBox()
        self.timeshift_limit.setRange(.25,32)
        self.timeshift_limit.setDecimals(2)
        self.timeshift_limit.setSingleStep(.25)
        self.timeshift_limit.setValue(self.original.get('timeshift_max_bytes',4*1024**3)/1024**3)
        self.timeshift_limit.setSuffix(' GiB')
        form.addRow('Rolling buffer storage cap',self.timeshift_limit)
        ts_row=QWidget(); ts_layout=QHBoxLayout(ts_row);ts_layout.setContentsMargins(0,0,0,0)
        self.timeshift_folder=QLineEdit(self.original.get('timeshift_dir',''))
        self.timeshift_folder.setReadOnly(True)
        self.timeshift_folder.setPlaceholderText('App data folder on this device')
        ts_button=QPushButton('Choose folder')
        ts_button.clicked.connect(self.pick_timeshift_folder)
        ts_layout.addWidget(self.timeshift_folder);ts_layout.addWidget(ts_button)
        form.addRow('Temporary buffer location',ts_row)
        warning=QLabel('Timeshift requires available disk space and clear MPEG-TS or TS/HLS video. This is NOT a saved recording. The oldest data is automatically discarded; the buffer is deleted when playback stops. Encrypted/fMP4 streams fall back to live playback.')
        warning.setWordWrap(True)
        form.addRow(warning)
        note=QLabel('Timers use UTC and do not move when timezone or guide correction changes.\nDesktop recording requires an awake computer. VLC 3 and the Ace engine must be installed separately.\nLinux uses an installed native Ace start-engine script and system libVLC. Mac playback can connect to a reachable engine.'); note.setWordWrap(True); form.addRow(note)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def apply_recommended_vosk_settings(self):
        """Explicit, editable Vosk synchronisation preset; no writes until Save."""
        self.cc_size.setValue(20)
        self.caption_delay.setValue(0)
        self.caption_video_delay.setValue(5000)
        # The 5s video delay requires a device-local rolling DVR; this is
        # opt-in only via the labelled button, never silently on upgrade.
        self.timeshift_enabled.setChecked(True)

    def add_free_playlists(self):
        existing=[u.strip() for u in self.playlists.toPlainText().splitlines() if u.strip()]
        combined=list(dict.fromkeys(existing+DEFAULT_PLAYLIST_URLS))
        if len(combined)>32:
            QMessageBox.warning(self,'DizyTV','The app allows up to 32 active playlists. '
                                'Remove unused sources first to make room for the UK FAST feeds.')
            return
        self.playlists.setPlainText('\n'.join(combined))
        self.add_uk_fast_guides(silent=True)

    def add_uk_fast_playlists(self):
        """Install matching FAST M3U/XMLTV pairs together, without partial edits."""
        existing=[u.strip() for u in self.playlists.toPlainText().splitlines() if u.strip()]
        guides=[u.strip() for u in self.feeds.toPlainText().splitlines() if u.strip()]
        combined=list(dict.fromkeys([*existing,*FAST_GUIDE_BY_PLAYLIST.keys()]))
        matching=list(dict.fromkeys([*guides,*FAST_GUIDE_BY_PLAYLIST.values()]))
        if len(combined)>32 or len(matching)>20:
            QMessageBox.warning(self,'DizyTV',
                'No playlists or guides were changed. You need room for three UK FAST '
                'M3U/XMLTV pairs (32 playlist / 20 guide limit). Remove unused entries '
                'from the corresponding lists first.')
            return
        self.playlists.setPlainText('\n'.join(combined))
        self.feeds.setPlainText('\n'.join(matching))

    def add_uk_fast_guides(self,silent=False):
        active={u.strip() for u in self.playlists.toPlainText().splitlines() if u.strip()}
        matched=[url for playlist,url in FAST_GUIDE_BY_PLAYLIST.items() if playlist in active]
        if not matched:
            if not silent:QMessageBox.information(self,'DizyTV','No matching UK FAST M3U sources selected. Click Add UK FAST playlists + matching guides above, then Save.')
            return
        existing=[u.strip() for u in self.feeds.toPlainText().splitlines() if u.strip()]
        combined=list(dict.fromkeys([*existing,*matched]))
        if len(combined)>20:
            QMessageBox.warning(self,'DizyTV','You already have 20 XMLTV guide URLs. '
                                'Remove unused guide sources to add the matching UK FAST guides.')
            return
        self.feeds.setPlainText('\n'.join(combined))

    def add_show_loop_playlists(self):
        existing=[u.strip() for u in self.playlists.toPlainText().splitlines() if u.strip()]
        combined=list(dict.fromkeys(existing+[url for _,url,_ in OPTIONAL_SHOW_LOOP_PLAYLISTS]))
        if len(combined)>32:
            QMessageBox.warning(self,'DizyTV','The app allows up to 32 active playlist sources. Remove unused ones first.')
            return
        self.playlists.setPlainText('\n'.join(combined))

    def add_uk_retransmissions(self):
        existing=[u.strip() for u in self.playlists.toPlainText().splitlines() if u.strip()]
        combined=list(dict.fromkeys(existing+[url for _,url,_ in OPTIONAL_UK_RETRANSMISSIONS]))
        if len(combined)>32:
            QMessageBox.warning(self,'DizyTV','At most 32 playlist URLs are supported. '
                                'Remove unused sources before adding UK retransmissions.')
            return
        self.playlists.setPlainText('\n'.join(combined))

    def add_optional_fast_playlists(self):
        existing=[u.strip() for u in self.playlists.toPlainText().splitlines() if u.strip()]
        combined=list(dict.fromkeys(existing + [url for _,url,_ in OPTIONAL_FAST_PLAYLISTS]))
        if len(combined)>32:
            QMessageBox.warning(self,'DizyTV','The app allows up to 32 active playlist URLs. '
                                'Remove duplicate/unused sources before adding the optional US FAST feeds.')
            return
        self.playlists.setPlainText('\n'.join(combined))

    def browse_iptv_directory(self):
        active=list(dict.fromkeys(u.strip() for u in self.playlists.toPlainText().splitlines()
                                  if u.strip()))
        dialog=IPTVDirectoryDialog(active,self)
        if dialog.exec()==QDialog.Accepted and dialog.added_urls:
            self.playlists.setPlainText('\n'.join(dict.fromkeys([*active,*dialog.added_urls])))

    def refresh_caption_language(self,*_):
        language=self.caption_language.currentText()
        installed=installed_language_model(language)
        busy=getattr(self,'download_task',None) is not None
        selected=(self.auto_model_path.text() if hasattr(self,'auto_model_path')
                  else self.original.get('auto_caption_model_dir',''))
        managed=managed_language_model(language, protected_path=selected)
        self.caption_language.setEnabled(not busy)
        self.model_download.setEnabled(not busy and installed is None)
        self.model_cancel.setEnabled(busy and
                                     getattr(self,'model_cancel_event',None) is not None and
                                     not self.model_cancel_event.is_set())
        self.model_remove.setEnabled(not busy and managed is not None)
        if busy:
            return
        if managed is not None:
            self.model_state.setText('Installed • '+language+' (DizyTV-managed download).')
        elif installed is not None:
            self.model_state.setText('Installed • '+language+
                                     ' (not eligible for removal: custom/external or bundled model).')
        else:
            self.model_state.setText('Not installed • select Download to add '+language+
                                     ' in DizyTV Settings. No speech data is sent to a cloud service.')

    def update_caption_model_progress(self,received,total):
        if total>0:
            self.model_progress.setRange(0,100)
            self.model_progress.setValue(min(100,round(received*100/total)))
            self.model_state.setText('Downloading '+self.caption_language.currentText()+
                                     ' • '+str(round(received/1048576,1))+' / '+
                                     str(round(total/1048576,1))+' MiB')
        else:
            self.model_progress.setRange(0,0)
            self.model_state.setText('Downloading '+self.caption_language.currentText()+
                                     ' • '+str(round(received/1048576,1))+' MiB')

    def cancel_caption_download(self):
        event=getattr(self,'model_cancel_event',None)
        if event is not None:
            event.set()
            self.model_cancel.setEnabled(False)
            self.model_state.setText('Cancelling language download…')

    def remove_caption_language(self):
        language=self.caption_language.currentText()
        if getattr(self,'download_task',None) is not None or language=='English (bundled)':
            return
        if QMessageBox.question(self,'Remove speech model',
                'Delete the downloaded '+language+' model from this device? '
                'Other downloaded languages and external model folders will not be touched.') != QMessageBox.Yes:
            return
        try:
            removed=remove_language_model(language, protected_path=self.auto_model_path.text())
        except (OSError,ValueError) as exc:
            self.model_state.setText('Could not remove model: '+str(exc)[:140])
            return
        self.refresh_caption_language()
        if removed:self.model_state.setText(language+' model removed. You can download it again.')

    def download_caption_language(self):
        language=self.caption_language.currentText()
        if getattr(self,'download_task',None) is not None:return
        cancel=threading.Event()
        self.model_cancel_event=cancel
        task=Task(lambda:install_language_model(
            language,progress=lambda received,total:task.signals.progress.emit(received,total),
            cancel=cancel))
        self.download_task=task
        self.model_progress.setVisible(True)
        self.model_progress.setRange(0,0)
        self.model_state.setText('Downloading '+language+' directly from official Vosk…')
        self.refresh_caption_language()
        def complete():
            self.download_task=None
            self.model_cancel_event=None
            self.model_progress.setVisible(False)
            self.refresh_caption_language()
        def done(path):
            complete()
        def failed(message):
            complete()
            self.model_state.setText(('Cancelled: ' if cancel.is_set() else 'Download failed: ')+message[:140])
        task.signals.progress.connect(self.update_caption_model_progress)
        task.signals.success.connect(done)
        task.signals.failure.connect(failed)
        QThreadPool.globalInstance().start(task)

    def choose_auto_caption_model(self):
        folder=QFileDialog.getExistingDirectory(
            self,'Select extracted offline Vosk speech model',self.auto_model_path.text())
        if folder:self.auto_model_path.setText(folder)

    def choose_auto_caption_ffmpeg(self):
        executable,_=QFileDialog.getOpenFileName(
            self,'Select installed FFmpeg',self.auto_ffmpeg_path.text(),'FFmpeg (ffmpeg ffmpeg.exe)')
        if executable:self.auto_ffmpeg_path.setText(executable)

    def pick_engine_path(self):
        if sys.platform.startswith('linux'):
            selected=self.engine_path.text() or '/opt/acestream/'
            options='Ace Stream Linux launcher (start-engine);;All files (*)'
        else:
            selected=self.engine_path.text() or os.environ.get('APPDATA','')
            options='Ace Stream engine (ace_engine.exe ace_console.exe)'
        path,_=QFileDialog.getOpenFileName(self,'Locate an installed Ace Stream engine',
                                            selected,options)
        if path:self.engine_path.setText(path)

    def pick_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Recording destination',self.folder.text())
        if folder:self.folder.setText(folder)
    def pick_timeshift_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Temporary timeshift folder',self.timeshift_folder.text())
        if folder:self.timeshift_folder.setText(folder)
    def values(self):
        urls=list(dict.fromkeys(u.strip() for u in self.playlists.toPlainText().splitlines() if u.strip()))
        if not urls:raise ValueError('Add at least one channel playlist URL')
        return dict(self.original,playlist_url=urls[0],playlist_urls=urls,engine_url=self.engine.text().strip(),
                    xmltv_urls=[u.strip() for u in self.feeds.toPlainText().splitlines() if u.strip()],timezone=self.zone.currentData(),
                    epg_offset_minutes=self.offset.value(),padding_before=self.before.value(),padding_after=self.after.value(),
                    reserve_bytes=int(self.reserve.value()*1024**3),recording_dir=self.folder.text(),
                    timeshift_enabled=self.timeshift_enabled.isChecked(),
                    timeshift_minutes=self.timeshift_minutes.value(),
                    timeshift_max_bytes=int(self.timeshift_limit.value()*1024**3),
                    timeshift_dir=self.timeshift_folder.text(),
                    ui_scale=self.ui_scale.value(),button_size=self.button_size.currentText(),
                    theme=self.theme.currentText(),vlc_decoder=self.vlc_decoder.currentText(),http_buffer_ms=self.http_buffer.value(),
                    subtitles_enabled=self.cc_enabled.isChecked(),subtitle_language=self.cc_language.currentText(),
                    subtitle_font=self.cc_font.currentText(),subtitle_size=self.cc_size.value(),
                    subtitle_colour=self.cc_colour.currentText(),subtitle_position=self.cc_position.currentText(),
                    auto_caption_model_dir=self.auto_model_path.text(),
                    auto_caption_ffmpeg_path=self.auto_ffmpeg_path.text(),
                    auto_caption_language=self.caption_language.currentText(),
                    auto_caption_delay_ms=self.caption_delay.value(),
                    auto_caption_video_delay_ms=self.caption_video_delay.value(),
                    guide_scale=self.guide_scale.value(),engine_executable=self.engine_path.text())


class ChannelHealthDialog(QDialog):
    """Explicit per-device channel checks in manually requested 40-item batches."""

    def __init__(self,store,selected,pool,on_change=None,parent=None):
        super().__init__(parent)
        from .sources import configured_playlists, source_label
        state=store.read()
        self.store=store
        self.on_change=on_change
        self.health_history=HealthHistory(store)
        self.last_batch_start=None
        self.setWindowTitle('Channel health — this computer')
        self.resize(725,540)
        self.pool=pool
        self.rows=list(state['channels'])
        self.selected=selected
        self.offset=0
        self.running=False
        self.scan_all=False
        self.results=[]
        layout=QVBoxLayout(self)
        description=QLabel('Checks run from THIS PC (with its current VPN/network). '
                           'A responding URL does not prove video playback. '
                           'Ace streams require real engine/peer playback. '
                           'Failed HTTP probes are not playback tests. Channels are never deleted; '
                           'you can hide confirmed missing streams and restore them later.')
        description.setWordWrap(True)
        layout.addWidget(description)
        self.source=QComboBox()
        self.source.addItem('All imported channels','')
        for url in configured_playlists(state['settings']):
            self.source.addItem(source_label(url),url)
        self.source.currentIndexChanged.connect(self.reset_filter)
        layout.addWidget(self.source)
        self.summary=QLabel('Ready • Test one channel or a manually requested batch of 40.')
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.progress=QProgressBar()
        self.progress.setObjectName('healthScanProgress')
        self.progress.setRange(0,len(self.rows))
        self.progress.setValue(0)
        self.progress.setFormat('%v / %m channels checked (%p%)')
        layout.addWidget(self.progress)
        self.output=QListWidget()
        layout.addWidget(self.output,1)
        self.auto_hide=QCheckBox('Automatically hide after two consecutive 404/410 checks (opt-in)')
        self.auto_hide.setToolTip('Only HTTP 404/410 twice for this exact channel ID. Never auto-hide 403, timeouts, Ace or HLS responses.')
        layout.addWidget(self.auto_hide)
        actions=QHBoxLayout()
        extras=QHBoxLayout()
        self.selected_button=QPushButton('Check selected channel')
        self.selected_button.setEnabled(True)
        self.selected_button.clicked.connect(self.check_selected)
        actions.addWidget(self.selected_button)
        self.batch_button=QPushButton('Check next 40')
        self.batch_button.clicked.connect(self.check_next)
        actions.addWidget(self.batch_button)
        self.scan_button=QPushButton('Scan all progressively')
        self.scan_button.setToolTip('Only on explicit request: process all selected channels in safe batches of 40, at most four network probes at a time.')
        self.scan_button.clicked.connect(self.start_progressive_scan)
        actions.addWidget(self.scan_button)
        self.stop_button=QPushButton('Stop after current batch')
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_progressive_scan)
        actions.addWidget(self.stop_button)
        self.recheck_button=QPushButton('Recheck last 40')
        self.recheck_button.setEnabled(False)
        self.recheck_button.clicked.connect(self.recheck_last)
        actions.addWidget(self.recheck_button)
        self.hide_confirmed=QPushButton('Hide confirmed missing')
        self.hide_confirmed.setEnabled(False)
        self.hide_confirmed.clicked.connect(self.hide_confirmed_missing)
        extras.addWidget(self.hide_confirmed)
        copy=QPushButton('Copy results')
        copy.clicked.connect(self.copy_results)
        extras.addWidget(copy)
        close=QPushButton('Close')
        close.clicked.connect(self.close)
        extras.addWidget(close)
        layout.addLayout(actions)
        layout.addLayout(extras)
        self.reset_filter()

    def filtered(self):
        source=self.source.currentData()
        return [row for row in self.rows
                if not source or source in (row.get('sources') or [row.get('source')])]

    def reset_filter(self,*_):
        # Changing sources cancels any queued continuation.
        self.scan_all=False
        total=len(self.filtered())
        self.stop_button.setEnabled(False)
        self.scan_button.setEnabled(not self.running and bool(total))
        self.offset=0
        self.results.clear()
        self.output.clear()
        # A 0..0 range animates as indeterminate even when there is no work.
        self.progress.setMaximum(max(1,total))
        self.progress.setFormat('%v / %m channels checked (%p%)' if total
                                else '0 / 0 channels checked')
        self.progress.setValue(0)
        self.summary.setText(f'{len(self.filtered()):,} channels in this selection. '
                             'Each click probes at most 40 using four network connections.')
        self.batch_button.setEnabled(not self.running and bool(self.filtered()))
        self.batch_button.setText('Check first 40')
        self.last_batch_start=None
        self.recheck_button.setEnabled(False)
        self.hide_confirmed.setEnabled(False)

    def start_progressive_scan(self):
        if self.running or not self.filtered():return
        if self.offset>=len(self.filtered()):
            self.offset=0
            self.results.clear()
            self.output.clear()
            self.progress.setValue(0)
        self.scan_all=True
        self.stop_button.setEnabled(True)
        self.scan_button.setEnabled(False)
        self.check_next()

    def stop_progressive_scan(self):
        # We cannot interrupt an in-flight DNS/HTTP call safely. At most one
        # 40-channel batch finishes; no further batch will be started.
        self.scan_all=False
        self.stop_button.setEnabled(False)
        self.scan_button.setEnabled(not self.running)
        self.batch_button.setEnabled(not self.running and self.offset<len(self.filtered()))
        if self.running:
            self.summary.setText('Stopping after current batch; completed results will be retained.')
        else:
            self.summary.setText(f'Paused after {self.offset:,} / {len(self.filtered()):,} channels.')

    def closeEvent(self,event):
        self.stop_progressive_scan()
        super().closeEvent(event)

    def reject(self):
        # Escape rejects a QDialog without going through closeEvent.
        self.stop_progressive_scan()
        super().reject()

    def continue_progressive_scan(self):
        # Stop/Close/Escape may arrive after a continuation has been queued.
        if self.scan_all:
            self.check_next()

    def check_selected(self):
        # This dialog is modeless: the main window's selection can change.
        current=getattr(self.parent(),'selected',self.selected)
        if current is None:
            self.summary.setText('Select a channel in the main window to check.')
            return
        self.run_batch([current],0,one=True)

    def check_next(self):
        rows=self.filtered()
        if self.offset>=len(rows):
            self.summary.setText('All channels in this selection have been checked.')
            return
        self.run_batch(rows,self.offset)

    def recheck_last(self):
        if self.last_batch_start is not None:
            self.run_batch(self.filtered(),self.last_batch_start)

    def set_hidden(self,ids):
        requested=set(ids)
        known={ch['id'] for ch in self.rows}
        permitted=requested & known
        if not permitted:return 0
        def update(state):
            state.setdefault('disabled_channels',[])
            state['disabled_channels']=sorted(set(state['disabled_channels'])|permitted)
        self.store.update(update)
        if self.on_change:self.on_change()
        return len(permitted)

    def hide_confirmed_missing(self):
        from .channel_health import confirmed_missing_ids
        candidate=confirmed_missing_ids(self.results)
        count=self.set_hidden(candidate)
        if count:
            self.summary.setText(f'{count} confirmed-missing channel(s) hidden from browsing. '
                                 'Enable Show disabled in the sidebar to restore any of them.')
        self.hide_confirmed.setEnabled(False)

    def run_batch(self,rows,start,one=False):
        if self.running:return
        from .channel_health import check_batch, BATCH_SIZE
        self.running=True
        # Do not let source changes invalidate an in-flight batch offset.
        self.source.setEnabled(False)
        self.batch_button.setEnabled(False)
        self.recheck_button.setEnabled(False)
        self.selected_button.setEnabled(False)
        if not one:self.last_batch_start=start
        count=min(BATCH_SIZE,len(rows)-start)
        self.summary.setText(f'Checking {count} streams from this computer… '
                             'A region/DRM-dependent stream may still fail in VLC.')
        task=Task(lambda:check_batch(rows,start,1 if one else BATCH_SIZE))
        self.health_task=task
        def success(payload):
            entries,end=payload
            checker_busy=any(entry['status']=='checker-busy' for entry in entries)
            # Capacity is a local scanner state, not a channel observation.
            # Keep the retry cursor and previous saved channel results intact.
            entries=[entry for entry in entries if entry['status']!='checker-busy']
            self.running=False
            self.source.setEnabled(True)
            if not one:self.offset=end
            self.progress.setValue(self.offset)
            self.results.extend(entries)
            try:
                self.health_history.record(entries)
                history_error=False
            except (OSError,ValueError):
                history_error=True
            for entry in entries:
                item=QListWidgetItem(entry['name'][:90]+'  •  '+
                                     entry['status'].replace('-',' ')+
                                     ' — '+entry['detail'])
                item.setData(Qt.UserRole,entry['id'])
                self.output.addItem(item)
            from .channel_health import confirmed_missing_ids
            confirmed=confirmed_missing_ids(self.results)
            if confirmed and self.auto_hide.isChecked():
                self.set_hidden(confirmed)
            self.hide_confirmed.setEnabled(bool(confirmed) and not self.auto_hide.isChecked())
            self.recheck_button.setEnabled(self.last_batch_start is not None)
            counts={}
            for entry in self.results:
                counts[entry['status']]=counts.get(entry['status'],0)+1
            self.summary.setText(f'{len(self.results)} checks this session · '+
                                 ', '.join(f'{k}: {n}' for k,n in sorted(counts.items()))+
                                 f' · batch position {self.offset}/{len(self.filtered())}. '
                                 'Results are network reachability hints, not playback proof.'+
                                 (' Previous-result cache could not be saved.' if history_error else ''))
            total=len(self.filtered())
            self.batch_button.setText('Check next 40')
            if checker_busy:
                self.scan_all=False
                self.summary.setText('Paused: stream checker is busy; retry unchecked channels later. '+self.summary.text())
            elif self.scan_all and self.offset<total:
                # A provider telling us to slow down is a reason to pause,
                # not to hammer the rest of its catalogue.
                if any(x['status']=='rate-limited' for x in entries):
                    self.scan_all=False
                    self.summary.setText('Paused on provider HTTP 429 rate limit. '+self.summary.text())
                else:
                    QTimer.singleShot(0,self.continue_progressive_scan)
            if self.offset>=total:
                self.scan_all=False
            self.batch_button.setEnabled(self.offset<total and not self.scan_all)
            self.stop_button.setEnabled(self.scan_all)
            self.scan_button.setEnabled(not self.scan_all)
            self.selected_button.setEnabled(True)
            self.health_task=None
        def failure(message):
            self.running=False
            self.scan_all=False
            self.stop_button.setEnabled(False)
            self.scan_button.setEnabled(True)
            self.source.setEnabled(True)
            # Transport errors can contain signed stream URLs or credentials.
            self.summary.setText('Health check failed; retry the batch.')
            self.batch_button.setEnabled(True)
            self.recheck_button.setEnabled(self.last_batch_start is not None)
            self.selected_button.setEnabled(True)
            self.health_task=None
        task.signals.success.connect(success)
        task.signals.failure.connect(failure)
        self.pool.start(task)

    def copy_results(self):
        import json
        # Never put URLs, access tokens, full headers or IPs in the clipboard.
        QApplication.clipboard().setText(json.dumps(self.results,indent=2))

class ChannelDuplicatesDialog(QDialog):
    """Human-reviewed same-name candidates; never delete or auto-hide feeds."""

    PAGE_GROUPS=80

    def __init__(self,store,on_change=None,parent=None):
        super().__init__(parent)
        self.store=store
        self.on_change=on_change
        self.setWindowTitle('DizyTV — duplicate channel candidates')
        self.resize(920,630)
        self.history=HealthHistory(store)
        self.groups=[]
        self.matches=[]
        self.loaded=0
        self.disabled=set()
        layout=QVBoxLayout(self)
        intro=QLabel(
            'Candidates share a channel name, country and TV/radio type, but may '
            'be different streams, providers or quality levels. +1 and named regional '
            'variants are kept distinct. Select individual entries to hide or restore; '
            'nothing is deleted or hidden automatically. Last HTTP results do NOT '
            'confirm video playback.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        top=QHBoxLayout()
        self.query=QLineEdit()
        self.query.setPlaceholderText('Filter duplicate names or providers')
        self.query.textChanged.connect(self.refilter)
        top.addWidget(self.query,1)
        self.status_filter=QComboBox()
        self.status_filter.addItem('Every previous check status','')
        self.status_filter.addItem('Includes HTTP 404 / 410 result','missing')
        self.status_filter.addItem('Has not been checked','unchecked')
        self.status_filter.addItem('Includes access-limited result','access-limited')
        self.status_filter.currentIndexChanged.connect(self.refilter)
        top.addWidget(self.status_filter)
        layout.addLayout(top)
        self.tree=QTreeWidget()
        self.tree.setObjectName('duplicateChannelTree')
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(['Channel / candidate group','Playlist source','Last HTTP result','Visibility'])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.setColumnWidth(0,300)
        self.tree.setColumnWidth(1,215)
        self.tree.setColumnWidth(2,205)
        self.tree.setColumnWidth(3,90)
        layout.addWidget(self.tree,1)
        self.count_label=QLabel()
        layout.addWidget(self.count_label)
        row=QHBoxLayout()
        self.hide_button=QPushButton('Hide selected channels')
        self.hide_button.clicked.connect(lambda:self.update_visibility(True))
        row.addWidget(self.hide_button)
        self.restore_button=QPushButton('Restore selected channels')
        self.restore_button.clicked.connect(lambda:self.update_visibility(False))
        row.addWidget(self.restore_button)
        self.more_button=QPushButton('Load 80 more groups')
        self.more_button.clicked.connect(self.show_more)
        row.addWidget(self.more_button)
        self.refresh_button=QPushButton('Refresh last results')
        self.refresh_button.clicked.connect(self.refresh)
        row.addWidget(self.refresh_button)
        close=QPushButton('Close')
        close.clicked.connect(self.close)
        row.addWidget(close)
        layout.addLayout(row)
        self.refresh()

    def refresh(self):
        state=self.store.read()
        self.groups=duplicate_groups(state['channels'])
        self.disabled=set(state.get('disabled_channels',()))
        self.latest=self.history.read()
        self.refilter()

    def refilter(self,*_):
        query=self.query.text().casefold().strip()
        check=self.status_filter.currentData()
        matches=[]
        for key,rows in self.groups:
            if query:
                if query not in key[0] and not any(
                        query in source_label((r.get('sources') or
                                  [r.get('source','')])[0]).casefold()
                        for r in rows):
                    continue
            if check and not any(
                    (r.get('id') not in self.latest if check=='unchecked'
                     else self.latest.get(r.get('id'),{}).get('status')==check)
                    for r in rows):
                continue
            matches.append((key,rows))
        self.matches=matches
        self.loaded=0
        self.tree.clear()
        self.show_more()

    def show_more(self):
        chunk=self.matches[self.loaded:self.loaded+self.PAGE_GROUPS]
        for key,rows in chunk:
            label=display_channel_name(rows[0].get('name',''))
            group=QTreeWidgetItem([f'{label}  ({len(rows)} candidates · {rows[0].get("country") or "Unspecified"})'])
            group.setFlags(group.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(group)
            for ch in rows:
                cid=ch['id']
                sources=ch.get('sources') or [ch.get('source','')]
                labels=list(dict.fromkeys(source_label(u) for u in sources if u))
                source=', '.join(labels[:2])+(' + more' if len(labels)>2 else '')
                result=self.latest.get(cid)
                health=('Not checked' if result is None else
                        result['status'].replace('-',' ')+
                        ' · '+time.strftime('%Y-%m-%d %H:%M',time.localtime(result['checked'])))
                item=QTreeWidgetItem([
                    display_channel_name(ch['name'])+'  ['+cid[:8]+']',
                    source or 'Unknown playlist',health,
                    'Hidden' if cid in self.disabled else 'Visible',
                ])
                item.setData(0,Qt.UserRole,cid)
                group.addChild(item)
        self.loaded+=len(chunk)
        self.more_button.setEnabled(self.loaded<len(self.matches))
        self.count_label.setText(
            f'{len(self.groups):,} groups with matching names · '
            f'{len(self.matches):,} matching groups · '
            f'{self.loaded:,} displayed. Select channel entries, not group headers.')

    def selected_ids(self):
        return {item.data(0,Qt.UserRole) for item in self.tree.selectedItems()
                if item.parent() is not None and item.data(0,Qt.UserRole)}

    def update_visibility(self,hide):
        ids=self.selected_ids()
        if not ids:
            self.count_label.setText('Select individual channel rows first.')
            return
        known={ch['id'] for ch in self.store.read()['channels']}
        ids &= known
        if not ids:return
        previous=set(self.disabled)
        def apply(state):
            disabled=set(state.get('disabled_channels',[]))
            if hide:disabled.update(ids)
            else:disabled.difference_update(ids)
            state['disabled_channels']=sorted(disabled)
        self.store.update(apply)
        if self.on_change:self.on_change()
        self.disabled=set(self.store.read()['disabled_channels'])
        for group_idx in range(self.tree.topLevelItemCount()):
            group=self.tree.topLevelItem(group_idx)
            for row_idx in range(group.childCount()):
                item=group.child(row_idx)
                cid=item.data(0,Qt.UserRole)
                if cid in ids:
                    item.setText(3,'Hidden' if cid in self.disabled else 'Visible')
        changed=len(previous.symmetric_difference(self.disabled))
        self.count_label.setText(
            f'{changed} channels '+('hidden' if hide else 'restored')+
            '. Changes affect the channel browser, guide and global search.')


class SystemUsageDialog(QDialog):
    """Read-only resource and VLC diagnostic panel, sampled only while visible."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner=owner
        self.sampler=SystemSampler()
        self.setWindowTitle('DizyTV — system usage')
        self.setObjectName('systemUsageDialog')
        self.resize(630,435)
        layout=QVBoxLayout(self)
        self.summary=QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.details=QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setObjectName('systemUsageReadout')
        layout.addWidget(self.details,1)
        explanation=QLabel(
            'CPU is shown as % of all logical cores and % of one core. '
            'Process memory includes libVLC in this process, but excludes detached '
            'recorders, external Ace Engine, and the FFmpeg caption child process. '
            'Measurements stay on this device. A reachable URL is not proof of playback.')
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.timer=QTimer(self)
        self.timer.setInterval(1250)
        self.timer.timeout.connect(self.refresh_snapshot)
        self.refresh_snapshot()

    @staticmethod
    def fmt(value,unit=''):
        return 'Unavailable' if value is None else str(value)+unit

    def refresh_snapshot(self):
        owner=self.owner
        stats=self.sampler.snapshot(owner.store.directory)
        ram=self.fmt(stats['process_memory_mib'],' MiB')
        if stats['process_memory_peak_only']:
            ram+=' (peak, not current)'
        self.summary.setText(
            'DizyTV: '+self.fmt(stats['process_cpu_percent'],'% total CPU')+
            '  •  '+ram+' RAM')
        lines=[
            'Platform: '+stats['platform'],
            'Logical CPU cores: '+str(stats['logical_cores']),
            'DizyTV CPU / all cores: '+self.fmt(stats['process_cpu_percent'],'%'),
            'DizyTV CPU / single-core equivalent: '+self.fmt(stats['process_one_core_percent'],'%'),
            'DizyTV working memory: '+ram,
            'System physical RAM used: '+self.fmt(stats['system_used_mib'],' MiB')+
            ' / '+self.fmt(stats['system_total_mib'],' MiB')+
            ' ('+self.fmt(stats['system_used_percent'],'%')+')',
            'Free space in app data folder: '+self.fmt(stats['recording_disk_free_gib'],' GiB'),
            'Imported channels: '+format(len(owner.state.get('channels',[])),','),
            'Guide programmes: '+format(len(owner.guide.get('programmes',[])),','),
            'Timeshift mode: '+('Active' if owner.timeshift is not None else 'Off'),
            'Local speech captions: '+('Active' if owner._auto_caption_worker is not None else 'Off'),
            'Player state: '+(str(owner.player.get_state()) if owner.player else 'Stopped'),
        ]
        if owner.player is not None:
            media=None
            try:
                import vlc
                media=owner.player.get_media()
                counters=vlc.MediaStats()
                if media is not None and media.get_stats(counters):
                    lines.extend([
                        'VLC decoded audio: '+str(counters.decoded_audio),
                        'VLC decoded video: '+str(counters.decoded_video),
                        'VLC displayed pictures: '+str(counters.displayed_pictures),
                        'VLC lost pictures: '+str(counters.lost_pictures),
                        'VLC demux bitrate: '+str(round(counters.demux_bitrate,2))+' MiB/s',
                        'VLC input bitrate: '+str(round(counters.input_bitrate,2))+' MiB/s',
                    ])
            except (AttributeError,RuntimeError,TypeError,OSError):
                lines.append('VLC playback counters unavailable')
            finally:
                if media is not None:media.release()
        self.details.setPlainText('\n'.join(lines))

    def showEvent(self,event):
        self.timer.start()
        super().showEvent(event)

    def hideEvent(self,event):
        self.timer.stop()
        super().hideEvent(event)

    def closeEvent(self,event):
        self.timer.stop()
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self,store=None,start_worker=True):
        super().__init__(); self.store=store or Store(); self.player=None; self.vlc_instance=None; self.task=None
        self.state=self.store.read(); self.guide={'names':{},'programmes':[]}; self.guide_start=int(time.time()/3600)*3600
        self.selected=None; self.global_search_dialog=None; self.start_worker=start_worker; self.pool=QThreadPool.globalInstance(); self.displayed_zone=''; self.source_errors=[]; self.engine_task=None; self.playback_started=0; self.playback_reported=False; self.cinema_mode=False; self.screen_dialog=None; self.guide_popup=None; self.screen_seek_slider=None; self.timeshift=None; self.timeshift_task=None; self.timeshift_lag=0
        self.last_live_recovery=0;self.last_good_video=time.monotonic()
        self._subtitle_auto_applied=False
        self._subtitle_manual_track=None
        self._subtitle_session_all_off=False
        self._subtitle_track_signature=()
        self._vlc_subtitle_profile=None
        self._playback_url=''
        self._play_request_serial=0
        self._auto_caption_worker=None
        self._auto_caption_worker_serial=None
        self._auto_caption_stopping=False
        self._auto_caption_seq=0
        self._auto_caption_overlay=None
        self._auto_caption_label=None
        self._auto_caption_text=''
        self._auto_caption_updated=0
        self._auto_caption_started_at=0
        self._auto_caption_restart_requested=False
        self._auto_caption_retry_budget=0
        self._active_holdback_ms=0
        self._auto_caption_queue=CaptionDelayQueue()
        self._auto_caption_timer=QTimer(self)
        self._auto_caption_timer.setInterval(80)
        self._auto_caption_timer.timeout.connect(self.poll_auto_caption_queue)
        self.last_capture_progress=time.monotonic();self.last_capture_seq=-1
        self.source_check=None;self.source_check_serial=0
        self._last_media_activity=None
        self._video_issue_notified=False
        self._direct_video_sample=None
        self._direct_video_progress=0
        self._direct_video_stalled=False
        self._active_direct_video=False
        self.detached_controls=None;self.detached_hide_timer=QTimer(self)
        self.detached_hide_timer.setSingleShot(True)
        self.detached_hide_timer.timeout.connect(self.hide_detached_controls)
        self.detached_mouse_position=None
        self.detached_mouse_timer=QTimer(self)
        self.detached_mouse_timer.setInterval(250)
        self.detached_mouse_timer.timeout.connect(self.poll_detached_mouse)
        self.popout_live_light=None;self.popout_live_button=None
        self.light_phase=False
        self.light_timer=QTimer(self)
        self.light_timer.setInterval(850)
        self.light_timer.timeout.connect(self.pulse_live_light)
        self._startup_layout_pending=True
        self._ui_hang_monitor=None
        self._ui_heartbeat_timer=QTimer(self)
        self._ui_heartbeat_timer.setInterval(1000)
        self._ui_heartbeat_timer.timeout.connect(self.heartbeat_ui)
        self.setWindowTitle('DizyTV'); self.resize(1150,730)
        self.setMinimumSize(480,360)
        self.setWindowIcon(QIcon(str(ASSETS/'branding/dizytv-logo.png')))
        root=QWidget();root.setObjectName('appShell');self.setCentralWidget(root);layout=QVBoxLayout(root);layout.setContentsMargins(9,8,9,8);layout.setSpacing(8)
        topbar=QWidget();topbar.setObjectName('appHeader');top=QHBoxLayout(topbar);top.setContentsMargins(4,4,4,4);top.setSpacing(8)
        logo=QLabel(); logo.setObjectName('dizytvLogo')
        logo.setFixedSize(54,54)
        logo.setAlignment(Qt.AlignCenter)
        logo.setPixmap(QPixmap(str(ASSETS/'branding/dizytv-logo.png')).scaled(54,54,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        top.addWidget(logo)
        self.header_logo=logo
        self.header_topbar=topbar
        brand=QLabel('DizyTV'); brand.setObjectName('brand'); top.addWidget(brand)
        theme_label=QLabel('Theme')
        theme_label.setObjectName('filterTitle')
        top.addWidget(theme_label)
        self.theme_picker=QComboBox()
        self.theme_picker.setObjectName('themePicker')
        self.theme_picker.setToolTip('Choose a DizyTV appearance; saved automatically')
        self.theme_picker.addItems(['Green','Dark','Light'])
        self.theme_picker.setCurrentText(self.state['settings'].get('theme','Green'))
        self.theme_picker.currentTextChanged.connect(self.choose_theme)
        top.addWidget(self.theme_picker)
        top.addStretch()
        self.timezone_label=QLabel();self.timezone_label.setObjectName('timezoneLabel');top.addWidget(self.timezone_label)
        for label,handler in [('Refresh channels',self.refresh_channels),('Source status',self.show_source_status),('Refresh guide',self.refresh_guide),('Settings',self.settings)]:
            b=QPushButton(label); b.clicked.connect(handler); top.addWidget(b)
        self.tools_button=QPushButton('Tools ▾')
        self.tools_button.setToolTip('Backup and restore your local DizyTV setup')
        tools_menu=QMenu(self.tools_button)
        tools_menu.addAction('Save local backup…',self.backup)
        tools_menu.addAction('Restore local backup…',self.restore)
        tools_menu.addSeparator()
        tools_menu.addAction('Set up Ace Stream engine…',self.open_ace_stream_setup)
        tools_menu.addAction('Check channel health…',self.open_channel_health)
        tools_menu.addAction('Find duplicate channels…',self.open_duplicate_channels)
        tools_menu.addAction('System usage…',self.open_system_usage)
        tools_menu.addAction('Selected channel source…',self.show_channel_source_details)
        tools_menu.addAction('Try another saved source…',self.try_alternative_source)
        tools_menu.addSeparator()
        self.ui_diagnostics_action=tools_menu.addAction('Log UI hangs locally (opt-in)')
        self.ui_diagnostics_action.setCheckable(True)
        self.ui_diagnostics_action.toggled.connect(self.toggle_ui_diagnostics)
        self.tools_button.setMenu(tools_menu)
        top.addWidget(self.tools_button)
        self.header_scroll=QScrollArea()
        self.header_scroll.setObjectName('toolbarScroll')
        self.header_scroll.setWidgetResizable(False)
        # Keep each header button at its full text width. On narrow windows,
        # make the overflow accessible instead of shrinking/cropping labels.
        self.header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.header_scroll.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        topbar.adjustSize()
        self.header_scroll.setWidget(topbar)
        self.header_scroll.setFixedHeight(topbar.sizeHint().height()+12)
        layout.addWidget(self.header_scroll)
        self.header_buttons=[logo,brand,self.timezone_label]+[top.itemAt(i).widget() for i in range(top.count()) if top.itemAt(i).widget() is not None]
        split=QSplitter();split.setChildrenCollapsible(True);layout.addWidget(split,1)
        self.split=split
        sidebar=QWidget();sidebar.setObjectName('appSidebar');side=QVBoxLayout(sidebar);side.setContentsMargins(10,10,10,10);side.setSpacing(7)
        # Keep each filter/checkbox/button at its full vertical size. When
        # space runs out, the sidebar scrolls instead of crushing text rows.
        side.setSizeConstraint(QLayout.SetMinimumSize)
        self.search=QLineEdit(); self.search.setPlaceholderText('Filter current channels'); self.search.textChanged.connect(self.render_channels); side.addWidget(self.search)
        self.country_filter=QComboBox(); self.genre_filter=QComboBox()
        self.kind_filter=QComboBox(); self.source_filter=QComboBox()
        self.section_filter=QComboBox()
        filters=QWidget(); filter_layout=QVBoxLayout(filters)
        filter_layout.setContentsMargins(0,0,0,0);filter_layout.setSpacing(3)
        for widget,title,default in (
            (self.source_filter,'Playlist','All playlists'),
            (self.country_filter,'Country','All countries'),
            (self.section_filter,'Category','All categories'),
            (self.genre_filter,'EPG genre','All genres'),
            (self.kind_filter,'TV / Radio / stream','All stream types')):
            label=QLabel(title)
            label.setObjectName('filterTitle')
            filter_layout.addWidget(label)
            widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            widget.setMinimumContentsLength(8)
            widget.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
            widget.setMinimumWidth(0)
            widget.addItem(default,'')
            widget.currentIndexChanged.connect(self.render_channels)
            filter_layout.addWidget(widget)
        side.addWidget(filters)
        order=QWidget()
        order_row=QHBoxLayout(order)
        order_row.setContentsMargins(0,0,0,0)
        order_row.addWidget(QLabel('Sort'))
        self.sort_picker=QComboBox()
        self.sort_picker.setObjectName('channelSort')
        self.sort_picker.addItems(CHANNEL_SORT_MODES)
        self.sort_picker.setCurrentText(self.state['settings'].get('channel_sort','Name A–Z'))
        self.sort_picker.currentTextChanged.connect(self.change_channel_sort)
        order_row.addWidget(self.sort_picker,1)
        side.addWidget(order)
        browser_label=QLabel('Countries / categories / channels'); side.addWidget(browser_label)
        self.country_tree=QTreeWidget(); self.country_tree.setHeaderHidden(True)
        self.country_tree.setMinimumHeight(86)
        self.country_tree.setMaximumHeight(240)
        self.country_tree.itemClicked.connect(self.country_tree_clicked)
        self.country_tree.itemDoubleClicked.connect(self.country_tree_double_clicked)
        self.country_tree.itemExpanded.connect(self.populate_expanded_section)
        side.addWidget(self.country_tree)
        self._tree_dirty=True
        selectors=QWidget()
        selector_row=QHBoxLayout(selectors)
        selector_row.setContentsMargins(0,0,0,0)
        self.favourites_only=QCheckBox('★ Favourites only')
        self.favourites_only.toggled.connect(self.render_channels)
        selector_row.addWidget(self.favourites_only)
        self.show_disabled=QCheckBox('Show disabled')
        self.show_disabled.setToolTip('Include hidden channels so they can be restored')
        self.show_disabled.toggled.connect(self.refresh_disabled_channels)
        selector_row.addWidget(self.show_disabled)
        side.addWidget(selectors)
        self.channels=QListWidget()
        self.channels.setMinimumHeight(86)
        self.channels.currentItemChanged.connect(self.choose_channel)
        self.channels.itemDoubleClicked.connect(lambda:self.play())
        side.addWidget(self.channels,1)
        for label,handler in [('★ Add / remove favourite',self.favourite),
                              ('Hide / restore selected',self.toggle_channel_visibility),
                              ('Map EPG',self.map_channel),('Edit categories',self.edit_categories)]:
            b=QPushButton(label); b.clicked.connect(handler); side.addWidget(b)
        self.sidebar=sidebar
        self.sidebar_scroll=QScrollArea()
        self.sidebar_scroll.setObjectName('sidebarScroll')
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.sidebar_scroll.setFrameShape(QFrame.NoFrame)
        self.sidebar_scroll.setMinimumWidth(0)
        self.sidebar_scroll.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Expanding)
        sidebar.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Expanding)
        # The panel will NEVER squeeze its buttons/labels shorter than their
        # full text. At extremely narrow widths its own scrollbar takes over.
        self.sidebar_scroll.setWidget(sidebar)
        self.country_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.country_tree.setTextElideMode(Qt.ElideNone)
        self.channels.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.channels.setTextElideMode(Qt.ElideNone)
        split.addWidget(self.sidebar_scroll); self.tabs=QTabWidget();self.tabs.setMinimumWidth(0)
        self.tabs.setObjectName('mainTabs')
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setUsesScrollButtons(True)
        self.tabs.tabBar().setElideMode(Qt.ElideRight)
        split.addWidget(self.tabs);split.setSizes([270,880])
        live=QWidget();live.setObjectName('livePage');live_layout=QVBoxLayout(live);live_layout.setContentsMargins(8,8,8,8);live_layout.setSpacing(6);self.live_layout=live_layout; self.now=QLabel('Choose a channel, then press Play');self.now.setObjectName('channelHeading'); self.now.setWordWrap(True); live_layout.addWidget(self.now)
        self.channel_banner=QLabel('')
        self.channel_banner.setObjectName('channelBanner')
        self.channel_banner.setWordWrap(True)
        self.channel_banner.hide()
        live_layout.addWidget(self.channel_banner)
        self.regional_notice=QLabel('')
        self.regional_notice.setObjectName('regionalAccessNotice')
        self.regional_notice.setAccessibleName('Possible regional access restriction')
        self.regional_notice.setWordWrap(True)
        self.regional_notice.setStyleSheet('QLabel { padding: 8px; border: 1px solid #bd9240; border-radius: 6px; }')
        self.regional_notice.hide()
        live_layout.addWidget(self.regional_notice)
        self.video=QFrame(); self.video.setStyleSheet('background:black;')
        # The offscreen Qt CI plugin cannot safely reparent native video
        # windows. Real Windows/macOS players still use a native libVLC surface.
        if os.environ.get('QT_QPA_PLATFORM')!='offscreen':
            self.video.setAttribute(Qt.WA_NativeWindow)
        self.video.setMouseTracking(True);self.video.installEventFilter(self); live_layout.addWidget(self.video,1)
        controls_widget=QWidget()
        controls_widget.setObjectName('playbackControlsRow')
        controls=QHBoxLayout(controls_widget)
        controls.setContentsMargins(4,2,4,2)
        controls.setSpacing(6)
        for label,handler in [('▶ Play',self.play),('■ Stop',self.stop_playback),('● Record',self.record_now)]:
            b=QPushButton(label); b.clicked.connect(handler); controls.addWidget(b)
        self.pause_button=QPushButton('⏸ Pause')
        self.pause_button.clicked.connect(self.toggle_pause)
        controls.addWidget(self.pause_button)
        self.rewind_button=QPushButton('↶ 30s')
        self.rewind_button.clicked.connect(lambda:self.seek_relative(-30000))
        controls.addWidget(self.rewind_button)
        self.forward_button=QPushButton('↷ 30s')
        self.forward_button.setToolTip('Skip forward 30 seconds in buffered TV, up to LIVE')
        self.forward_button.clicked.connect(lambda:self.seek_relative(30000))
        controls.addWidget(self.forward_button)
        self.live_button=QPushButton('LIVE')
        self.live_button.clicked.connect(self.jump_to_live)
        controls.addWidget(self.live_button)
        self.live_light=QLabel('●')
        self.live_light.setToolTip('Green: live; amber: buffering, rewound or paused; red: stopped/error')
        controls.addWidget(self.live_light)
        self.guide_button=QPushButton('☷ Guide')
        self.guide_button.clicked.connect(self.show_tv_guide)
        controls.addWidget(self.guide_button)
        self.info_button=QPushButton('Info')
        self.info_button.clicked.connect(self.show_tv_info)
        controls.addWidget(self.info_button)
        self.subtitle_button=QPushButton('CC Subtitles')
        self.subtitle_button.setObjectName('subtitleButton')
        self.subtitle_button.setToolTip('Subtitle tracks, closed captions and optional local subtitle files')
        self.subtitle_button.clicked.connect(self.show_subtitle_menu)
        controls.addWidget(self.subtitle_button)
        self.cinema_button=QPushButton('▣ Cinema')
        self.cinema_button.clicked.connect(self.toggle_cinema)
        controls.addWidget(self.cinema_button)
        self.screen_button=QPushButton('⛶ Screen')
        self.screen_button.clicked.connect(self.toggle_screen_fullscreen)
        controls.addWidget(self.screen_button)
        self.popout_button=QPushButton('▣ Pop out')
        self.popout_button.setToolTip('Open a separate resizable TV window while the guide stays available')
        self.popout_button.clicked.connect(self.open_popout)
        controls.addWidget(self.popout_button)
        self.controls_scroll=QScrollArea()
        self.controls_scroll.setObjectName('playerControlScroll')
        self.controls_scroll.setWidgetResizable(False)
        # The native horizontal scrollbar rendered as an ugly grey strip
        # under the media buttons in a normal-width TV window. Keep scrolling
        # functional with slim overflow chevrons but NEVER show that scrollbar.
        self.controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls_scroll.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        controls_widget.adjustSize()
        self.controls_scroll.setWidget(controls_widget)
        self.controls_scroll.setFixedHeight(controls_widget.sizeHint().height()+6)
        controls_strip=QWidget()
        controls_strip.setObjectName('playerControlsStrip')
        strip_layout=QHBoxLayout(controls_strip)
        strip_layout.setContentsMargins(0,0,0,0)
        strip_layout.setSpacing(3)
        self.controls_prev=QToolButton()
        self.controls_prev.setText('‹')
        self.controls_prev.setObjectName('mediaScrollArrow')
        self.controls_prev.setToolTip('Previous playback controls')
        self.controls_prev.setFixedWidth(29)
        self.controls_prev.clicked.connect(lambda:self.scroll_player_buttons(-240))
        self.controls_next=QToolButton()
        self.controls_next.setText('›')
        self.controls_next.setObjectName('mediaScrollArrow')
        self.controls_next.setToolTip('More playback controls')
        self.controls_next.setFixedWidth(29)
        self.controls_next.clicked.connect(lambda:self.scroll_player_buttons(240))
        strip_layout.addWidget(self.controls_prev)
        strip_layout.addWidget(self.controls_scroll,1)
        strip_layout.addWidget(self.controls_next)
        live_layout.addWidget(controls_strip)
        bar=self.controls_scroll.horizontalScrollBar()
        bar.rangeChanged.connect(self.sync_player_button_arrows)
        bar.valueChanged.connect(lambda _value:self.sync_player_button_arrows())
        QTimer.singleShot(0,self,self.sync_player_button_arrows)
        self.tv_controls=controls
        for item in range(controls.count()):
            widget=controls.itemAt(item).widget()
            if isinstance(widget,QPushButton):
                if widget in (self.live_button,):widget.setObjectName('tvLive')
                elif widget in (self.pause_button,self.popout_button):widget.setObjectName('tvPrimary')
                elif widget.text().startswith(('■','● Record')):widget.setObjectName('tvDanger')
        self.seek_notice=QLabel('Live pause / rewind: available only when this stream offers a seekable DVR window');self.seek_notice.setObjectName('playbackHint')
        self.seek_notice.setWordWrap(True)
        live_layout.addWidget(self.seek_notice)
        self.seek_slider=TimeSeekSlider(Qt.Horizontal)
        self.seek_slider.setObjectName('seekBar')
        self.seek_slider.seek_requested.connect(self.seek_relative)
        self.seek_slider.setRange(0,1000)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderReleased.connect(self.seek_from_slider)
        live_layout.addWidget(self.seek_slider)
        volume_row=QHBoxLayout()
        volume_row.addWidget(QLabel('Volume'))
        self.volume_slider=MediaRailSlider(Qt.Horizontal)
        self.volume_slider.setObjectName('volumeBar')
        self.volume_slider.setRange(0,100)
        self.volume_slider.setValue(85)
        self.volume_slider.valueChanged.connect(self.set_tv_volume)
        volume_row.addWidget(self.volume_slider,1)
        live_layout.addLayout(volume_row)
        self.tabs.addTab(live,'Live TV')
        guide_page=QWidget(); guide_layout=QVBoxLayout(guide_page); nav=QHBoxLayout()
        for label,delta in [('← Earlier',-21600),('Now',0),('Later →',21600)]:
            b=QPushButton(label); b.clicked.connect(lambda checked=False,d=delta:self.move_guide(d)); nav.addWidget(b)
        self.guide_date=QLabel(); nav.addWidget(self.guide_date); guide_layout.addLayout(nav)
        self.grid=GuideGrid(); self.grid.channel_clicked.connect(self.play_guide_channel); self.grid.programme_record_requested.connect(self.schedule_programme); self.grid.channel_record_requested.connect(self.record_guide_channel)
        scroll=QScrollArea();scroll.setWidget(self.grid);scroll.setWidgetResizable(True)
        self.guide_scroll=scroll
        guide_layout.addWidget(scroll); self.tabs.addTab(guide_page,'TV Guide')
        recordings=QWidget(); rec_layout=QVBoxLayout(recordings)
        self.jobs=QTableWidget(0,5); self.jobs.setHorizontalHeaderLabels(['Programme','Start','End','Status','Size']); self.jobs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.jobs.setSelectionBehavior(QTableWidget.SelectRows); self.jobs.setSelectionMode(QTableWidget.SingleSelection); rec_layout.addWidget(self.jobs)
        rec_buttons=QHBoxLayout()
        for label,handler in [('Stop / cancel',self.cancel_job),('Rearm restored timer',self.rearm_job),('Play file',self.play_file),('Delete file',self.delete_file)]:
            b=QPushButton(label); b.clicked.connect(handler); rec_buttons.addWidget(b)
        rec_layout.addLayout(rec_buttons); hint=QLabel('One recording at a time. Closing this window leaves the recorder running.\nAfter a reboot, open DizyTV to resume future timers. This alpha does not wake a sleeping computer.'); hint.setWordWrap(True); rec_layout.addWidget(hint); self.tabs.addTab(recordings,'Recordings')
        self.global_search_button=QPushButton('⌕  Search channels and programmes  •  Ctrl+K');self.global_search_button.setObjectName('globalSearch')
        self.global_search_button.setToolTip('Search all imported playlists and upcoming programme titles, independent of filters')
        self.global_search_button.clicked.connect(self.open_global_search)
        layout.insertWidget(1,self.global_search_button)
        self.global_search_shortcut=QShortcut(QKeySequence('Ctrl+K'),self)
        self.global_search_shortcut.activated.connect(self.open_global_search)
        self.status=QLabel('Ready  •  Configure sources and recording storage in Settings');self.status.setObjectName('appStatus');layout.addWidget(self.status)
        self.apply_interface_scale()
        self.load_guide(); self.render_channels(); self.tick()
        if os.environ.get('DIZYTV_UI_DIAGNOSTICS')=='1':
            self.ui_diagnostics_action.setChecked(True)
        self.light_timer.start()
        self.clock=QTimer(self); self.clock.timeout.connect(self.tick); self.clock.start(5000)
        self.refresh_clock=QTimer(self); self.refresh_clock.timeout.connect(self.refresh_channels); self.refresh_clock.start(6*3600*1000)
        self.guide_clock=QTimer(self); self.guide_clock.timeout.connect(self.refresh_guide); self.guide_clock.start(12*3600*1000)
        if start_worker:
            ensure_worker(self.store.directory)
            # Previously cached Ace channels hid newly configured public feeds.
            # Always refresh on startup, retaining cached channels until success.
            QTimer.singleShot(200,self.refresh_channels)
    def heartbeat_ui(self):
        if self._ui_hang_monitor is not None:
            self._ui_hang_monitor.heartbeat()

    def toggle_ui_diagnostics(self,enabled):
        """Log a Python main-thread stack when the Qt loop stops responding."""
        if enabled:
            if self._ui_hang_monitor is not None:
                return
            self._ui_hang_monitor=UiHangMonitor(self.store.directory/'diagnostics')
            self._ui_hang_monitor.start()
            self._ui_heartbeat_timer.start()
            self.status.setText('UI hang logging enabled locally: '+
                                str(self._ui_hang_monitor.path)+
                                ' — inspect stack paths before sharing.')
        else:
            self._ui_heartbeat_timer.stop()
            if self._ui_hang_monitor is not None:
                self._ui_hang_monitor.stop()
                self._ui_hang_monitor=None
            self.status.setText('UI hang logging disabled. Existing local logs are retained.')

    def showEvent(self,event):
        super().showEvent(event)
        if self._startup_layout_pending:
            self._startup_layout_pending=False
            # Qt computes stylesheet-driven QPushButton hints only once the
            # real platform window is shown. The initial pre-show QScrollArea
            # dimensions can therefore clip the logo and header controls.
            QTimer.singleShot(0,self,self.settle_startup_toolbar_layout)

    def settle_startup_toolbar_layout(self):
        """Polish shared Windows/macOS/Linux controls after the real Qt layout.

        Qt calculates platform-specific text/DPI size hints only after the
        window is shown and the saved stylesheet has been applied. The content
        area is never allowed to shrink a label; overflow remains scrollable.
        """
        if not hasattr(self,'header_scroll'):
            return
        sidebar=self.sidebar
        sidebar.ensurePolished()
        # Never let QSplitter/QScrollArea compress a category label, filter,
        # dropdown, favourite checkbox or action button below its styled
        # text height.  The panel scrolls VERTICALLY when the window is short.
        # Remember each widget's real pre-policy minimum. Qt style size hints
        # change on 80%/100%/150% and Compact/Normal/Large transitions; minima
        # imposed by an earlier layout must be cleared BEFORE recomputing them.
        original=getattr(self,'_sidebar_original_min_heights',None)
        if original is None:
            original={}
            self._sidebar_original_min_heights=original
        for widget in sidebar.findChildren(QWidget):
            if not isinstance(widget,(QLabel,QPushButton,QComboBox,
                                      QCheckBox,QLineEdit)):
                continue
            initial=original.setdefault(widget,widget.minimumHeight())
            widget.setMinimumHeight(initial)
            widget.ensurePolished()
            hint=widget.sizeHint().height()
            if hint>0:
                widget.setMinimumHeight(max(initial,hint))
        sidebar.setMinimumHeight(0)
        sidebar.layout().invalidate()
        sidebar.layout().activate()
        required_height=sidebar.layout().minimumSize().height()
        sidebar.setMinimumHeight(required_height)
        self.sidebar_scroll.updateGeometry()
        for widget in (self.country_filter,self.genre_filter,self.kind_filter,
                       self.source_filter,self.section_filter,self.sort_picker):
            widget.ensurePolished()
        # Keep the viewer's selected splitter width. The side panel scrolls
        # vertically if the window is too short, without consuming extra video
        # space merely because category labels have wide text.
        self.sidebar_scroll.updateGeometry()
        for area in (self.header_scroll,self.controls_scroll):
            child=area.widget()
            if child is None:
                continue
            child.ensurePolished()
            for widget in child.findChildren(QWidget):
                widget.ensurePolished()
            child_layout=child.layout()
            if child_layout:
                child_layout.invalidate()
                child_layout.activate()
            child.adjustSize()
            base_height=child.sizeHint().height()
            if area is self.header_scroll:
                base_height=max(base_height,self.header_logo.height()+8)
                child.setMinimumWidth(child.sizeHint().width())
            scrollbar=area.horizontalScrollBar()
            # The header has a visible scrollbar when needed; the playback
            # strip uses its existing chevrons and no native scrollbar.
            extra=(scrollbar.sizeHint().height()
                   if area is self.header_scroll and scrollbar.maximum()>scrollbar.minimum()
                   else 0)
            desired=base_height+(12 if area is self.header_scroll else 6)+extra
            if area.height()!=desired:
                area.setFixedHeight(desired)
            area.updateGeometry()
        self.sync_player_button_arrows()

    def error(self,message):
        self.status.setText(message); QMessageBox.warning(self,'DizyTV',message)
    def load_guide(self):
        path=self.store.directory/'guide.json'
        try:
            if path.exists() and path.stat().st_size<=100*1024**2:
                self.guide=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    def change_channel_sort(self,mode):
        if mode not in CHANNEL_SORT_MODES:return
        if self.store.read()['settings'].get('channel_sort')!=mode:
            self.state=self.store.update(lambda state:state['settings'].update(channel_sort=mode))
        self._tree_dirty=True
        self.render_channels()

    def refresh_disabled_channels(self,*_):
        self._tree_dirty=True
        self.render_channels()
        dlg=getattr(self,'global_search_dialog',None)
        if dlg is not None and dlg.isVisible():
            dlg.refresh_catalogue()

    def toggle_channel_visibility(self):
        if not self.selected:
            self.status.setText('Select a channel to hide or restore.')
            return
        cid=self.selected['id']
        current=cid in set(self.store.read().get('disabled_channels',()))
        label=display_channel_name(self.selected['name'])
        def change(state):
            hidden=set(state.get('disabled_channels',()))
            if cid in hidden:hidden.remove(cid)
            else:hidden.add(cid)
            state['disabled_channels']=sorted(hidden)
        self.store.update(change)
        self.refresh_disabled_channels()
        self.status.setText(('Restored ' if current else 'Hidden ')+label+
                            ' — use Show disabled to restore it later.')

    def open_system_usage(self):
        existing=getattr(self,'usage_dialog',None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        self.usage_dialog=SystemUsageDialog(self)
        self.usage_dialog.show()

    def open_duplicate_channels(self):
        existing=getattr(self,'duplicate_dialog',None)
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
        self.duplicate_dialog=ChannelDuplicatesDialog(self.store,self.refresh_disabled_channels,self)
        self.duplicate_dialog.show()

    def open_channel_health(self):
        dialog=getattr(self,'health_dialog',None)
        if dialog is not None and dialog.isVisible():
            dialog.raise_()
            dialog.activateWindow()
            return
        dialog=ChannelHealthDialog(self.store,self.selected,self.pool,self.refresh_disabled_channels,self)
        self.health_dialog=dialog
        dialog.show()

    def try_alternative_source(self):
        """Only user-selected saved alternatives, never redirect automatically."""
        selected=self.selected
        if not selected:
            QMessageBox.information(self,'DizyTV alternatives','Select a channel first.')
            return
        rows=independent_candidates(catalogue(self.state),selected)
        if not rows:
            QMessageBox.information(self,'DizyTV alternatives',
                'No separate saved source is available for this channel, country and programme type. '
                'A programme guide entry alone does not guarantee a playable stream.')
            return
        # Do not expose private M3U URLs or tokens in the picker.
        labels=[display_channel_name(item['name'])+' — '+
                safe_source_label((item.get('sources') or [item.get('source','')])[0])+
                ' [candidate '+str(i+1)+', not verified]' for i,item in enumerate(rows)]
        label,accepted=QInputDialog.getItem(self,'Try another saved source',
            'Choose a different imported stream; playback is not guaranteed:',
            labels,0,False)
        if not accepted:
            return
        alternate=rows[labels.index(label)]
        # Preserve existing favourites and manual EPG mappings: no state
        # mutation, and never erase the original selected channel.
        match=next((i for i in range(self.channels.count())
                    if self.channels.item(i).data(Qt.UserRole)['id']==alternate['id']),None)
        if match is None:
            # A playlist/genre/country filter may hide the selected source.
            # Reuse global search's visibility reset before changing playback.
            self.reveal_global_channel(alternate,show_guide=False)
        else:
            self.selected=alternate
            self.channels.setCurrentRow(match)
            self.render_now()
        self.play()

    def show_channel_source_details(self):
        """Show playlist provenance without exposing private URLs or tokens."""
        channel=self.selected
        if not channel:
            QMessageBox.information(self,'DizyTV channel source','Select a channel first.')
            return
        origins=list(dict.fromkeys(x for x in
                 (channel.get('sources') or [channel.get('source','')]) if x))
        labels=[safe_source_label(origin) for origin in origins] or ['Unknown source']
        message=('Channel: '+display_channel_name(channel['name'])+
                 '\nImported playlist: '+', '.join(labels)+
                 '\n\nAn EPG listing is independent of the video stream. '+
                 'A working guide does not establish a working playback URL. '+
                 'Network errors do not prove a feed is permanently dead. '+
                 'Custom provider URLs and credentials are hidden.')
        QMessageBox.information(self,'DizyTV — Channel source details',message)

    def show_source_status(self):
        state=self.store.read(); counts={}
        for ch in state['channels']:
            for key in set(ch.get('sources') or
                           [ch.get('source','https://search-ace.stream/playlist')]):
                counts[key]=counts.get(key,0)+1
        lines=['Saved unique channels per configured playlist (not guaranteed playable):']
        for url in configured_playlists(state['settings']):
            lines.append(f'{source_label(url)}: {counts.get(url,0)}')
        lines.append('Zero means none saved from that source. Click Refresh channels to retry.')
        if self.source_errors:
            lines.append('Last refresh failures (old cache preserved when possible):')
            lines.extend(self.source_errors)
        QMessageBox.information(self,'DizyTV playlist import status','\n'.join(lines))

    def guide_index(self):
        # 85,000+ XMLTV entries were being re-scanned for each filter change
        # and each periodic EPG redraw. Cache by guide object identity and
        # invalidate naturally when Refresh guide replaces the guide dict.
        if getattr(self, '_indexed_guide', None) is not self.guide:
            by_channel={}
            genres={}
            for programme in self.guide['programmes']:
                cid=programme['channel']
                by_channel.setdefault(cid,[]).append(programme)
                categories=programme.get('categories',[])
                if categories:
                    genres.setdefault(cid,set()).update(normalise_genre(c) for c in categories)
            self._programme_by_channel=by_channel
            self._genre_by_channel=genres
            self._guide_name_lookup=guide_lookup(self.guide['names'])
            self._indexed_guide=self.guide
        return self._programme_by_channel,self._genre_by_channel

    def matched_guide(self,ch):
        self.guide_index()
        return match_guide(ch,self.state['mappings'],self.guide['names'],self._guide_name_lookup)

    def build_country_tree(self,channels):
        if not self._tree_dirty:return
        self.country_tree.blockSignals(True)
        self.country_tree.setUpdatesEnabled(False)
        try:
            self.country_tree.clear()
            self._tree_generation=getattr(self,'_tree_generation',0)+1
            self._tree_children={}
            groups={}
            for ch in channels:
                country=ch.get('country') or 'Unspecified'
                section=channel_section(ch)
                groups.setdefault(country,{}).setdefault(section,[]).append(ch)
            lazy=len(channels)>3000
            for country in sorted(groups,key=lambda c:(c=='Unspecified',c.casefold())):
                sections=groups[country]
                total=sum(len(values) for values in sections.values())
                country_item=QTreeWidgetItem([f'{country} ({total})'])
                country_item.setData(0,Qt.UserRole,('country',country,'',''))
                self.country_tree.addTopLevelItem(country_item)
                for section in sorted(sections):
                    values=sections[section]
                    section_item=QTreeWidgetItem([f'{section} ({len(values)})'])
                    section_item.setData(0,Qt.UserRole,('section',country,section,''))
                    country_item.addChild(section_item)
                    if lazy:
                        # Populating thousands of nested QTreeWidgetItems during
                        # each import previously froze the UI for several seconds.
                        # Load only an expanded section and yield every 250 rows.
                        self._tree_children[(country,section)]=values
                        section_item.addChild(QTreeWidgetItem(['Expand to browse channels…']))
                    else:
                        for ch in sorted(values,key=lambda c:display_channel_name(c['name']).casefold()):
                            leaf=QTreeWidgetItem([display_channel_name(ch['name'])])
                            leaf.setData(0,Qt.UserRole,('channel',country,section,ch['id']))
                            section_item.addChild(leaf)
                country_item.setExpanded(country in ('United Kingdom','United States'))
            self._tree_dirty=False
        finally:
            self.country_tree.setUpdatesEnabled(True)
            self.country_tree.blockSignals(False)

    def populate_expanded_section(self,item):
        data=item.data(0,Qt.UserRole)
        if not data or data[0]!='section':return
        _,country,section,_=data
        key=(country,section)
        values=getattr(self,'_tree_children',{}).pop(key,None)
        if values is None:return
        generation=self._tree_generation
        item.takeChildren()  # discard the one placeholder
        ordered=sorted(values,key=lambda c:display_channel_name(c['name']).casefold())
        def fill(start=0):
            if generation!=self._tree_generation:return
            self.country_tree.setUpdatesEnabled(False)
            try:
                for ch in ordered[start:start+250]:
                    leaf=QTreeWidgetItem([display_channel_name(ch['name'])])
                    leaf.setData(0,Qt.UserRole,('channel',country,section,ch['id']))
                    item.addChild(leaf)
            finally:
                self.country_tree.setUpdatesEnabled(True)
            if start+250<len(ordered):
                QTimer.singleShot(0,self.country_tree,lambda:fill(start+250))
        fill()

    def country_tree_clicked(self,item,*_):
        item_data=item.data(0,Qt.UserRole)
        if not item_data:return
        kind,country,section,cid=item_data
        self.country_filter.blockSignals(True)
        self.country_filter.setCurrentIndex(max(0,self.country_filter.findData(country)))
        self.country_filter.blockSignals(False)
        self.section_filter.blockSignals(True)
        self.section_filter.setCurrentIndex(max(0,self.section_filter.findData(section if kind!='country' else '')))
        self.section_filter.blockSignals(False)
        self.render_channels()
        if kind=='channel':
            for idx in range(self.channels.count()):
                candidate=self.channels.item(idx)
                if candidate.data(Qt.UserRole)['id']==cid:
                    self.channels.setCurrentItem(candidate)
                    self.channels.scrollToItem(candidate)
                    break

    def country_tree_double_clicked(self,item,*_):
        data=item.data(0,Qt.UserRole)
        if data and data[0]=='channel':
            self.country_tree_clicked(item)
            self.play()

    def render_channels(self,*_):
        previous=self.selected['id'] if self.selected else None
        self.state=self.store.read()
        source=catalogue(self.state,include_disabled=self.show_disabled.isChecked())
        disabled=set(self.state.get('disabled_channels',()))
        self.channels.blockSignals(True)
        self.channels.clear()
        sort_mode=self.sort_picker.currentText()
        source=[ch for _,ch in sorted(enumerate(source),
                    key=lambda entry:channel_sort_key(entry[1],sort_mode,entry[0]))]
        self.build_country_tree(source)
        selected_source=self.source_filter.currentData()
        urls=configured_playlists(self.state['settings'])
        counts={}
        for ch in source:
            for source_url in set(ch.get('sources') or
                                  [ch.get('source','https://search-ace.stream/playlist')]):
                counts[source_url]=counts.get(source_url,0)+1
        self.source_filter.blockSignals(True); self.source_filter.clear()
        self.source_filter.addItem('All playlists','')
        self.source_filter.addItem('HTTP/HLS (no Ace engine)','<http>')
        self.source_filter.addItem('Ace Stream only','<ace>')
        for url in urls:
            self.source_filter.addItem(f'{source_label(url)} ({counts.get(url,0)})',url)
        self.source_filter.setCurrentIndex(max(0,self.source_filter.findData(selected_source)))
        self.source_filter.blockSignals(False)
        _,genre_by_id=self.guide_index()
        for widget,key,label in ((self.country_filter,'country','All countries'),(self.genre_filter,'genre','All genres'),(self.kind_filter,'kind','All stream types')):
            chosen=widget.currentData(); values={(channel_kind(c) if key=='kind' else c.get(key,'Unspecified')) for c in source}
            if key=='genre':values.update(g for genres in genre_by_id.values() for g in genres)
            if key=='kind':values.update(c.get('transport','Ace Stream' if c['stream'].startswith('acestream:') else 'HTTP') for c in source)
            widget.blockSignals(True); widget.clear(); widget.addItem(label,'')
            for value in sorted(values):widget.addItem(value,value)
            widget.setCurrentIndex(max(0,widget.findData(chosen))); widget.blockSignals(False)
        selected_country=self.country_filter.currentData()
        selected_section=self.section_filter.currentData()
        sections={channel_section(ch) for ch in source if not selected_country or ch.get('country','Unspecified')==selected_country}
        # Always show the 24/7 category even before its optional sources load.
        sections.add('24/7 Shows & Loops')
        self.section_filter.blockSignals(True); self.section_filter.clear()
        self.section_filter.addItem('All categories','')
        for section in sorted(sections):
            self.section_filter.addItem(section,section)
        self.section_filter.setCurrentIndex(max(0,self.section_filter.findData(selected_section)))
        self.section_filter.blockSignals(False)
        query=self.search.text().casefold(); favs=set(self.state['favourites'])
        active_source=self.source_filter.currentData()
        for ch in source:
            transport=ch.get('transport','Ace Stream' if ch['stream'].startswith('acestream:') else 'HTTP')
            source_urls=ch.get('sources') or [ch.get('source','https://search-ace.stream/playlist')]
            if active_source=='<http>' and transport=='Ace Stream': continue
            if active_source=='<ace>' and transport!='Ace Stream': continue
            if active_source not in ('','<http>','<ace>') and active_source not in source_urls: continue
            if query not in (ch['name']+' '+display_channel_name(ch['name'])+' '+ch['group']).casefold() or self.favourites_only.isChecked() and ch['id'] not in favs:continue
            if self.section_filter.currentData() and channel_section(ch)!=self.section_filter.currentData():continue
            country=self.country_filter.currentData(); genre=self.genre_filter.currentData(); kind=self.kind_filter.currentData()
            if country and ch.get('country','Unspecified')!=country:continue
            if kind and kind not in (channel_kind(ch),ch.get('transport','Ace Stream' if ch['stream'].startswith('acestream:') else 'HTTP')):continue
            key=self.matched_guide(ch)
            if genre and ch.get('genre','Unspecified')!=genre and genre not in genre_by_id.get(key,set()):continue
            prefix='⛔ ' if ch['id'] in disabled else ('★ ' if ch['id'] in favs else '')
            item=QListWidgetItem(prefix+display_channel_name(ch['name']))
            item.setData(Qt.UserRole,ch)
            if ch['id'] in disabled:
                item.setToolTip('Hidden from the normal directory. Select and click Hide / restore selected.')
            self.channels.addItem(item)
            if ch['id']==previous:self.channels.setCurrentItem(item); self.selected=ch
        self.channels.blockSignals(False); self.render_guide()
    def choose_channel(self,item,*_):
        self.regional_notice.hide()
        self.selected=item.data(Qt.UserRole) if item else None; self.render_now()
    def render_now(self):
        if not self.selected:return
        cid=self.matched_guide(self.selected); now=time.time()
        by_channel,_=self.guide_index()
        items=[p for p in by_channel.get(cid,()) if p['end']>now][:2]
        self.now.setText(display_channel_name(self.selected['name'])+'\n'+'\n'.join(format_time(p['start'],self.state['settings']['timezone'],False,detected_zone())+'  '+p['title'] for p in items) if items else display_channel_name(self.selected['name'])+' — no guide match')
    def render_guide(self):
        # Pass ALL channels matching the catalogue's active filters. GuideGrid
        # paints only its visible rows; channels without EPG are retained.
        channels=[self.channels.item(i).data(Qt.UserRole) for i in range(self.channels.count())]
        genre=self.genre_filter.currentData()
        by_channel,_=self.guide_index()
        resolved={}
        guide_channels={}
        programmes=[]
        end=self.guide_start+6*3600
        for ch in channels:
            key=self.matched_guide(ch)
            resolved[ch['id']]=key
            # Alternate streams can share an EPG ID. Index its programmes once
            # so every row paints one copy, preserving the active genre union.
            guide_channels[key]=guide_channels.get(key,False) or not genre or ch.get('genre','Unspecified')==genre
        for key,all_genres in guide_channels.items():
            for p in by_channel.get(key,()):
                if not (p['start']<end and p['end']>self.guide_start):
                    continue
                if not all_genres and genre not in {normalise_genre(c) for c in p.get('categories',[])}:
                    continue
                programmes.append(p)
        self.grid.set_guide_scale(self.state['settings'].get('guide_scale',100))
        self.grid.set_data(channels,programmes,resolved,self.state['settings']['timezone'],self.guide_start)
        self.guide_date.setText(
            format_time(self.guide_start,self.state['settings']['timezone'],detected=detected_zone())+
            f'  •  {len(channels):,} selected channels')
    def move_guide(self,delta):
        self.guide_start=self.guide_start+delta if delta else int(time.time()/3600)*3600; self.render_guide()
    def apply_interface_scale(self):
        settings=self.state['settings']
        app=QApplication.instance()
        theme=settings.get('theme','Green')
        if app:app.setStyleSheet(desktop_style(settings.get('ui_scale',100),
                                               settings.get('button_size','Normal'),theme))
        self.theme_picker.blockSignals(True)
        self.theme_picker.setCurrentText(theme)
        self.theme_picker.blockSignals(False)
        self.grid.set_theme(theme)
        for rail in (self.seek_slider,self.volume_slider,self.screen_seek_slider):
            if rail is not None:rail.set_rail_theme(theme)
        if self.detached_controls is not None:
            for rail in self.detached_controls.findChildren(MediaRailSlider):
                rail.set_rail_theme(theme)
        self.style_auto_caption_overlay()
        if self.detached_controls is not None:
            self.detached_controls.setStyleSheet(
                overlay_theme_style(self._detached_base_style,theme))
        if self.screen_dialog is not None:
            self.screen_dialog.setStyleSheet(
                'QDialog#tvWindow { background:'+theme_color('#101713',theme)+'; }')
        self.channel_banner.setStyleSheet(
            'background:'+theme_color('#304d36',theme)+';color:'+
            ('#1e293b' if theme=='Light' else '#ffffff')+';padding:8px;')
        for scroll in (self.header_scroll,self.controls_scroll):
            widget=scroll.widget()
            if widget:
                widget.adjustSize()
                scroll.setFixedHeight(widget.sizeHint().height()+(12 if scroll is self.header_scroll else 6))
        QTimer.singleShot(0,self,self.settle_startup_toolbar_layout)

    def scroll_player_buttons(self,step):
        bar=self.controls_scroll.horizontalScrollBar()
        bar.setValue(max(bar.minimum(),min(bar.maximum(),bar.value()+step)))
        self.sync_player_button_arrows()

    def sync_player_button_arrows(self,*_):
        if not hasattr(self,'controls_scroll'):return
        bar=self.controls_scroll.horizontalScrollBar()
        has_overflow=bar.maximum()>bar.minimum()
        for arrow in (self.controls_prev,self.controls_next):
            arrow.setVisible(has_overflow)
        self.controls_prev.setEnabled(bar.value()>bar.minimum())
        self.controls_next.setEnabled(bar.value()<bar.maximum())

    def playback_light_state(self):
        if not self.player or not self.playback_started:
            return 'stopped'
        status=str(self.player.get_state())
        if status.endswith(('.Error','.Ended','.Stopped')):
            return 'stopped'
        if status.endswith('.Paused') or self.timeshift_lag>3:
            return 'buffering'
        if status.endswith('.Playing'):
            # Direct HTTP/HLS and Ace playback has no local timeshift watchdog.
            # Do not report an otherwise healthy Playing stream as buffering
            # just because last_good_video was set when playback started.
            if self.timeshift is None:
                return 'buffering' if self._direct_video_stalled else 'live'
            return 'live' if time.monotonic()-self.last_good_video<18 else 'buffering'
        return 'buffering'

    def pulse_live_light(self):
        """Pulse ONLY the small green dot; keep the LIVE button steady.

        Amber means buffering, paused, or behind LIVE; red means stopped or
        error. Unlike the old implementation neither warning state flashes.
        Avoid reapplying unchanged button styles on every timer tick, which
        causes distracting button-wide repainting on Windows.
        """
        state=self.playback_light_state()
        self.light_phase=not self.light_phase
        colours={'live':'#3cdb80','buffering':'#f2b450','stopped':'#f26a60'}
        bright=colours[state]
        dot_colour=('#247744' if not self.light_phase else bright) if state=='live' else bright
        hint={'live':'Playing at LIVE',
              'buffering':'Buffering, paused or watching behind LIVE',
              'stopped':'Stopped / stream error'}[state]
        for label in (self.live_light,self.popout_live_light):
            if label is not None:
                label.setText('●')
                style='QLabel {background:transparent;color:'+dot_colour+';font-size:16px;font-weight:bold;}'
                if label.styleSheet()!=style:label.setStyleSheet(style)
                if label.toolTip()!=hint:label.setToolTip(hint)
        background={'live':'rgba(16,55,33,200)',
                    'buffering':'rgba(63,43,14,200)',
                    'stopped':'rgba(67,25,27,200)'}[state]
        steady_style=('QPushButton {border:1px solid '+bright+';'
                      'background:'+background+';font-weight:700;'
                      'color:'+bright+';}')
        for button in (self.live_button,self.popout_live_button):
            if button is not None:
                if button.styleSheet()!=steady_style:button.setStyleSheet(steady_style)
                if button.toolTip()!=hint:button.setToolTip(hint)

    def video_output_warning(self):
        """Inspect actual video and audio counters without restarting playback."""
        if not self.player or not self.playback_started:
            return None
        media=None
        try:
            import vlc
            media=self.player.get_media()
            if media is None:return None
            stats=vlc.MediaStats()
            if not media.get_stats(stats):return None
            tracks=self.player.video_get_track_count()
            size=self.player.video_get_size(0)
            if not isinstance(size,tuple) or len(size)!=2:size=None
            return diagnose_video_output(
                int(stats.decoded_audio),int(stats.decoded_video),
                int(stats.displayed_pictures),tracks if tracks>=0 else None,size)
        except (AttributeError,TypeError,RuntimeError,OSError):
            return None
        finally:
            if media is not None:media.release()

    def media_activity(self,video_only=False):
        """VLC's decoded picture/audio counters catch freezes with State.Playing.

        Older VLC builds may not provide stats; do not guess in that case.
        """
        media=None
        try:
            import vlc
            media=self.player.get_media()
            if media is None:return None
            stats=vlc.MediaStats()
            if not media.get_stats(stats):return None
            if video_only:return int(stats.displayed_pictures)
            return int(stats.displayed_pictures)+int(stats.played_abuffers)
        except (AttributeError,TypeError,RuntimeError,OSError):
            return None
        finally:
            if media is not None:media.release()

    def check_direct_playback(self,now=None):
        """Warn about frozen HTTP video without retrying or touching Ace sessions.

        Audio may keep advancing while the last video frame is frozen. Only
        observe displayed pictures, after this session has displayed a frame;
        unavailable stats and an intentional pause are not evidence of a stall.
        """
        now=time.monotonic() if now is None else now
        active=(self.player and self.playback_started and self.timeshift is None
                and self._active_direct_video
                and str(self.player.get_state()).endswith('.Playing'))
        frames=self.media_activity(video_only=True) if active else None
        if frames is None or frames<=0:
            self._direct_video_sample=None
            self._direct_video_progress=now
            self._direct_video_stalled=False
            return
        if frames!=self._direct_video_sample:
            self._direct_video_sample=frames
            self._direct_video_progress=now
            self._direct_video_stalled=False
        elif now-self._direct_video_progress>=18 and not self._direct_video_stalled:
            self._direct_video_stalled=True
            self.status.setText('Video frame counter stopped advancing for 18 seconds. '
                                'The source, segments or video output may be stalled; '
                                'try another feed or check System usage decoder counters.')

    def check_live_timeshift(self,now=None):
        """Recover VLC buffering/errors only if the local cache is still growing.

        Never interrupt user pause, replay, or a scheduled recording.
        """
        if (self.timeshift is None or self.timeshift_task is not None
                or self.player is None or not self.playback_started):
            return
        now=time.monotonic() if now is None else now
        entries=self.timeshift.window.snapshot()
        if not entries:return
        if entries[-1].seq!=self.last_capture_seq:
            self.last_capture_seq=entries[-1].seq
            self.last_capture_progress=now
        status=str(self.player.get_state())
        if status.endswith('.Paused'):
            self.last_good_video=now
            return
        playing=status.endswith('.Playing')
        if playing:
            frames=self.media_activity()
            if frames is None:
                self.last_good_video=now
                return
            if frames!=self._last_media_activity:
                self._last_media_activity=frames
                self.last_good_video=now
                return
        if now-self.last_capture_progress>25:
            self.seek_notice.setText('Timeshift capture is not receiving new video. Source may be offline; you can switch to direct LIVE.')
            return
        if (self.timeshift_lag==0 and now-self.last_good_video>=18
                and now-self.last_live_recovery>=45
                and (playing or status.endswith('.Buffering') or status.endswith('.Error')
                     or status.endswith('.Ended'))):
            # Reconnecting the player does not stop or erase the capture ring.
            # A moving Vosk holdback remains held back after recovery; never
            # silently switch a synced viewer to the unbuffered LIVE endpoint.
            if self._active_holdback_ms:
                if len(self.timeshift.window.holdback_entries(
                        self._active_holdback_ms/1000))<3:
                    self.seek_notice.setText('Vosk video buffer refilling; waiting for playable fragments.')
                    return
                target=self.timeshift.holdback_url(self._active_holdback_ms/1000)
            else:
                target=self.timeshift.live_url()
            self.last_live_recovery=now
            self.last_good_video=now
            self.play_url(target,preserve_captions=self._auto_caption_worker is not None)
            if not self.playback_started:
                self.stop_auto_captions()
                return
            self.status.setText('Recovered stalled buffered TV playback'+
                                (' while preserving Vosk video delay.' if self._active_holdback_ms
                                 else ' to LIVE.'))

    def stop_caption_on_terminal_playback(self):
        """Hide stale Vosk text if the current source has actually ended.

        Never interfere with recoverable timeshift buffering: the DVR watchdog
        can reconnect a held-back stream as long as new fragments arrive.
        """
        if self._auto_caption_worker is None or self._auto_caption_stopping:
            return
        if not self.player or not self.playback_started:
            self.stop_auto_captions()
            return
        try:status=str(self.player.get_state())
        except (AttributeError,OSError,RuntimeError):return
        terminal=(status.endswith('.Ended') or status.endswith('.Error')
                  or status.endswith('.Stopped'))
        if not terminal:
            return
        if (self.timeshift is not None and self.timeshift_task is None
                and self.timeshift_lag==0):
            if time.monotonic()-self.last_capture_progress<=25:
                return  # Moving holdback or live DVR watchdog can recover.
        # Fixed replay does not have an automatic reconnect path; stop Vosk
        # rather than reading ahead on an ended or failed video.
        self.stop_auto_captions()
        self.status.setText('Stream playback ended; offline speech captions stopped.')

    def tick(self):
        # Detached recording workers hold a cross-process state lock while
        # writing. The five-second Qt timer must not wait behind that lock.
        snapshot=self.store.try_read()
        if snapshot is not None:
            self.state=snapshot
        zone=self.state['settings']['timezone']
        label=('Auto: '+detected_zone() if zone=='auto' else zone); local=format_time(time.time(),zone,False,detected_zone()); key=label+' '+local.rsplit(' ',1)[-1]
        self.timezone_label.setText(label+' • '+local)
        if key!=self.displayed_zone:self.displayed_zone=key; self.render_guide()
        self.render_now(); self.jobs.setRowCount(len(self.state['jobs']))
        for row,job in enumerate(self.state['jobs']):
            values=[job['title'],format_time(job['start'],zone,detected=detected_zone()),format_time(job['end'],zone,detected=detected_zone()),job['status'],f"{job.get('bytes',0)/1024**2:.1f} MiB"]
            for col,value in enumerate(values):
                item=QTableWidgetItem(value); item.setToolTip(job.get('error','')); self.jobs.setItem(row,col,item)
        self.grid.update()
        self.check_live_timeshift()
        self.check_direct_playback()
        self.sync_subtitles()
        self.stop_caption_on_terminal_playback()
        if self._auto_caption_overlay is not None and time.monotonic()-self._auto_caption_updated>6:
            self._auto_caption_overlay.hide()
        if self.player and self.playback_started:
            local_active=self.timeshift is not None and bool(self.timeshift.window.snapshot())
            seekable=bool(self.player.is_seekable()) or local_active
            length=self.player.get_length()
            position=self.player.get_time()
            self.seek_slider.setEnabled(local_active or (seekable and length>0))
            if seekable and length>0 and position>=0 and not self.seek_slider.isSliderDown():
                self.seek_slider.setValue(max(0,min(1000,int(position*1000/length))))
            if self.screen_seek_slider is not None:
                self.screen_seek_slider.setEnabled(local_active or (seekable and length>0))
                if seekable and length>0 and position>=0 and not self.screen_seek_slider.isSliderDown():
                    self.screen_seek_slider.setValue(max(0,min(1000,int(position*1000/length))))
            self.rewind_button.setEnabled(seekable)
            self.forward_button.setEnabled(seekable)
            self.pause_button.setEnabled(seekable)
            if local_active:
                available=self.timeshift.window.latest_seconds()
                self.seek_notice.setText('Device buffer: '+str(int(available//60))+' min cached of '+str(self.timeshift.window.minutes)+' min / '+str(round(self.timeshift.window.total/1024**3,2))+' GiB; max '+str(round(self.timeshift.window.max_bytes/1024**3,1))+' GiB')
                if not self.seek_slider.isSliderDown():
                    self.seek_slider.setValue(max(0,1000-int(self.timeshift_lag/max(1,available)*1000)))
            else:
                # VLC can retain seekable state from an earlier failed stream.
                state_name=str(self.player.get_state())
                if not state_name.endswith(('.Playing','.Paused')):
                    self.seek_notice.setText('Playback not confirmed — seekability is not decoded video.')
                else:
                    self.seek_notice.setText('DVR seeking supported (picture not verified)' if seekable else 'LIVE — no local time-shift enabled')
        # VLC can be in State.Playing with audible audio and a black video
        # surface. Inspect decoded/displayed frames separately after startup.
        if (self.player and self.playback_started and not self._video_issue_notified
                and time.monotonic()-self.playback_started>=15
                and str(self.player.get_state()).endswith('.Playing')
                and (not self.selected or channel_kind(self.selected)!='Radio')):
            warning=self.video_output_warning()
            if warning:
                self._video_issue_notified=True
                self.status.setText('Video diagnostic: '+warning)
        # A recovered stream must clear an earlier access-denied notice.
        if (self.regional_notice.isVisible() and self.player and self.playback_started
                and str(self.player.get_state()).endswith('.Playing')):
            self.regional_notice.hide()
        if self.player and self.playback_started and not self.playback_reported:
            state=str(self.player.get_state())
            if state.endswith('.Playing'):
                self.playback_reported=True
                if not self._video_issue_notified:self.status.setText('Now playing inside DizyTV')
            elif state.endswith('.Error') or state.endswith('.Ended'):
                self.playback_reported=True
                from .core import ace_id
                if self.selected and ace_id(self.selected['stream']):
                    # Do not replace a genuine VLC failure with a misleading
                    # green "Ace Engine port 6878 is open" diagnostic.
                    self.status.setText('Ace Engine provided a stream, but VLC could not decode/play it. '
                                        'Check channel peers, engine playback and VLC 3 x64.')
                else:
                    self.status.setText('VLC could not play this source. Checking the provider response…')
                    if self.timeshift is None:self.diagnose_stream()
            elif time.monotonic()-self.playback_started>25:
                self.playback_reported=True
                from .core import ace_id
                if self.selected and ace_id(self.selected['stream']):
                    self.status.setText('Ace stream has not produced playable video after 25 seconds. '
                                        'The engine port alone does not prove the channel has peers or decodable media.')
                else:
                    self.status.setText('Stream did not begin within 25 seconds; checking host response…')
                    if self.timeshift is None:self.diagnose_stream()
    def async_task(self,function,success):
        if self.task:self.status.setText('A refresh is already running'); return
        self.task=Task(function)
        def done(result):
            self.task=None
            try:success(result)
            except (ValueError,OSError) as exc:fail(str(exc))
        def fail(message):self.task=None; self.status.setText('Refresh failed — cached data retained: '+message)
        self.task.signals.success.connect(done); self.task.signals.failure.connect(fail); self.pool.start(self.task)
    def refresh_channels(self):
        current=self.store.read(); self.status.setText('Importing free channel sources…')
        def done(result):
            channels,success,errors=result
            self.source_errors=errors
            if success:
                self.store.update(lambda s:s.update(channels=channels))
                self._tree_dirty=True
            self.render_channels()
            self.status.setText(f'{len(channels)} channels • {success} sources refreshed'+(f' • {len(errors)} failed (open Source status)' if errors else '')+' • use playlist filter to view free HTTP/HLS')
            if not self.guide['programmes'] and self.state['settings']['xmltv_urls']:
                QTimer.singleShot(300,self.refresh_guide)
        self.async_task(lambda:refresh_catalogue(current['settings'],current['channels'],download),done)
    def refresh_guide(self):
        settings=self.store.read()['settings']
        if not settings['xmltv_urls']:self.error('Add one or more XMLTV URLs in Settings'); return
        self.status.setText('Importing XMLTV guide…')
        def fetch():
            names={}; programmes=[]; errors=[]
            for url in settings['xmltv_urls']:
                try:
                    n,p=parse_xmltv(download(url),settings['epg_offset_minutes'])
                    names.update(n); programmes.extend(p)
                except Exception as exc:
                    errors.append(type(exc).__name__)
            if not names and not programmes:
                raise ValueError(f'All {len(settings["xmltv_urls"])} guide sources failed; cached guide retained')
            return {'names':names,'programmes':sorted(programmes,key=lambda p:(p['channel'],p['start']))}, errors
        def done(result):
            guide, errors=result
            atomic_json(self.store.directory/'guide.json',guide); self.guide=guide; self.render_channels(); self.render_now()
            self.status.setText(f"Imported {len(guide['programmes'])} programmes"+(f" • {len(errors)} guide source(s) failed" if errors else '')+" • timers unchanged")
        self.async_task(fetch,done)
    def choose_theme(self,theme):
        if theme not in ('Green','Dark','Light'):return
        if self.store.read()['settings'].get('theme','Green')!=theme:
            self.state=self.store.update(lambda s:s['settings'].update(theme=theme))
        self.apply_interface_scale()

    def settings(self):
        dialog=Settings(self.store.read(),self)
        if dialog.exec()==QDialog.Accepted:
            try:
                before=self.state['settings']
                updated=dialog.values()
                self.store.update(lambda s:s.update(settings=updated))
                self.state=self.store.read()
                self.apply_interface_scale()
                # Preserve a manually selected SRT or broadcast track on pure
                # appearance edits, but reset selection after disabling /
                # re-enabling or changing the requested caption language.
                if (before.get('subtitles_enabled',True)!=updated.get('subtitles_enabled',True)
                        or before.get('subtitle_language','Auto')!=updated.get('subtitle_language','Auto')):
                    self._subtitle_manual_track=None
                self._subtitle_auto_applied=False
                self._subtitle_track_signature=()
                self.sync_subtitles()
                self.render_guide()
                self.tick()
                if (self.player is not None and
                        before.get('vlc_decoder','Auto')!=updated.get('vlc_decoder','Auto')):
                    self.status.setText('VLC video decoding saved ('+updated['vlc_decoder']+'). Restart DizyTV to apply; active playback was not interrupted.')
                elif self._vlc_subtitle_profile is not None and tuple(vlc_subtitle_options(self.state['settings']))!=self._vlc_subtitle_profile:
                    self.status.setText('Subtitle appearance saved; new font, size, colour and position apply after restarting DizyTV.')

            except ValueError as exc:self.error(str(exc))
    def favourite(self):
        if not self.selected:return
        cid=self.selected['id']
        def change(s):
            if cid in s['favourites']:s['favourites'].remove(cid)
            else:s['favourites'].append(cid)
        self.store.update(change); self.render_channels()
    def edit_categories(self):
        if not self.selected:return
        channel=self.selected; dialog=QDialog(self); dialog.setWindowTitle('Categories — '+channel['name']); layout=QFormLayout(dialog)
        country=QComboBox(); country.setEditable(True); country.addItems(['Unspecified']+sorted(set(COUNTRIES.values()))); country.setCurrentText(channel.get('country','Unspecified'))
        genre=QComboBox(); genre.setEditable(True); genre.addItems(['Unspecified']+[g for g,_ in GENRES]); genre.setCurrentText(channel.get('genre','Unspecified'))
        kind=QComboBox(); kind.addItems(['TV','Radio']); kind.setCurrentText(channel.get('kind','TV'))
        layout.addRow('Country',country); layout.addRow('Genre',genre); layout.addRow('Stream type',kind)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel|QDialogButtonBox.Reset); layout.addRow(buttons)
        reset=[False]
        def source_categories():reset[0]=True; dialog.accept()
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); buttons.button(QDialogButtonBox.Reset).setText('Use source categories'); buttons.button(QDialogButtonBox.Reset).clicked.connect(source_categories)
        if dialog.exec()==QDialog.Accepted:
            def change(s):
                overrides=s.setdefault('category_overrides',{})
                if reset[0]:overrides.pop(channel['id'],None)
                else:overrides[channel['id']]={'country':country.currentText().strip() or 'Unspecified','genre':normalise_genre(genre.currentText()),'kind':kind.currentText()}
            try:self.store.update(change); self._tree_dirty=True; self.render_channels(); self.status.setText('Categories saved • kept across refresh and backup')
            except ValueError as exc:self.error(str(exc))
    def map_channel(self):
        if not self.selected:return
        dialog=QDialog(self)
        dialog.setWindowTitle('Map EPG — '+display_channel_name(self.selected['name']))
        dialog.resize(680,520)
        layout=QVBoxLayout(dialog)
        label=QLabel('Choose the correct XMLTV station. Similar names are suggestions only; '
                     'regional schedules must be selected explicitly.',dialog)
        label.setWordWrap(True);layout.addWidget(label)
        query=QLineEdit(dialog)
        query.setObjectName('epgMappingSearch')
        query.setPlaceholderText('Search XMLTV channel names or IDs…')
        layout.addWidget(query)
        results=QListWidget(dialog)
        results.setObjectName('epgMappingOptions')
        layout.addWidget(results,1)
        suggestions=guide_suggestions(self.selected,self.guide['names'])
        suggested_keys={key for key,_ in suggestions}
        choices=[('', 'No mapping (leave guide blank)', False)]
        choices.extend((key,name,True) for key,name in suggestions)
        choices.extend((key,name,False) for key,name in
                       sorted(self.guide['names'].items(),key=lambda x:(x[1].casefold(),x[0].casefold()))
                       if key not in suggested_keys)
        for key,name,suggested in choices:
            text=('★ Suggested: ' if suggested else '')+name+('  ·  '+key if key else '')
            item=QListWidgetItem(text)
            item.setData(Qt.UserRole,key)
            results.addItem(item)
        def filter_options(text):
            needle=text.strip().casefold()
            first=None
            for index in range(results.count()):
                item=results.item(index)
                visible=needle in item.text().casefold()
                item.setHidden(not visible)
                if visible and first is None:first=item
            if first is not None:results.setCurrentItem(first)
            else:results.clearSelection()
        query.textChanged.connect(filter_options)
        existing=self.state['mappings'].get(self.selected['id'])
        start=next((index for index,option in enumerate(choices) if option[0]==existing),0)
        results.setCurrentRow(start)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel,dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec()==QDialog.Accepted:
            selected=results.currentItem()
            if selected is None or selected.isHidden():return
            cid=self.selected['id'];target=selected.data(Qt.UserRole)
            self.store.update(lambda s:s['mappings'].update({cid:target}))
            self.state=self.store.read()
            self.render_guide();self.render_now()
    def create_auto_caption_overlay(self):
        if self._auto_caption_overlay is not None:return
        native=(os.name=='nt' and os.environ.get('QT_QPA_PLATFORM')!='offscreen')
        if native:
            parent=self.screen_dialog or self
            overlay=QDialog(parent,Qt.Tool|Qt.FramelessWindowHint|Qt.WindowTransparentForInput)
            overlay.setAttribute(Qt.WA_TranslucentBackground,True)
            overlay.setAttribute(Qt.WA_ShowWithoutActivating,True)
            content=QVBoxLayout(overlay)
            content.setContentsMargins(0,0,0,0)
        else:
            overlay=QFrame(self.video)
            overlay.setAttribute(Qt.WA_TransparentForMouseEvents,True)
            content=QVBoxLayout(overlay)
            content.setContentsMargins(0,0,0,0)
        overlay.setObjectName('autoCaptionOverlay')
        caption=QLabel(overlay)
        caption.setObjectName('autoCaptionText')
        caption.setTextFormat(Qt.PlainText)
        caption.setWordWrap(True)
        caption.setAlignment(Qt.AlignCenter)
        content.addWidget(caption)
        self._auto_caption_overlay=overlay
        self._auto_caption_label=caption
        self.style_auto_caption_overlay()
        self.position_auto_caption_overlay()

    def style_auto_caption_overlay(self):
        label=self._auto_caption_label
        if label is None:return
        settings=self.state['settings']
        rgb=COLOURS.get(settings.get('subtitle_colour','White'),'0xFFFFFF')
        colour='#'+rgb[2:]
        backdrop='rgba(255,255,255,222)' if colour=='#000000' else 'rgba(0,0,0,190)'
        font={'Sans':'Arial','Serif':'Georgia','Monospace':'Consolas'}.get(
            settings.get('subtitle_font','Sans'),'Arial')
        size=settings.get('subtitle_size',20)
        label.setStyleSheet(
            'QLabel#autoCaptionText {font-family:"'+font+'";font-size:'+str(size)+'px;'
            'font-weight:700;color:'+colour+';background:'+backdrop+';'
            'border-radius:10px;padding:10px 18px;}')
        self.position_auto_caption_overlay()

    def position_auto_caption_overlay(self):
        overlay=self._auto_caption_overlay
        if overlay is None or self.video.width()<1 or self.video.height()<1:return
        size=self.state['settings'].get('subtitle_size',20)
        width=max(100,int(self.video.width()*.86))
        height=max(64,min(self.video.height()//2,size*3+26))
        margin=POSITIONS.get(self.state['settings'].get('subtitle_position','Bottom'),16)
        x=max(0,(self.video.width()-width)//2)
        y=max(0,self.video.height()-height-margin)
        overlay.resize(width,height)
        if isinstance(overlay,QDialog):
            overlay.move(self.video.mapToGlobal(QPoint(x,y)))
        else:
            overlay.move(x,y)

    def destroy_auto_caption_overlay(self):
        overlay=self._auto_caption_overlay
        self._auto_caption_overlay=None
        self._auto_caption_label=None
        if overlay is not None:
            overlay.hide()
            overlay.close()
            overlay.deleteLater()

    def receive_auto_caption(self,serial,text):
        if serial!=self._auto_caption_seq or self._auto_caption_worker is None:return
        text=caption_text(text)
        if not text:return
        self._auto_caption_queue.push(text,round(time.monotonic()*1000))
        self.poll_auto_caption_queue()

    def poll_auto_caption_queue(self):
        if self._auto_caption_worker is None or self._auto_caption_stopping:return
        delay=self.state['settings'].get('auto_caption_delay_ms',0)
        text=self._auto_caption_queue.pop_due(round(time.monotonic()*1000),delay)
        if text is not None:
            self.show_auto_caption_text(text)

    def show_auto_caption_text(self,text):
        self._auto_caption_text=text
        self._auto_caption_updated=time.monotonic()
        self.create_auto_caption_overlay()
        self._auto_caption_label.setText(text)
        self.position_auto_caption_overlay()
        self._auto_caption_overlay.show()
        self._auto_caption_overlay.raise_()
        # On Windows both caption text and pop-out controls are native tool
        # windows. Keep controls above arriving caption updates while visible.
        if (self.screen_dialog is not None and self.detached_controls is not None
                and self.detached_controls.isVisible()):
            self.detached_controls.raise_()

    def change_auto_caption_delay(self,change_ms=None):
        """Live adjustment of Vosk text ONLY; VLC broadcast captions stay untouched."""
        old=self.store.read()['settings'].get('auto_caption_delay_ms',0)
        delay=0 if change_ms is None else max(0,min(10000,old+change_ms))
        self.state=self.store.update(lambda s:s['settings'].update(auto_caption_delay_ms=delay))
        self.poll_auto_caption_queue()
        self.status.setText('Local Vosk subtitle delay: '+str(delay)+' ms. '
                            '0 ms shows recognised words immediately. '
                            'A separate speech connection cannot anticipate audio.')

    def auto_caption_finished(self,serial,reason):
        # Invalidate old Qt signals immediately; this also removes the overlay
        # even if FFmpeg exits spontaneously after a source stops.
        if serial!=self._auto_caption_worker_serial:return
        was_stopping=self._auto_caption_stopping
        queued_restart=self._auto_caption_restart_requested
        current=(serial==self._auto_caption_seq)
        self._auto_caption_worker=None
        self._auto_caption_worker_serial=None
        self._auto_caption_stopping=False
        self._auto_caption_restart_requested=False
        self._auto_caption_signals=None
        self._auto_caption_timer.stop()
        self._auto_caption_queue.clear()
        self._auto_caption_text=''
        self.destroy_auto_caption_overlay()
        if queued_restart and not current and self.player and self.playback_started:
            QTimer.singleShot(0,self.toggle_auto_captions)
        elif current and not was_stopping and self._auto_caption_retry_budget>0:
            # Unexpected FFmpeg loss: bounded retries, never infinite reconnect
            # loops. The retry checks the same session and requires live video.
            QTimer.singleShot(2500,lambda:self.retry_auto_captions(serial))
            if reason:self.status.setText(reason+' Retrying Vosk if video is still playing…')
        elif reason and not was_stopping:self.status.setText(reason)

    def retry_auto_captions(self,serial):
        if (serial!=self._auto_caption_seq or self._auto_caption_worker is not None
                or not self.player or not self.playback_started
                or self._auto_caption_retry_budget<=0):
            return
        try:state=str(self.player.get_state())
        except (AttributeError,OSError,RuntimeError):return
        if not state.endswith('.Playing'):
            return
        self._auto_caption_retry_budget-=1
        self.toggle_auto_captions(automated=True)

    def stop_auto_captions(self):
        self._auto_caption_restart_requested=False
        self._auto_caption_retry_budget=0
        self._auto_caption_seq+=1
        self._auto_caption_timer.stop()
        self._auto_caption_queue.clear()
        worker=self._auto_caption_worker
        if worker is not None:
            self._auto_caption_stopping=True
            worker.stop()
        self._auto_caption_text=''
        self.destroy_auto_caption_overlay()

    def toggle_auto_captions(self, automated=False):
        if self._auto_caption_worker is not None:
            if self._auto_caption_stopping:
                self._auto_caption_restart_requested=True
                self.status.setText('Restarting Vosk automatically when the previous speech worker finishes cleanup…')
                return
            self.stop_auto_captions()
            self.status.setText('Stopping local speech captions; waiting for speech model cleanup…')
            return
        if not self.player or not self.playback_started or not self._playback_url:
            self.status.setText('Play a live channel before starting local speech captions.')
            return
        try:play_state=str(self.player.get_state())
        except (AttributeError,OSError,RuntimeError):play_state=''
        if play_state.endswith(('.Stopped','.Ended','.Error')):
            self.status.setText('The stream is stopped; restart playback before generating Vosk captions.')
            return
        settings=self.state['settings']
        language=settings.get('auto_caption_language','English (bundled)')
        model_override=settings.get('auto_caption_model_dir','') if language=='English (bundled)' else ''
        if language!='English (bundled)':
            installed=installed_language_model(language)
            if installed is None:
                self.status.setText('Offline '+language+' model not installed. '
                                    'Open Settings → Optional Vosk languages and download it first.')
                return
            model_override=str(installed)
        # When timeshift is playing a local loopback URL, the external FFmpeg
        # audio reader needs the original source, not a short buffer segment.
        caption_source=(self.timeshift.source if self.timeshift is not None else self._playback_url)
        try:
            ffmpeg,model=verify_caption_engine(model_override,
                                               settings.get('auto_caption_ffmpeg_path',''))
        except (ValueError,OSError) as exc:
            self.status.setText('Local captions unavailable: '+str(exc)+
                                ' Open Settings to check optional model/FFmpeg overrides.')
            return
        if not automated:
            self._auto_caption_retry_budget=2
        self._auto_caption_seq+=1
        serial=self._auto_caption_seq
        signals=CaptionSignals(self)
        signals.caption.connect(self.receive_auto_caption)
        signals.finished.connect(self.auto_caption_finished)
        self._auto_caption_signals=signals
        def safe_caption(text):
            try:signals.caption.emit(serial,text)
            except RuntimeError:pass  # Window was closed while worker was stopping.
        def safe_finished(reason):
            try:signals.finished.emit(serial,reason)
            except RuntimeError:pass
        worker=LocalCaptionWorker(ffmpeg,caption_source,model,safe_caption,safe_finished)
        self._auto_caption_worker=worker
        self._auto_caption_worker_serial=serial
        self._auto_caption_stopping=False
        self.status.setText('Starting '+language+' offline captions (local FFmpeg + Vosk). '
                            'Listening for speech; captions may take several seconds. '
                            'Second source connection; no microphone or cloud speech.')
        self._auto_caption_started_at=time.monotonic()
        self._auto_caption_queue.clear()
        self._auto_caption_timer.start()
        # Show a visible acknowledgment that auto CC was selected. Only actual
        # recognition results replace this text; it is not fabricated dialogue.
        self.create_auto_caption_overlay()
        self._auto_caption_label.setText('Preparing offline subtitles…')
        self._auto_caption_updated=time.monotonic()
        self.position_auto_caption_overlay()
        self._auto_caption_overlay.show()
        self._auto_caption_overlay.raise_()
        worker.start()
        QTimer.singleShot(12000,lambda:self.caption_waiting_status(serial))

    def caption_waiting_status(self,serial):
        if (serial==self._auto_caption_seq and self._auto_caption_worker is not None
                and not self._auto_caption_text and not self._auto_caption_stopping):
            self.status.setText('Offline captions are running but no speech has been recognised '
                                'yet. Check audible dialogue and that FFmpeg can access this '
                                'stream; music or audio-only restrictions may prevent text.')
            if self._auto_caption_label is not None:
                self._auto_caption_label.setText('Listening for dialogue…')
                self._auto_caption_updated=time.monotonic()
                self._auto_caption_overlay.show()

    def sync_subtitles(self):
        """Use the embedded subtitle stream without another video connection.

        Transport manifests may reveal subtitle tracks after playback begins,
        so a cheap periodic scan is safer than a one-shot lookup on Play.
        """
        if not self.player or not self.playback_started:return
        # The VLC decoder may re-enable an embedded caption track AFTER a
        # buffered retune starts, even if video_set_spu(-1) succeeded earlier.
        # Keep Off pending until tracks are available, and retry when the
        # decoder's selection or track signature changes.
        if (self._subtitle_session_all_off or self._subtitle_manual_track==-1 or
                not self.state['settings'].get('subtitles_enabled',True)):
            tracks=subtitle_tracks(self.player)
            signature=tuple(tracks)
            try:
                current=self.player.video_get_spu()
                if (current!=-1 or not self._subtitle_auto_applied or
                        signature!=self._subtitle_track_signature):
                    accepted=self.player.video_set_spu(-1)==0
                    # A decoder without published tracks is not yet ready;
                    # check again on the next timer, even if it returned 0.
                    self._subtitle_auto_applied=accepted and bool(tracks)
                    self._subtitle_track_signature=signature
            except (AttributeError,OSError,RuntimeError):
                self._subtitle_auto_applied=False
            return
        if self._subtitle_manual_track is not None:
            return
        tracks=subtitle_tracks(self.player)
        signature=tuple(tracks)
        if not tracks:return
        if self._subtitle_auto_applied and signature==self._subtitle_track_signature:return
        target=suggested_subtitle(tracks,self.state['settings'].get('subtitle_language','Auto'))
        try:
            if target is None:return
            if self.player.video_get_spu()!=target and self.player.video_set_spu(target)!=0:
                # HLS caption tracks can be listed before VLC is ready to
                # activate them. Try again on the next timer tick.
                return
            self._subtitle_auto_applied=True
            self._subtitle_track_signature=signature
        except (AttributeError,OSError,RuntimeError):pass

    def disable_all_subtitles(self):
        """CC Off disables both independent caption engines immediately."""
        self._subtitle_session_all_off=True
        self.stop_auto_captions()
        self._subtitle_manual_track=-1
        self._subtitle_auto_applied=False  # force Off retry after track parsing
        self._subtitle_track_signature=()
        if self.player and self.playback_started:
            try:self.player.video_set_spu(-1)
            except (AttributeError,OSError,RuntimeError):pass
        self.status.setText('All subtitles off (broadcast + offline Vosk).')

    def choose_subtitle_track(self,track):
        if not self.player or not self.playback_started:return
        if track!=-1 and track not in {key for key,_ in subtitle_tracks(self.player)}:return
        try:
            if self.player.video_set_spu(track)!=0:
                self.status.setText('This channel cannot enable the selected subtitle track.')
                return
        except (AttributeError,OSError,RuntimeError):
            self.status.setText('Subtitle selection is not available from this VLC build.')
            return
        if track!=-1:
            self._subtitle_session_all_off=False
        self._subtitle_manual_track=track
        self._subtitle_auto_applied=track!=-1
        self._subtitle_track_signature=()
        self.status.setText('Subtitles off' if track==-1 else 'Subtitle track '+str(track)+' selected')

    def load_subtitle_file(self):
        if not self.player or not self.playback_started:
            self.status.setText('Play a programme before adding subtitle files.')
            return
        path,_=QFileDialog.getOpenFileName(
            self,'Load captions for current video','','Subtitles (*.srt *.ass *.ssa *.vtt *.sub)')
        if not path:return
        try:
            path=external_subtitle_path(path)
            if not self.player.video_set_subtitle_file(path):
                raise ValueError('VLC could not read this subtitle file')
            # File subtitles are an explicit user choice: the periodic
            # broadcast preference must not replace the newly attached slave.
            self._subtitle_manual_track='external'
            self._subtitle_auto_applied=True
            if not self.state['settings'].get('subtitles_enabled',True):
                self.state=self.store.update(
                    lambda s:s['settings'].update(subtitles_enabled=True))
            self.status.setText('Subtitle file attached to current playback (not saved to recordings)')
        except (ValueError,OSError,RuntimeError,AttributeError) as exc:
            self.status.setText('Cannot load subtitles: '+str(exc))

    def show_subtitle_menu(self):
        menu=QMenu(self.screen_dialog or self)
        tracks=subtitle_tracks(self.player)
        menu.addSection('Broadcast subtitle tracks')
        if self.player and self.playback_started:
            action=menu.addAction('Off — all subtitles (including Vosk)')
            action.triggered.connect(self.disable_all_subtitles)
            embedded_only=menu.addAction('Off — broadcast captions only')
            embedded_only.triggered.connect(lambda:self.choose_subtitle_track(-1))
            for key,name in tracks:
                action=menu.addAction('CC  '+name)
                action.setCheckable(True)
                try:action.setChecked(self.player.video_get_spu()==key)
                except (RuntimeError,OSError,AttributeError):pass
                action.triggered.connect(lambda _,id=key:self.choose_subtitle_track(id))
            if not tracks:
                no_captions=menu.addAction('No embedded captions reported by this stream')
                no_captions.setEnabled(False)
        else:
            not_playing=menu.addAction('Play a channel to discover its caption tracks')
            not_playing.setEnabled(False)
        menu.addSeparator()
        load=menu.addAction('Load SRT / ASS / VTT file…')
        load.triggered.connect(self.load_subtitle_file)
        appearance=menu.addAction('Subtitle size, font, colour, position…')
        appearance.triggered.connect(self.settings)
        menu.addSection('Speech-generated captions')
        auto=menu.addAction('Restart Vosk when cleanup finishes'
                            if self._auto_caption_stopping else
                            ('Stop local speech captions' if self._auto_caption_worker
                             else 'Generate live subtitles (offline Vosk + FFmpeg)'))
        auto.setEnabled(not self._auto_caption_stopping or not self._auto_caption_restart_requested)
        auto.triggered.connect(self.toggle_auto_captions)
        menu.addSection('Vosk text timing (not embedded subtitles)')
        delay=self.state['settings'].get('auto_caption_delay_ms',0)
        current=menu.addAction('Current added delay: '+str(delay)+' ms')
        current.setEnabled(False)
        earlier=menu.addAction('Less delay (−250 ms)')
        earlier.setEnabled(delay>0)
        earlier.triggered.connect(lambda:self.change_auto_caption_delay(-250))
        later=menu.addAction('More delay (+250 ms)')
        later.setEnabled(delay<10000)
        later.triggered.connect(lambda:self.change_auto_caption_delay(250))
        reset=menu.addAction('Reset Vosk delay to 0 ms')
        reset.setEnabled(delay!=0)
        reset.triggered.connect(lambda:self.change_auto_caption_delay())
        menu.addSection('Video/audio holdback via local timeshift')
        video_delay=self.state['settings'].get('auto_caption_video_delay_ms',0)
        local_ready=(self.timeshift is not None and self.timeshift_task is None
                     and self.player is not None and bool(self.playback_started))
        current_video=menu.addAction('Target video delay: '+str(video_delay)+' ms')
        current_video.setEnabled(False)
        advance=menu.addAction('Less VIDEO delay (−1 second)')
        advance.setEnabled(local_ready and video_delay>0)
        advance.triggered.connect(lambda:self.change_auto_caption_video_delay(-1000))
        hold=menu.addAction('More VIDEO delay (+1 second)')
        hold.setEnabled(local_ready and video_delay<30000)
        hold.triggered.connect(lambda:self.change_auto_caption_video_delay(1000))
        video_reset=menu.addAction('Reset VIDEO delay to live')
        video_reset.setEnabled(local_ready and video_delay>0)
        video_reset.triggered.connect(lambda:self.change_auto_caption_video_delay())
        if not local_ready:
            notice=menu.addAction('Enable on-device timeshift in Settings to delay video')
            notice.setEnabled(False)
        menu.exec(QCursor.pos())

    def init_player(self):
        if self.player:return
        # An installed application always uses its verified package-private
        # VLC binaries and modules; never silently load an older system VLC.
        from .media_runtime import configure_private_vlc
        configure_private_vlc()
        import vlc
        self._vlc_subtitle_profile=tuple(vlc_subtitle_options(self.state['settings']))
        vlc_options=['--no-video-title-show',*self._vlc_subtitle_profile]
        if self.state['settings'].get('vlc_decoder','Auto')=='Software':
            vlc_options.append('--avcodec-hw=none')
        self.vlc_instance=vlc.Instance(*vlc_options)
        self.player=self.vlc_instance.media_player_new()
        self.player.audio_set_volume(self.volume_slider.value())
        win=int(self.video.winId())
        if sys.platform=='darwin':self.player.set_nsobject(win)
        elif os.name=='nt':self.player.set_hwnd(win)
        else:self.player.set_xwindow(win)
    def play_url(self,url,preserve_captions=False):
        self.regional_notice.hide()
        # Only the in-place DVR caption-sync controls use preserve_captions;
        # channel tuning, record recovery and ordinary seeks retain old reset.
        if not preserve_captions:
            self.stop_auto_captions()
        self._playback_url=url
        self._active_direct_video=False
        try:
            self.init_player()
            self.player.stop()
            media=self.vlc_instance.media_new(url)
            # Some free HLS origins reject libVLC's default User-Agent.
            # This is format compatibility, not bypassing geo/DRM restrictions.
            if url.lower().startswith(('http://','https://')):
                media.add_option(':http-user-agent='+PLAYBACK_USER_AGENT)
                # Apply only to direct network media, not captured local DVR.
                # VLC's per-media network caching is preferable to global
                # decoder/reclock changes, and avoids changing working Ace sessions.
                from .core import ace_id
                direct=(self.selected is not None and
                        not ace_id(self.selected.get('stream','')) and self.timeshift is None)
                # Browsing a different channel must not change how we monitor
                # the media already playing, especially an Ace engine session.
                self._active_direct_video=bool(direct and channel_kind(self.selected)!='Radio')
                if direct:
                    media.add_option(':network-caching='+str(
                        self.state['settings'].get('http_buffer_ms',4000)))
            self.player.set_media(media); media.release()
            self._subtitle_auto_applied=False
            self._subtitle_manual_track=(-1 if self._subtitle_session_all_off else None)
            self._subtitle_track_signature=()
            if self.player.play()==-1:raise RuntimeError('libVLC could not start playback')
            if self._subtitle_session_all_off:
                try:self.player.video_set_spu(-1)
                except (AttributeError,OSError,RuntimeError):pass
            self.playback_started=time.monotonic(); self.playback_reported=False
            self._last_media_activity=None
            self._video_issue_notified=False
            self._direct_video_sample=None
            self._direct_video_progress=0
            self._direct_video_stalled=False
            self.last_good_video=time.monotonic()
            self.source_check_serial+=1
            self.pause_button.setText('⏸ Pause')
            if self.selected:
                key=self.matched_guide(self.selected)
                now=int(time.time())
                current=next((p for p in self.guide_index()[0].get(key,[]) if p['start']<=now<p['end']),None)
                self.channel_banner.setText(display_channel_name(self.selected['name'])+
                                            ('  •  Now: '+current['title'] if current else '  •  LIVE'))
                self.channel_banner.show()
                QTimer.singleShot(5000,self.channel_banner.hide)
            self.tabs.setCurrentIndex(0)
            self.status.setText('Connecting to stream…')
        except Exception as exc:
            self.playback_started=0
            self.stop_auto_captions()
            self.error('Playback could not start. Check that VLC 3 is installed and the stream is available. '+str(exc))
    def detected_timezone(self):
        return detected_zone()

    def open_global_search(self):
        if self.global_search_dialog is not None:
            self.global_search_dialog.show()
            self.global_search_dialog.raise_()
            self.global_search_dialog.activateWindow()
            self.global_search_dialog.query.setFocus()
            return
        dialog=GlobalSearch(self)
        self.global_search_dialog=dialog
        dialog.finished.connect(lambda _:setattr(self,'global_search_dialog',None))
        dialog.show()

    def reveal_global_channel(self,ch,programme=None,show_guide=True):
        """Show a global search result even when existing filters hide it."""
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.favourites_only.blockSignals(True)
        self.favourites_only.setChecked(False)
        self.favourites_only.blockSignals(False)
        for widget in (self.source_filter,self.country_filter,self.section_filter,
                       self.genre_filter,self.kind_filter):
            widget.blockSignals(True)
            widget.setCurrentIndex(0)
            widget.blockSignals(False)
        self.render_channels()
        self.select_guide_channel(ch)
        if not show_guide:return
        if programme is not None:
            self.guide_start=(int(programme['start'])//3600)*3600
        self.tabs.setCurrentIndex(1)
        self.render_guide()
        index=next((i for i,row in enumerate(self.grid.rows) if row['id']==ch['id']),None)
        if index is not None:
            height,_,_,_=self.grid.geometry_units()
            self.guide_scroll.verticalScrollBar().setValue(max(0,48+index*height-40))
        self.grid.update()

    def select_guide_channel(self,ch):
        self.selected=ch
        # Keep the sidebar and Now/Next label in step with the programme grid.
        for idx in range(self.channels.count()):
            item=self.channels.item(idx)
            if item.data(Qt.UserRole)['id']==ch['id']:
                self.channels.setCurrentItem(item)
                break
        self.render_now()

    def play_guide_channel(self,ch):
        self.select_guide_channel(ch)
        self.tabs.setCurrentIndex(0)
        self.play()

    def record_guide_channel(self,ch):
        self.select_guide_channel(ch)
        self.record_now()

    def open_ace_stream_setup(self):
        if sys.platform.startswith('linux'):
            # The .deb includes this bootstrap in the PyInstaller application.
            # Download the original publisher archive only on explicit consent.
            from .linux_ace_bootstrap import compatibility, install_original
            from .engine import linux_engine_path
            try:
                existing=linux_engine_path(self.state['settings'].get('engine_executable',''))
            except RuntimeError as exc:
                # An explicitly selected but now-missing launcher is a
                # Settings problem, not consent to install another engine.
                QMessageBox.warning(self,'DizyTV — configured Ace engine',str(exc))
                return
            if existing:
                QMessageBox.information(self,'DizyTV — Ace Stream engine',
                    'An existing Linux Ace engine is already configured:\n'+
                    str(existing)+'\n\nDizyTV will not replace it or start a second installer.')
                return
            if getattr(self,'_ace_bootstrap_task',None) is not None:
                self.status.setText('Original Ace Stream download is already running.')
                return
            try:
                compatibility()
            except RuntimeError as exc:
                from .outpace import packaged_binary
                helper=packaged_binary()
                if helper is not None:
                    QMessageBox.information(
                        self,'DizyTV — bundled Outpace',
                        'The original proprietary Ace engine is not verified for this Linux release.\n\n'
                        'DizyTV includes the separately AGPL-licensed Outpace engine for '
                        'compatible public Ace swarms. It starts automatically when you '
                        'select a compatible Ace channel; no additional install is required.\n\n'
                        'Original engine compatibility: '+str(exc))
                else:
                    QMessageBox.warning(self,'DizyTV — Linux Ace compatibility',
                        str(exc)+'\n\nOfficial Linux products: https://docs.acestream.net/products/\n'
                        'The DizyTV .deb still works for ordinary HTTP/HLS channels.')
                return
            answer=QMessageBox.question(
                self,'Install original Ace Stream engine?',
                'Optional third-party software: Ace Stream uses peer-to-peer network '
                'bandwidth and has its own publisher terms.\n\n'
                'This downloads the publisher\'s unchanged Ubuntu 22.04 engine '
                'from download.acestream.media into your own ~/.local/opt/acestream '
                'folder. A fixed SHA-256 checksum will be checked before installing. '
                'Nothing is executed automatically by setup.\n\n'
                'Publisher terms: https://www.acestream.org/license\n'
                'Proceed with this optional download?',
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer!=QMessageBox.Yes:
                return
            cancel=threading.Event()
            progress=QProgressDialog('Downloading original Ace Stream engine…',
                                     'Cancel download',0,1000,self)
            progress.setWindowTitle('DizyTV — optional Ace Stream installation')
            progress.setMinimumDuration(0)
            progress.setWindowModality(Qt.NonModal)
            progress.setAutoClose(False)
            progress.canceled.connect(cancel.set)
            task=None
            def work():
                return install_original(
                    consent=True,cancel=cancel.is_set,
                    progress=lambda received,total:task.signals.progress.emit(received,total))
            task=Task(work)
            self._ace_bootstrap_task=task
            self._ace_bootstrap_progress=progress
            def onprogress(received,total):
                if total:
                    progress.setValue(min(990,round(received/max(1,total)*990)))
                progress.setLabelText(
                    'Downloading and verifying original Ace Stream: '+
                    str(round(received/1024/1024,1))+' MiB')
            def done(path):
                self._ace_bootstrap_task=None
                progress.setValue(1000);progress.close()
                self.status.setText('Original Ace Stream engine staged and verified.')
                QMessageBox.information(
                    self,'DizyTV — Ace Stream engine installed',
                    'Verified publisher archive installed at:\n'+path+
                    '\n\nThe original engine was not launched during installation. '
                    'Playing an Ace channel will start its local engine when needed. '
                    'This does not guarantee the selected stream has peers.')
            def failed(message):
                self._ace_bootstrap_task=None
                progress.close()
                self.status.setText('Optional Ace setup did not complete; DizyTV is unaffected.')
                QMessageBox.warning(self,'DizyTV — optional Ace setup',message)
            task.signals.progress.connect(onprogress)
            task.signals.success.connect(done)
            task.signals.failure.connect(failed)
            progress.show()
            self.pool.start(task)
            return
        # Proprietary Ace binaries are never silently bundled or rehosted.
        site='https://docs.acestream.net/products/'
        if not QDesktopServices.openUrl(QUrl(site)):
            self.error('Could not open the official Ace Stream products page in your browser.')

    def diagnose_stream(self):
        if not self.selected:
            return
        from .core import ace_id
        is_ace=ace_id(self.selected['stream']) is not None
        if is_ace:
            self.source_check_serial+=1
            serial=self.source_check_serial
            channel=self.selected['id']
            diagnostic=Task(lambda:engine_diagnostics(self.state['settings']['engine_url']))
            self.source_check=diagnostic
            def ready(message):
                if serial==self.source_check_serial and self.selected and self.selected['id']==channel:
                    self.status.setText(message+' If Ace was started in console mode, no tray icon is expected.')
            diagnostic.signals.success.connect(ready)
            self.pool.start(diagnostic)
            return
        self.source_check_serial+=1
        serial=self.source_check_serial
        channel=self.selected['id']
        url=self.selected['stream']
        origins=self.selected.get('sources') or [self.selected.get('source','')]
        origin_label=safe_source_label(origins[0] if origins else '')
        diagnostic=Task(lambda:probe_stream(url))
        self.source_check=diagnostic
        def ready(message):
            if (serial==self.source_check_serial and self.selected and
                    self.selected['id']==channel):
                self.status.setText(origin_label+': '+message)
                notice=regional_access_notice(message)
                if notice:
                    self.regional_notice.setText(notice)
                    self.regional_notice.show()
                else:
                    self.regional_notice.hide()
        diagnostic.signals.success.connect(ready)
        diagnostic.signals.failure.connect(lambda _message:None)
        self.pool.start(diagnostic)

    def close_timeshift(self):
        self._active_holdback_ms=0
        prior=self.timeshift
        self.timeshift=None
        self.timeshift_task=None
        self.timeshift_lag=0
        self.last_capture_seq=-1
        self.last_capture_progress=time.monotonic()
        self.last_good_video=time.monotonic()
        if prior:
            # Buffer/server cleanup may involve disk IO or socket timeouts.
            # Never block the Qt event loop, including window shutdown.
            prior.close_async()

    def play_stream(self,url):
        # The new stream may wait many seconds for the DVR: old subtitles must
        # disappear at channel-switch REQUEST time, not after the new buffer.
        self.stop_auto_captions()
        # Capture/loopback starts off the GUI thread; unsupported sources fail
        # open to ordinary live video. No cache is created unless opted in.
        self.close_timeshift()
        settings=self.state['settings']
        if not settings.get('timeshift_enabled',False):
            self.play_url(url)
            return
        folder=settings.get('timeshift_dir') or str(self.store.directory/'timeshift')
        try:
            session=RollingTimeshift(
                url,folder,settings.get('timeshift_minutes',30),
                settings.get('timeshift_max_bytes',4*1024**3),
                max(1024**3,settings.get('reserve_bytes',1024**3)))
        except (OSError,ValueError) as exc:
            self.status.setText('Timeshift unavailable: '+str(exc)+' — watching live')
            self.play_url(url)
            return
        self.timeshift=session
        self.last_capture_seq=-1
        self.last_capture_progress=time.monotonic()
        self.last_good_video=time.monotonic()
        self.status.setText('Preparing temporary local timeshift buffer…')
        requested_delay_ms=(settings.get('auto_caption_video_delay_ms',0)
                            if settings.get('timeshift_enabled',False) else 0)
        job=Task(lambda:session.start_delayed(requested_delay_ms/1000))
        self.timeshift_task=job
        def ready(local_url):
            if self.timeshift is not session:
                session.close_async()
                return
            self.timeshift_task=None
            self.play_url(local_url)
            self._active_holdback_ms=requested_delay_ms
            self.timeshift_lag=0  # Fixed replay lag; moving live holdback is separate.
            self.seek_notice.setText('Temporary on-device timeshift is recording; up to '+str(session.window.minutes)+
                                     ' minutes'+(' • video ~'+str(round(self.timeshift_lag,1))+'s behind LIVE for Vosk sync'
                                                 if self.timeshift_lag>0 else ''))
        def failed(message):
            if self.timeshift is not session:return
            self.timeshift=None
            self.timeshift_task=None
            session.close_async()
            self.play_url(url)
            self.seek_notice.setText('Timeshift unavailable ('+message+'); playing original stream')
        job.signals.success.connect(ready)
        job.signals.failure.connect(failed)
        self.pool.start(job)

    def change_auto_caption_video_delay(self,change_ms=None):
        """Move the complete A/V playback behind live, using existing local DVR.

        A separate source-based FFmpeg recognition worker is intentionally kept
        alive across this *same-source* replay so its timeline isn't restarted.
        This cannot guarantee media-clock sync for providers serving mismatched
        live edges, but gives users a real picture+sound holdback control.
        """
        old=self.store.read()['settings'].get('auto_caption_video_delay_ms',0)
        target=0 if change_ms is None else max(0,min(30000,old+change_ms))
        if (self.timeshift is None or self.timeshift_task is not None
                or self.player is None or not self.playback_started):
            self.status.setText('Video holdback needs fully started local timeshift playback. '
                                'Enable “Keep a temporary on-device rolling buffer” in Settings, '
                                'then restart the channel. No stream was interrupted.')
            return
        # Readiness is about PLAYABLE fragments after filtering, not total
        # buffered seconds (long 10-second segments may leave zero video).
        playable=len(self.timeshift.window.holdback_entries(target/1000))
        if target>0 and playable<3:
            self.status.setText('Waiting for buffered playback: '+str(playable)+
                                ' playable segments; at least 3 required.')
            return
        actual=target/1000 if target>0 else 0.0
        try:
            target_url=(self.timeshift.holdback_url(actual) if actual>0 else
                        self.timeshift.live_url())
            # Do not stop Vosk while retuning ONLY the current DVR replay URL.
            self.play_url(target_url,preserve_captions=True)
            if not self.playback_started:
                self.stop_auto_captions()
                return
        except (OSError,RuntimeError,ValueError) as exc:
            self.status.setText('Could not adjust video delay: '+str(exc)[:160])
            return
        self._active_holdback_ms=target
        self.timeshift_lag=0
        self.state=self.store.update(lambda s:s['settings'].update(auto_caption_video_delay_ms=target))
        self.seek_notice.setText('DVR video/audio ~'+str(round(actual,1))+
                                 's behind live; selected target '+str(target)+' ms. '
                                 'Existing Vosk subtitle delay stays separate.')
        self.status.setText('Video/audio holdback '+str(target)+' ms. '
                            'Matching stream positions is approximate; '
                            'network source clocks may differ.')

    def play(self):
        if not self.selected:return
        active=[j for j in self.store.read()['jobs'] if j['status']=='recording' and j['channel_id']!=self.selected['id']]
        if active:self.error('A different channel is recording. Stop or finish that recording before switching playback.'); return
        ch=self.selected
        url=stream_url(ch['stream'],self.state['settings']['engine_url'])
        from .core import ace_id
        is_ace=ace_id(ch['stream']) is not None
        if is_ace and self.engine_task is not None:
            self.status.setText('Ace Stream engine startup is already in progress…'); return
        self.regional_notice.hide()
        # The viewer has requested a new channel NOW. Remove old Vosk words
        # before an Ace engine/TV source may spend seconds connecting.
        self.stop_auto_captions()
        if not is_ace:
            # Supersede pending Ace preparation when tuning a direct channel.
            # Its late callbacks must neither start video nor block a new Ace request.
            self.engine_task=None
        self._play_request_serial+=1
        serial=self._play_request_serial
        if is_ace:
            self.status.setText('Connecting to Ace Engine and preparing channel; waiting for available peers…')
            def prepare():
                ensure_ready(self.state['settings']['engine_url'],
                             executable_path=self.state['settings'].get('engine_executable',''),
                             directory=self.store.directory)
                return start_playback_session(ch['stream'],self.state['settings']['engine_url'],
                                              directory=self.store.directory)
            task=Task(prepare)
            self.engine_task=task
            def ready(playback_url):
                if serial!=self._play_request_serial or self.engine_task is not task:return
                self.engine_task=None
                if self.selected and self.selected['id']==ch['id']:
                    self.play_stream(playback_url)
            def failed(message):
                if serial!=self._play_request_serial or self.engine_task is not task:return
                self.engine_task=None
                if self.selected and self.selected['id']==ch['id']:
                    self.status.setText('Ace playback failed: '+message)
                    self.error('Ace Stream engine was detected, but could not prepare this channel. '+
                               message+'\n\nTry the channel in the official Ace player to check peers.')
            task.signals.success.connect(ready); task.signals.failure.connect(failed)
            self.pool.start(task)
        else:
            # Ordinary HTTP/HLS streams play without the Ace Stream engine.
            self.play_stream(url)
    def moveEvent(self,event):
        super().moveEvent(event)
        # Windows' native transparent caption window is in global screen
        # coordinates. Moving the main window does not move the video widget
        # relative to its parent, so its own move event is not sufficient.
        if self._auto_caption_overlay is not None:
            self.position_auto_caption_overlay()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self._auto_caption_overlay is not None:
            self.position_auto_caption_overlay()

    def eventFilter(self,obj,event):
        if obj is self.video and event.type() in (QEvent.Resize,QEvent.Move):
            self.position_auto_caption_overlay()
        if obj is self.screen_dialog and event.type() in (QEvent.Resize,QEvent.Move):
            self.position_auto_caption_overlay()
        if obj is self.video and event.type()==QEvent.MouseButtonDblClick:
            self.toggle_screen_fullscreen()
            return True
        if self.screen_dialog is not None and obj in (self.video,self.screen_dialog,self.detached_controls):
            if event.type() in (QEvent.MouseMove,QEvent.Enter):
                self.show_detached_controls()
            if obj is self.screen_dialog and event.type() in (QEvent.Resize,QEvent.Move,QEvent.Show):
                self.position_detached_overlay()
        return super().eventFilter(obj,event)

    def set_tv_volume(self,volume):
        if self.player:self.player.audio_set_volume(volume)

    def seek_from_slider(self):
        if self.timeshift is not None:
            available=self.timeshift.window.latest_seconds()
            lag=available*(1000-self.seek_slider.value())/1000
            try:
                self.play_url(self.timeshift.replay_url(lag))
                self.timeshift_lag=lag
                self.seek_notice.setText('Playing cached live TV, ~'+str(int(lag))+'s behind live')
            except RuntimeError as exc:self.seek_notice.setText(str(exc))
            return
        if self.player and self.player.is_seekable() and self.player.get_length()>0:
            position=max(0,min(1000,self.seek_slider.value()))
            self.player.set_time(self.player.get_length()*position//1000)

    def _rebind_video(self):
        if os.environ.get('QT_QPA_PLATFORM')=='offscreen':
            # Native HWND/NSView reparenting is not testable by the offscreen
            # platform plugin; UI ownership tests can still verify layout.
            return
        if self.player:
            handle=int(self.video.winId())
            if sys.platform=='darwin':self.player.set_nsobject(handle)
            elif os.name=='nt':self.player.set_hwnd(handle)
            else:self.player.set_xwindow(handle)

    def toggle_pause(self):
        if not self.player or not self.playback_started:
            self.status.setText('Select and play a channel first.')
            return
        if not self.timeshift and not self.player.is_seekable():
            self.seek_notice.setText('This source has no seekable DVR window. Enable on-device timeshift in Settings.')
            return
        paused=bool(self.player.get_state()==__import__('vlc').State.Paused)
        self.player.set_pause(0 if paused else 1)
        self.pause_button.setText('⏸ Pause' if paused else '▶ Resume')
        self.status.setText('Playback resumed' if paused else 'Live TV paused in the available DVR window')

    def seek_relative(self,delta_ms):
        if not self.player or not self.playback_started:return
        if self.timeshift is not None:
            available=self.timeshift.window.latest_seconds()
            if available<=0:
                self.seek_notice.setText('Local timeshift buffer is still filling.')
                return
            # A positive delta skips toward LIVE; a negative delta rewinds.
            seconds_back=max(0.0,min(available,float(self.timeshift_lag)-delta_ms/1000.0))
            if seconds_back<1.0:
                self.jump_to_live()
                return
            try:
                self.play_url(self.timeshift.replay_url(seconds_back))
                self.timeshift_lag=seconds_back
                self.seek_notice.setText('Device buffer: ~'+str(int(seconds_back))+' seconds behind LIVE')
            except (ValueError,RuntimeError) as exc:
                self.seek_notice.setText('Timeshift seek unavailable: '+str(exc))
            return
        if not self.player.is_seekable():
            self.seek_notice.setText('This live stream has no seekable DVR window.')
            return
        current=self.player.get_time()
        length=self.player.get_length()
        if current<0:
            self.seek_notice.setText('The stream has not exposed a DVR position yet.')
            return
        target=max(0,current+delta_ms)
        if length>0:target=min(length,target)
        self.player.set_time(target)
        self.seek_notice.setText('Rewound 30 seconds' if delta_ms<0 else 'Moved forward')

    def jump_to_live(self):
        if not self.player or not self.playback_started:return
        if self.timeshift is not None:
            self.play_url(self.timeshift.live_url())
            self.timeshift_lag=0
            self.seek_notice.setText('LIVE — playing most recently cached stream')
            return
        if self.player.is_seekable() and self.player.get_length()>0:
            self.player.set_time(max(0,self.player.get_length()-1000))
            self.player.set_pause(0)
            self.pause_button.setText('⏸ Pause')
        else:
            self.play()
        self.seek_notice.setText('LIVE — near the latest available playback point')

    def toggle_cinema(self):
        if self.screen_dialog is not None:
            self.exit_screen_fullscreen()
        self.cinema_mode=not self.cinema_mode
        self.sidebar.setVisible(not self.cinema_mode)
        for widget in self.header_buttons:
            if widget:widget.setVisible(not self.cinema_mode)
        # Tabs remain accessible when not in cinema mode.
        self.tabs.tabBar().setVisible(not self.cinema_mode)
        self.cinema_button.setText('↩ Normal' if self.cinema_mode else '▣ Cinema')
        self.status.setText('Cinema view — use Normal to restore browsing' if self.cinema_mode else 'Normal windowed view')

    def open_popout(self):
        """Keep TV video visible in a resizable modeless window beside the EPG."""
        if self.screen_dialog is not None:
            self.screen_dialog.showNormal()
            self.screen_dialog.resize(800,520)
            self.screen_dialog.raise_()
            self.show_detached_controls()
            return
        self.open_video_window(fullscreen=False)

    def toggle_screen_fullscreen(self):
        if self.screen_dialog is not None:
            if self.screen_dialog.isFullScreen():
                self.screen_dialog.showNormal()
                self.screen_dialog.resize(800,520)
            else:
                self.screen_dialog.showFullScreen()
            self.show_detached_controls()
            return
        self.open_video_window(fullscreen=True)

    def open_video_window(self,fullscreen=False):
        if self.screen_dialog is not None:return
        screen=QDialog(self)
        screen.setWindowTitle('DizyTV — TV player')
        screen.setWindowFlag(Qt.Window,True)
        screen.setModal(False)
        screen.setMinimumSize(360,240)
        screen.resize(800,520)
        screen.setObjectName('tvWindow')
        screen.setStyleSheet('QDialog#tvWindow { background:'+
                             theme_color('#101713',self.state['settings'].get('theme','Green'))+'; }')
        screen.setMouseTracking(True)
        screen.installEventFilter(self)
        vbox=QVBoxLayout(screen)
        vbox.setContentsMargins(6,6,6,6)
        vbox.setSpacing(4)
        self.video.setParent(screen)
        vbox.addWidget(self.video,1)

        # The same libVLC player remains attached; do not start a second feed.
        # Separate owned translucent tool window overlays native VLC video HWND.
        # Windows libVLC uses a native HWND: an owned translucent *window*
        # is required to cover it. On macOS/Linux use a normal child overlay:
        # native Qt.Tool children produce QWidgetWindow shutdown crashes there.
        native_overlay=(os.name=='nt' and os.environ.get('QT_QPA_PLATFORM')!='offscreen')
        if native_overlay:
            panel=QDialog(screen,Qt.Tool|Qt.FramelessWindowHint)
            panel.setModal(False)
        else:
            panel=QFrame(screen)
        panel.setObjectName('playerControls')
        # WA_TranslucentBackground is only safe on a real native tool
        # window. For Qt offscreen tests and other platforms use a
        # stylesheet-transparent normal child without native promotion.
        panel.setAttribute(Qt.WA_TranslucentBackground,native_overlay)
        if native_overlay:panel.setAttribute(Qt.WA_ShowWithoutActivating,True)
        panel.installEventFilter(self)
        ratio=max(.75,min(1.5,self.state['settings'].get('ui_scale',100)/100))
        compact=self.state['settings'].get('button_size','Normal')=='Compact'
        padding=max(2,round((3 if compact else 5)*ratio))
        # The floating overlay is FULLY TRANSPARENT between the controls.
        # Only its small pill buttons and slider tracks have translucent fills.
        # This panel is NOT in the video layout: no window or video resizing.
        prefix=('QDialog' if native_overlay else 'QFrame')+'#playerControls '
        self._detached_base_style=''.join((
            prefix+'{background:transparent;border:0;}',
            prefix+'QPushButton {background:rgba(10,35,23,135);color:#edfff0;'
                'border:1px solid rgba(161,213,173,150);border-radius:7px;'
                'padding:'+str(padding)+'px '+str(padding+3)+'px;'
                'font-size:'+str(max(9,round(11*ratio)))+'px;}',
            prefix+'QPushButton:hover {background:rgba(17,70,43,180);}',
            prefix+'QLabel {background:transparent;color:#effff0;}',
            prefix+'QSlider {background:transparent;border:0;padding:0;margin:0;}',
            prefix+'QSlider::groove:horizontal {height:4px;'
                'background:rgba(14,40,29,120);border:0;border-radius:2px;}',
            prefix+'QSlider::add-page:horizontal {'
                'background:rgba(14,40,29,120);border:0;border-radius:2px;}',
            prefix+'QSlider::sub-page:horizontal {'
                'background:rgba(86,205,128,190);border-radius:2px;}',
            prefix+'QSlider::handle:horizontal {width:13px;margin:-5px 0;'
                'border:2px solid rgba(210,255,227,200);'
                'background:rgba(106,227,147,215);border-radius:7px;}',
        ))
        panel.setStyleSheet(overlay_theme_style(self._detached_base_style,
                                               self.state['settings'].get('theme','Green')))
        panel.setMouseTracking(True)
        panel_layout=QVBoxLayout(panel)
        panel_layout.setContentsMargins(2,1,2,1)
        panel_layout.setSpacing(2)
        # Scrollable single-line controls, even in a narrow 360px pop-out.
        button_row=QWidget(panel)
        button_row.setStyleSheet('background:transparent;border:0;')
        bar=QHBoxLayout(button_row)
        bar.setContentsMargins(0,0,0,0)
        bar.setSpacing(max(2,round(4*ratio)))
        for title,callback in (('⏯ Play/Pause',self.toggle_pause),
                               ('↶ 30s',lambda:self.seek_relative(-30000)),
                               ('↷ 30s',lambda:self.seek_relative(30000)),
                               ('LIVE',self.jump_to_live),
                               ('☷ Guide',self.show_tv_guide),
                               ('Info',self.show_tv_info),
                               ('CC Subtitles',self.show_subtitle_menu),
                               ('⛶ Full',self.toggle_screen_fullscreen),
                               ('↩ Dock',self.exit_screen_fullscreen)):
            button=QPushButton(title,panel)
            button.clicked.connect(callback)
            if title=='LIVE':
                button.setObjectName('tvLive')
                self.popout_live_button=button
            bar.addWidget(button)
            if title=='LIVE':
                self.popout_live_light=QLabel('●',button_row)
                bar.addWidget(self.popout_live_light)
        button_scroll=QScrollArea(panel)
        button_scroll.setFrameShape(QFrame.NoFrame)
        button_scroll.setWidgetResizable(False)
        button_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        button_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        button_scroll.setStyleSheet('QScrollArea {background:transparent;border:0;}'
                                    'QWidget {background:transparent;}')
        button_row.adjustSize()
        button_scroll.setWidget(button_row)
        button_scroll.setFixedHeight(button_row.sizeHint().height()+6)
        pop_nav=QWidget(panel)
        pop_nav_layout=QHBoxLayout(pop_nav)
        pop_nav_layout.setContentsMargins(0,0,0,0)
        pop_nav_layout.setSpacing(3)
        left=QToolButton(pop_nav)
        left.setObjectName('mediaScrollArrow')
        left.setText('‹')
        left.setFixedWidth(28)
        right=QToolButton(pop_nav)
        right.setObjectName('mediaScrollArrow')
        right.setText('›')
        right.setFixedWidth(28)
        scroll_bar=button_scroll.horizontalScrollBar()
        left.clicked.connect(lambda:scroll_bar.setValue(scroll_bar.value()-180))
        right.clicked.connect(lambda:scroll_bar.setValue(scroll_bar.value()+180))
        def sync_popout_arrows(*_):
            overflow=scroll_bar.maximum()>scroll_bar.minimum()
            left.setVisible(overflow)
            right.setVisible(overflow)
            left.setEnabled(scroll_bar.value()>scroll_bar.minimum())
            right.setEnabled(scroll_bar.value()<scroll_bar.maximum())
        scroll_bar.rangeChanged.connect(sync_popout_arrows)
        scroll_bar.valueChanged.connect(sync_popout_arrows)
        pop_nav_layout.addWidget(left)
        pop_nav_layout.addWidget(button_scroll,1)
        pop_nav_layout.addWidget(right)
        panel_layout.addWidget(pop_nav)
        QTimer.singleShot(0,sync_popout_arrows)
        self.screen_seek_slider=TimeSeekSlider(Qt.Horizontal,panel)
        self.screen_seek_slider.setObjectName('seekBar')
        self.screen_seek_slider.set_rail_theme(self.state['settings'].get('theme','Green'))
        self.screen_seek_slider.seek_requested.connect(self.seek_relative)
        self.screen_seek_slider.setRange(0,1000)
        self.screen_seek_slider.sliderReleased.connect(self.seek_screen_slider)
        panel_layout.addWidget(self.screen_seek_slider)
        volume_line=QHBoxLayout()
        volume_line.addWidget(QLabel('Volume',panel))
        volume=MediaRailSlider(Qt.Horizontal,panel)
        volume.setObjectName('volumeBar')
        volume.set_rail_theme(self.state['settings'].get('theme','Green'))
        volume.setRange(0,100)
        volume.setValue(self.volume_slider.value())
        volume.valueChanged.connect(self.volume_slider.setValue)
        self.volume_slider.valueChanged.connect(volume.setValue)
        volume_line.addWidget(volume,1)
        panel_layout.addLayout(volume_line)
        self.detached_controls=panel
        self.screen_dialog=screen
        screen.finished.connect(self.exit_screen_fullscreen)
        escape=QShortcut(QKeySequence('Escape'),screen)
        escape.activated.connect(self.exit_screen_fullscreen)
        if fullscreen:screen.showFullScreen()
        else:screen.show()
        self.video.show()
        self._rebind_video()
        if self._auto_caption_overlay is not None:
            self.destroy_auto_caption_overlay()
            if self._auto_caption_worker is not None and self._auto_caption_text:
                self.receive_auto_caption(self._auto_caption_seq,self._auto_caption_text)
        self.detached_mouse_position=QCursor.pos()
        self.detached_mouse_timer.start()
        self.show_detached_controls()

    def position_detached_overlay(self):
        if self.screen_dialog is None or self.detached_controls is None:return
        panel=self.detached_controls;screen=self.screen_dialog
        panel.resize(max(300,screen.width()-16),panel.sizeHint().height())
        point=QPoint(8,max(8,screen.height()-panel.height()-12))
        panel.move(screen.mapToGlobal(point) if os.name=='nt' else point)

    def cursor_over_detached_controls(self,point):
        panel=self.detached_controls
        return bool(panel is not None and panel.isVisible() and
                    panel.rect().contains(panel.mapFromGlobal(point)))

    def poll_detached_mouse(self):
        if self.screen_dialog is None:return
        point=QCursor.pos()
        if point==self.detached_mouse_position:return
        self.detached_mouse_position=point
        if (self.screen_dialog.frameGeometry().contains(point) or
                self.cursor_over_detached_controls(point)):
            self.show_detached_controls()

    def show_detached_controls(self):
        if self.screen_dialog is None or self.detached_controls is None:return
        self.position_detached_overlay()
        self.detached_controls.show()
        self.detached_controls.raise_()
        self.detached_hide_timer.start(3500)

    def hide_detached_controls(self):
        if self.detached_controls is None or self.screen_dialog is None:return
        if (self.cursor_over_detached_controls(QCursor.pos()) or
                (self.screen_seek_slider is not None and self.screen_seek_slider.isSliderDown())):
            self.detached_hide_timer.start(1600)
            return
        self.detached_controls.hide()

    def seek_screen_slider(self):
        if self.screen_seek_slider is None:return
        if self.timeshift is not None:
            self.seek_slider.setValue(self.screen_seek_slider.value())
            self.seek_from_slider()
        elif self.player and self.player.is_seekable() and self.player.get_length()>0:
            self.player.set_time(self.player.get_length()*self.screen_seek_slider.value()//1000)

    def exit_screen_fullscreen(self):
        screen=self.screen_dialog
        if screen is None:return
        self.detached_hide_timer.stop()
        self.detached_mouse_timer.stop()
        overlay=self.detached_controls
        self.screen_dialog=None
        self.screen_seek_slider=None
        self.detached_controls=None
        self.popout_live_light=None;self.popout_live_button=None
        if overlay:
            overlay.hide()
            overlay.close()
            overlay.deleteLater()
        self.video.setParent(None)
        self.live_layout.insertWidget(2,self.video,1)
        self.video.show()
        self._rebind_video()
        if self._auto_caption_overlay is not None:
            self.destroy_auto_caption_overlay()
        if self._auto_caption_worker is not None and self._auto_caption_text:
            self.receive_auto_caption(self._auto_caption_seq,self._auto_caption_text)
        screen.close()
        screen.deleteLater()

    def show_tv_info(self):
        if not self.selected:return
        title=display_channel_name(self.selected['name'])
        key=self.matched_guide(self.selected)
        programs=self.guide_index()[0].get(key,[])
        now=int(time.time())
        current=next((p for p in programs if p['start']<=now<p['end']),None)
        following=next((p for p in programs if p['start']>now),None)
        lines=[title,'LIVE']
        for prefix,program in (('Now',current),('Next',following)):
            if program:
                lines.append(prefix+': '+program['title']+' — '+format_time(program['start'],self.state['settings']['timezone'],True,detected_zone()))
            else:lines.append(prefix+': No EPG match')
        parent=self.screen_dialog or self
        QMessageBox.information(parent,'DizyTV — Channel information','\n'.join(lines))

    def show_tv_guide(self):
        dialog=QDialog(self.screen_dialog or self)
        dialog.setWindowTitle('DizyTV — Quick channel guide')
        dialog.resize(580,560)
        layout=QVBoxLayout(dialog)
        query=QLineEdit(dialog)
        query.setPlaceholderText('Find a channel by name or country')
        layout.addWidget(query)
        results=QListWidget(dialog)
        layout.addWidget(results,1)
        counter=QLabel(dialog)
        layout.addWidget(counter)
        more=QPushButton('Show next 150 channels',dialog)
        layout.addWidget(more)
        channels=catalogue(self.store.read(),include_disabled=self.show_disabled.isChecked())
        page_size=150
        matching=[]
        shown=0
        def show_more():
            nonlocal shown
            for ch in matching[shown:shown+page_size]:
                item=QListWidgetItem(display_channel_name(ch['name'])+' · '+ch.get('country',''))
                item.setData(Qt.UserRole,ch)
                results.addItem(item)
            shown=min(len(matching),shown+page_size)
            counter.setText(f'{len(matching):,} matching channels · showing {shown:,}')
            more.setEnabled(shown<len(matching))
        def populate():
            nonlocal matching,shown
            results.clear()
            needle=query.text().casefold().strip()
            matching=[ch for ch in channels
                      if needle in (display_channel_name(ch['name'])+' '+ch.get('country','')).casefold()]
            shown=0
            show_more()
        def tune(item):
            ch=item.data(Qt.UserRole)
            dialog.close()
            self.select_guide_channel(ch)
            self.tabs.setCurrentIndex(0)
            self.play()
        query.textChanged.connect(populate)
        more.clicked.connect(show_more)
        results.itemDoubleClicked.connect(tune)
        layout.addWidget(QLabel('Double-click a channel to watch. Use TV Guide for recording.'))
        populate()
        self.guide_popup=dialog
        dialog.show()

    def stop_playback(self):
        self.regional_notice.hide()
        self._play_request_serial+=1
        self.engine_task=None
        self.source_check_serial+=1
        self.stop_auto_captions()
        if self.player:self.player.stop()
        self.close_timeshift()
        self.playback_started=0
        self.seek_slider.setEnabled(False)
        self.rewind_button.setEnabled(False)
        self.forward_button.setEnabled(False)
        self.pause_button.setEnabled(False)
    def add_job(self,job):
        def change(s):
            if not s['settings']['recording_dir'] or not Path(s['settings']['recording_dir']).is_dir():raise ValueError('Choose an available recording folder in Settings first')
            if check_conflicts(s['jobs'],job):raise ValueError('This timer overlaps another recording including its padding')
            s['jobs'].append(job)
        try:self.store.update(change); ensure_worker(self.store.directory); self.tick(); self.tabs.setCurrentIndex(2)
        except ValueError as exc:self.error(str(exc))
    def record_now(self):
        if not self.selected:return
        options=['30 minutes','60 minutes','120 minutes','Until current programme ends','Until stopped (maximum 24 hours)']
        value,ok=QInputDialog.getItem(self,'Record now','Recording length',options,0,False)
        if not ok:return
        now=int(time.time()); title=self.selected['name']; end=now+{'30 minutes':1800,'60 minutes':3600,'120 minutes':7200}.get(value,86400)
        if value.startswith('Until current'):
            key=self.matched_guide(self.selected); programme=next((p for p in self.guide['programmes'] if p['channel']==key and p['start']<=now<p['end']),None)
            if not programme:self.error('No current programme is mapped for this channel'); return
            end=programme['end']+self.state['settings']['padding_after']*60; title=programme['title']
        self.add_job(make_job(self.selected['id'],title,now,end,0,0))
    def schedule_programme(self,ch,p):
        if p['end']<=time.time():self.error('This programme has already ended'); return
        settings=self.state['settings']; message=f"{ch['name']} — {p['title']}\n{format_time(p['start'],settings['timezone'],detected=detected_zone())}\n{format_time(p['end'],settings['timezone'],detected=detected_zone())}\nPadding: {settings['padding_before']} minutes before / {settings['padding_after']} after"
        if QMessageBox.question(self,'Schedule recording',message)==QMessageBox.Yes:
            self.add_job(make_job(ch['id'],p['title'],p['start'],p['end'],settings['padding_before'],settings['padding_after']))
    def selected_job(self):
        row=self.jobs.currentRow(); return self.state['jobs'][row] if 0<=row<len(self.state['jobs']) else None
    def cancel_job(self):
        job=self.selected_job()
        if job and job['status'] in ('queued','starting','recording','paused'):
            self.store.update(lambda s:[j.update(status='cancelled') for j in s['jobs'] if j['id']==job['id']]); self.tick()
    def rearm_job(self):
        job=self.selected_job()
        if not job or job['status']!='paused':return
        def change(s):
            if not s['settings']['recording_dir'] or not Path(s['settings']['recording_dir']).is_dir():raise ValueError('Choose a recording folder first')
            if job['end']<=time.time():raise ValueError('This timer has expired')
            if not any(c['id']==job['channel_id'] for c in s['channels']):raise ValueError('Refresh this channel before rearming')
            if check_conflicts(s['jobs'],job):raise ValueError('This timer overlaps an active timer')
            for j in s['jobs']:
                if j['id']==job['id']:j['status']='queued'
        try:self.store.update(change); ensure_worker(self.store.directory); self.tick()
        except ValueError as exc:self.error(str(exc))
    def play_file(self):
        job=self.selected_job()
        if not job:return
        paths=list(dict.fromkeys([s.get('path','') for s in job.get('segments',[])]+[job.get('path','')]))
        paths=[p for p in paths if p and Path(p).is_file()]
        if not paths:self.error('This recording has no available local file'); return
        if len(paths)>1:
            selected,ok=QInputDialog.getItem(self,'Play recording segment','An interrupted recording contains multiple preserved files',paths,0,False)
            if not ok:return
        else:selected=paths[0]
        # A recording is a new playback request: detach the live capture and
        # pending engine callback before its watchdog or seek controls can
        # redirect the file back to LIVE.
        self.stop_playback()
        self.play_url(str(Path(selected).resolve()))
    def delete_file(self):
        job=self.selected_job()
        if not job or job['status'] in ('queued','starting','recording'):return
        if QMessageBox.question(self,'Delete recording','Delete this local recording file?')==QMessageBox.Yes:
            try:
                paths=[s.get('path','') for s in job.get('segments',[])]+[job.get('path','')]
                for path in set(paths):
                    if path:Path(path).unlink(missing_ok=True)
                self.store.update(lambda s:s.update(jobs=[j for j in s['jobs'] if j['id']!=job['id']])); self.tick()
            except OSError as exc:self.error(str(exc))
    def backup(self):
        path,_=QFileDialog.getSaveFileName(self,'Save DizyTV backup','DizyTV-backup.json','JSON (*.json)')
        if path:
            try:Path(path).write_text(export_backup(self.store.read()),encoding='utf-8'); self.status.setText('Backup saved on this device')
            except (OSError,ValueError) as exc:self.error(str(exc))
    def restore(self):
        path,_=QFileDialog.getOpenFileName(self,'Restore DizyTV backup','','JSON (*.json)')
        if not path:return
        try:
            if Path(path).stat().st_size>MAX_BACKUP:raise ValueError('Backup exceeds 16 MiB')
            restored=restore_backup(Path(path).read_text(encoding='utf-8'))
            if QMessageBox.question(self,'Restore backup',f"Replace preferences with {len(restored['channels'])} channels, {len(restored['favourites'])} favourites and {len(restored['jobs'])} timers?\nChoose storage again afterwards. Restored timers stay paused.")!=QMessageBox.Yes:return
            def change(s):
                if any(j['status'] in ('starting','recording') for j in s['jobs']):raise ValueError('Stop the active recording before restoring a backup')
                s.clear(); s.update(restored)
            self.store.update(change)
            self.selected=None
            self.guide={'names':{},'programmes':[]}
            atomic_json(self.store.directory/'guide.json',self.guide)
            self.state=self.store.read()
            # Restoring a backup must apply its caption on/off preference to
            # the current VLC player, not reuse the previous playback cache.
            self._subtitle_manual_track=None
            self._subtitle_auto_applied=False
            self._subtitle_track_signature=()
            self.apply_interface_scale()
            self.render_channels()
            self.sync_subtitles()
            self.tick()
            self.status.setText('Backup restored • choose storage and rearm timers explicitly')
        except (OSError,ValueError) as exc:self.error(str(exc))
    def closeEvent(self,event):
        self._ui_heartbeat_timer.stop()
        if self._ui_hang_monitor is not None:
            self._ui_hang_monitor.stop()
            self._ui_hang_monitor=None
        # Modeless tools may own timers or queued progressive work. Hiding the
        # main window does not close them, so route shutdown through their
        # cancellation/cleanup handlers before stopping the player.
        for name in ('health_dialog','duplicate_dialog','usage_dialog'):
            dialog=getattr(self,name,None)
            if dialog is not None:dialog.close()
        for timer in (self.light_timer,self.detached_hide_timer,
                      self.detached_mouse_timer,self.clock,
                      self.refresh_clock,self.guide_clock):
            timer.stop()
        self.exit_screen_fullscreen()
        self.stop_playback()
        if self.player:self.player.release(); self.player=None
        if self.vlc_instance:self.vlc_instance.release(); self.vlc_instance=None
        # Only stop the Outpace child that DizyTV itself launched. Do not
        # disrupt an active/due-soon detached recording, or wait on the Qt UI.
        if sys.platform=='darwin' or sys.platform.startswith('linux'):
            from .outpace import stop_owned_daemon
            latest=self.store.try_read()
            jobs=(latest or self.state).get('jobs',[])
            now=time.time()
            from .core import ace_request_params
            channels={c['id']:c for c in (latest or self.state).get('channels',[])}
            # Keep the GUI-owned helper only when a *currently active Ace*
            # recording still needs it. Future timers start an engine from
            # the detached recorder when due; ordinary HTTP jobs do not need
            # Outpace, and paused/cancelled jobs must not pin a P2P daemon.
            pending=(latest is None or any(
                job.get('status') in ('recording','starting') and
                job.get('start',now+1) <= now < job.get('end',0) and
                ace_request_params(channels.get(job.get('channel_id'),{}).get('stream','')) is not None
                for job in jobs))
            # Hand off even an idle GUI-owned helper when a detached worker
            # exists: another open DizyTV window may still be viewing it.
            # The worker performs native-session and PID checks off the Qt
            # thread. Tests/smoke mode without a worker stop it directly.
            if pending or self.start_worker:
                from .outpace import handoff_owned_daemon
                handed_off=handoff_owned_daemon(self.store.directory)
                if not pending and not handed_off:
                    stop_owned_daemon()
            else:
                stop_owned_daemon()
        super().closeEvent(event)


def run(directory=None,smoke=False):
    app=QApplication(sys.argv); app.setApplicationName('DizyTV'); app.setOrganizationName('DizygoticCode'); app.setStyleSheet(desktop_style())
    window=MainWindow(Store(directory),start_worker=not smoke); window.show()
    if smoke:QTimer.singleShot(1200,app.quit)
    return app.exec()
