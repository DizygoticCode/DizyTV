"""Non-destructive Dizy-branded Live TV dashboard composition.

All controls, storage, EPG, playback and recorder behaviour stay owned by
desktop.MainWindow. This module rearranges existing widgets and adds a second
view onto the *same* guide model; it does not introduce sample channels.
"""
from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QToolButton, QVBoxLayout, QWidget,
)


def dashboard_style(theme='Green', scale=1.0):
    """Additional palette-aware, DPI-scaled rules for existing themes."""
    palettes = {
        'Green': ('#0f1713', '#17241c', '#213529', '#3d634b',
                  '#eaf8ef', '#a9c7b1', '#65dca0', '#12271c'),
        'Dark': ('#101721', '#192432', '#253548', '#425b77',
                 '#eef5ff', '#a8bed6', '#84b4fa', '#152238'),
        'Light': ('#edf4f9', '#ffffff', '#e1ebf6', '#bfd0e2',
                  '#203149', '#5a7089', '#246cba', '#eff5fc'),
    }
    bg, surface, raised, border, fg, muted, accent, active = palettes.get(
        theme, palettes['Green']
    )
    scale = max(.75, min(1.5, float(scale)))
    return f"""
QWidget#dashboardNavigation {{
    background:{surface}; border:1px solid {border}; border-radius:12px;
}}
QPushButton#dashboardNavButton {{
    color:{muted}; background:transparent; border:1px solid transparent;
    border-radius:9px; padding:{round(9*scale)}px {round(13*scale)}px; font-weight:650;
}}
QPushButton#dashboardNavButton:hover {{
    color:{fg}; background:{raised}; border-color:{border};
}}
QPushButton#dashboardNavButton[active="true"] {{
    color:{accent}; background:{active}; border:1px solid {border};
}}
QFrame#dashboardInfo,QFrame#dashboardTimeline {{
    background:{surface}; border:1px solid {border}; border-radius:12px;
}}
QLabel#dashboardEyebrow {{
    color:{accent}; font-size:{round(11*scale)}px; font-weight:750; letter-spacing:1px;
}}
QLabel#dashboardProgrammeTitle {{
    color:{fg}; font-size:{round(21*scale)}px; font-weight:750;
}}
QLabel#dashboardProgrammeMeta,QLabel#dashboardProgrammeDescription {{
    color:{muted}; font-size:{round(12*scale)}px;
}}
QPushButton#dashboardExpandGuide {{
    color:{accent}; background:{raised}; border:1px solid {border};
    border-radius:8px; padding:5px 9px;
}}
QFrame#dashboardVideoFrame {{ background:{bg}; border:1px solid {border}; border-radius:12px; }}
"""


def _select_section(window, section):
    """Navigate to existing catalogue filters; never fabricate media pages."""
    for control in (window.section_filter, window.genre_filter):
        for index in range(1, control.count()):
            value = control.itemData(index)
            if value and str(value).casefold() == section.casefold():
                window.section_filter.setCurrentIndex(0)
                window.genre_filter.setCurrentIndex(0)
                control.setCurrentIndex(index)
                window.tabs.setCurrentIndex(0)
                return True
    window.tabs.setCurrentIndex(0)
    window.status.setText(
        f'No {section.lower()} category imported yet. Add a suitable playlist '
        'or EPG source in Settings; existing channels are unchanged.'
    )
    return False


def navigate(window, route):
    """Keep original tabs, filters, settings and shortcuts operational."""
    if route == 'live':
        window.tabs.setCurrentIndex(0)
    elif route == 'guide':
        window.tabs.setCurrentIndex(1)
    elif route == 'dvr':
        window.tabs.setCurrentIndex(2)
    elif route == 'search':
        window.open_global_search()
        return
    elif route in ('Movies', 'Series', 'Sports'):
        _select_section(window, route)
    else:
        return
    _highlight_navigation(window)


def _highlight_navigation(window):
    if not hasattr(window, 'dashboard_navigation_buttons'):
        return
    index = window.tabs.currentIndex()
    active = {0: 'live', 1: 'guide', 2: 'dvr'}.get(index)
    for route, button in window.dashboard_navigation_buttons.items():
        desired = route == active
        if button.property('active') != desired:
            button.setProperty('active', desired)
            button.style().unpolish(button)
            button.style().polish(button)


def update_dashboard_details(window, programmes=None):
    """Show real selected-channel guide data; never claim fake stream quality."""
    if not hasattr(window, 'dashboard_programme_title'):
        return
    channel = window.selected
    if not channel:
        window.dashboard_programme_title.setText('Find something to watch')
        window.dashboard_programme_meta.setText('Select a channel from your playlists')
        window.dashboard_programme_description.setText(
            'Your programme information appears here when XMLTV data is available.'
        )
        return
    window.dashboard_programme_meta.setText(
        '  •  '.join(str(value) for value in
                    (channel.get('country'), channel.get('genre'))
                    if value and value != 'Unspecified') or 'Live channel'
    )
    items = programmes or []
    now = time.time()
    current = next((p for p in items if p['start'] <= now < p['end']), None)
    upcoming = next((p for p in items if p['start'] > now), None)
    if current:
        window.dashboard_programme_title.setText(current['title'])
        remaining = max(0, int((current['end'] - now) / 60))
        window.dashboard_programme_description.setText(
            (current.get('description') or f'On now • approximately {remaining} minutes remaining')
            + (f"\nUp next: {upcoming['title']}" if upcoming else '')
        )
    elif upcoming:
        window.dashboard_programme_title.setText(upcoming['title'])
        window.dashboard_programme_description.setText('Upcoming programme — see the guide for schedule details.')
    else:
        window.dashboard_programme_title.setText('No guide match')
        window.dashboard_programme_description.setText(
            'You can still play this source. Choose Map EPG to match programme listings.'
        )


def install_dashboard(window, live_layout, root_layout):
    """Compose a polished Live TV page without replacing any native features.

    The original native VLC video surface and channel heading are *moved*, not
    recreated. Full TV Guide and Recordings tabs stay intact; the bottom
    timeline is a second, synchronised read-only view of their guide data.
    """
    nav = QWidget()
    nav.setObjectName('dashboardNavigation')
    nav_row = QHBoxLayout(nav)
    nav_row.setContentsMargins(7, 5, 7, 5)
    nav_row.setSpacing(3)
    window.dashboard_navigation_buttons = {}
    for title, route in (
        ('Live TV', 'live'), ('TV Guide', 'guide'),
        ('Movies', 'Movies'), ('Series', 'Series'),
        ('Sports', 'Sports'), ('DVR', 'dvr'),
        ('Search', 'search'),
    ):
        button = QPushButton(title)
        button.setObjectName('dashboardNavButton')
        button.setProperty('active', route == 'live')
        button.clicked.connect(
            lambda checked=False, destination=route: navigate(window, destination)
        )
        button.setToolTip(
            'Filter channels already imported into DizyTV'
            if route in ('Movies', 'Series', 'Sports') else title
        )
        nav_row.addWidget(button)
        window.dashboard_navigation_buttons[route] = button
    nav_row.addStretch(1)
    nav_scroll = QScrollArea()
    nav_scroll.setObjectName('dashboardNavScroll')
    nav_scroll.setWidgetResizable(False)
    nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    nav_scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    nav.adjustSize()
    nav_scroll.setWidget(nav)
    nav_scroll.setFixedHeight(nav.sizeHint().height() + 4)
    nav_shell = QWidget()
    nav_shell.setObjectName('dashboardNavShell')
    nav_shell_row = QHBoxLayout(nav_shell)
    nav_shell_row.setContentsMargins(0, 0, 0, 0)
    nav_shell_row.setSpacing(3)
    previous = QToolButton()
    previous.setText('‹')
    previous.setObjectName('mediaScrollArrow')
    previous.setToolTip('Earlier navigation sections')
    previous.setFixedWidth(29)
    more = QToolButton()
    more.setText('›')
    more.setObjectName('mediaScrollArrow')
    more.setToolTip('More navigation sections')
    more.setFixedWidth(29)
    nav_shell_row.addWidget(previous)
    nav_shell_row.addWidget(nav_scroll, 1)
    nav_shell_row.addWidget(more)
    bar = nav_scroll.horizontalScrollBar()
    def sync_nav(*_):
        overflow = bar.maximum() > bar.minimum()
        previous.setVisible(overflow)
        more.setVisible(overflow)
        previous.setEnabled(bar.value() > bar.minimum())
        more.setEnabled(bar.value() < bar.maximum())
    previous.clicked.connect(lambda: bar.setValue(max(bar.minimum(), bar.value() - 220)))
    more.clicked.connect(lambda: bar.setValue(min(bar.maximum(), bar.value() + 220)))
    bar.rangeChanged.connect(sync_nav)
    bar.valueChanged.connect(sync_nav)
    root_layout.insertWidget(1, nav_shell)
    window.dashboard_nav_scroll = nav_scroll
    window.dashboard_nav_shell = nav_shell
    window.dashboard_nav_previous = previous
    window.dashboard_nav_more = more
    sync_nav()

    hero = QSplitter(Qt.Horizontal)
    hero.setObjectName('dashboardHero')
    hero.setChildrenCollapsible(False)
    hero.setHandleWidth(8)

    player_panel = QFrame()
    player_panel.setObjectName('dashboardVideoFrame')
    player_layout = QVBoxLayout(player_panel)
    player_layout.setContentsMargins(5, 5, 5, 5)
    # This is the original native video widget used for libVLC rendering.
    live_layout.removeWidget(window.video)
    player_layout.addWidget(window.video, 1)
    player_panel.setMinimumWidth(160)
    hero.addWidget(player_panel)

    details = QFrame()
    details.setObjectName('dashboardInfo')
    info = QVBoxLayout(details)
    info.setContentsMargins(17, 15, 17, 15)
    info.setSpacing(9)
    eyebrow = QLabel('●  NOW SHOWING')
    eyebrow.setObjectName('dashboardEyebrow')
    info.addWidget(eyebrow)
    live_layout.removeWidget(window.now)
    info.addWidget(window.now)
    window.dashboard_programme_title = QLabel()
    window.dashboard_programme_title.setObjectName('dashboardProgrammeTitle')
    window.dashboard_programme_title.setWordWrap(True)
    info.addWidget(window.dashboard_programme_title)
    window.dashboard_programme_meta = QLabel()
    window.dashboard_programme_meta.setObjectName('dashboardProgrammeMeta')
    window.dashboard_programme_meta.setWordWrap(True)
    info.addWidget(window.dashboard_programme_meta)
    window.dashboard_programme_description = QLabel()
    window.dashboard_programme_description.setObjectName('dashboardProgrammeDescription')
    window.dashboard_programme_description.setWordWrap(True)
    info.addWidget(window.dashboard_programme_description)
    # Preserve regional-access notice in the new information panel.
    live_layout.removeWidget(window.channel_banner)
    info.addWidget(window.channel_banner)
    info.addStretch(1)
    details.setMinimumWidth(165)
    hero.addWidget(details)
    hero.setStretchFactor(0, 7)
    hero.setStretchFactor(1, 4)
    hero.setSizes([710, 400])
    window.dashboard_hero = hero
    live_layout.insertWidget(0, hero, 5)

    timeline = QFrame()
    timeline.setObjectName('dashboardTimeline')
    timeline_layout = QVBoxLayout(timeline)
    timeline_layout.setContentsMargins(8, 7, 8, 8)
    timeline_layout.setSpacing(5)
    toolbar = QHBoxLayout()
    title = QLabel('●  LIVE PROGRAMME GUIDE')
    title.setObjectName('dashboardEyebrow')
    toolbar.addWidget(title)
    toolbar.addStretch()
    toggle = QPushButton('Hide timeline')
    toggle.setObjectName('dashboardExpandGuide')
    toolbar.addWidget(toggle)
    expand = QPushButton('Full guide')
    expand.setObjectName('dashboardExpandGuide')
    expand.clicked.connect(lambda: navigate(window, 'guide'))
    toolbar.addWidget(expand)
    timeline_layout.addLayout(toolbar)

    dashboard_grid = type(window.grid)()
    dashboard_grid.channel_clicked.connect(window.play_guide_channel)
    dashboard_grid.programme_record_requested.connect(window.schedule_programme)
    dashboard_grid.channel_record_requested.connect(window.record_guide_channel)
    timeline_scroll = QScrollArea()
    timeline_scroll.setObjectName('dashboardGuideScroll')
    timeline_scroll.setWidget(dashboard_grid)
    timeline_scroll.setWidgetResizable(True)
    timeline_scroll.setMinimumHeight(85)
    timeline_layout.addWidget(timeline_scroll, 1)
    toggle.clicked.connect(
        lambda: (
            timeline_scroll.setVisible(not timeline_scroll.isVisible()),
            toggle.setText('Hide timeline' if timeline_scroll.isVisible() else 'Show timeline'),
        )
    )
    window.dashboard_grid = dashboard_grid
    window.dashboard_timeline = timeline
    live_layout.addWidget(timeline, 3)
    window.tabs.currentChanged.connect(lambda _index: _highlight_navigation(window))
    update_dashboard_details(window)
