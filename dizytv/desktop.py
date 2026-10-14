"""Native Qt desktop client for Windows and macOS."""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
from zoneinfo import available_timezones

from PySide6.QtCore import Qt, QUrl, QTimer, QTimeZone, QRunnable, QThreadPool, QObject, Signal, QRectF, QEvent, QPoint
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QDesktopServices, QShortcut, QKeySequence, QCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QCheckBox, QSplitter,
    QTabWidget, QFrame, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QPlainTextEdit, QFileDialog, QMessageBox, QInputDialog, QMenu, QSlider, QSizePolicy)

from .core import (parse_playlist, parse_xmltv, format_time, stream_url, make_job,
                   check_conflicts, export_backup, restore_backup, MAX_BACKUP, validate_state, normalise_genre, catalogue, match_guide, guide_lookup, display_channel_name, channel_section, channel_kind, COUNTRIES, GENRES)
from .network import download
from .sources import configured_playlists, refresh_catalogue, DEFAULT_GUIDE_URLS, DEFAULT_PLAYLIST_URLS, source_label
from .storage import Store, atomic_json
from .recorder import ensure_worker
from .engine import ensure_ready, engine_diagnostics
from .timeshift import RollingTimeshift
from .stream_diagnostics import probe_stream

ASSETS = Path(getattr(sys,'_MEIPASS', Path(__file__).resolve().parent.parent))/'assets'
STYLE = '''
QWidget { background:#151e19; color:#f3ead5; font-size:14px; }
QLabel#brand { font-size:27px; font-weight:800; }
QPushButton { background:#355b43; border:1px solid #54785b; padding:9px 15px; border-radius:7px; }
QPushButton:hover { background:#477552; } QPushButton:disabled { color:#8a938b; }
QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#202d24; padding:8px; border:1px solid #405246; border-radius:5px; }
QListWidget { background:#1a261e; border:0; } QListWidget::item { padding:12px; border-bottom:1px solid #2f4033; }
QListWidget::item:selected { background:#416248; }
QTabBar::tab { padding:12px 22px; background:#25362b; } QTabBar::tab:selected { background:#416248; }
QTableWidget { gridline-color:#354638; background:#19251d; }
QHeaderView::section { background:#2d4133; padding:8px; border:0; }
QPushButton#tvPrimary { background:#397f51; border:1px solid #64b679; color:white; font-weight:700; }
QPushButton#tvPrimary:hover { background:#4b9963; }
QPushButton#tvDanger { background:#69352f; border:1px solid #b26354; }
QPushButton#tvLive { background:#713b38; border:1px solid #cc7771; font-weight:700; color:#ffe2d4; }
QSlider::groove:horizontal { height:8px; border:1px solid #355c48; background:#21392e; border-radius:4px; }
QSlider::sub-page:horizontal { background:#61bd7c; border-radius:4px; }
QSlider::handle:horizontal { width:16px; margin:-6px 0; border:2px solid #d9f6dd; background:#72df99; border-radius:8px; }
QSlider:disabled::handle:horizontal { background:#6b746d; border-color:#99a69d; }
QSlider#seekBar::groove:horizontal { height:10px; }
QSlider#seekBar::handle:horizontal { width:20px; margin:-7px 0; border-radius:10px; }
QSlider#volumeBar::sub-page:horizontal { background:#62adca; }
QScrollArea#toolbarScroll, QScrollArea#playerControlScroll { border:0; background:transparent; }
'''


def desktop_style(scale=100, button_size='Normal'):
    """Respect TV DPI while allowing smaller independent UI/controls."""
    scale=max(75,min(150,int(scale)))/100
    pad={'Compact':(4,8),'Normal':(9,15),'Large':(13,20)}.get(button_size,(9,15))
    return (STYLE.replace('font-size:14px;',f'font-size:{round(14*scale)}px;')
                 .replace('font-size:27px;',f'font-size:{round(27*scale)}px;')
                 .replace('padding:9px 15px;',f'padding:{round(pad[0]*scale)}px {round(pad[1]*scale)}px;')
                 .replace('padding:12px 22px;',f'padding:{round(10*scale)}px {round(18*scale)}px;')
                 .replace('QListWidget::item { padding:12px;',f'QListWidget::item {{ padding:{round(9*scale)}px;'))


def detected_zone():
    value = bytes(QTimeZone.systemTimeZoneId()).decode('utf-8')
    return value if value in available_timezones() else 'UTC'


class Signals(QObject):
    success = Signal(object)
    failure = Signal(str)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__(); self.function = function; self.signals = Signals()
    def run(self):
        try:
            self.signals.success.emit(self.function())
        except Exception as exc:
            self.signals.failure.emit(str(exc))


class GuideGrid(QWidget):
    channel_clicked = Signal(object)
    programme_record_requested = Signal(object,object)
    channel_record_requested = Signal(object)
    def __init__(self):
        super().__init__(); self.rows=[]; self.programmes=[]; self.hitboxes=[]; self.zone='auto'; self.start=0
        self.guide_scale=100
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
        self.rows = channels[:250]; self.programmes = programmes; self.mappings=mappings
        self.zone=zone; self.start=start
        self.update_dimensions()
    def paintEvent(self,event):
        p=QPainter(self); p.fillRect(self.rect(),QColor('#15221a')); self.hitboxes=[]
        rowheight,left,hour,font=self.geometry_units()
        p.setFont(QFont('Sans Serif',font)); scale=hour/3600
        for i in range(7):
            x=left+i*hour
            p.setPen(QColor('#47654b')); p.drawLine(x,0,x,self.height())
            p.setPen(QColor('#f3ead5')); p.drawText(x+5,30,format_time(self.start+i*3600,self.zone,False,detected_zone()))
        by_channel={}
        for item in self.programmes:
            if item['start']<self.start+6*3600 and item['end']>self.start:
                by_channel.setdefault(item['channel'],[]).append(item)
        for row,ch in enumerate(self.rows):
            y=48+row*rowheight
            p.fillRect(0,y,left,rowheight-3,QColor('#253b2b'))
            p.setPen(QColor('#f3ead5')); p.drawText(QRectF(12,y+4,left-20,rowheight-8),Qt.AlignVCenter|Qt.TextWordWrap,display_channel_name(ch['name']))
            key=self.mappings.get(ch['id'],ch['tvg_id'])
            entries=by_channel.get(key,[])
            if not entries:
                p.setPen(QColor('#95a695')); p.drawText(left+15,y+33,'No guide match — choose Map EPG for this channel')
            for item in entries:
                x=left+max(0,item['start']-self.start)*scale
                width=(min(item['end'],self.start+6*3600)-max(item['start'],self.start))*scale
                rect=QRectF(x+2,y+2,max(0,width-4),rowheight-6)
                p.fillRect(rect,QColor('#3c5c42' if item['start']<=time.time()<item['end'] else '#283e30'))
                p.setPen(QColor('#f3ead5')); p.drawText(rect.adjusted(8,2,-8,-2),Qt.AlignVCenter|Qt.TextWordWrap,item['title'])
                self.hitboxes.append((rect,ch,item))
        x=left+(time.time()-self.start)*scale
        if left<=x<=left+6*hour:
            p.setPen(QColor('#f4af71')); p.drawLine(int(x),40,int(x),self.height())
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
            programme=next((p for rect,ch,p in reversed(self.hitboxes)
                            if ch['id']==channel['id'] and rect.contains(event.position())),None)
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
        self.engine=QLineEdit(self.original['engine_url']); form.addRow('Ace engine address',self.engine)
        self.engine_path=QLineEdit(self.original.get('engine_executable',''))
        self.engine_path.setReadOnly(True)
        self.engine_path.setPlaceholderText('Auto-detect from Windows registry / AppData')
        exe_button=QPushButton('Choose installed EXE')
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
        self.guide_scale=QSpinBox()
        self.guide_scale.setRange(55,130);self.guide_scale.setSingleStep(5)
        self.guide_scale.setSuffix(' %');self.guide_scale.setValue(self.original.get('guide_scale',100))
        form.addRow('TV guide density / size',self.guide_scale)
        self.feeds=QPlainTextEdit('\n'.join(self.original['xmltv_urls'])); self.feeds.setPlaceholderText('One XMLTV URL per line'); self.feeds.setMaximumHeight(95); form.addRow('XMLTV sources',self.feeds)
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
        note=QLabel('Timers use UTC and do not move when timezone or guide correction changes.\nDesktop recording requires an awake computer. VLC 3 and the Ace engine must be installed separately.\nMac playback connects to a reachable Windows/Linux Ace engine.'); note.setWordWrap(True); form.addRow(note)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def add_free_playlists(self):
        existing=[u.strip() for u in self.playlists.toPlainText().splitlines() if u.strip()]
        self.playlists.setPlainText('\n'.join(dict.fromkeys(existing + DEFAULT_PLAYLIST_URLS)))

    def pick_engine_path(self):
        path,_=QFileDialog.getOpenFileName(self,'Locate an installed Ace Stream engine',
              self.engine_path.text() or os.environ.get('APPDATA',''),
              'Ace Stream engine (ace_engine.exe ace_console.exe)')
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
                    guide_scale=self.guide_scale.value(),engine_executable=self.engine_path.text())


class MainWindow(QMainWindow):
    def __init__(self,store=None,start_worker=True):
        super().__init__(); self.store=store or Store(); self.player=None; self.vlc_instance=None; self.task=None
        self.state=self.store.read(); self.guide={'names':{},'programmes':[]}; self.guide_start=int(time.time()/3600)*3600
        self.selected=None; self.start_worker=start_worker; self.pool=QThreadPool.globalInstance(); self.displayed_zone=''; self.source_errors=[]; self.engine_task=None; self.playback_started=0; self.playback_reported=False; self.cinema_mode=False; self.screen_dialog=None; self.guide_popup=None; self.screen_seek_slider=None; self.timeshift=None; self.timeshift_task=None; self.timeshift_lag=0
        self.last_live_recovery=0;self.last_good_video=time.monotonic()
        self.last_capture_progress=time.monotonic();self.last_capture_seq=-1
        self.source_check=None;self.source_check_serial=0
        self._last_media_activity=None
        self.detached_controls=None;self.detached_hide_timer=QTimer(self)
        self.detached_hide_timer.setSingleShot(True)
        self.detached_hide_timer.timeout.connect(self.hide_detached_controls)
        self.detached_mouse_position=None
        self.detached_mouse_timer=QTimer(self)
        self.detached_mouse_timer.setInterval(250)
        self.detached_mouse_timer.timeout.connect(self.poll_detached_mouse)
        self.setWindowTitle('DizyTV'); self.resize(1150,730)
        self.setMinimumSize(480,360)
        self.setWindowIcon(QIcon(str(ASSETS/'branding/dizytv-logo.png')))
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root)
        topbar=QWidget(); top=QHBoxLayout(topbar);top.setContentsMargins(3,3,3,3)
        logo=QLabel(); logo.setPixmap(QPixmap(str(ASSETS/'branding/dizytv-logo.png')).scaled(75,75,Qt.KeepAspectRatio,Qt.SmoothTransformation)); top.addWidget(logo)
        brand=QLabel('DizyTV'); brand.setObjectName('brand'); top.addWidget(brand); top.addStretch()
        self.timezone_label=QLabel(); top.addWidget(self.timezone_label)
        for label,handler in [('Refresh channels',self.refresh_channels),('Source status',self.show_source_status),('Refresh guide',self.refresh_guide),('Settings',self.settings)]:
            b=QPushButton(label); b.clicked.connect(handler); top.addWidget(b)
        self.header_scroll=QScrollArea()
        self.header_scroll.setObjectName('toolbarScroll')
        self.header_scroll.setWidgetResizable(False)
        self.header_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.header_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.header_scroll.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        topbar.adjustSize()
        self.header_scroll.setWidget(topbar)
        self.header_scroll.setFixedHeight(topbar.sizeHint().height()+20)
        layout.addWidget(self.header_scroll)
        self.header_buttons=[logo,brand,self.timezone_label]+[top.itemAt(i).widget() for i in range(top.count()) if top.itemAt(i).widget() is not None]
        split=QSplitter();split.setChildrenCollapsible(True);layout.addWidget(split,1)
        self.split=split
        sidebar=QWidget(); side=QVBoxLayout(sidebar); self.search=QLineEdit(); self.search.setPlaceholderText('Search channels or groups'); self.search.textChanged.connect(self.render_channels); side.addWidget(self.search)
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
            label.setStyleSheet('color:#a8c5ad')
            filter_layout.addWidget(label)
            widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            widget.setMinimumContentsLength(8)
            widget.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
            widget.setMinimumWidth(0)
            widget.addItem(default,'')
            widget.currentIndexChanged.connect(self.render_channels)
            filter_layout.addWidget(widget)
        side.addWidget(filters)
        browser_label=QLabel('Countries / categories / channels'); side.addWidget(browser_label)
        self.country_tree=QTreeWidget(); self.country_tree.setHeaderHidden(True)
        self.country_tree.setMaximumHeight(240)
        self.country_tree.itemClicked.connect(self.country_tree_clicked)
        self.country_tree.itemDoubleClicked.connect(self.country_tree_double_clicked)
        side.addWidget(self.country_tree)
        self._tree_dirty=True
        self.favourites_only=QCheckBox('★ Favourites only'); self.favourites_only.toggled.connect(self.render_channels); side.addWidget(self.favourites_only)
        self.channels=QListWidget(); self.channels.currentItemChanged.connect(self.choose_channel); self.channels.itemDoubleClicked.connect(lambda:self.play()); side.addWidget(self.channels,1)
        for label,handler in [('★ Add / remove favourite',self.favourite),('Map EPG',self.map_channel),('Edit categories',self.edit_categories)]:
            b=QPushButton(label); b.clicked.connect(handler); side.addWidget(b)
        self.sidebar=sidebar
        sidebar.setMinimumWidth(0)
        sidebar.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Expanding)
        split.addWidget(sidebar); self.tabs=QTabWidget();self.tabs.setMinimumWidth(0)
        split.addWidget(self.tabs);split.setSizes([270,880])
        live=QWidget(); live_layout=QVBoxLayout(live); self.live_layout=live_layout; self.now=QLabel('Choose a channel, then press Play'); self.now.setWordWrap(True); live_layout.addWidget(self.now)
        self.channel_banner=QLabel('')
        self.channel_banner.setStyleSheet('background:#304d36; color:white; padding:8px;')
        self.channel_banner.setWordWrap(True)
        self.channel_banner.hide()
        live_layout.addWidget(self.channel_banner)
        self.video=QFrame(); self.video.setStyleSheet('background:black;'); self.video.setAttribute(Qt.WA_NativeWindow); self.video.setMouseTracking(True);self.video.installEventFilter(self); live_layout.addWidget(self.video,1)
        controls_widget=QWidget()
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
        self.live_button=QPushButton('● LIVE')
        self.live_button.clicked.connect(self.jump_to_live)
        controls.addWidget(self.live_button)
        self.guide_button=QPushButton('☷ Guide')
        self.guide_button.clicked.connect(self.show_tv_guide)
        controls.addWidget(self.guide_button)
        self.info_button=QPushButton('Info')
        self.info_button.clicked.connect(self.show_tv_info)
        controls.addWidget(self.info_button)
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
        setup_engine=QPushButton('Set up Ace Stream engine')
        setup_engine.setToolTip('Visit the official provider to install the optional P2P engine. Never needed for HTTP/HLS channels.')
        setup_engine.clicked.connect(self.open_ace_stream_setup)
        controls.addWidget(setup_engine)
        self.controls_scroll=QScrollArea()
        self.controls_scroll.setObjectName('playerControlScroll')
        self.controls_scroll.setWidgetResizable(False)
        self.controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls_scroll.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Fixed)
        controls_widget.adjustSize()
        self.controls_scroll.setWidget(controls_widget)
        self.controls_scroll.setFixedHeight(controls_widget.sizeHint().height()+20)
        live_layout.addWidget(self.controls_scroll)
        self.tv_controls=controls
        for item in range(controls.count()):
            widget=controls.itemAt(item).widget()
            if isinstance(widget,QPushButton):
                if widget in (self.live_button,):widget.setObjectName('tvLive')
                elif widget in (self.pause_button,self.popout_button):widget.setObjectName('tvPrimary')
                elif widget.text().startswith(('■','● Record')):widget.setObjectName('tvDanger')
        self.seek_notice=QLabel('Live pause / rewind: available only when this stream offers a seekable DVR window')
        self.seek_notice.setWordWrap(True)
        live_layout.addWidget(self.seek_notice)
        self.seek_slider=QSlider(Qt.Horizontal)
        self.seek_slider.setObjectName('seekBar')
        self.seek_slider.setRange(0,1000)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderReleased.connect(self.seek_from_slider)
        live_layout.addWidget(self.seek_slider)
        volume_row=QHBoxLayout()
        volume_row.addWidget(QLabel('Volume'))
        self.volume_slider=QSlider(Qt.Horizontal)
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
        self.grid=GuideGrid(); self.grid.channel_clicked.connect(self.play_guide_channel); self.grid.programme_record_requested.connect(self.schedule_programme); self.grid.channel_record_requested.connect(self.record_guide_channel); scroll=QScrollArea(); scroll.setWidget(self.grid); scroll.setWidgetResizable(True); guide_layout.addWidget(scroll); self.tabs.addTab(guide_page,'TV Guide')
        recordings=QWidget(); rec_layout=QVBoxLayout(recordings)
        self.jobs=QTableWidget(0,5); self.jobs.setHorizontalHeaderLabels(['Programme','Start','End','Status','Size']); self.jobs.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.jobs.setSelectionBehavior(QTableWidget.SelectRows); self.jobs.setSelectionMode(QTableWidget.SingleSelection); rec_layout.addWidget(self.jobs)
        rec_buttons=QHBoxLayout()
        for label,handler in [('Stop / cancel',self.cancel_job),('Rearm restored timer',self.rearm_job),('Play file',self.play_file),('Delete file',self.delete_file)]:
            b=QPushButton(label); b.clicked.connect(handler); rec_buttons.addWidget(b)
        rec_layout.addLayout(rec_buttons); hint=QLabel('One recording at a time. Closing this window leaves the recorder running.\nAfter a reboot, open DizyTV to resume future timers. This alpha does not wake a sleeping computer.'); hint.setWordWrap(True); rec_layout.addWidget(hint); self.tabs.addTab(recordings,'Recordings')
        backup=QWidget(); back_layout=QVBoxLayout(backup); message=QLabel('Keep your DizyTV setup on your own device\n\nBack up favourites, channel listings, guide mappings, preferences and timers.\nVideo files and device storage permissions are excluded. Restored timers stay paused until you choose storage and rearm them.'); message.setWordWrap(True); back_layout.addWidget(message)
        for label,handler in [('Save local backup',self.backup),('Restore local backup',self.restore)]:
            b=QPushButton(label); b.clicked.connect(handler); back_layout.addWidget(b)
        back_layout.addStretch(); self.tabs.addTab(backup,'Backup & Restore')
        self.status=QLabel('Native alpha • Configure your engine, XMLTV sources and recording storage in Settings'); layout.addWidget(self.status)
        self.apply_interface_scale()
        self.load_guide(); self.render_channels(); self.tick()
        self.clock=QTimer(self); self.clock.timeout.connect(self.tick); self.clock.start(5000)
        self.refresh_clock=QTimer(self); self.refresh_clock.timeout.connect(self.refresh_channels); self.refresh_clock.start(6*3600*1000)
        self.guide_clock=QTimer(self); self.guide_clock.timeout.connect(self.refresh_guide); self.guide_clock.start(12*3600*1000)
        if start_worker:
            ensure_worker(self.store.directory)
            # Previously cached Ace channels hid newly configured public feeds.
            # Always refresh on startup, retaining cached channels until success.
            QTimer.singleShot(200,self.refresh_channels)
    def error(self,message):
        self.status.setText(message); QMessageBox.warning(self,'DizyTV',message)
    def load_guide(self):
        path=self.store.directory/'guide.json'
        try:
            if path.exists() and path.stat().st_size<=100*1024**2:
                self.guide=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    def show_source_status(self):
        state=self.store.read(); counts={}
        for ch in state['channels']:
            key=ch.get('source','https://search-ace.stream/playlist')
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
        self.country_tree.clear()
        groups={}
        for ch in channels:
            country=ch.get('country') or 'Unspecified'
            section=channel_section(ch)
            groups.setdefault(country,{}).setdefault(section,[]).append(ch)
        for country in sorted(groups,key=lambda c:(c=='Unspecified',c.casefold())):
            sections=groups[country]
            total=sum(len(values) for values in sections.values())
            country_item=QTreeWidgetItem([f'{country} ({total})'])
            country_item.setData(0,Qt.UserRole,('country',country,'',''))
            self.country_tree.addTopLevelItem(country_item)
            for section in sorted(sections):
                values=sorted(sections[section],key=lambda ch:display_channel_name(ch['name']).casefold())
                section_item=QTreeWidgetItem([f'{section} ({len(values)})'])
                section_item.setData(0,Qt.UserRole,('section',country,section,''))
                country_item.addChild(section_item)
                for ch in values:
                    channel_item=QTreeWidgetItem([display_channel_name(ch['name'])])
                    channel_item.setData(0,Qt.UserRole,('channel',country,section,ch['id']))
                    section_item.addChild(channel_item)
            country_item.setExpanded(country in ('United Kingdom','United States'))
        self.country_tree.blockSignals(False)
        self._tree_dirty=False

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
        previous=self.selected['id'] if self.selected else None; self.state=self.store.read(); source=catalogue(self.state); self.channels.blockSignals(True); self.channels.clear()
        # Give free HTTP/HLS channels prominence, without removing Ace streams.
        source.sort(key=lambda ch:(ch.get('transport')=='Ace Stream',ch.get('country')!='United Kingdom',display_channel_name(ch['name']).casefold()))
        self.build_country_tree(source)
        selected_source=self.source_filter.currentData()
        urls=configured_playlists(self.state['settings'])
        counts={}
        for ch in source:
            source_url=ch.get('source','https://search-ace.stream/playlist')
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
            source_url=ch.get('source','https://search-ace.stream/playlist')
            if active_source=='<http>' and transport=='Ace Stream': continue
            if active_source=='<ace>' and transport!='Ace Stream': continue
            if active_source not in ('','<http>','<ace>') and active_source!=source_url: continue
            if query not in (ch['name']+' '+display_channel_name(ch['name'])+' '+ch['group']).casefold() or self.favourites_only.isChecked() and ch['id'] not in favs:continue
            if self.section_filter.currentData() and channel_section(ch)!=self.section_filter.currentData():continue
            country=self.country_filter.currentData(); genre=self.genre_filter.currentData(); kind=self.kind_filter.currentData()
            if country and ch.get('country','Unspecified')!=country:continue
            if kind and kind not in (channel_kind(ch),ch.get('transport','Ace Stream' if ch['stream'].startswith('acestream:') else 'HTTP')):continue
            key=self.matched_guide(ch)
            if genre and ch.get('genre','Unspecified')!=genre and genre not in genre_by_id.get(key,set()):continue
            item=QListWidgetItem(('★ ' if ch['id'] in favs else '')+display_channel_name(ch['name'])); item.setData(Qt.UserRole,ch); self.channels.addItem(item)
            if ch['id']==previous:self.channels.setCurrentItem(item); self.selected=ch
        self.channels.blockSignals(False); self.render_guide()
    def choose_channel(self,item,*_):
        self.selected=item.data(Qt.UserRole) if item else None; self.render_now()
    def render_now(self):
        if not self.selected:return
        cid=self.matched_guide(self.selected); now=time.time()
        by_channel,_=self.guide_index()
        items=[p for p in by_channel.get(cid,()) if p['end']>now][:2]
        self.now.setText(display_channel_name(self.selected['name'])+'\n'+'\n'.join(format_time(p['start'],self.state['settings']['timezone'],False,detected_zone())+'  '+p['title'] for p in items) if items else display_channel_name(self.selected['name'])+' — no guide match')
    def render_guide(self):
        # The grid only paints 250 visible channels within a six-hour window;
        # never pass the complete XMLTV cache to its paintEvent.
        channels=[self.channels.item(i).data(Qt.UserRole) for i in range(min(self.channels.count(),250))]
        genre=self.genre_filter.currentData()
        by_channel,_=self.guide_index()
        resolved={}
        programmes=[]
        end=self.guide_start+6*3600
        for ch in channels:
            key=self.matched_guide(ch)
            resolved[ch['id']]=key
            for p in by_channel.get(key,()):
                if not (p['start']<end and p['end']>self.guide_start):
                    continue
                if genre and ch.get('genre','Unspecified')!=genre and genre not in {normalise_genre(c) for c in p.get('categories',[])}:
                    continue
                programmes.append(p)
        self.grid.set_guide_scale(self.state['settings'].get('guide_scale',100))
        self.grid.set_data(channels,programmes,resolved,self.state['settings']['timezone'],self.guide_start)
        self.guide_date.setText(format_time(self.guide_start,self.state['settings']['timezone'],detected=detected_zone()))
    def move_guide(self,delta):
        self.guide_start=self.guide_start+delta if delta else int(time.time()/3600)*3600; self.render_guide()
    def apply_interface_scale(self):
        settings=self.state['settings']
        app=QApplication.instance()
        if app:app.setStyleSheet(desktop_style(settings.get('ui_scale',100),
                                               settings.get('button_size','Normal')))
        for scroll in (self.header_scroll,self.controls_scroll):
            widget=scroll.widget()
            if widget:
                widget.adjustSize()
                scroll.setFixedHeight(widget.sizeHint().height()+20)

    def media_activity(self):
        """VLC's decoded picture/audio counters catch freezes with State.Playing.

        Older VLC builds may not provide stats; do not guess in that case.
        """
        try:
            import vlc
            media=self.player.get_media()
            if media is None:return None
            stats=vlc.MediaStats()
            if not media.get_stats(stats):return None
            return int(stats.displayed_pictures)+int(stats.played_abuffers)
        except (AttributeError,TypeError,RuntimeError,OSError):
            return None

    def check_live_timeshift(self,now=None):
        """Recover VLC buffering/errors only if the local cache is still growing.

        Never interrupt user pause, replay, or a scheduled recording.
        """
        if self.timeshift is None or self.player is None or not self.playback_started:
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
            self.last_live_recovery=now
            self.last_good_video=now
            # Reconnecting the player does not stop or erase the capture ring.
            self.play_url(self.timeshift.live_url())
            self.status.setText('Recovered stalled timeshift playback to LIVE automatically.')

    def tick(self):
        self.state=self.store.read(); zone=self.state['settings']['timezone']
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
        if self.player and self.playback_started:
            local_active=self.timeshift is not None and bool(self.timeshift.window.snapshot())
            seekable=bool(self.player.is_seekable()) or local_active
            length=self.player.get_length()
            position=self.player.get_time()
            self.seek_slider.setEnabled(local_active or (seekable and length>0))
            if seekable and length>0 and position>=0 and not self.seek_slider.isSliderDown():
                self.seek_slider.setValue(max(0,min(1000,int(position*1000/length))))
            if self.screen_seek_slider is not None:
                self.screen_seek_slider.setEnabled(seekable and length>0)
                if seekable and length>0 and position>=0 and not self.screen_seek_slider.isSliderDown():
                    self.screen_seek_slider.setValue(max(0,min(1000,int(position*1000/length))))
            self.rewind_button.setEnabled(seekable)
            self.pause_button.setEnabled(seekable)
            if local_active:
                available=self.timeshift.window.latest_seconds()
                self.seek_notice.setText('Device buffer: '+str(int(available//60))+' min cached of '+str(self.timeshift.window.minutes)+' min / '+str(round(self.timeshift.window.total/1024**3,2))+' GiB; max '+str(round(self.timeshift.window.max_bytes/1024**3,1))+' GiB')
                if not self.seek_slider.isSliderDown():
                    self.seek_slider.setValue(max(0,1000-int(self.timeshift_lag/max(1,available)*1000)))
            else:
                self.seek_notice.setText('DVR window available' if seekable else 'LIVE — no local time-shift enabled')
        if self.player and self.playback_started and not self.playback_reported:
            state=str(self.player.get_state())
            if state.endswith('.Playing'):
                self.playback_reported=True
                self.status.setText('Now playing inside DizyTV')
            elif state.endswith('.Error') or state.endswith('.Ended'):
                self.playback_reported=True
                self.status.setText('VLC could not play this source. Checking the provider response…')
                if self.timeshift is None:self.diagnose_stream()
            elif time.monotonic()-self.playback_started>25:
                self.playback_reported=True
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
    def settings(self):
        dialog=Settings(self.store.read(),self)
        if dialog.exec()==QDialog.Accepted:
            try:
                self.store.update(lambda s:s.update(settings=dialog.values()))
                self.state=self.store.read()
                self.apply_interface_scale()
                self.render_guide()
                self.tick()
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
        options=['No mapping']+[key+' — '+name for key,name in sorted(self.guide['names'].items())]
        value,ok=QInputDialog.getItem(self,'Guide channel mapping','Choose the correct XMLTV channel',options,0,False)
        if ok:
            cid=self.selected['id']; target='' if value=='No mapping' else value.split(' — ')[0]
            self.store.update(lambda s:s['mappings'].update({cid:target})); self.state=self.store.read(); self.render_guide(); self.render_now()
    def init_player(self):
        if self.player:return
        if os.name=='nt':
            for root in ('PROGRAMFILES','PROGRAMFILES(X86)'):
                folder=Path(os.environ.get(root,'C:/Program Files'))/'VideoLAN'/'VLC'
                if (folder/'libvlc.dll').exists():
                    os.environ['PATH']=str(folder)+os.pathsep+os.environ.get('PATH',''); self.dll_dir=os.add_dll_directory(str(folder)); break
        import vlc
        self.vlc_instance=vlc.Instance('--no-video-title-show'); self.player=self.vlc_instance.media_player_new()
        self.player.audio_set_volume(self.volume_slider.value())
        win=int(self.video.winId())
        if sys.platform=='darwin':self.player.set_nsobject(win)
        elif os.name=='nt':self.player.set_hwnd(win)
        else:self.player.set_xwindow(win)
    def play_url(self,url):
        try:
            self.init_player()
            self.player.stop()
            media=self.vlc_instance.media_new(url)
            # Some free HLS origins reject libVLC's default User-Agent.
            # This is format compatibility, not bypassing geo/DRM restrictions.
            if url.startswith('http'):
                media.add_option(':http-user-agent=Mozilla/5.0 (compatible; DizyTV/0.1)')
            self.player.set_media(media); media.release()
            if self.player.play()==-1:raise RuntimeError('libVLC could not start playback')
            self.playback_started=time.monotonic(); self.playback_reported=False
            self._last_media_activity=None
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
            self.error('Playback could not start. Check that VLC 3 is installed and the stream is available. '+str(exc))
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
        # Do not redistribute, download or silently execute proprietary binaries.
        # The browser opens the provider's official page with the latest Windows version.
        if not QDesktopServices.openUrl(QUrl('https://docs.acestream.net/products/')):
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
        diagnostic=Task(lambda:probe_stream(self.selected['stream']))
        self.source_check=diagnostic
        def ready(message):
            if (serial==self.source_check_serial and self.selected and
                    self.selected['id']==channel):
                self.status.setText(message)
        diagnostic.signals.success.connect(ready)
        diagnostic.signals.failure.connect(lambda _message:None)
        self.pool.start(diagnostic)

    def close_timeshift(self):
        prior=self.timeshift
        self.timeshift=None
        self.timeshift_task=None
        self.timeshift_lag=0
        self.last_capture_seq=-1
        self.last_capture_progress=time.monotonic()
        self.last_good_video=time.monotonic()
        if prior:
            prior.close()

    def play_stream(self,url):
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
        job=Task(session.start)
        self.timeshift_task=job
        def ready(local_url):
            if self.timeshift is not session:
                session.close()
                return
            self.timeshift_task=None
            self.play_url(local_url)
            self.seek_notice.setText('Temporary on-device timeshift is recording; up to '+str(session.window.minutes)+' minutes')
        def failed(message):
            if self.timeshift is not session:return
            self.timeshift=None
            self.timeshift_task=None
            session.close()
            self.play_url(url)
            self.seek_notice.setText('Timeshift unavailable ('+message+'); playing original stream')
        job.signals.success.connect(ready)
        job.signals.failure.connect(failed)
        self.pool.start(job)

    def play(self):
        if not self.selected:return
        active=[j for j in self.store.read()['jobs'] if j['status']=='recording' and j['channel_id']!=self.selected['id']]
        if active:self.error('A different channel is recording. Stop or finish that recording before switching playback.'); return
        ch=self.selected
        url=stream_url(ch['stream'],self.state['settings']['engine_url'])
        from .core import ace_id
        if ace_id(ch['stream']):
            if self.engine_task is not None:
                self.status.setText('Ace Stream engine startup is already in progress…'); return
            self.status.setText('Checking/starting your installed Ace Stream engine…')
            task=Task(lambda:ensure_ready(self.state['settings']['engine_url'],
                                          executable_path=self.state['settings'].get('engine_executable','')))
            self.engine_task=task
            def ready(_):
                self.engine_task=None
                if self.selected and self.selected['id']==ch['id']:
                    self.play_stream(url)
            def failed(message):
                self.engine_task=None
                self.status.setText('Ace Stream unavailable: '+message)
                self.error('Could not start Ace Stream. '+message+
                           '\n\nYou can choose the installed engine EXE in Settings.')
            task.signals.success.connect(ready); task.signals.failure.connect(failed)
            self.pool.start(task)
        else:
            # Ordinary HTTP/HLS streams play without the Ace Stream engine.
            self.play_stream(url)
    def eventFilter(self,obj,event):
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
            seconds_back=max(0,self.timeshift_lag)+abs(delta_ms)/1000
            try:
                self.play_url(self.timeshift.replay_url(seconds_back))
                self.timeshift_lag=seconds_back
                self.seek_notice.setText('Playing from device cache, about '+str(int(seconds_back))+' seconds behind LIVE')
            except (ValueError,RuntimeError) as exc:
                self.seek_notice.setText('Rewind not ready: '+str(exc))
            return
        if not self.player.is_seekable():
            self.seek_notice.setText('Rewind is unavailable: this stream has no seekable DVR window.')
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
        screen.setStyleSheet('QDialog#tvWindow { background:#101713; }')
        screen.setMouseTracking(True)
        screen.installEventFilter(self)
        vbox=QVBoxLayout(screen)
        vbox.setContentsMargins(6,6,6,6)
        vbox.setSpacing(4)
        self.video.setParent(screen)
        vbox.addWidget(self.video,1)

        # The same libVLC player remains attached; do not start a second feed.
        # Separate owned translucent tool window overlays native VLC video HWND.
        panel=QFrame(screen,Qt.Tool|Qt.FramelessWindowHint)
        panel.setObjectName('playerControls')
        panel.setAttribute(Qt.WA_TranslucentBackground,True)
        panel.setAttribute(Qt.WA_ShowWithoutActivating,True)
        panel.installEventFilter(self)
        ratio=max(.75,min(1.5,self.state['settings'].get('ui_scale',100)/100))
        compact=self.state['settings'].get('button_size','Normal')=='Compact'
        padding=max(2,round((3 if compact else 5)*ratio))
        # The floating overlay is FULLY TRANSPARENT between the controls.
        # Only its small pill buttons and slider tracks have translucent fills.
        # This panel is NOT in the video layout: no window or video resizing.
        panel.setStyleSheet(
          'QFrame#playerControls {background:transparent;border:0;}'
          'QFrame#playerControls QPushButton {'
          'background:rgba(10,35,23,135);color:#edfff0;'
          'border:1px solid rgba(161,213,173,150);'
          'border-radius:7px;padding:'+str(padding)+'px '+str(padding+3)+'px;'
          'font-size:'+str(max(9,round(11*ratio)))+'px;}'
          'QFrame#playerControls QPushButton:hover {background:rgba(17,70,43,180);}'
          'QFrame#playerControls QLabel {background:transparent;color:#effff0;}'
          'QFrame#playerControls QSlider {background:transparent;}'
          'QFrame#playerControls QSlider::groove:horizontal {'
          'height:5px;background:rgba(14,40,29,120);border:0;border-radius:2px;}'
          'QFrame#playerControls QSlider::sub-page:horizontal {'
          'background:rgba(86,205,128,190);border-radius:2px;}'
          'QFrame#playerControls QSlider::handle:horizontal {'
          'width:13px;margin:-5px 0;border:1px solid rgba(210,255,227,200);'
          'background:rgba(106,227,147,215);border-radius:7px;}')
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
                               ('● LIVE',self.jump_to_live),
                               ('☷ Guide',self.show_tv_guide),
                               ('Info',self.show_tv_info),
                               ('⛶ Full',self.toggle_screen_fullscreen),
                               ('↩ Dock',self.exit_screen_fullscreen)):
            button=QPushButton(title,panel)
            button.clicked.connect(callback)
            if title=='● LIVE':button.setObjectName('tvLive')
            bar.addWidget(button)
        button_scroll=QScrollArea(panel)
        button_scroll.setFrameShape(QFrame.NoFrame)
        button_scroll.setWidgetResizable(False)
        button_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        button_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        button_scroll.setStyleSheet('QScrollArea {background:transparent;border:0;}'
                                    'QWidget {background:transparent;}')
        button_row.adjustSize()
        button_scroll.setWidget(button_row)
        button_scroll.setFixedHeight(button_row.sizeHint().height()+14)
        panel_layout.addWidget(button_scroll)
        self.screen_seek_slider=QSlider(Qt.Horizontal,panel)
        self.screen_seek_slider.setObjectName('seekBar')
        self.screen_seek_slider.setRange(0,1000)
        self.screen_seek_slider.sliderReleased.connect(self.seek_screen_slider)
        panel_layout.addWidget(self.screen_seek_slider)
        volume_line=QHBoxLayout()
        volume_line.addWidget(QLabel('Volume',panel))
        volume=QSlider(Qt.Horizontal,panel)
        volume.setObjectName('volumeBar')
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
        self.detached_mouse_position=QCursor.pos()
        self.detached_mouse_timer.start()
        self.show_detached_controls()

    def position_detached_overlay(self):
        if self.screen_dialog is None or self.detached_controls is None:return
        panel=self.detached_controls;screen=self.screen_dialog
        panel.resize(max(300,screen.width()-16),panel.sizeHint().height())
        panel.move(screen.mapToGlobal(QPoint(8,max(8,screen.height()-panel.height()-12))))

    def poll_detached_mouse(self):
        if self.screen_dialog is None:return
        point=QCursor.pos()
        if point==self.detached_mouse_position:return
        self.detached_mouse_position=point
        if (self.screen_dialog.frameGeometry().contains(point) or
            self.detached_controls and self.detached_controls.frameGeometry().contains(point)):
            self.show_detached_controls()

    def show_detached_controls(self):
        if self.screen_dialog is None or self.detached_controls is None:return
        self.position_detached_overlay()
        self.detached_controls.show()
        self.detached_controls.raise_()
        self.detached_hide_timer.start(3500)

    def hide_detached_controls(self):
        if self.detached_controls is None or self.screen_dialog is None:return
        if (self.detached_controls.frameGeometry().contains(QCursor.pos()) or
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
        if overlay:overlay.close();overlay.deleteLater()
        self.video.setParent(None)
        self.live_layout.insertWidget(2,self.video,1)
        self.video.show()
        self._rebind_video()
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
        channels=catalogue(self.store.read())
        def populate():
            results.clear()
            needle=query.text().casefold().strip()
            matches=(ch for ch in channels if needle in (display_channel_name(ch['name'])+' '+ch.get('country','')).casefold())
            for index,ch in enumerate(matches):
                if index>=120:break
                item=QListWidgetItem(display_channel_name(ch['name'])+' · '+ch.get('country',''))
                item.setData(Qt.UserRole,ch)
                results.addItem(item)
        def tune(item):
            ch=item.data(Qt.UserRole)
            dialog.close()
            self.select_guide_channel(ch)
            self.tabs.setCurrentIndex(0)
            self.play()
        query.textChanged.connect(populate)
        results.itemDoubleClicked.connect(tune)
        layout.addWidget(QLabel('Double-click a channel to watch. Use TV Guide for recording.'))
        populate()
        self.guide_popup=dialog
        dialog.show()

    def stop_playback(self):
        if self.player:self.player.stop()
        self.close_timeshift()
        self.playback_started=0
        self.seek_slider.setEnabled(False)
        self.rewind_button.setEnabled(False)
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
            self.store.update(change); self.selected=None; self.guide={'names':{},'programmes':[]}; atomic_json(self.store.directory/'guide.json',self.guide); self.render_channels(); self.tick(); self.status.setText('Backup restored • choose storage and rearm timers explicitly')
        except (OSError,ValueError) as exc:self.error(str(exc))
    def closeEvent(self,event):
        self.exit_screen_fullscreen()
        self.stop_playback()
        if self.player:self.player.release(); self.player=None
        if self.vlc_instance:self.vlc_instance.release(); self.vlc_instance=None
        super().closeEvent(event)


def run(directory=None,smoke=False):
    app=QApplication(sys.argv); app.setApplicationName('DizyTV'); app.setOrganizationName('DizygoticCode'); app.setStyleSheet(desktop_style())
    window=MainWindow(Store(directory),start_worker=not smoke); window.show()
    if smoke:QTimer.singleShot(1200,app.quit)
    return app.exec()
