"""Optional isolated Qt WebEngine viewer for permitted public Matchday pages.

The browser has no privileged JavaScript bridge, no persistent cookies/storage,
no popups, no permissions, no local file access, and no private-network URLs.
Installed packages may omit QtWebEngine; callers then use external browser.
"""
from __future__ import annotations

from ipaddress import ip_address
import re
from urllib.parse import urlsplit

from .matchday import safe_public_url


def _private_host(host):
    host = (host or '').lower().rstrip('.')
    if '%' in host:
        return True
    if (not host or host in ('localhost',) or host.endswith(
            ('.localhost', '.local', '.internal', '.test'))):
        return True
    if re.fullmatch(r'(?i)(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*', host):
        return True
    try:
        return not ip_address(host).is_global
    except ValueError:
        return False


def open_embedded_player(url, parent):
    """Show isolated in-app web player; return False when WebEngine unavailable.

    This does not verify copyright permissions, video resolution, or working
    playback, and does not extract or bypass protected media.
    """
    url = safe_public_url(url)
    try:
        from PySide6.QtCore import Qt, QUrl
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
        from PySide6.QtWebEngineCore import (
            QWebEngineProfile, QWebEnginePage, QWebEngineUrlRequestInterceptor,
            QWebEngineSettings)
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except (ImportError, RuntimeError):
        return False

    host = urlsplit(url).hostname

    class Guard(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info):
            resource = info.requestUrl()
            scheme = resource.scheme().lower()
            if scheme in ('data', 'blob', 'about'):
                return
            if scheme != 'https' or _private_host(resource.host()):
                info.block(True)

    class Page(QWebEnginePage):
        def acceptNavigationRequest(self, candidate, nav_type, is_main_frame):
            if not is_main_frame:
                return True
            return (candidate.scheme().lower() == 'https'
                    and candidate.host().lower() == host)

        def createWindow(self, _kind):
            # Prevent arbitrary popups; external browser remains explicit.
            return None

    dialog = QDialog(parent)
    dialog.setWindowTitle('DizyTV Matchday — isolated website player (unverified)')
    dialog.resize(920, 620)
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)
    layout = QVBoxLayout(dialog)
    warning = QLabel('Third-party webpage • no account integration or viewing-rights verification. '
                     'Use the external-browser option if embedded playback is blocked.')
    warning.setWordWrap(True)
    layout.addWidget(warning)
    profile = QWebEngineProfile(dialog)  # unnamed: off-the-record
    profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.NoCache)
    interceptor = Guard(profile)
    profile.setUrlRequestInterceptor(interceptor)
    page = Page(profile, dialog)
    page.featurePermissionRequested.connect(lambda origin, feature:
        page.setFeaturePermission(origin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser))
    settings = page.settings()
    settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
    settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
    view = QWebEngineView(dialog)
    view.setPage(page)
    layout.addWidget(view, 1)
    dialog.show()
    view.setUrl(QUrl(url))
    return True
