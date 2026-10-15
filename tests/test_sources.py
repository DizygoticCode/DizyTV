import unittest

from dizytv.core import default_state, export_backup, restore_backup, match_guide, validate_state
from dizytv.sources import LEGACY_URL, DEFAULT_PLAYLIST_URLS, DEFAULT_GUIDE_URLS, configured_playlists, refresh_catalogue

def feed(url, name="News", tvg="News.us"):
    return '#EXTM3U\n#EXTINF:-1 tvg-id="'+tvg+'",'+name+'\n'+url+'\n'


class FreeSourceTests(unittest.TestCase):
    def test_import_errors_identify_builtin_source_not_generic_hostname(self):
        from dizytv.sources import source_label
        uk=DEFAULT_PLAYLIST_URLS[1]
        self.assertEqual('UK free television',source_label(uk))
        settings={'playlist_url':uk,'playlist_urls':[uk]}
        _,success,errors=refresh_catalogue(settings,[{'id':'a'*40,'name':'Cached','group':'','tvg_id':'','stream':'https://example.com/a.m3u8','source':uk}],lambda _: (_ for _ in ()).throw(OSError('offline')))
        self.assertEqual(0,success)
        self.assertEqual(['UK free television: OSError'],errors)

    def test_new_country_and_classic_series_movies_comedy_presets(self):
        from dizytv.sources import FREE_PLAYLISTS,source_label
        sources=dict((label,url) for label,url,_ in FREE_PLAYLISTS)
        for label,country in (
            ('IPTV-org Canada','ca'),('IPTV-org Australia','au'),
            ('IPTV-org New Zealand','nz'),('IPTV-org South Africa','za'),
            ('IPTV-org Singapore','sg'),('IPTV-org Hong Kong','hk')):
            self.assertIn('/countries/'+country+'.m3u',sources[label])
        for category in ('classic','series','movies','comedy','sports'):
            url='https://iptv-org.github.io/iptv/categories/'+category+'.m3u'
            self.assertIn(url,DEFAULT_PLAYLIST_URLS)
            self.assertIn('Free ',source_label(url))
        self.assertEqual(19,len(DEFAULT_PLAYLIST_URLS))
        self.assertEqual(20,len(FREE_PLAYLISTS))
        state=default_state()
        self.assertEqual(DEFAULT_PLAYLIST_URLS,state['settings']['playlist_urls'])
        self.assertEqual(19,len(configured_playlists(state['settings'])))

    def test_same_stream_is_searchable_under_region_and_series_feeds(self):
        from dizytv.sources import FREE_PLAYLISTS
        presets={label:url for label,url,_ in FREE_PLAYLISTS}
        region=presets['IPTV-org Canada']
        series=presets['Free television series channels']
        url='https://example.com/same-stream.m3u8'
        settings={'playlist_url':region,'playlist_urls':[region,series]}
        rows,success,errors=refresh_catalogue(settings,[],lambda _:feed(url,'Old Show 24/7'))
        self.assertEqual((2,[]),(success,errors))
        self.assertEqual(1,len(rows))
        self.assertEqual([region,series],rows[0]['sources'])
        self.assertEqual('Canada',rows[0]['country'])
        self.assertEqual('Series',rows[0]['genre'])
        state=default_state()
        state['channels']=rows
        validate_state(state)
        self.assertEqual([region,series],
                         restore_backup(export_backup(state))['channels'][0]['sources'])
        broken=default_state()
        broken['channels']=[{**rows[0],'sources':[region,'not-an-http-url']}]
        with self.assertRaises(ValueError):
            validate_state(broken)

    def test_region_and_24_7_source_hints_do_not_override_real_metadata(self):
        from dizytv.sources import FREE_PLAYLISTS
        urls={label:url for label,url,_ in FREE_PLAYLISTS}
        canada=urls['IPTV-org Canada']
        series=urls['Free television series channels']
        settings={'playlist_url':canada,'playlist_urls':[canada,series]}
        def fetch(url):
            if url==canada:
                return feed('https://example.com/canada.m3u8','Canadian Live')
            return feed('https://example.com/series.m3u8','Classic Drama')
        channels,success,errors=refresh_catalogue(settings,[],fetch)
        self.assertEqual(2,success)
        self.assertEqual([],errors)
        self.assertEqual('Canada',channels[0]['country'])
        self.assertEqual('Series',channels[1]['genre'])
        def metadata(_):
            return '#EXTM3U\n#EXTINF:-1 tvg-genre="Sport" tvg-country="AU",Sports Channel\nhttps://example.com/sport.m3u8\n'
        rows,_,_=refresh_catalogue({'playlist_url':series,'playlist_urls':[series]},[],metadata)
        self.assertEqual('Sport',rows[0]['genre'])
        self.assertEqual('Australia',rows[0]['country'])

    def test_free_uk_fast_presets_exist_and_us_fast_is_explicit_opt_in(self):
        from dizytv.sources import FREE_PLAYLISTS, OPTIONAL_FAST_PLAYLISTS
        fast={label:url for label,url,_ in FREE_PLAYLISTS}
        for name in ('Plex FAST UK · series/24-7',
                     'Samsung TV Plus FAST UK','Pluto TV FAST UK'):
            self.assertIn(name,fast)
            self.assertIn(fast[name],DEFAULT_PLAYLIST_URLS)
        for label,url,_ in OPTIONAL_FAST_PLAYLISTS:
            self.assertIn('US',label)
            self.assertNotIn(url,DEFAULT_PLAYLIST_URLS)

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
