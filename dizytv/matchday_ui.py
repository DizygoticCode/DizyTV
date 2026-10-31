"""Desktop Matchday view, isolated from channel EPG and recording state.

Uses a worker thread for slow free-tier fixture metadata and only opens
explicitly permission-confirmed user links. No DRM, geo or auth bypass.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import time

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QComboBox, QCheckBox, QLineEdit, QTableWidget,
                               QTableWidgetItem, QAbstractItemView, QInputDialog,
                               QMessageBox, QDialog)

from .matchday import cached_fixtures, load_sources, add_source, is_favourite


class _FetchSignals(QObject):
    finished = Signal(object, object, bool)
    failed = Signal(str)


class _Fetch(QRunnable):
    def __init__(self, folder):
        super().__init__()
        self.folder = folder
        self.signals = _FetchSignals()

    def run(self):
        try:
            fixtures, errors, stale = cached_fixtures(self.folder, refresh=True)
            self.signals.finished.emit(fixtures, errors, stale)
        except (OSError, ValueError) as exc:
            self.signals.failed.emit('Fixture refresh unavailable: ' + type(exc).__name__)


class MatchdayPage(QWidget):
    def __init__(self, store, on_hls_play, parent=None):
        super().__init__(parent)
        self.setObjectName('matchdayPage')
        self.store = store
        # Qt reparents tabs to QStackedWidget: keep owner independent of parent().
        self._main_window = parent
        self.on_hls_play = on_hls_play
        self.fixtures = []
        self.visible = []
        self._fetching = False
        self._task = None
        layout = QVBoxLayout(self)
        heading = QLabel('⚽  Matchday — free football fixtures')
        heading.setObjectName('channelHeading')
        layout.addWidget(heading)
        self.notice = QLabel(
            'Fixture data: TheSportsDB public free tier (limited results; not a complete schedule). '
            'A listed match does NOT mean a free playable stream exists. '
            'Only add a source you are authorised to view.')
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        toolbar = QHBoxLayout()
        self.when = QComboBox()
        self.when.addItems(['Upcoming', 'Today', 'Tomorrow', 'Weekend'])
        self.when.currentTextChanged.connect(self.render)
        toolbar.addWidget(self.when)
        self.fav_team = QLineEdit()
        self.fav_team.setPlaceholderText('Favourite club')
        self.fav_team.setMaximumWidth(220)
        pref = Path(self.store.directory) / 'matchday-favourite.txt'
        try:
            self.fav_team.setText(pref.read_text('utf-8')[:80].strip() if pref.is_file() and pref.stat().st_size <= 200 else 'Southampton')
        except OSError:
            self.fav_team.setText('Southampton')
        self.fav_team.editingFinished.connect(self.save_favourite)
        self.fav_team.textChanged.connect(self.render)
        toolbar.addWidget(self.fav_team)
        self.fav_only = QCheckBox('★ Club only')
        self.fav_only.toggled.connect(self.render)
        toolbar.addWidget(self.fav_only)
        self.refresh_button = QPushButton('Refresh fixtures')
        self.refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_button)
        layout.addLayout(toolbar)
        self.fixtures_table = QTableWidget(0, 4)
        self.fixtures_table.setHorizontalHeaderLabels(['Kickoff (local)', 'Fixture', 'Competition', 'Source'])
        self.fixtures_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.fixtures_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.fixtures_table.setAlternatingRowColors(True)
        self.fixtures_table.horizontalHeader().setStretchLastSection(True)
        self.fixtures_table.itemSelectionChanged.connect(self.display_sources)
        layout.addWidget(self.fixtures_table, 3)
        self.sources = QTableWidget(0, 3)
        self.sources.setHorizontalHeaderLabels(['Saved viewing option', 'Type', 'Verification'])
        self.sources.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sources.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sources.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.sources, 1)
        buttons = QHBoxLayout()
        self.add_button = QPushButton('Add authorised viewing link…')
        self.add_button.clicked.connect(self.add_viewing_source)
        buttons.addWidget(self.add_button)
        self.open_button = QPushButton('Open selected source')
        self.open_button.clicked.connect(self.open_source)
        buttons.addWidget(self.open_button)
        self.embed_button = QPushButton('Try embedded webpage')
        self.embed_button.setToolTip('Experimental isolated WebEngine; opens browser if unavailable')
        self.embed_button.clicked.connect(self.open_embed)
        buttons.addWidget(self.embed_button)
        layout.addLayout(buttons)
        self.status = QLabel('No fixtures loaded. Refresh to request public fixture metadata.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        try:
            self.fixtures, errors, stale = cached_fixtures(self.store.directory, offline=True)
            self.status.setText('Cached fixtures (may be old). Refresh for current provider data.' if self.fixtures else
                                'No cached fixtures. Refresh to load the free fixture feed.')
        except (OSError, ValueError):
            pass
        self.render()

    def save_favourite(self):
        text = self.fav_team.text().strip()[:80]
        if not text:
            return
        # A separate optional local preference, never touch recording state.
        # One-line plain UTF-8, atomically replaced for crash safety.
        path = Path(self.store.directory) / 'matchday-favourite.txt'
        import os, tempfile
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                    dir=path.parent, prefix='.matchday-', delete=False) as fp:
                name=fp.name
                fp.write(text+'\n')
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(name,path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    def refresh(self):
        if self._fetching:
            return
        self._fetching = True
        self.refresh_button.setEnabled(False)
        self.status.setText('Fetching free-tier fixture metadata in a background worker…')
        self._task = _Fetch(self.store.directory)
        self._task.signals.finished.connect(self._refreshed)
        self._task.signals.failed.connect(self._failed)
        QThreadPool.globalInstance().start(self._task)

    def _refreshed(self, fixtures, errors, stale):
        self._fetching = False
        self.refresh_button.setEnabled(True)
        self._task = None
        self.fixtures = fixtures
        self.render()
        self.status.setText(
            f'{len(fixtures)} fixture entries from free-tier provider'
            + (' (older cache retained)' if stale else '')
            + (f'; {len(errors)} competition requests unavailable' if errors else '')
            + '. Coverage is incomplete; viewing links are not automatically verified.')

    def _failed(self, error):
        self._fetching = False
        self.refresh_button.setEnabled(True)
        self._task = None
        self.status.setText(error + '. Existing cached fixtures retained.')

    def _display_zone(self):
        # No I/O in render(): a 20,000-channel state validation would stall Qt
        # if repeated for every listed fixture on every keystroke.
        owner = self._main_window
        value = (getattr(owner, 'state', {}) or {}).get('settings', {}).get('timezone', 'auto')
        try:
            return ZoneInfo(value) if value != 'auto' else datetime.now().astimezone().tzinfo
        except (ValueError, KeyError, TypeError):
            return datetime.now().astimezone().tzinfo

    @staticmethod
    def _day(event, zone):
        return datetime.fromtimestamp(event['kickoff'], tz=zone)

    def render(self, *_):
        zone = self._display_zone()
        today = datetime.now(zone).date()
        mode = self.when.currentText()
        favourite = self.fav_team.text().strip()
        filtered = []
        for entry in self.fixtures:
            if not isinstance(entry, dict) or not isinstance(entry.get('kickoff'), int):
                continue
            day = self._day(entry,zone).date()
            if mode == 'Today' and day != today:
                continue
            if mode == 'Tomorrow' and day != today + timedelta(days=1):
                continue
            if mode == 'Weekend' and (day.weekday() not in (5,6) or not today <= day <= today + timedelta(days=7)):
                continue
            if mode == 'Upcoming' and not today <= day <= today + timedelta(days=14):
                continue
            if self.fav_only.isChecked() and favourite and not is_favourite(entry, favourite):
                continue
            filtered.append(entry)
        self.visible = filtered
        self.fixtures_table.setRowCount(len(filtered))
        for row, entry in enumerate(filtered):
            values = [self._day(entry,zone).strftime('%a %d %b %H:%M'),
                      entry.get('home', '')+' v '+entry.get('away',''),
                      entry.get('competition',''), 'Not verified']
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 1 and favourite and is_favourite(entry, favourite):
                    item.setText('★ '+value)
                self.fixtures_table.setItem(row,column,item)
        self.display_sources()

    def chosen_fixture(self):
        row = self.fixtures_table.currentRow()
        return self.visible[row] if 0 <= row < len(self.visible) else None

    def display_sources(self):
        entry = self.chosen_fixture()
        try:
            matches = [x for x in load_sources(self.store.directory) if entry and x['event_id']==entry['id']]
        except (OSError, ValueError):
            matches = []
        self._sources = matches
        self.sources.setRowCount(len(matches))
        for row, source in enumerate(matches):
            for col,value in enumerate((source['label'],source['kind'].upper(),'User-submitted • unverified')):
                self.sources.setItem(row,col,QTableWidgetItem(value))

    def add_viewing_source(self):
        entry = self.chosen_fixture()
        if not entry:
            self.status.setText('Select a fixture first.')
            return
        label, ok = QInputDialog.getText(self,'Viewing source','Description / source name')
        if not ok or not label.strip():
            return
        kind, ok = QInputDialog.getItem(self,'Viewing source','Format', ['Browser page', 'Direct HLS stream'],0,False)
        if not ok:
            return
        url, ok = QInputDialog.getText(self,'Viewing source','Public HTTPS URL (without query tokens)')
        if not ok or not url.strip():
            return
        notice = ('Confirm this viewing link is free to access AND that you have '
                  'permission to view/embed it. DizyTV does not verify rights, '
                  'quality, location or playback. Continue?')
        if QMessageBox.question(self,'Authorised viewing only',notice,
                                QMessageBox.Yes | QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
            return
        try:
            add_source(self.store.directory,dict(event_id=entry['id'],label=label,url=url,
                       kind='hls' if kind=='Direct HLS stream' else 'web',
                       permission_confirmed=True))
            self.display_sources()
            self.status.setText('Locally saved as unverified. No source data was sent to a directory.')
        except (ValueError,OSError) as exc:
            QMessageBox.warning(self,'Source not saved',str(exc))

    def open_embed(self):
        row = self.sources.currentRow()
        source_list = getattr(self, '_sources', [])
        if not 0 <= row < len(source_list):
            self.status.setText('Select a saved browser source first.')
            return
        source = source_list[row]
        if source['kind'] != 'web':
            self.status.setText('A direct HLS link belongs in the VLC player, not WebEngine.')
            return
        from .matchday_web import open_embedded_player
        try:
            if open_embedded_player(source['url'], self):
                self.status.setText('Third-party page opened in isolated WebEngine (playback not verified).')
            else:
                QDesktopServices.openUrl(QUrl(source['url']))
                self.status.setText('Embedded player unavailable; using the external browser.')
        except (OSError, ValueError, RuntimeError) as exc:
            self.status.setText('Embedded playback not available: '+str(exc))

    def open_source(self):
        entry=self.chosen_fixture()
        row=self.sources.currentRow()
        if not entry or not 0 <= row < len(getattr(self,'_sources',[])):
            self.status.setText('Select a saved viewing source first.')
            return
        source=self._sources[row]
        if source['kind']=='hls':
            self.on_hls_play(source['url'])
            self.status.setText('Sent authorised HLS source to native VLC; actual playback not yet verified.')
        else:
            QDesktopServices.openUrl(QUrl(source['url']))
            self.status.setText('Opened an unverified viewing page in your browser. No authentication or bypass attempted.')
