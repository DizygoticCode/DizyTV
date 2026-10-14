import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from dizytv.subtitles import (
    COLOURS, POSITIONS, FONTS, validate_caption_settings,
    vlc_subtitle_options, subtitle_tracks, suggested_subtitle,
    external_subtitle_path,
)
from dizytv.core import default_state, validate_state, export_backup, restore_backup


class SubtitleContractTests(unittest.TestCase):
    def test_default_subtitles_and_legacy_backup_are_preserved(self):
        state=default_state()
        self.assertTrue(state['settings']['subtitles_enabled'])
        self.assertIn('--freetype-fontsize=28',vlc_subtitle_options(state['settings']))
        restored=restore_backup(export_backup(state))
        self.assertEqual(state['settings']['subtitle_colour'],
                         restored['settings']['subtitle_colour'])
        for key in ('subtitles_enabled','subtitle_size','subtitle_colour',
                    'subtitle_position','subtitle_font','subtitle_language'):
            state['settings'].pop(key)
        validate_state(state)
        self.assertIn('--freetype-fontsize=28',vlc_subtitle_options(state['settings']))

    def test_preferences_bound_colour_size_font_position_and_language(self):
        state=default_state()
        s=state['settings']
        s.update(subtitle_size=44,subtitle_colour='Yellow',
                 subtitle_font='Monospace',subtitle_position='Raised',
                 subtitle_language='English',subtitles_enabled=True)
        validate_state(state)
        options=vlc_subtitle_options(s)
        self.assertIn('--freetype-color=0xFFFF00',options)
        self.assertIn('--freetype-fontsize=44',options)
        self.assertIn('--freetype-font=Consolas',options)
        self.assertIn('--sub-margin=70',options)
        invalid=[('subtitle_size',0),('subtitle_size',65),('subtitle_size',20.5),
                 ('subtitle_colour','Magenta'),('subtitle_position','Offscreen'),
                 ('subtitle_font','Random;font=evil'),('subtitle_language','fr'),
                 ('subtitles_enabled','yes')]
        for key,bad in invalid:
            original=s[key]
            s[key]=bad
            with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):
                validate_state(state)
            s[key]=original

    def test_vlc_tracks_handle_bytes_and_missing_subtitles(self):
        player=Mock()
        player.video_get_spu_description.return_value=[
            (-1,b'Disable'),(0,b'French'),(5,b'English [en]'),
            (5,b'Duplicate'),(6,None)]
        self.assertEqual([(0,'French'),(5,'English [en]'),(6,'Subtitles')],
                         subtitle_tracks(player))
        self.assertEqual(5,suggested_subtitle(subtitle_tracks(player),'English'))
        self.assertEqual(0,suggested_subtitle(subtitle_tracks(player)))
        self.assertIsNone(suggested_subtitle([]))
        player.video_get_spu_description.return_value=None
        self.assertEqual([],subtitle_tracks(player))

    def test_bare_english_language_codes_are_preferred_over_first_foreign_track(self):
        for code in ('eng','en','en-US','en_GB','[en]','ENG','English (United Kingdom)'):
            with self.subTest(label=code):
                self.assertEqual(4,suggested_subtitle([(1,'French'),(4,code)],'English'))
        # Do not conflate arbitrary titles containing similar letters.
        self.assertEqual(1,suggested_subtitle([(1,'Français'),(4,'Engagement')],
                                              'English'))

    def test_external_subtitle_file_must_exist_and_be_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'captions.srt'
            path.write_text('1\n00:00:01,000 --> 00:00:02,000\nHello\n',encoding='utf-8')
            self.assertEqual(str(path.resolve()),external_subtitle_path(path))
            with self.assertRaises(ValueError):
                external_subtitle_path(Path(folder)/'missing.srt')
            unknown=Path(folder)/'bad.exe'
            unknown.write_bytes(b'not a caption file')
            with self.assertRaises(ValueError):
                external_subtitle_path(unknown)


if __name__ == '__main__':
    unittest.main()
