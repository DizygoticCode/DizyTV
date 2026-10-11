import unittest

from dizytv.core import default_state, export_backup, restore_backup, match_guide, validate_state
from dizytv.sources import LEGACY_URL, DEFAULT_PLAYLIST_URLS, DEFAULT_GUIDE_URLS, configured_playlists, refresh_catalogue

def feed(url, name="News", tvg="News.us"):
    return '#EXTM3U\n#EXTINF:-1 tvg-id="'+tvg+'",'+name+'\n'+url+'\n'


class FreeSourceTests(unittest.TestCase):
    def test_default_presets_include_uk_us_and_epg(self):
        state=default_state()
        self.assertTrue(any('countries/us.m3u' in u for u in state['settings']['playlist_urls']))
        self.assertTrue(any('playlist_uk.m3u8' in u for u in state['settings']['playlist_urls']))
        self.assertTrue(any('Freeview-EPG' in u for u in state['settings']['xmltv_urls']))
        self.assertEqual(state['settings']['playlist_urls'],configured_playlists(state['settings']))

    def test_refresh_deduplicates_and_retains_failed_source(self):
        urls=['https://example.com/one.m3u','https://example.com/two.m3u','https://example.com/three.m3u']
        settings={'playlist_url':urls[0], 'playlist_urls':urls}
        old=[{'id':'f'*40, 'name':'Saved', 'group':'', 'tvg_id':'','stream':'https://example.com/saved.ts', 'source':urls[2]}]
        def fetch(url):
            if url==urls[2]: raise OSError('network outage')
            return feed('https://example.com/shared.m3u8')
        channels,successful,errors=refresh_catalogue(settings,old,fetch)
        self.assertEqual(2,successful)
        self.assertEqual(1,len(errors))
        self.assertEqual(2,len(channels))
        self.assertEqual('Saved',channels[1]['name'])
        s=default_state(); s['channels']=channels; validate_state(s)
        self.assertEqual(2,len(restore_backup(export_backup(s))['channels']))

    def test_all_sources_failing_does_not_wipe_saved_catalogue(self):
        old=[{'id':'f'*40,'name':'Saved','group':'','tvg_id':'','stream':'https://example.com/saved.ts'}]
        settings={'playlist_url':LEGACY_URL,'playlist_urls':[LEGACY_URL]}
        channels,done,errors=refresh_catalogue(settings,old,lambda u: (_ for _ in ()).throw(OSError('offline')))
        self.assertEqual(old,channels); self.assertEqual(0,done); self.assertEqual(1,len(errors))

    def test_country_hint_applied_without_overriding_metadata(self):
        uk=[u for u in DEFAULT_PLAYLIST_URLS if 'countries/uk' in u][0]
        settings={'playlist_url':uk,'playlist_urls':[uk]}
        rows,_,_=refresh_catalogue(settings,[],lambda _:feed('https://example.com/uk.m3u8'))
        self.assertEqual('United Kingdom',rows[0]['country'])

    def test_existing_alpha_state_gets_preset_sources_and_guides(self):
        import tempfile
        from dizytv.storage import Store, atomic_json
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            old = default_state()
            old['settings'].pop('playlist_urls')
            old['settings']['xmltv_urls'] = []
            old['settings']['playlist_url'] = 'https://example.com/my-list.m3u'
            atomic_json(store.path, old)
            migrated = store.read()['settings']
            self.assertEqual('https://example.com/my-list.m3u', migrated['playlist_urls'][0])
            self.assertIn('https://example.com/my-list.m3u', migrated['playlist_urls'])
            self.assertEqual(DEFAULT_GUIDE_URLS, migrated['xmltv_urls'])
            store.update(lambda state: state['settings'].update(epg_offset_minutes=0))
            self.assertEqual(DEFAULT_GUIDE_URLS, store.read()['settings']['xmltv_urls'])

    def test_guide_match_is_exact_and_does_not_guess_regions(self):
        ch={'id':'a'*40,'tvg_id':'','name':'BBC News HD'}
        self.assertEqual('bbc-news',match_guide(ch,{}, {'bbc-news':'BBC News','bbc-one':'BBC One'}))
        self.assertEqual('',match_guide(ch,{ch['id']:''},{'bbc-news':'BBC News'}))
        self.assertEqual('',match_guide({'id':ch['id'],'tvg_id':'','name':'BBC One'}, {}, {'a':'BBC One','b':'BBC One'}))
        self.assertEqual('BBCNews.uk',match_guide({'id':ch['id'],'tvg_id':'bbcnews.uk','name':'Unknown'}, {}, {'BBCNews.uk':'BBC News'}))


if __name__ == '__main__': unittest.main()
