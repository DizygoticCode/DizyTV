"""Deterministic Matchday parser, safety, cache and source validation."""
from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from dizytv.matchday import (LEAGUES, add_source, cached_fixtures,
                             collect_fixtures, is_favourite, load_sources,
                             parse_fixtures, safe_public_url, validate_source)
from dizytv.matchday_web import _private_host


def event(event_id='1234', league='4329', home='Southampton', away='QPR',
          kickoff='2026-10-31T15:00:00'):
    return {'idEvent': event_id, 'idLeague': league, 'strHomeTeam': home,
            'strAwayTeam': away, 'strTimestamp': kickoff, 'strSport': 'Soccer'}


class MatchdayTests(unittest.TestCase):
    def test_all_nine_target_competitions_have_fixed_ids(self):
        self.assertEqual(9, len(LEAGUES))
        self.assertEqual(9, len(set(i for i, _ in LEAGUES)))

    def test_parser_ignores_other_leagues_and_unknown_times(self):
        rows = {'events': [event(), event('2', '4328'),
                           event('3', kickoff=''), event('4', home='')]}
        parsed = parse_fixtures(rows, '4329')
        self.assertEqual(['1234'], [x['id'] for x in parsed])
        self.assertEqual(1793458800, parsed[0]['kickoff'])
        self.assertTrue(is_favourite(parsed[0]))
        self.assertFalse(is_favourite(parsed[0], 'Chelsea'))

    def test_provider_request_bounded_and_no_fake_playback(self):
        calls = []
        def fetch(endpoint, params):
            calls.append((endpoint, dict(params)))
            if endpoint == 'eventsnextleague.php' and params['id'] == '4329':
                return {'events': [event()]}
            return {'events': []}
        fixtures, errors = collect_fixtures(date(2026, 10, 31), fetch)
        self.assertEqual([], errors)
        self.assertEqual(11, len(calls))
        self.assertEqual(1, len(fixtures))
        self.assertNotIn('url', fixtures[0])
        self.assertNotIn('verified', fixtures[0])

    def test_partial_failures_still_preserve_valid_fixtures(self):
        def fetch(endpoint, params):
            if params.get('id') == '4328':
                raise OSError('private error with source credentials')
            return {'events': [event()] if params.get('id') == '4329' else []}
        fixtures, errors = collect_fixtures(date(2026, 10, 31), fetch)
        self.assertEqual(1, len(fixtures))
        self.assertEqual(['Premier League: OSError'], errors)

    def test_cache_reuses_and_refreshes_without_wiping_on_failure(self):
        successful = lambda _endpoint, params: {'events': [event()] if params.get('id') == '4329' else []}
        def failed(_endpoint, _params):
            raise OSError('offline')
        with TemporaryDirectory() as folder:
            first, errors, stale = cached_fixtures(folder, fetch=successful, now=1000)
            self.assertEqual(1, len(first))
            self.assertFalse(stale)
            again, errors, cached = cached_fixtures(folder, fetch=failed, now=1010)
            self.assertEqual(first, again)
            self.assertTrue(cached)
            old, errors, stale = cached_fixtures(folder, fetch=failed, now=5000)
            self.assertEqual(first, old)
            self.assertTrue(stale)

    def test_refresh_cooldown_counts_failed_attempts_too(self):
        calls = []
        def failed(_endpoint, _params):
            calls.append(1)
            raise OSError('offline')
        with TemporaryDirectory() as folder:
            first, errors, stale = cached_fixtures(folder, fetch=failed, now=1000)
            self.assertEqual([], first)
            self.assertEqual(11, len(calls))
            again, errors, cached = cached_fixtures(folder, fetch=failed, now=1010, refresh=True)
            self.assertEqual([], again)
            self.assertEqual(11, len(calls))
            self.assertIn('Refresh cooldown active', errors)
            refreshed, errors, cached = cached_fixtures(folder, fetch=failed, now=1121, refresh=True)
            self.assertEqual([], refreshed)
            self.assertEqual(22, len(calls))

    def test_source_rejects_credentials_private_hosts_and_unconfirmed_rights(self):
        bad = ['http://example.com/a.m3u8', 'https://127.0.0.1/a.m3u8',
               'https://localhost/a.m3u8', 'https://user:pass@example.com/a',
               'https://example.com/a?token=xyz', 'https://example.com/a#frag',
               'https://private.local/a', 'https://example.com:444/a',
               'https://127.1/live.m3u8', 'https://0177.0.0.1/live.m3u8',
               'https://0x7f.0.0.1/live.m3u8',
               'https://%31%32%37.0.0.1/watch', 'https://127%2e0%2e0%2e1/watch',
               'https://%6cocalhost/watch',
               'https://１２７.０.０.１/watch',
               'https://１２７.0.0.1/watch',
               'https://ｅｘａｍｐｌｅ.org/watch']
        for url in bad:
            with self.subTest(url=url), self.assertRaises(ValueError):
                safe_public_url(url)
        self.assertEqual('https://example.org/café',
                         safe_public_url('https://example.org/café'))
        self.assertTrue(_private_host('１２７.０.０.１'))
        self.assertTrue(_private_host('%31%32%37.0.0.1'))
        self.assertFalse(_private_host('cdn.example.org'))
        sample = {'event_id':'1234', 'label':'Authorised viewing page',
                  'url':'https://example.org/watch', 'kind':'web'}
        with self.assertRaisesRegex(ValueError, 'permission'):
            validate_source(sample)
        sample['permission_confirmed'] = True
        result = validate_source(sample)
        self.assertFalse(result['verified'])
        with TemporaryDirectory() as folder:
            rows = add_source(folder, sample)
            self.assertEqual(rows, add_source(folder, sample))
            self.assertEqual(1, len(load_sources(folder)))
            self.assertFalse((Path(folder)/'state.json').exists())

    def test_direct_source_requires_hls_media_url(self):
        link = {'event_id':'1234', 'label':'Direct HLS', 'permission_confirmed':True,
                'kind':'hls', 'url':'https://video.example.org/index.html'}
        with self.assertRaisesRegex(ValueError, 'm3u8'):
            validate_source(link)
        link['url'] = 'https://video.example.org/live.m3u8'
        self.assertEqual('hls', validate_source(link)['kind'])


if __name__ == '__main__':
    unittest.main()
