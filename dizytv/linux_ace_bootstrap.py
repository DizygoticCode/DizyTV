"""Optional, in-app Linux bootstrap for the ORIGINAL publisher Ace Stream engine.

The DizyTV .deb embeds this bootstrap code, not the proprietary engine.
It never executes a publisher binary at download/install time, and requires
explicit UI consent before fetching anything. No sudo or global modifications.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

VERSION = "3.2.11"
# Current upstream product listing identifies Ubuntu 22.04 + Python 3.10.
# This is NOT a verified Ubuntu 24.04/ Python 3.12 build.
OFFICIAL_URL = (
    "https://download.acestream.media/linux/"
    "acestream_3.2.11_ubuntu_22.04_x86_64_py3.10.tar.gz"
)
# Fixed digest independently documented by multiple community build
# manifests; not a publisher signature. Verify original HTTPS *and* digest.
SHA256 = "9b6bbd76a55e5a434641afae3b9cf8e6154ce1cf392152ec3aed5ac265432b2e"
MAX_ARCHIVE_BYTES = 140 * 1024 * 1024
MAX_EXPANDED_BYTES = 600 * 1024 * 1024
MAX_MEMBERS = 15000
PUBLISHER_HOST = "download.acestream.media"


def check_publisher_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != PUBLISHER_HOST
            or parsed.port not in (None, 443) or parsed.username is not None
            or parsed.password is not None or parsed.fragment):
        raise ValueError("Ace Stream download must stay on the official HTTPS publisher host")
    return url


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_publisher_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def linux_distribution(path="/etc/os-release"):
    values = {}
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return values.get("ID", "").lower(), values.get("VERSION_ID", "")


def compatibility(distribution=None, machine=None):
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Linux Ace bootstrap is not available on this platform")
    distro, version = distribution or linux_distribution()
    arch = machine or platform.machine()
    if arch not in ("x86_64", "amd64"):
        raise RuntimeError("Official Ace Stream Linux archive is x86-64 only")
    if distro != "ubuntu" or version != "22.04":
        raise RuntimeError(
            "The original publisher currently lists Ace Stream Linux 3.2.11 "
            "for Ubuntu 22.04 / Python 3.10, not this operating system ("
            + (distro or "unknown") + " " + (version or "unknown") + "). "
            "DizyTV will not execute an unverified engine on this machine. "
            "You can still connect an already-installed trusted local or remote engine.")
    return True


def download_official(destination, opener=None, digest=SHA256, progress=None, cancel=None):
    """Fixed publisher URL, size bound, fixed SHA and same-host HTTPS redirects."""
    check_publisher_url(OFFICIAL_URL)
    if opener is None:
        opener = build_opener(OfficialRedirect()).open
    request = Request(OFFICIAL_URL, headers={"User-Agent": "DizyTV-vendor-bootstrap/1"})
    total = 0
    hashed = hashlib.sha256()
    try:
        with opener(request, timeout=90) as response, Path(destination).open("xb") as output:
            check_publisher_url(response.geturl())
            if getattr(response, "status", 200) != 200:
                raise RuntimeError("Ace publisher did not return a successful download")
            size = response.headers.get("Content-Length") if hasattr(response, "headers") else None
            size = int(size) if size and size.isdecimal() else None
            if size is not None and size > MAX_ARCHIVE_BYTES:
                raise RuntimeError("Ace engine download exceeds the size limit")
            while True:
                if cancel is not None and cancel():
                    raise RuntimeError("Ace Stream download cancelled; no files installed")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise RuntimeError("Ace engine download exceeds the size limit")
                hashed.update(chunk)
                output.write(chunk)
                if progress:
                    progress(total, size or MAX_ARCHIVE_BYTES)
        if hashed.hexdigest() != digest:
            raise RuntimeError("Ace engine checksum mismatch: no installation performed")
        with Path(destination).open("rb") as archive:
            if archive.read(2) != b"\x1f\x8b":
                raise RuntimeError("Ace publisher returned a non-gzip file")
        return total
    except Exception:
        Path(destination).unlink(missing_ok=True)
        raise


def extract_verified_archive(archive_path, destination):
    """Bound expanded size; Python 3.12 tar 'data' filter excludes unsafe links."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) > MAX_MEMBERS or sum(m.size for m in members if m.isfile()) > MAX_EXPANDED_BYTES:
            raise RuntimeError("Unexpected size of Ace Stream archive")
        for member in members:
            parts = PurePosixPath(member.name).parts
            if (not parts or any(p in (".", "..") for p in parts)
                    or member.name.startswith("/") or member.isdev()
                    or member.isfifo()):
                raise RuntimeError("Unsafe file in Ace Stream publisher archive")
        # No global chown, /opt writes, or unsafe symlinks. tarfile data filter
        # rejects link targets outside destination and unsafe special files.
        archive.extractall(destination, filter="data")
    candidates = [destination] + [p for p in destination.iterdir() if p.is_dir()]
    matches = [p for p in candidates if (p / "start-engine").is_file()]
    if len(matches) != 1:
        raise RuntimeError("Publisher archive lacks a unique start-engine launcher")
    selected = matches[0]
    launcher = selected / "start-engine"
    if launcher.is_symlink():
        raise RuntimeError("Publisher's engine launcher is an unexpected symbolic link")
    launcher.chmod(launcher.stat().st_mode | 0o100)
    return selected


def install_original(*, consent=False, destination=None, progress=None, cancel=None,
                     opener=None, distribution=None, machine=None, digest=SHA256):
    """Opt-in per-user install with atomic publish and zero automatic execution."""
    if consent is not True:
        raise PermissionError("Ace Stream P2P installation requires explicit user consent")
    compatibility(distribution, machine)
    target = Path(destination) if destination is not None else (
        Path.home() / ".local" / "opt" / "acestream"
    )
    if target.exists() or target.is_symlink():
        raise FileExistsError("Ace Stream already exists at the selected destination; refusing to overwrite it")
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    # All staging and rename operations happen on the user's own filesystem.
    with tempfile.TemporaryDirectory(prefix=".dizytv-ace-", dir=parent) as temp:
        root = Path(temp)
        archive = root / "official.tar.gz"
        download_official(archive, opener=opener, digest=digest, progress=progress, cancel=cancel)
        if cancel is not None and cancel():
            raise RuntimeError("Ace Stream installation cancelled")
        content = extract_verified_archive(archive, root / "unpack")
        if cancel is not None and cancel():
            raise RuntimeError("Ace Stream installation cancelled")
        # This provenance marker belongs to DizyTV; upstream engine remains
        # otherwise unchanged. No scripts, services or executables are run.
        (content / ".dizytv-publisher-install.json").write_text(
            json.dumps({"source": OFFICIAL_URL, "version": VERSION, "sha256": digest}) + "\n",
            encoding="utf-8")
        if target.exists():
            raise FileExistsError("A separate engine installation appeared during setup")
        content.rename(target)
    return str(target / "start-engine")
