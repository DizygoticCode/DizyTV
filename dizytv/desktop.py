"""Native Qt desktop client for Windows and macOS."""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path
from zoneinfo import available_timezones

from PySide6.QtCore import Qt, QTimer, QTimeZone, QRunnable, QThreadPool, QObject, Signal, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem, QCheckBox, QSplitter,
    QTabWidget, QFrame, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QSpinBox, QDoubleSpinBox,
    QPlainTextEdit, QFileDialog, QMessageBox, QInputDialog)

from .core import (parse_playlist, parse_xmltv, format_time, stream_url, make_job,
                   check_conflicts, export_backup, restore_backup, MAX_BACKUP, validate_state, normalise_genre, catalogue, COUNTRIES, GENRES)
from .network import download
from .storage import Store, atomic_json
from .recorder import ensure_worker

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
'''


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
    programme_clicked = Signal(object,object)
    def __init__(self):
        super().__init__(); self.rows=[]; self.programmes=[]; self.hitboxes=[]; self.zone='auto'; self.start=0
    def set_data(self,channels,programmes,mappings,zone,start):
        self.rows = channels[:250]; self.programmes = programmes; self.mappings=mappings
        self.zone=zone; self.start=start
        self.setMinimumSize(1350,max(420,60+len(self.rows)*58)); self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.fillRect(self.rect(),QColor('#15221a')); self.hitboxes=[]
        p.setFont(QFont('Sans Serif',11)); rowheight=58; left=210; scale=180/3600
        for i in range(7):
            x=left+i*180
            p.setPen(QColor('#47654b')); p.drawLine(x,0,x,self.height())
            p.setPen(QColor('#f3ead5')); p.drawText(x+5,30,format_time(self.start+i*3600,self.zone,False,detected_zone()))
        by_channel={}
        for item in self.programmes:
            if item['start']<self.start+6*3600 and item['end']>self.start:
                by_channel.setdefault(item['channel'],[]).append(item)
        for row,ch in enumerate(self.rows):
            y=48+row*rowheight
            p.fillRect(0,y,left,rowheight-3,QColor('#253b2b'))
            p.setPen(QColor('#f3ead5')); p.drawText(QRectF(12,y+4,left-20,rowheight-8),Qt.AlignVCenter|Qt.TextWordWrap,ch['name'])
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
        if left<=x<=left+1080:
            p.setPen(QColor('#f4af71')); p.drawLine(int(x),40,int(x),self.height())
    def mousePressEvent(self,event):
        for rect,ch,item in self.hitboxes:
            if rect.contains(event.position()):
                self.programme_clicked.emit(ch,item); break


class Settings(QDialog):
    def __init__(self,state,parent):
        super().__init__(parent); self.setWindowTitle('DizyTV settings'); self.resize(690,640)
        self.original=state['settings'].copy(); form=QFormLayout(self)
        self.playlist=QLineEdit(self.original['playlist_url']); form.addRow('Channel playlist',self.playlist)
        self.engine=QLineEdit(self.original['engine_url']); form.addRow('Ace engine address',self.engine)
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
        note=QLabel('Timers use UTC and do not move when timezone or guide correction changes.\nDesktop recording requires an awake computer. VLC 3 and the Ace engine must be installed separately.\nMac playback connects to a reachable Windows/Linux Ace engine.'); note.setWordWrap(True); form.addRow(note)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def pick_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Recording destination',self.folder.text())
        if folder:self.folder.setText(folder)
    def values(self):
        return dict(self.original,playlist_url=self.playlist.text().strip(),engine_url=self.engine.text().strip(),
                    xmltv_urls=[u.strip() for u in self.feeds.toPlainText().splitlines() if u.strip()],timezone=self.zone.currentData(),
                    epg_offset_minutes=self.offset.value(),padding_before=self.before.value(),padding_after=self.after.value(),
                    reserve_bytes=int(self.reserve.value()*1024**3),recording_dir=self.folder.text())


class MainWindow(QMainWindow):
    def __init__(self,store=None,start_worker=True):
        super().__init__(); self.store=store or Store(); self.player=None; self.vlc_instance=None; self.task=None
        self.state=self.store.read(); self.guide={'names':{},'programmes':[]}; self.guide_start=int(time.time()/3600)*3600
        self.selected=None; self.start_worker=start_worker; self.pool=QThreadPool.globalInstance(); self.displayed_zone=''
        self.setWindowTitle('DizyTV'); self.resize(1320,820); self.setWindowIcon(QIcon(str(ASSETS/'branding/dizytv-logo.png')))
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root)
        top=QHBoxLayout(); logo=QLabel(); logo.setPixmap(QPixmap(str(ASSETS/'branding/dizytv-logo.png')).scaled(75,75,Qt.KeepAspectRatio,Qt.SmoothTransformation)); top.addWidget(logo)
        brand=QLabel('DizyTV'); brand.setObjectName('brand'); top.addWidget(brand); top.addStretch()
        self.timezone_label=QLabel(); top.addWidget(self.timezone_label)
        for label,handler in [('Refresh channels',self.refresh_channels),('Refresh guide',self.refresh_guide),('Settings',self.settings)]:
            b=QPushButton(label); b.clicked.connect(handler); top.addWidget(b)
        layout.addLayout(top)
        split=QSplitter(); layout.addWidget(split,1)
        sidebar=QWidget(); side=QVBoxLayout(sidebar); self.search=QLineEdit(); self.search.setPlaceholderText('Search channels or groups'); self.search.textChanged.connect(self.render_channels); side.addWidget(self.search)
        self.country_filter=QComboBox(); self.genre_filter=QComboBox(); self.kind_filter=QComboBox()
        for widget,label in ((self.country_filter,'All countries'),(self.genre_filter,'All genres'),(self.kind_filter,'All stream types')):
            widget.addItem(label,''); widget.currentIndexChanged.connect(self.render_channels); side.addWidget(widget)
        self.favourites_only=QCheckBox('★ Favourites only'); self.favourites_only.toggled.connect(self.render_channels); side.addWidget(self.favourites_only)
        self.channels=QListWidget(); self.channels.currentItemChanged.connect(self.choose_channel); self.channels.itemDoubleClicked.connect(lambda:self.play()); side.addWidget(self.channels,1)
        for label,handler in [('★ Add / remove favourite',self.favourite),('Map EPG',self.map_channel),('Edit categories',self.edit_categories)]:
            b=QPushButton(label); b.clicked.connect(handler); side.addWidget(b)
        split.addWidget(sidebar); self.tabs=QTabWidget(); split.addWidget(self.tabs); split.setSizes([300,1000])
        live=QWidget(); live_layout=QVBoxLayout(live); self.now=QLabel('Choose a channel, then press Play'); self.now.setWordWrap(True); live_layout.addWidget(self.now)
        self.video=QFrame(); self.video.setStyleSheet('background:black;'); self.video.setAttribute(Qt.WA_NativeWindow); live_layout.addWidget(self.video,1)
        controls=QHBoxLayout()
        for label,handler in [('▶ Play',self.play),('■ Stop playback',self.stop_playback),('● Record now',self.record_now)]:
            b=QPushButton(label); b.clicked.connect(handler); controls.addWidget(b)
        live_layout.addLayout(controls); self.tabs.addTab(live,'Live TV')
        guide_page=QWidget(); guide_layout=QVBoxLayout(guide_page); nav=QHBoxLayout()
        for label,delta in [('← Earlier',-21600),('Now',0),('Later →',21600)]:
            b=QPushButton(label); b.clicked.connect(lambda checked=False,d=delta:self.move_guide(d)); nav.addWidget(b)
        self.guide_date=QLabel(); nav.addWidget(self.guide_date); guide_layout.addLayout(nav)
        self.grid=GuideGrid(); self.grid.programme_clicked.connect(self.schedule_programme); scroll=QScrollArea(); scroll.setWidget(self.grid); scroll.setWidgetResizable(True); guide_layout.addWidget(scroll); self.tabs.addTab(guide_page,'TV Guide')
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
        self.load_guide(); self.render_channels(); self.tick()
        self.clock=QTimer(self); self.clock.timeout.connect(self.tick); self.clock.start(5000)
        self.refresh_clock=QTimer(self); self.refresh_clock.timeout.connect(self.refresh_channels); self.refresh_clock.start(6*3600*1000)
        if start_worker:ensure_worker(self.store.directory)
        if start_worker and not self.state['channels']:QTimer.singleShot(200,self.refresh_channels)
    def error(self,message):
        self.status.setText(message); QMessageBox.warning(self,'DizyTV',message)
    def load_guide(self):
        path=self.store.directory/'guide.json'
        try:
            if path.exists() and path.stat().st_size<=100*1024**2:
                self.guide=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
    def render_channels(self,*_):
        previous=self.selected['id'] if self.selected else None; self.state=self.store.read(); source=catalogue(self.state); self.channels.blockSignals(True); self.channels.clear()
        genre_by_id={}
        for p in self.guide['programmes']:
            genre_by_id.setdefault(p['channel'],set()).update(normalise_genre(v) for v in p.get('categories',[]))
        for widget,key,label in ((self.country_filter,'country','All countries'),(self.genre_filter,'genre','All genres'),(self.kind_filter,'kind','All stream types')):
            chosen=widget.currentData(); values={c.get(key,'TV' if key=='kind' else 'Unspecified') for c in source}
            if key=='genre':values.update(g for genres in genre_by_id.values() for g in genres)
            if key=='kind':values.update(c.get('transport','Ace Stream' if c['stream'].startswith('acestream:') else 'HTTP') for c in source)
            widget.blockSignals(True); widget.clear(); widget.addItem(label,'')
            for value in sorted(values):widget.addItem(value,value)
            widget.setCurrentIndex(max(0,widget.findData(chosen))); widget.blockSignals(False)
        query=self.search.text().casefold(); favs=set(self.state['favourites'])
        for ch in source:
            if query not in (ch['name']+' '+ch['group']).casefold() or self.favourites_only.isChecked() and ch['id'] not in favs:continue
            country=self.country_filter.currentData(); genre=self.genre_filter.currentData(); kind=self.kind_filter.currentData()
            if country and ch.get('country','Unspecified')!=country:continue
            if kind and kind not in (ch.get('kind','TV'),ch.get('transport','Ace Stream' if ch['stream'].startswith('acestream:') else 'HTTP')):continue
            key=self.state['mappings'].get(ch['id'],ch['tvg_id'])
            if genre and ch.get('genre','Unspecified')!=genre and genre not in genre_by_id.get(key,set()):continue
            item=QListWidgetItem(('★ ' if ch['id'] in favs else '')+ch['name']); item.setData(Qt.UserRole,ch); self.channels.addItem(item)
            if ch['id']==previous:self.channels.setCurrentItem(item); self.selected=ch
        self.channels.blockSignals(False); self.render_guide()
    def choose_channel(self,item,*_):
        self.selected=item.data(Qt.UserRole) if item else None; self.render_now()
    def render_now(self):
        if not self.selected:return
        cid=self.state['mappings'].get(self.selected['id'],self.selected['tvg_id']); now=time.time()
        items=[p for p in self.guide['programmes'] if p['channel']==cid and p['end']>now][:2]
        self.now.setText(self.selected['name']+'\n'+'\n'.join(format_time(p['start'],self.state['settings']['timezone'],False,detected_zone())+'  '+p['title'] for p in items) if items else self.selected['name']+' — no guide match')
    def render_guide(self):
        channels=[self.channels.item(i).data(Qt.UserRole) for i in range(self.channels.count())]
        genre=self.genre_filter.currentData()
        source_genre_ids={self.state['mappings'].get(ch['id'],ch['tvg_id']) for ch in channels if ch.get('genre','Unspecified')==genre}
        programmes=[p for p in self.guide['programmes'] if not genre or p['channel'] in source_genre_ids or genre in {normalise_genre(c) for c in p.get('categories',[])}]
        self.grid.set_data(channels,programmes,self.state['mappings'],self.state['settings']['timezone'],self.guide_start)
        self.guide_date.setText(format_time(self.guide_start,self.state['settings']['timezone'],detected=detected_zone()))
    def move_guide(self,delta):
        self.guide_start=self.guide_start+delta if delta else int(time.time()/3600)*3600; self.render_guide()
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
        url=self.store.read()['settings']['playlist_url']; self.status.setText('Importing channel playlist…')
        def done(channels):
            self.store.update(lambda s:s.update(channels=channels)); self.render_channels(); self.status.setText(f'Imported {len(channels)} channels • '+format_time(time.time(),self.state['settings']['timezone'],detected=detected_zone()))
        self.async_task(lambda:parse_playlist(download(url)),done)
    def refresh_guide(self):
        settings=self.store.read()['settings']
        if not settings['xmltv_urls']:self.error('Add one or more XMLTV URLs in Settings'); return
        self.status.setText('Importing XMLTV guide…')
        def fetch():
            names={}; programmes=[]
            for url in settings['xmltv_urls']:
                n,p=parse_xmltv(download(url),settings['epg_offset_minutes']); names.update(n); programmes.extend(p)
            return {'names':names,'programmes':sorted(programmes,key=lambda p:(p['channel'],p['start']))}
        def done(guide):
            atomic_json(self.store.directory/'guide.json',guide); self.guide=guide; self.render_channels(); self.render_now(); self.status.setText(f"Imported {len(guide['programmes'])} programmes • accepted timers keep their UTC times")
        self.async_task(fetch,done)
    def settings(self):
        dialog=Settings(self.store.read(),self)
        if dialog.exec()==QDialog.Accepted:
            try:self.store.update(lambda s:s.update(settings=dialog.values())); self.state=self.store.read(); self.render_guide(); self.tick()
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
            try:self.store.update(change); self.render_channels(); self.status.setText('Categories saved • kept across refresh and backup')
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
        win=int(self.video.winId())
        if sys.platform=='darwin':self.player.set_nsobject(win)
        elif os.name=='nt':self.player.set_hwnd(win)
        else:self.player.set_xwindow(win)
    def play_url(self,url):
        try:
            self.init_player(); media=self.vlc_instance.media_new(url); self.player.set_media(media); media.release()
            if self.player.play()==-1:raise RuntimeError('libVLC could not start playback')
            self.tabs.setCurrentIndex(0); self.status.setText('Connecting… engine availability and peers may affect playback')
        except Exception as exc:self.error('Playback could not start. Install VLC 3 for this app architecture and check the Ace engine. '+str(exc))
    def play(self):
        if not self.selected:return
        active=[j for j in self.store.read()['jobs'] if j['status']=='recording' and j['channel_id']!=self.selected['id']]
        if active:self.error('A different channel is recording. Stop or finish that recording before switching playback.'); return
        self.play_url(stream_url(self.selected['stream'],self.state['settings']['engine_url']))
    def stop_playback(self):
        if self.player:self.player.stop()
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
            key=self.state['mappings'].get(self.selected['id'],self.selected['tvg_id']); programme=next((p for p in self.guide['programmes'] if p['channel']==key and p['start']<=now<p['end']),None)
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
        self.stop_playback()
        if self.player:self.player.release(); self.player=None
        if self.vlc_instance:self.vlc_instance.release(); self.vlc_instance=None
        super().closeEvent(event)


def run(directory=None,smoke=False):
    app=QApplication(sys.argv); app.setApplicationName('DizyTV'); app.setOrganizationName('DizygoticCode'); app.setStyleSheet(STYLE)
    window=MainWindow(Store(directory),start_worker=not smoke); window.show()
    if smoke:QTimer.singleShot(1200,app.quit)
    return app.exec()
