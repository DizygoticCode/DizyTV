"""Deterministic subtitle-delay tests: no network, Vosk runtime, or TV required."""
import unittest

from dizytv.caption_sync import CaptionDelayQueue
from dizytv.core import default_state, export_backup, restore_backup, validate_state


class CaptionSyncTests(unittest.TestCase):
    def test_zero_delay_is_immediate_and_positive_delay_holds_captions(self):
        q=CaptionDelayQueue()
        q.push('Cartman starts talking',1000)
        self.assertEqual('Cartman starts talking',q.pop_due(1000,0))
        q.push('Another line',1200)
        self.assertIsNone(q.pop_due(1699,500))
        self.assertEqual('Another line',q.pop_due(1700,500))
        self.assertIsNone(q.pop_due(2700,500))

    def test_coalesces_many_partial_updates_to_latest_due_text(self):
        q=CaptionDelayQueue()
        for i in range(30):
            q.push('partial '+str(i),1000+i*100)
        self.assertEqual('partial 10',q.pop_due(2250,250))
        self.assertEqual('partial 29',q.pop_due(10000,250))
        self.assertEqual(0,len(q))

    def test_reducing_delay_releases_waiting_text_without_changing_video(self):
        q=CaptionDelayQueue()
        q.push('early captions need delaying',1000)
        self.assertIsNone(q.pop_due(1400,1000))
        self.assertEqual('early captions need delaying',q.pop_due(1400,250))
        q.push('old programme',2000)
        q.clear()
        self.assertIsNone(q.pop_due(15000,0))

    def test_queue_stays_bounded_for_slow_streams(self):
        q=CaptionDelayQueue()
        for i in range(1000):
            q.push('phrase '+str(i),i)
        self.assertEqual(CaptionDelayQueue.MAX_PENDING,len(q))
        self.assertEqual('phrase 999',q.pop_due(30000,10000))

    def test_invalid_values_and_empty_updates_are_safe(self):
        q=CaptionDelayQueue()
        q.push('',100)
        self.assertEqual(0,len(q))
        q.push('ok',100)
        for invalid in (-1,10001,True,False,1.5,'100'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    q.pop_due(20000,invalid)
        self.assertEqual('ok',q.pop_due(100,0))

    def test_caption_delay_setting_validates_and_survives_backup(self):
        state=default_state()
        self.assertEqual(0,state['settings']['auto_caption_delay_ms'])
        for amount in (0,250,5000,10000):
            state['settings']['auto_caption_delay_ms']=amount
            validate_state(state)
            self.assertEqual(amount,restore_backup(export_backup(state))['settings']['auto_caption_delay_ms'])
        for bad in (-1,10001,True,0.1,'200'):
            with self.subTest(bad=bad):
                state['settings']['auto_caption_delay_ms']=bad
                with self.assertRaises(ValueError):
                    validate_state(state)
        state['settings'].pop('auto_caption_delay_ms')
        validate_state(state)  # Old releases don't have this setting yet.


if __name__ == '__main__':
    unittest.main()
