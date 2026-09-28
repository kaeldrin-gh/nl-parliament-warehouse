"""The loader's guarantees, on DuckDB with the same append-only operations as BigQuery."""

from datetime import UTC, datetime, timedelta

import pytest

from ingest.entities import BY_NAME
from ingest.loader import (
    CHECKPOINTS,
    LEDGER,
    BudgetExceeded,
    Loader,
    NotBootstrapped,
    RecoveryNeeded,
)
from ingest.sink import DuckDBSink
from ingest.syncfeed import Change, Page

STEMMING = BY_NAME["Stemming"]
FRACTIE = BY_NAME["Fractie"]
T0 = datetime(2026, 9, 28, 6, 0, tzinfo=UTC)

# Staging's "current version" rule (docs/design.md, Transformation).
CURRENT = """
    select id, soort, origin
    from raw.stemming_changes
    qualify row_number() over (
        partition by id order by source_updated desc, resume_token desc nulls last
    ) = 1
"""


def vote(id_, soort="Voor", changed="2026-09-01T10:00:00+02:00", deleted=False):
    return {
        "Id": id_,
        "Verwijderd": deleted,
        "GewijzigdOp": changed,
        "ApiGewijzigdOp": "2026-09-01T08:00:01Z",
        "Soort": soort,
        "Besluit_Id": "b1",
        "FractieGrootte": 9,
        "ActorFractie": "X",
        "Vergissing": False,
    }


def change(id_, token, soort="Voor", changed="2026-09-02T10:00:00", deleted=False):
    return Change(
        entity="stemming",
        id=id_,
        resume_token=token,
        api_updated="2026-09-02T08:00:01Z",
        source_updated=changed,
        deleted=deleted,
        fields={} if deleted else {"soort": soort, "fractieGrootte": "9", "vergissing": "false"},
        refs={} if deleted else {"besluit": ["b1"]},
    )


class FakeApi:
    def __init__(self, head=100, odata=None, feed=None):
        self._head = head
        self.odata = odata or {}
        self.feed = feed or {}

    def head(self):
        return self._head

    def odata_pages(self, entity):
        yield from self.odata.get(entity.name, [])

    def feed_page(self, after, category=None):
        later = [c for c in self.feed.get(category, []) if c.resume_token > after][:250]
        return Page(changes=later, next_token=later[-1].resume_token if later else None)


def make(api, **kwargs):
    sink = DuckDBSink(clock=lambda: T0)
    return Loader(api, sink, clock=lambda: T0, log=lambda _: None, **kwargs), sink


def current(sink):
    return {row[0]: row[1:] for row in sink.query(CURRENT)}


def test_changes_update_delete_and_add_after_the_snapshot():
    api = FakeApi(
        head=100,
        odata={"Stemming": [[vote("a"), vote("b"), vote("c")]]},
        feed={
            "Stemming": [
                change("a", 101, soort="Tegen"),
                change("b", 102, deleted=True),
                change("d", 103),
            ]
        },
    )
    loader, sink = make(api)

    loader.bootstrap([STEMMING])
    loaded = loader.run_changes([STEMMING])

    now = current(sink)
    assert loaded == {"Stemming": 3}
    assert now["a"] == ("Tegen", "feed")
    assert now["c"] == ("Voor", "snapshot")
    assert now["d"] == ("Voor", "feed")
    assert sink.query("select deleted from raw.stemming_changes where resume_token = 102") == [
        (True,)
    ]
    assert loader.checkpoints() == {"Stemming": 103}


def test_a_second_run_without_new_changes_writes_nothing():
    api = FakeApi(odata={"Stemming": [[vote("a")]]}, feed={"Stemming": [change("a", 101)]})
    loader, sink = make(api)
    loader.bootstrap([STEMMING])
    loader.run_changes([STEMMING])
    before = sink.query("select count(*) from raw.stemming_changes")

    assert loader.run_changes([STEMMING]) == {"Stemming": 0}
    assert sink.query("select count(*) from raw.stemming_changes") == before


def test_a_crash_between_rows_and_checkpoint_rereads_without_changing_the_result():
    feed = {"Stemming": [change("a", 101, soort="Tegen"), change("d", 102)]}
    clean, clean_sink = make(FakeApi(odata={"Stemming": [[vote("a")]]}, feed=feed))
    clean.bootstrap([STEMMING])
    clean.run_changes([STEMMING])

    crashy, sink = make(FakeApi(odata={"Stemming": [[vote("a")]]}, feed=feed))
    crashy.bootstrap([STEMMING])
    real_checkpoint = crashy._checkpoint

    def crash(*args, **kwargs):
        raise ConnectionError("died after writing rows")

    crashy._checkpoint = crash
    with pytest.raises(ConnectionError):
        crashy.run_changes([STEMMING])
    crashy._checkpoint = real_checkpoint
    crashy.run_changes([STEMMING])

    assert sink.query("select count(*) from raw.stemming_changes where origin = 'feed'") == [(4,)]
    assert current(sink) == current(clean_sink)
    assert crashy.checkpoints() == {"Stemming": 102}


def test_a_change_seen_by_both_snapshot_and_feed_resolves_to_the_feed_row():
    # The change landed after the head was taken but before OData was read.
    same_version = "2026-09-02T10:00:00"
    api = FakeApi(
        head=100,
        odata={"Stemming": [[vote("a", soort="Tegen", changed=f"{same_version}+02:00")]]},
        feed={"Stemming": [change("a", 101, soort="Tegen", changed=same_version)]},
    )
    loader, sink = make(api)

    loader.bootstrap([STEMMING])
    loader.run_changes([STEMMING])

    assert current(sink)["a"] == ("Tegen", "feed")


def test_changes_refuse_to_run_before_bootstrap():
    loader, _ = make(FakeApi())

    with pytest.raises(NotBootstrapped):
        loader.run_changes([STEMMING])


def test_bootstrap_does_not_reload_silently():
    loader, _ = make(FakeApi(odata={"Stemming": [[vote("a")]]}))
    loader.bootstrap([STEMMING])

    with pytest.raises(RuntimeError, match="already bootstrapped"):
        loader.bootstrap([STEMMING])


def test_an_expired_table_with_a_live_checkpoint_stops_the_run_until_it_is_rebuilt():
    api = FakeApi(odata={"Stemming": [[vote("a")]]}, feed={"Stemming": [change("d", 101)]})
    loader, sink = make(api)
    loader.bootstrap([STEMMING])
    sink.drop("stemming_changes")

    with pytest.raises(RecoveryNeeded, match="bootstrap --entity Stemming --force"):
        loader.run_changes([STEMMING])

    api._head = 101
    loader.bootstrap([STEMMING], force=True)
    loader.run_changes([STEMMING])
    assert set(current(sink)) == {"a"}
    assert loader.checkpoints() == {"Stemming": 101}


def test_renewal_waits_until_a_table_nears_expiry_then_renews_all_together():
    api = FakeApi(odata={"Stemming": [[vote("a")]], "Fractie": [[{"Id": "f1"}]]})
    loader, sink = make(api)
    loader.bootstrap([STEMMING, FRACTIE])

    assert loader.renew() == []

    sink.age("fractie_changes", T0 - timedelta(days=50))
    for table in ("stemming_changes", CHECKPOINTS, LEDGER):
        sink.age(table, T0 - timedelta(days=10))
    renewed = loader.renew()

    assert renewed == sorted(["fractie_changes", "stemming_changes", CHECKPOINTS, LEDGER])
    assert sink.query("select count(*) from raw.stemming_changes") == [(1,)]
    renew_rows = sink.query(f"select count(*) from raw.{LEDGER} where step = 'renew'")
    assert renew_rows == [(4,)]


def test_the_storage_guard_stops_writes_at_the_limit():
    api = FakeApi(odata={"Stemming": [[vote("a")]]}, feed={"Stemming": [change("d", 101)]})
    loader, sink = make(api, limit_bytes=10**9)
    loader.bootstrap([STEMMING])
    loader.limit = loader.written_bytes()

    with pytest.raises(BudgetExceeded):
        loader.run_changes([STEMMING])
    assert sink.query("select count(*) from raw.stemming_changes") == [(1,)]
    assert loader.checkpoints() == {"Stemming": 100}


def test_long_runs_checkpoint_after_every_batch():
    feed = {"Stemming": [change(f"v{i}", 101 + i) for i in range(600)]}
    loader, sink = make(FakeApi(odata={"Stemming": [[vote("a")]]}, feed=feed), pages_per_batch=1)
    loader.bootstrap([STEMMING])

    loader.run_changes([STEMMING])

    tokens = [
        row[0]
        for row in sink.query(
            "select resume_token from raw.checkpoints where mode = 'feed' order by resume_token"
        )
    ]
    assert tokens == [350, 600, 700]
