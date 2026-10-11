import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

from dizytv.core import (parse_playlist, parse_xmltv, format_time, make_job,
                         check_conflicts, safe_filename, restore_backup, export_backup,
                         default_state, validate_state)
from dizytv.storage import Store

ACE = 'a' * 40
PLAYLIST = f'''#EXTM3U
#EXTINF:-1 tvg-id="bbc.one" group-title="UK",BBC One
acestream://{ACE}
#EXTINF:-1,Duplicate
http://127.0.0.1:6878/ace/getstream?id={ACE}
'''
XML = '''<?xml version="1.0"?><tv>
<channel id="bbc.one"><display-name>BBC One</display-name></channel>
<programme channel="bbc.one" start="20261025013000 +0100" stop="20261025013000 +0000"><title>Clock change</title></programme>
</tv>'''


class CoreTests(unittest.TestCase):
    def test_oversized_state_update_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory); store.update(lambda s:s.update(favourites=['a'*40])); before=store.path.read_bytes()
            channels=[{'id':f'{i:040x}','name':'N'*512,'group':'UK','tvg_id':'','stream':f'https://example.com/streams/{i}.ts'} for i in range(26000)]
            with self.assertRaisesRegex(ValueError,'too large'):
                store.update(lambda s:s.update(channels=channels))
            self.assertEqual(before,store.path.read_bytes())
            self.assertEqual(['a'*40],store.read()['favourites'])

    def test_country_genre_and_stream_categories(self):
        source = f'#EXTM3U\n#EXTINF:-1 tvg-country="GB" group-title="Sports",Local Sport\nacestream://{ACE}\n#EXTINF:-1 tvg-country="US" radio="true" group-title="Music",Radio\nhttps://example.com/live.ts\n'
        channels = parse_playlist(source)
        self.assertEqual('United Kingdom', channels[0]['country'])
        self.assertEqual('Sport', channels[0]['genre'])
        self.assertEqual('TV', channels[0]['kind'])
        self.assertEqual('Ace Stream', channels[0]['transport'])
        self.assertEqual('United States', channels[1]['country'])
        self.assertEqual('Radio', channels[1]['kind'])
        self.assertEqual('Unspecified', parse_playlist(PLAYLIST.replace('group-title="UK"',''))[0]['country'])

    def test_xmltv_preserves_programme_genres(self):
        xml = XML.replace('<title>Clock change</title>','<title>Clock change</title><category>News</category><category>Current affairs</category>')
        self.assertEqual(['News','Current affairs'], parse_xmltv(xml)[1][0]['categories'])

    def test_catalogue_stable_ids_deduplication(self):
        channels = parse_playlist(PLAYLIST)
        self.assertEqual(1, len(channels))
        self.assertEqual(ACE, channels[0]['id'])
        self.assertEqual('bbc.one', channels[0]['tvg_id'])
        self.assertEqual('UK', channels[0]['group'])

    def test_xmltv_utc_offsets_dst_and_correction(self):
        _, programmes = parse_xmltv(XML)
        p = programmes[0]
        self.assertEqual(3600, p['end'] - p['start'])
        self.assertIn('BST', format_time(p['start'], 'Europe/London'))
        self.assertIn('GMT', format_time(p['end'], 'Europe/London'))
        self.assertEqual('01:30 BST', format_time(p['start'], 'Europe/London', day=False))
        self.assertEqual(p['start'] + 1800, parse_xmltv(XML, 30)[1][0]['start'])

    def test_xmltv_without_offset_is_utc_and_no_entities(self):
        xml = '<tv><programme channel="x" start="20261011120000" stop="20261011130000"><title>X</title></programme></tv>'
        start = parse_xmltv(xml)[1][0]['start']
        self.assertEqual(12, datetime.fromtimestamp(start, timezone.utc).hour)
        with self.assertRaises(ValueError):
            parse_xmltv('<!DOCTYPE tv [<!ENTITY x SYSTEM "file:///etc/passwd">]><tv/>')

    def test_store_refresh_preserves_favourites_and_mappings(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            store.update(lambda s: s.update(channels=parse_playlist(PLAYLIST), favourites=[ACE], mappings={ACE: 'bbc.one'}))
            store.update(lambda s: s.update(channels=parse_playlist(PLAYLIST.replace('BBC One', 'BBC ONE HD'))))
            self.assertEqual([ACE], store.read()['favourites'])
            self.assertEqual('bbc.one', store.read()['mappings'][ACE])
            self.assertTrue((Path(folder)/'state.json').exists())

    def test_backup_restore_resets_storage_and_pauses_timers(self):
        state = default_state()
        state['settings']['recording_dir'] = '/another/device'
        state['channels'] = parse_playlist(PLAYLIST)
        state['favourites'] = [ACE]
        state['jobs'] = [make_job(ACE, 'News', 2000000000, 2000003600, 0, 0)]
        backup = export_backup(state)
        self.assertNotIn('/another/device', backup)
        restored = restore_backup(backup, now=1900000000)
        self.assertEqual('', restored['settings']['recording_dir'])
        self.assertEqual('paused', restored['jobs'][0]['status'])
        self.assertEqual(2000000000, restored['jobs'][0]['start'])
        restored['settings']['timezone'] = 'America/New_York'
        self.assertEqual(2000000000, restored['jobs'][0]['start'])
        self.assertEqual([ACE], restored['favourites'])

    def test_invalid_backup_never_overwrites_state(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder))
            before = store.read()
            for payload in ['{}', '{"app":"DizyTV","version":999,"data":{}}', '{"app":"DizyTV","version":1,"data":{"jobs":"oops"}}']:
                with self.assertRaises(ValueError):
                    store.replace(restore_backup(payload))
                self.assertEqual(before, store.read())
        state = default_state()
        state['settings']['timezone'] = 'No/Such_Zone'
        with self.assertRaises(ValueError):
            validate_state(state)

    def test_conflicts_padding_and_adjacent_timers(self):
        job = make_job(ACE, 'News', 2000000000, 2000003600, 2, 5)
        self.assertEqual(1999999880, job['start'])
        self.assertEqual(2000003900, job['end'])
        overlap = make_job(ACE, 'Next', 2000003600, 2000007200, 0, 0)
        self.assertEqual([job], check_conflicts([job], overlap))
        adjacent = make_job(ACE, 'Later', job['end'], job['end']+60, 0, 0)
        self.assertEqual([], check_conflicts([job], adjacent))
        job['status'] = 'paused'
        self.assertEqual([], check_conflicts([job], overlap))

    def test_safe_filename_cannot_escape_folder(self):
        name = safe_filename('../CON: ./News\\x?*', 2000000000)
        self.assertNotIn('/', name)
        self.assertNotIn('\\', name)
        self.assertTrue(name.endswith('.ts'))
        self.assertLess(len(name), 180)


if __name__ == '__main__':
    unittest.main()
