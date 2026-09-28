"""HTTP access to the Tweede Kamer Gegevensmagazijn: SyncFeed pages and OData pages.

The API throttles per IP address, so requests go out one at a time with a
short pause, and transient failures (timeouts, 429, 5xx) back off and retry.
"""

import json
import time
from collections.abc import Iterator
from urllib.parse import urlencode

import requests

from ingest.entities import Entity
from ingest.records import odata_query
from ingest.syncfeed import Page, parse_page

BASE = "https://gegevensmagazijn.tweedekamer.nl"
FEED = f"{BASE}/SyncFeed/2.0/Feed"
ODATA = f"{BASE}/OData/v4/2.0"
RETRY_STATUS = {429, 500, 502, 503, 504}


class TkApi:
    def __init__(self, session=None, pause: float = 0.2, retries: int = 6, sleep=time.sleep):
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent", "nl-parliament-warehouse (+https://github.com/kaeldrin-gh)"
        )
        self.pause = pause
        self.retries = retries
        self.sleep = sleep
        self.requests = 0

    def get(self, url: str) -> bytes:
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, timeout=120)
                if response.status_code not in RETRY_STATUS:
                    response.raise_for_status()
                    self.requests += 1
                    self.sleep(self.pause)
                    return response.content
                reason = f"HTTP {response.status_code}"
            except (requests.ConnectionError, requests.Timeout) as exc:
                reason = type(exc).__name__
            if attempt == self.retries:
                raise RuntimeError(f"{url}: gave up after {self.retries} retries ({reason})")
            self.sleep(min(2**attempt, 60))
        raise AssertionError("unreachable")

    def feed_page(self, after: int | None, category: str | None = None) -> Page:
        params = {}
        if after is not None:
            params["skiptoken"] = after
        if category:
            params["category"] = category
        return parse_page(self.get(f"{FEED}?{urlencode(params)}"))

    def head(self) -> int:
        """The position of the newest change: the smallest skiptoken with nothing after it.

        Found by bisection on the unfiltered feed, about 25 to 50 requests.
        """
        low, high = 0, 1 << 20
        while self.feed_page(high).changes:
            low, high = high, high * 2
        while high - low > 1:
            middle = (low + high) // 2
            if self.feed_page(middle).changes:
                low = middle
            else:
                high = middle
        return high

    def odata_pages(self, entity: Entity) -> Iterator[list[dict]]:
        url = f"{ODATA}/{entity.name}?{urlencode(odata_query(entity))}"
        while url:
            body = json.loads(self.get(url))
            yield body["value"]
            url = body.get("@odata.nextLink")
