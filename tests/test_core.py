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
    def test_source_country_tags_do_not_treat_quality_tags_as_countries(self):
        source = '#EXTM3U\n#EXTINF:-1,Channel [HD] [RU]\nhttps://example.com/a.ts\n#EXTINF:-1 tvg-country="GB",Channel [RU]\nhttps://example.com/b.ts\n#EXTINF:-1,Channel [FHD]\nhttps://example.com/c.ts'
        self.assertEqual(['Russia','United Kingdom','Unspecified'], [c['country'] for c in parse_playlist(source)])

    def test_saved_categories_survive_refresh_and_portable_backup(self):
        from dizytv.core import catalogue
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory)
            store.update(lambda s:s.update(channels=parse_playlist(PLAYLIST),category_overrides={ACE:{'country':'Ireland','genre':'News','kind':'Radio'}}))
            store.update(lambda s:s.update(channels=parse_playlist(PLAYLIST.replace('BBC One','Updated name'))))
            restored=restore_backup(export_backup(store.read()))
            channel=catalogue(restored)[0]
            self.assertEqual(('Updated name','Ireland','News','Radio','Ace Stream'),tuple(channel[k] for k in ('name','country','genre','kind','transport')))
            self.assertEqual('United Kingdom',restored['channels'][0]['country'])
            bad=default_state(); bad['category_overrides']={ACE:{'stream':'https://example.com/changed'}}
            with self.assertRaises(ValueError):validate_state(bad)

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


    def test_guide_lookup_is_equivalent_and_rejects_ambiguous_labels(self):
        from dizytv.core import guide_lookup, match_guide
        names={'bbc-north':'BBC One','bbc-south':'BBC One','bbc-two':'BBC Two HD'}
        lookup=guide_lookup(names)
        channel={'id':'a'*40,'tvg_id':'','name':'BBC One Ⓖ'}
        self.assertEqual('',match_guide(channel,{},names,lookup))
        channel['tvg_id']='bbc-two'
        self.assertEqual('bbc-two',match_guide(channel,{},names,lookup))

    def test_freeview_uk_aliases_markers_and_regional_ambiguity(self):
        from dizytv.core import match_guide
        names={
            'BBCTwoHD.uk':'BBC Two HD','BBCFourHD.uk':'BBC Four HD',
            '5.uk':'5 HD','BBCOneSouth.uk':'BBC One South HD',
            'BBCOneLondonHD.uk':'BBC One London HD',
            'ITV1London.uk':'ITV1 London HD',
        }
        make=lambda key,name,cid='a'*40:{'id':cid,'tvg_id':key,'name':name}
        self.assertEqual('BBCTwoHD.uk',match_guide(make('BBCTwo.uk','BBC Two Ⓖ'),{},names))
        self.assertEqual('BBCFourHD.uk',match_guide(make('BBCFour.uk','BBC Four Ⓖ'),{},names))
        self.assertEqual('5.uk',match_guide(make('Channel5.uk','Channel 5 Ⓢ'),{},names))
        self.assertEqual('BBCTwoHD.uk',match_guide(make('BBCTwoHD.uk@HD','BBC Two'),{},names))
        self.assertEqual('BBCOne.uk',match_guide(make('BBCOne.uk','BBC One Ⓖ'),{},names))
        self.assertEqual('BBCOneSouth.uk',match_guide(make('BBCOne.uk','BBC One Ⓖ'),{'a'*40:'BBCOneSouth.uk'},names))
        self.assertEqual('',match_guide(make('BBCOne.uk','BBC One Ⓖ'),{'a'*40:''},names))
        self.assertEqual('ITV1.uk',match_guide(make('ITV1.uk','ITV 1'),{},names))

    def test_radio_from_uk_playlist_ids_and_names(self):
        from dizytv.core import channel_kind,channel_section,parse_playlist
        m3u=('#EXTM3U\n'
             '#EXTINF:-1 tvg-id="BBCRadio1.uk" tvg-country="GB" group-title="UK",BBC Radio 1\n'
             'https://example.com/radio1.m3u8\n'
             '#EXTINF:-1 tvg-id="BBCRadioAsianNetwork.uk" tvg-country="GB" group-title="UK",BBC Asian Network\n'
             'https://example.com/asian.m3u8\n'
             '#EXTINF:-1 tvg-id="BBCOne.uk" tvg-country="GB" group-title="UK",BBC One\n'
             'https://example.com/tv.m3u8\n')
        channels=parse_playlist(m3u)
        self.assertEqual(['Radio','Radio','TV'],[c['kind'] for c in channels])
        # Cached alpha states have old kind=TV: derive the category at display time.
        old=dict(channels[0],kind='TV')
        self.assertEqual('Radio',channel_kind(old))
        self.assertEqual('Radio',channel_section(old))
        self.assertEqual('TV',channel_kind(channels[2]))

    def test_presentational_name_cleanup_and_country_sections(self):
        from dizytv.core import display_channel_name,channel_section
        samples={
            'BBC One Ⓖ @HD':'BBC One',
            'BBC Two @':'BBC Two',
            'BBC Four Ⓢ':'BBC Four',
            'BBC One @1080p':'BBC One',
            'NBC News [HD]':'NBC News',
            'AT&T SportsNet':'AT&T SportsNet',
            'Great! Movies':'Great! Movies',
            'Channel 5 @ UK Ⓖ':'Channel 5',
            '  ':'Unnamed channel',
        }
        for raw,expected in samples.items():
            self.assertEqual(expected,display_channel_name(raw),raw)
        channels=parse_playlist('#EXTM3U\n#EXTINF:-1 tvg-id="BBCOne.uk" tvg-country="GB" group-title="UK",BBC One @ HD Ⓖ\nhttps://example.com/bbc.m3u8')
        self.assertEqual('BBC One @ HD Ⓖ',channels[0]['name'])
        self.assertEqual('BBCOne.uk',channels[0]['tvg_id'])
        self.assertEqual('https://example.com/bbc.m3u8',channels[0]['stream'])
        self.assertEqual('BBC One',display_channel_name(channels[0]['name']))
        self.assertEqual('General TV',channel_section(channels[0]))
        self.assertEqual('News',channel_section({'name':'BBC News','genre':'Unspecified','group':'UK','kind':'TV'}))
        self.assertEqual('Sport',channel_section({'name':'ESPN','genre':'Sport','group':'USA','kind':'TV'}))
        self.assertEqual('Radio',channel_section({'name':'Radio 1','genre':'Music','group':'UK','kind':'Radio'}))

    def test_optional_timeshift_settings_are_bounded(self):
        from dizytv.core import default_state,validate_state
        s=default_state()
        self.assertFalse(s['settings']['timeshift_enabled'])
        s['settings']['timeshift_enabled']=True
        s['settings']['timeshift_minutes']=240
        s['settings']['timeshift_max_bytes']=32*1024**3
        validate_state(s)
        s['settings']['timeshift_minutes']=241
        with self.assertRaises(ValueError):validate_state(s)
        s['settings']['timeshift_minutes']=30
        s['settings']['timeshift_max_bytes']=128*1024**2
        with self.assertRaises(ValueError):validate_state(s)
        del s['settings']['timeshift_enabled']
        del s['settings']['timeshift_minutes']
        del s['settings']['timeshift_max_bytes']
        del s['settings']['timeshift_dir']
        # Old installations remain valid without new keys.
        validate_state(s)

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
