import unittest

from dizytv.iptv_directory import (
    DIRECTORY_ROWS, DIRECTORY_TYPES, DIRECTORY_URL, WORLDWIDE_URL,
    parse_directory, directory_search,
)
from dizytv.sources import source_label, refresh_catalogue
from dizytv.core import default_state, validate_state


class IPTVDirectoryTests(unittest.TestCase):
    def test_snapshot_contains_every_published_group_and_1279_concrete_urls(self):
        self.assertEqual(1279, len(DIRECTORY_ROWS))
        self.assertEqual(1279, len({row[2] for row in DIRECTORY_ROWS}))
        groups={name:sum(r[0]==name for r in DIRECTORY_ROWS)
                for name in DIRECTORY_TYPES[1:]}
        self.assertEqual({'Indexes':4, 'Countries':189, 'States & provinces':350,
                          'Cities':457, 'Regions':42, 'Categories':31,
                          'Languages':206}, groups)
        self.assertIn(WORLDWIDE_URL, [r[2] for r in DIRECTORY_ROWS])
        self.assertEqual('United Kingdom', next(r[1] for r in DIRECTORY_ROWS
                                               if r[2].endswith('/countries/uk.m3u')))
        self.assertEqual([], [row for row in DIRECTORY_ROWS
                              if '<FILENAME>' in row[2]])

    def test_directory_search_respects_type_country_parent_and_multiword_queries(self):
        matches=directory_search(DIRECTORY_ROWS,'Countries','new zealand')
        self.assertEqual(1,len(matches))
        self.assertEqual('New Zealand',matches[0][1])
        cities=directory_search(DIRECTORY_ROWS,'Cities','sydney australia')
        self.assertTrue(any(row[1]=='Sydney' and row[3]=='Australia' for row in cities))
        self.assertGreater(len(directory_search(DIRECTORY_ROWS,'Languages','english')),0)
        self.assertGreater(len(directory_search(DIRECTORY_ROWS,'Categories','series')),0)
        self.assertEqual([],directory_search(DIRECTORY_ROWS,'Categories','sydney'))

    def test_online_directory_parser_parses_tables_country_subdivisions_and_cities(self):
        text='''### Grouped by category
<tr><td>Comedy</td><td align="right">11</td><td><code>https://iptv-org.github.io/iptv/categories/comedy.m3u</code></td></tr>
### Grouped by language
<tr><td align="left">English</td><td>10</td><td><code>https://iptv-org.github.io/iptv/languages/eng.m3u</code></td></tr>
### Grouped by broadcast area
#### Countries
- 🇦🇺 Australia <code>https://iptv-org.github.io/iptv/countries/au.m3u</code>
  - New South Wales <code>https://iptv-org.github.io/iptv/subdivisions/au-nsw.m3u</code>
    - Sydney <code>https://iptv-org.github.io/iptv/cities/ausyd.m3u</code>
#### Regions
- Oceania <code>https://iptv-org.github.io/iptv/regions/oce.m3u</code>
'''
        with self.assertRaisesRegex(ValueError,'directory'):
            parse_directory(text)
        # Reject tiny/partial online indexes rather than replacing the bundled copy.
        self.assertIn('raw.githubusercontent.com',DIRECTORY_URL)

    def test_directory_hints_attach_country_and_category_without_duplicating_streams(self):
        country='https://iptv-org.github.io/iptv/countries/au.m3u'
        city='https://iptv-org.github.io/iptv/cities/ausyd.m3u'
        cat='https://iptv-org.github.io/iptv/categories/comedy.m3u'
        urls=[country,city,cat]
        settings={'playlist_url':country,'playlist_urls':urls}
        playlist='#EXTM3U\n#EXTINF:-1,Australian Comedy\nhttps://example.com/stream.m3u8\n'
        rows,successful,errors=refresh_catalogue(settings,[],lambda url:playlist)
        self.assertEqual((3,[]),(successful,errors))
        self.assertEqual(1,len(rows))
        self.assertEqual(urls,rows[0]['sources'])
        self.assertEqual('Australia',rows[0]['country'])
        self.assertEqual('Comedy',rows[0]['genre'])
        self.assertIn('Sydney',source_label(city))
        state=default_state();state['channels']=rows
        validate_state(state)

    def test_both_caches_retained_if_one_source_fails(self):
        au='https://iptv-org.github.io/iptv/countries/au.m3u'
        comedy='https://iptv-org.github.io/iptv/categories/comedy.m3u'
        settings={'playlist_url':au,'playlist_urls':[au,comedy]}
        shared='#EXTM3U\n#EXTINF:-1,Shared Show\nhttps://example.com/shared.m3u8\n'
        old,_,_=refresh_catalogue(settings,[],lambda _:shared)
        new,success,errors=refresh_catalogue(
            settings,old,lambda url: shared if url==comedy else
            (_ for _ in ()).throw(OSError('feed unreachable')))
        self.assertEqual(1,success)
        self.assertEqual(1,len(errors))
        self.assertEqual([au,comedy],new[0]['sources'])
        self.assertEqual(1,len(new))
        # The optional UK and 24/7 US source packs expanded the explicit
        # bound from 24 to 32 while keeping the safety limit finite.
        at_limit=default_state()
        at_limit['settings']['playlist_urls']=[
            'https://example.com/'+str(i)+'.m3u' for i in range(32)]
        validate_state(at_limit)
        too_many=default_state()
        too_many['settings']['playlist_urls']=[
            'https://example.com/'+str(i)+'.m3u' for i in range(33)]
        with self.assertRaises(ValueError):
            validate_state(too_many)


if __name__ == '__main__':
    unittest.main()
