"""No network, P2P engine execution or root privileges in the CI tests."""
import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dizytv import linux_ace_bootstrap as ace


class FakePublisher:
    status = 200

    def __init__(self, content, url=ace.OFFICIAL_URL):
        self.content=io.BytesIO(content)
        self.headers={"Content-Length":str(len(content))}
        self.url=url

    def __enter__(self):
        return self

    def __exit__(self,*_):
        return False

    def geturl(self):
        return self.url

    def read(self,n):
        return self.content.read(n)


def archive_with(entries):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode="w:gz") as archive:
        for name,data in entries:
            info=tarfile.TarInfo(name)
            info.size=len(data)
            info.mode=0o755 if name.endswith("start-engine") else 0o644
            archive.addfile(info,io.BytesIO(data))
    return output.getvalue()


class LinuxAceBootstrapTests(unittest.TestCase):
    def test_official_download_is_fixed_and_unsupported_distro_fails_closed(self):
        self.assertEqual("download.acestream.media",ace.PUBLISHER_HOST)
        self.assertRegex(ace.SHA256,r"^[a-f0-9]{64}$")
        with patch.object(ace.sys,'platform','linux'):
            with self.assertRaisesRegex(RuntimeError,"Ubuntu 22.04"):
                ace.compatibility(("ubuntu","24.04"),"x86_64")
            with self.assertRaisesRegex(RuntimeError,"x86-64"):
                ace.compatibility(("ubuntu","22.04"),"aarch64")
            self.assertTrue(ace.compatibility(("ubuntu","22.04"),"x86_64"))

    def test_no_consent_no_network_or_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                ace.install_original(destination=Path(tmp)/"ace")
            self.assertFalse((Path(tmp)/"ace").exists())

    def test_refuses_insecure_or_private_redirects(self):
        for url in ("http://download.acestream.media/linux/ace.tar.gz",
                    "https://user:secret@download.acestream.media/file",
                    "https://evil.example/download",
                    "https://download.acestream.media:444/file"):
            with self.subTest(url=url),self.assertRaises(ValueError):
                ace.check_publisher_url(url)
        data=archive_with([("start-engine",b"original")])
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"download.tar.gz"
            with self.assertRaisesRegex(ValueError,"official HTTPS"):
                ace.download_official(target,
                    opener=lambda *_args,**_kw:FakePublisher(data,url="https://evil.example/payload"))
            self.assertFalse(target.exists())

    def test_installs_original_archive_atomically_without_executing_binary(self):
        data=archive_with([
            ("acestream_3.2.11/start-engine",b"#!/bin/sh\nexit 0\n"),
            ("acestream_3.2.11/acestreamengine",b"FAKE-ELF-NOT-EXECUTED"),
        ])
        digest=hashlib.sha256(data).hexdigest()
        received=[]
        with tempfile.TemporaryDirectory() as tmp,patch.object(ace.sys,'platform','linux'):
            target=Path(tmp)/"acestream"
            result=ace.install_original(
                consent=True,destination=target,digest=digest,
                distribution=("ubuntu","22.04"),machine="x86_64",
                opener=lambda *_args,**_kw:FakePublisher(data),
                progress=lambda count,expected:received.append((count,expected)))
            self.assertEqual(result,str(target/"start-engine"))
            self.assertTrue((target/"start-engine").is_file())
            self.assertTrue((target/"acestreamengine").is_file())
            self.assertTrue((target/".dizytv-publisher-install.json").is_file())
            self.assertTrue(received)
            with self.assertRaises(FileExistsError):
                ace.install_original(consent=True,destination=target,
                    distribution=("ubuntu","22.04"),machine="x86_64")

    def test_bad_digest_or_cancel_never_publishes_partial_install(self):
        data=archive_with([("start-engine",b"fixture")])
        with tempfile.TemporaryDirectory() as tmp,patch.object(ace.sys,'platform','linux'):
            target=Path(tmp)/"engine"
            base=dict(consent=True,destination=target,
                      distribution=("ubuntu","22.04"),machine="x86_64",
                      opener=lambda *_a,**_kw:FakePublisher(data))
            with self.assertRaisesRegex(RuntimeError,"checksum mismatch"):
                ace.install_original(**base)
            self.assertFalse(target.exists())
            with self.assertRaisesRegex(RuntimeError,"cancelled"):
                ace.install_original(**base,cancel=lambda:True)
            self.assertFalse(target.exists())

    def test_reject_traversal_and_symlink_leaving_user_directory(self):
        bad=archive_with([("../escape",b"escape"),
                          ("start-engine",b"fixture")])
        with tempfile.TemporaryDirectory() as tmp:
            extract=Path(tmp)/"extract"
            with (Path(tmp)/"archive.tar.gz").open("wb") as f:
                f.write(bad)
            with self.assertRaisesRegex(RuntimeError,"Unsafe"):
                ace.extract_verified_archive(Path(tmp)/"archive.tar.gz",extract)
            self.assertFalse((Path(tmp)/"escape").exists())
            # A tarfile 'data' filter rejects a symlink to /etc.
            symlink=io.BytesIO()
            with tarfile.open(fileobj=symlink,mode="w:gz") as tar:
                m=tarfile.TarInfo("start-engine")
                m.type=tarfile.SYMTYPE
                m.linkname="/etc/passwd"
                tar.addfile(m)
            (Path(tmp)/"other.tar.gz").write_bytes(symlink.getvalue())
            with self.assertRaises((tarfile.TarError,RuntimeError,ValueError)):
                ace.extract_verified_archive(Path(tmp)/"other.tar.gz",Path(tmp)/"other")
