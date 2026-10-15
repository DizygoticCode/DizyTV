"""Local, token-free last health-check snapshots for manual channel comparison.

Never store stream URLs, query tokens, names, IP addresses, HTTP headers or
diagnostic details. No automatic hiding is based on this single latest result.
This separate cache is NOT included in DizyTV's portable backup.
"""
from __future__ import annotations

import json
import time
from .storage import atomic_json, file_lock

KNOWN_STATUSES=frozenset((
    'missing','access-limited','rate-limited','provider-error','rejected',
    'not-a-stream','manifest-only','playlist-only','data-response','unverified',
    'unreachable','skipped','engine-required',
))
MAX_CACHE_BYTES=8*1024*1024
MAX_ITEMS=50000
MAX_AGE_SECONDS=90*24*3600


class HealthHistory:
    def __init__(self,store):
        self.store=store
        self.path=store.directory/'health-results.json'
        self.lock=store.directory/'health-results.lock'

    def _read(self):
        try:
            if not self.path.exists() or self.path.stat().st_size>MAX_CACHE_BYTES:
                return {}
            obj=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(obj,dict):return {}
            now=int(time.time())
            valid={}
            for cid,row in obj.items():
                if (isinstance(cid,str) and 1<=len(cid)<=128
                    and isinstance(row,dict)
                    and row.get('status') in KNOWN_STATUSES
                    and type(row.get('checked')) is int
                    and 0<=now-row['checked']<=MAX_AGE_SECONDS):
                    valid[cid]={'status':row['status'],'checked':row['checked']}
            return valid
        except (OSError,ValueError,TypeError):
            return {}

    def read(self):
        with file_lock(self.lock):
            return self._read()

    def record(self,entries):
        """Update only completed checks. URL-bearing fields are discarded."""
        with file_lock(self.lock):
            rows=self._read()
            checked=int(time.time())
            for entry in entries:
                cid=entry.get('id')
                status=entry.get('status')
                if (isinstance(cid,str) and 1<=len(cid)<=128
                    and status in KNOWN_STATUSES):
                    rows[cid]={'status':status,'checked':checked}
            if len(rows)>MAX_ITEMS:
                newest=sorted(rows.items(),key=lambda kv:kv[1]['checked'],reverse=True)
                rows=dict(newest[:MAX_ITEMS])
            atomic_json(self.path,rows,max_bytes=MAX_CACHE_BYTES)
        return rows
