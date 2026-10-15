"""Bounded monotonic scheduling for locally generated Vosk captions.

DizyTV's Vosk recogniser listens to a separate FFmpeg connection. The arrival
time of partial/final recognition text is not a presentation timestamp for the
video. This queue allows viewers to *delay* captions, never to claim we can
predict words or infer a shared live clock from independent stream requests.
"""
from collections import deque


class CaptionDelayQueue:
    """Latest-due-text scheduler; partial updates never pile up indefinitely."""

    MAX_PENDING = 256

    def __init__(self):
        self._pending = deque(maxlen=self.MAX_PENDING)

    def clear(self):
        self._pending.clear()

    def push(self, text, arrival_ms):
        if not isinstance(text, str) or not text:
            return
        self._pending.append((int(arrival_ms), text))

    def pop_due(self, now_ms, delay_ms=0):
        if type(delay_ms) is not int or not 0 <= delay_ms <= 10000:
            raise ValueError('Caption delay must be between 0 and 10,000 ms')
        # Display only the latest text that is due: repeated Vosk partials
        # shouldn't leave older, out-of-date captions on screen.
        latest = None
        while self._pending and self._pending[0][0] + delay_ms <= now_ms:
            latest = self._pending.popleft()[1]
        return latest

    def __len__(self):
        return len(self._pending)
