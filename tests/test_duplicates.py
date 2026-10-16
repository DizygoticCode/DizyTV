import json
import tempfile
import time
import unittest
from pathlib import Path
from dizytv.duplicates import duplicate_groups
from dizytv.health_history import HealthHistory
from dizytv.storage import Store


def ch(cid,name,country='United Kingdom',kind='TV'):
    return {'id':cid,'name':name,'country':country,'kind':kind,
            'group':'Entertainment','tvg_id':name,'stream':'https://example.com/'+cid}


class DuplicateTests(unittest.TestCase):
    def test_same_name_same_country_and_kind_are_only_candidates(self):
        channels=[
            ch('a','E4'),ch('b','E4 HD'),ch('c','E4 +1'),
            ch('d','E4','United States'),ch('e','E4',kind='Radio'),
            ch('f','BBC One South'),ch('g','BBC One North'),
            ch('h','Os Simpsons'),ch('i','Os Simpsons'),
            ch('j','日本テレビ'),ch('k','日本テレビ'),
        ]
        groups=duplicate_groups(channels)
        self.assertEqual(3,len(groups))
        keys=[{row['id'] for row in group} for _,group in groups]
        self.assertIn({'a','b'},keys)
        self.assertIn({'h','i'},keys)
        self.assertIn({'j','k'},keys)
        self.assertNotIn('c',set().union(*keys))
        self.assertNotIn('d',set().union(*keys))
        self.assertNotIn('e',set().union(*keys))

    def test_last_http_results_persist_only_safe_status_and_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp)
            history=HealthHistory(store)
            self.assertEqual({},history.read())
            history.record([
                {'id':'a'*40,'status':'missing','name':'Private provider',
                 'stream':'https://example.com/live?token=secret',
                 'detail':'https://example.com/live?token=secret'},
                {'id':'b'*40,'status':'manifest-only','detail':'token=other'},
                {'id':'c'*40,'status':'not-a-status','detail':'discard'},
            ])
            again=HealthHistory(store).read()
            self.assertEqual('missing',again['a'*40]['status'])
            self.assertEqual('manifest-only',again['b'*40]['status'])
            self.assertNotIn('c'*40,again)
            data=Path(tmp,'health-results.json').read_text(encoding='utf-8')
            self.assertNotIn('secret',data)
            self.assertNotIn('Private provider',data)
            self.assertNotIn('https:',data)
            self.assertNotIn('token=',data)
            # History lives outside state and exported JSON backup.
            self.assertNotIn('health-results',Path(tmp,'state.json').read_text(encoding='utf-8') if
                             Path(tmp,'state.json').exists() else '')

    def test_stale_or_malformed_entries_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=HealthHistory(Store(tmp))
            Path(tmp,'health-results.json').write_text(json.dumps({
                'old':{'status':'missing','checked':int(time.time())-100*24*3600},
                'bad':{'status':'unknown','checked':int(time.time())},
                'fresh':{'status':'unreachable','checked':int(time.time())},
            }),encoding='utf-8')
            self.assertEqual(['fresh'],list(h.read()))

    def test_malformed_status_does_not_discard_other_saved_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=HealthHistory(Store(tmp))
            now=int(time.time())
            Path(tmp,'health-results.json').write_text(json.dumps({
                'fresh':{'status':'missing','checked':now},
                'malformed':{'status':['missing'],'checked':now},
            }),encoding='utf-8')
            self.assertEqual({'fresh':{'status':'missing','checked':now}},h.read())

    def test_deeply_malformed_cache_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            h=HealthHistory(Store(tmp))
            Path(tmp,'health-results.json').write_text('['*20000+']'*20000,encoding='utf-8')
            try:
                rows=h.read()
            except RecursionError:
                self.fail('A corrupt optional health cache must not prevent opening the viewer')
            self.assertEqual({},rows)


if __name__=='__main__':
    unittest.main()


class AlternativesTests(unittest.TestCase):
    def test_only_distinct_same_station_and_region_candidates(self):
        from dizytv.duplicates import independent_candidates
        selected={'id':'orig','name':'ITV2 HD','country':'United Kingdom','kind':'TV',
                  'stream':'https://example.org/one.m3u8'}
        alt={'id':'other','name':'ITV2 SD','country':'United Kingdom','kind':'TV',
             'stream':'https://example.org/two.m3u8'}
        wrong_region={'id':'foreign','name':'ITV2','country':'Ireland','kind':'TV',
                      'stream':'https://example.org/three.m3u8'}
        plus_one={'id':'plus','name':'ITV2 +1','country':'United Kingdom','kind':'TV',
                  'stream':'https://example.org/four.m3u8'}
        same_stream={'id':'duplicate','name':'ITV2','country':'United Kingdom','kind':'TV',
                     'stream':selected['stream']}
        self.assertEqual([alt],independent_candidates(
            [selected,alt,wrong_region,plus_one,same_stream],selected))
