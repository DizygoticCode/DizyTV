"""Dedicated 24/7 directory and reversible hidden-channel regression tests."""
import hashlib
import tempfile
import unittest

from dizytv.core import default_state, parse_playlist, validate_state, channel_section, catalogue
from dizytv.channel_browser import channel_sort_key, is_show_loop_channel, stable_channel_key
from dizytv.channel_health import confirmed_missing_ids
from dizytv.storage import Store
from dizytv.sources import OPTIONAL_SHOW_LOOP_PLAYLISTS, OPTIONAL_UK_RETRANSMISSIONS


def channel(name, group='Series', country='United Kingdom', chno=''):
    return dict(id=hashlib.sha1((name+group).encode()).hexdigest(),
                name=name, group=group, genre='Series',
                country=country, kind='TV', transport='HTTP', tvg_id=name,
                stream='https://example.com/'+name.replace(' ','-'),chno=chno)


class BrowserTests(unittest.TestCase):

    def test_international_channel_names_keep_distinct_sort_keys(self):
        names = ['Русское ТВ', '中国电视', 'Énergie TV', 'Ελληνικά', '日本テレビ']
        keys = [channel_sort_key(channel(name), 'Name A–Z') for name in names]
        self.assertEqual(len(names), len(set(keys)))
        self.assertTrue(any('中国' in key[0] for key in keys))

    def test_24_7_classifies_specific_shows_and_marathons(self):
        for name in ('South Park','Rick and Morty','Family Guy','The Simpsons',
                     'Brooklyn 99','The Goldbergs','The Big Bang Theory',
                     'Young Sheldon','Friends','Futurama',
                     'Pluto TV Sitcoms','Pluto TV Comedy Movies',
                     '24/7 Comedy Series','Comedy Movie Marathon'):
            with self.subTest(name=name):
                self.assertTrue(is_show_loop_channel(channel(name)),
                                msg=name)
                self.assertEqual('24/7 Shows & Loops',channel_section(channel(name)))
        for name,group in (
            ('BBC News','News'),('Sky Sports 24/7','Sport'),
            ('Classic Rock 24/7','Music'),('BBC One','General'),
            ('Southampton FC 24/7','Football'),
            ('Garfield and Friends','Kids'),
            ('Barbie and Friends','Kids')):
            with self.subTest(name=name):
                self.assertFalse(is_show_loop_channel(channel(name,group)))
                self.assertNotEqual('24/7 Shows & Loops',
                                    channel_section(channel(name,group)))

    def test_247_alias_and_exact_friends_sitcom(self):
        self.assertTrue(is_show_loop_channel(channel('247 South Park')))
        self.assertTrue(is_show_loop_channel(channel('247 Friends')))
        self.assertFalse(is_show_loop_channel(channel('Garfield and Friends','Kids')))

    def test_group_tag_finds_generic_named_marathons(self):
        self.assertTrue(is_show_loop_channel(channel('The Classics','24/7 Comedy Series')))
        self.assertTrue(is_show_loop_channel(channel('Comedy Showcase','Binge Watch TV Loops')))

    def test_freeview_and_similar_sort_keep_plus_ones_together(self):
        channels=[channel('E4 +1'), channel('BBC Two'),channel('E4'),
                  channel('BBC One'),channel('E4 Extra'),channel('ITV1')]
        sorted_uk=sorted(channels,key=lambda c:channel_sort_key(c,'UK Freeview style'))
        self.assertEqual(['BBC One','BBC Two','ITV1'],[c['name'] for c in sorted_uk[:3]])
        self.assertLess([c['name'] for c in sorted_uk].index('E4'),
                        [c['name'] for c in sorted_uk].index('E4 +1'))
        similar=sorted(channels,key=lambda c:channel_sort_key(c,'Similar names / +1'))
        names=[c['name'] for c in similar]
        self.assertEqual(names.index('E4')+1,names.index('E4 +1'))
        original=sorted(enumerate(channels),
                        key=lambda p:channel_sort_key(p[1],'Playlist order',p[0]))
        self.assertEqual(channels,[x[1] for x in original])

    def test_playlist_lcn_and_plex_token_ids_survive_refresh(self):
        raw='#EXTM3U\n#EXTINF:-1 tvg-id="E4.uk" tvg-chno="13" group-title="UK",E4\nhttps://example.com/e4.m3u8\n'
        ch=parse_playlist(raw)[0]
        self.assertEqual('13',ch['chno'])
        base='https://epg.provider.plex.tv/library/parts/01234567-89ab/'
        self.assertEqual(stable_channel_key(base+'?token=old'),
                         stable_channel_key(base+'?token=new'))
        self.assertNotEqual(stable_channel_key('https://example.com/a?id=1'),
                            stable_channel_key('https://example.com/a?id=2'))

    def test_hide_and_restore_preserve_epg_and_favourites(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(folder)
            a=channel('E4'); b=channel('South Park')
            def seed(st):
                st['channels']=[a,b]
                st['favourites']=[a['id']]
                st['mappings']={a['id']:'E4.uk'}
                st['disabled_channels']=[a['id']]
            store.update(seed)
            state=store.read()
            self.assertEqual([b['id']],[c['id'] for c in catalogue(state,include_disabled=False)])
            self.assertEqual(2,len(catalogue(state,include_disabled=True)))
            self.assertEqual([a['id']],state['favourites'])
            self.assertEqual('E4.uk',state['mappings'][a['id']])
            store.update(lambda st:st.update(disabled_channels=[]))
            self.assertEqual(2,len(catalogue(store.read(),include_disabled=False)))
            legacy=store.read()
            legacy.pop('disabled_channels')
            self.assertIs(validate_state(legacy),legacy)

    def test_consecutive_missing_only_excludes_404_410_not_geo_denied(self):
        key=hashlib.sha1(b'channel').hexdigest()
        result=lambda status:dict(id=key,status=status)
        self.assertFalse(confirmed_missing_ids([result('missing')]))
        self.assertEqual({key},confirmed_missing_ids([result('missing'),result('missing')]))
        self.assertFalse(confirmed_missing_ids([result('missing'),result('access-limited'),
                                                result('missing')]))
        self.assertFalse(confirmed_missing_ids([result('missing'),result('rate-limited')]))

    def test_additional_us_and_uk_candidate_presets_exist(self):
        self.assertEqual(4,len(OPTIONAL_SHOW_LOOP_PLAYLISTS))
        self.assertEqual(2,len(OPTIONAL_UK_RETRANSMISSIONS))
        for name,url,_ in (*OPTIONAL_SHOW_LOOP_PLAYLISTS,*OPTIONAL_UK_RETRANSMISSIONS):
            self.assertTrue(url.startswith('https://'))
        state=default_state()
        state['settings']['channel_sort']='UK Freeview style'
        validate_state(state)
        state['settings']['channel_sort']='Bad mode'
        with self.assertRaises(ValueError):validate_state(state)


if __name__=='__main__':
    unittest.main()
