"""Small reusable HTTP cache with bounded retries; no access-control bypass."""
import hashlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from weekly_common import dump_json, load_json


def fetch(url, cache, timeout=30, retries=2, refresh=False):
    if not url.startswith('https://'):
        raise ValueError('Only explicit HTTPS source URLs are supported')
    cache = Path(cache)
    key = hashlib.sha256(url.encode()).hexdigest()
    body, meta = cache / (key + '.body'), cache / (key + '.json')
    if not refresh and body.is_file() and meta.is_file():
        info = load_json(meta)
        payload = body.read_bytes()
        if info['url'] == url and hashlib.sha256(payload).hexdigest() == info['sha256']:
            return payload, dict(info, cache_hit=True)
    retries = min(max(int(retries), 0), 3)
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'WeeklyHighlights/1.0 (personal research; metadata and authorized full text)'})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                info = {'url': url, 'final_url': response.geturl(), 'status': response.status,
                        'content_type': response.headers.get('Content-Type'),
                        'fetched_at': datetime.now(timezone.utc).isoformat(),
                        'sha256': hashlib.sha256(payload).hexdigest()}
            cache.mkdir(parents=True, exist_ok=True)
            temp = body.with_suffix('.part')
            temp.write_bytes(payload)
            temp.replace(body)
            dump_json(meta, info, overwrite=True)
            return payload, dict(info, cache_hit=False)
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504) or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == retries:
                raise
        time.sleep(min(2 ** attempt, 4))
