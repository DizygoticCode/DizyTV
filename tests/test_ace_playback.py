"""Guard the Ace Engine -> actual playable URL handoff."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from dizytv.core import ace_id, parse_playlist, stream_url
from dizytv import engine

HASH = "a" * 40
ENGINE = "http://127.0.0.1:6878"


class AcePlaybackTests(unittest.TestCase):
    def session_response(self, playback_url):
        return io.BytesIO(json.dumps({
            "response": {"playback_url": playback_url, "is_live": 1},
            "error": None
        }).encode())

    def test_infohash_is_never_silently_converted_to_content_id(self):
        original = "http://localhost:6878/ace/getstream?infohash=" + HASH + "&hlc=1&transcode_audio=0"
        parsed = parse_playlist("#EXTM3U\n#EXTINF:-1,Test\n" + original + "\n")
        self.assertEqual(parsed[0]["stream"], original)
        self.assertEqual(parsed[0]["id"], HASH)
        converted = stream_url(parsed[0]["stream"], "http://127.0.0.1:6879")
        self.assertIn("/ace/getstream?infohash=" + HASH, converted)
        self.assertIn("hlc=1", converted)
        self.assertIn("transcode_audio=0", converted)
        self.assertTrue(converted.startswith("http://127.0.0.1:6879/"))
        self.assertNotIn("?id=", converted)

    def test_acestream_content_id_preserves_existing_behavior(self):
        self.assertEqual(ace_id("acestream://" + HASH), HASH)
        self.assertEqual(stream_url("acestream://" + HASH, ENGINE), ENGINE + "/ace/getstream?id=" + HASH)

    def test_non_ace_urls_not_misidentified(self):
        ordinary = "https://example.com/stream?id=" + HASH
        self.assertIsNone(ace_id(ordinary))
        self.assertEqual(stream_url(ordinary, ENGINE), ordinary)

    def test_session_returns_validated_playback_url_for_vlc(self):
        playback = ENGINE + "/ace/content/" + HASH + "/session-token"
        with patch.object(engine, "urlopen", return_value=self.session_response(playback)) as open_url:
            resolved = engine.start_playback_session("acestream://" + HASH, ENGINE)
        self.assertEqual(resolved, playback)
        requested = open_url.call_args.args[0]
        self.assertIn("format=json", requested)
        self.assertIn("id=" + HASH, requested)

    def test_session_request_keeps_infohash_and_safe_options(self):
        original = ENGINE + "/ace/getstream?infohash=" + HASH + "&hlc=1"
        with patch.object(engine, "urlopen", return_value=self.session_response(ENGINE + "/ace/m/live.m3u8")) as get:
            engine.start_playback_session(original, ENGINE)
        self.assertIn("infohash=" + HASH, get.call_args.args[0])
        self.assertNotIn("id=" + HASH, get.call_args.args[0])
        self.assertIn("hlc=1", get.call_args.args[0])

    def test_engine_does_not_return_any_untrusted_external_media_url(self):
        for url in ("https://evil.example.net/stream",
                    "http://127.0.0.1:9999/stream",
                    "file:///C:/secret"):
            with self.subTest(url=url):
                with patch.object(engine, "urlopen", return_value=self.session_response(url)):
                    with self.assertRaisesRegex(RuntimeError, "outside its configured endpoint"):
                        engine.start_playback_session("acestream://" + HASH, ENGINE)

    def test_engine_error_is_reported_as_source_failure_not_connected(self):
        payload = io.BytesIO(b'{"error": "No peers available", "response": null}')
        with patch.object(engine, "urlopen", return_value=payload):
            with self.assertRaisesRegex(RuntimeError, "No peers available"):
                engine.start_playback_session("acestream://" + HASH, ENGINE)

    def test_missing_session_does_not_try_fake_playback(self):
        with patch.object(engine, "urlopen", return_value=io.BytesIO(b'{"response": {}, "error": null}')):
            with self.assertRaisesRegex(RuntimeError, "no playback URL"):
                engine.start_playback_session("acestream://" + HASH, ENGINE)

    def test_engine_http_error_is_helpfully_reported(self):
        with patch.object(engine, "urlopen", side_effect=HTTPError(ENGINE, 404, "Not Found", {}, None)):
            with self.assertRaisesRegex(RuntimeError, "HTTP 404"):
                engine.start_playback_session("acestream://" + HASH, ENGINE)


if __name__ == "__main__":
    unittest.main()
