"""Cross-source channel and upcoming XMLTV programme search."""
import time

from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QListWidget,
                               QListWidgetItem,QPushButton,QLabel)
from .core import catalogue,display_channel_name,channel_section,format_time

def find_global(channels,by_guide_id,epg_keys,query,now=None):
    needle=query.strip().casefold()
    if len(needle)<2:return []
    now=int(time.time()) if now is None else int(now)
    reverse={}
    channel_hits=[]
    for ch in channels:
        epg_id=epg_keys.get(ch['id'])
        if epg_id:reverse.setdefault(epg_id,[]).append(ch)
        searchable=' '.join(str(ch.get(k,'')) for k in ('name','group','country','genre','kind','transport'))
        if needle in searchable.casefold():channel_hits.append(('channel',ch,None))
    channel_hits.sort(key=lambda x:display_channel_name(x[1]['name']).casefold())
    show_hits=[]
    for epg_id,progs in by_guide_id.items():
        matches=reverse.get(epg_id)
        if not matches:continue
        for p in progs:
            if p['end']<=now or needle not in p['title'].casefold():continue
            show_hits.extend(('programme',ch,p) for ch in matches)
    show_hits.sort(key=lambda x:(x[2]['start'],display_channel_name(x[1]['name']).casefold()))
    return channel_hits+show_hits

class GlobalSearch(QDialog):
    PAGE=150
    def __init__(self,main):
        super().__init__(main)
        self.main=main
        self.setWindowFlag(Qt.Window,True)
        self.setWindowTitle('DizyTV — Global channel & programme search')
        self.resize(770,590)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Search ALL imported channels and current/future EPG programmes — independent of filters'))
        self.query=QLineEdit(self)
        self.query.setPlaceholderText('Channel name, genre, country or programme title…')
        layout.addWidget(self.query)
        self.count=QLabel('Type at least two characters')
        layout.addWidget(self.count)
        self.results=QListWidget(self)
        layout.addWidget(self.results,1)
        row=QHBoxLayout()
        self.watch=QPushButton('▶ Watch')
        self.guide=QPushButton('☷ Show in guide')
        self.record=QPushButton('● Record programme…')
        self.more=QPushButton('Next 150')
        for btn in (self.watch,self.guide,self.record,self.more):row.addWidget(btn)
        layout.addLayout(row)
        self.entries=[]
        self.shown=0
        self.channels=catalogue(main.store.read(),include_disabled=main.show_disabled.isChecked())
        self.by_id,_=main.guide_index()
        self.epg_ids={ch['id']:main.matched_guide(ch) for ch in self.channels}
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.search)
        self.query.textChanged.connect(lambda _:self.timer.start())
        self.watch.clicked.connect(self.watch_hit)
        self.guide.clicked.connect(self.show_hit)
        self.record.clicked.connect(self.record_hit)
        self.more.clicked.connect(self.show_more)
        self.results.itemDoubleClicked.connect(lambda _:self.show_hit())
        self.results.currentItemChanged.connect(lambda *_:self.refresh_buttons())
        self.refresh_buttons()
        self.query.setFocus()
    def refresh_catalogue(self):
        self.channels=catalogue(self.main.store.read(),
                                include_disabled=self.main.show_disabled.isChecked())
        self.epg_ids={ch['id']:self.main.matched_guide(ch) for ch in self.channels}
        self.search()

    def search(self):
        self.entries=find_global(self.channels,self.by_id,self.epg_ids,self.query.text())
        self.shown=0
        self.results.clear()
        self.show_more()
    def show_more(self):
        for kind,ch,p in self.entries[self.shown:self.shown+self.PAGE]:
            label=('📺 '+display_channel_name(ch['name'])+'  ·  '+ch.get('country','')+'  ·  '+channel_section(ch)
                   if kind=='channel' else
                   '📅 '+p['title']+'  ·  '+display_channel_name(ch['name'])+'  ·  '+
                   format_time(p['start'],self.main.state['settings']['timezone'],True,
                               self.main.detected_timezone()))
            item=QListWidgetItem(label)
            item.setData(Qt.UserRole,(kind,ch,p))
            self.results.addItem(item)
        self.shown=min(len(self.entries),self.shown+self.PAGE)
        self.count.setText(f'{len(self.entries):,} matches across all sources · showing {self.shown:,}')
        self.more.setEnabled(self.shown<len(self.entries))
        if self.shown and self.results.currentRow()<0:self.results.setCurrentRow(0)
        self.refresh_buttons()
    def chosen(self):
        item=self.results.currentItem()
        return item.data(Qt.UserRole) if item else None
    def refresh_buttons(self):
        hit=self.chosen()
        self.watch.setEnabled(hit is not None)
        self.guide.setEnabled(hit is not None)
        self.record.setEnabled(bool(hit and hit[0]=='programme' and hit[2]['end']>time.time()))
    def watch_hit(self):
        hit=self.chosen()
        if hit:
            self.main.reveal_global_channel(hit[1],show_guide=False)
            self.main.tabs.setCurrentIndex(0)
            self.close()
            self.main.play()
    def show_hit(self):
        hit=self.chosen()
        if hit:
            self.main.reveal_global_channel(hit[1],programme=hit[2])
            self.close()
    def record_hit(self):
        hit=self.chosen()
        if hit and hit[0]=='programme':
            self.main.schedule_programme(hit[1],hit[2])
