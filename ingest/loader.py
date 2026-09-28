"""Bootstrap, daily change run and renewal of the raw layer.

Write order is the whole correctness argument (docs/design.md, Ingestion):
rows first, then the checkpoint. A crash between the two re-reads the batch on
the next run; the duplicate rows share `(id, source_updated)` and staging keeps
one. Nothing is ever updated or deleted in place.
"""

import os
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from ingest.entities import METADATA, Column, Entity
from ingest.records import from_feed, from_odata
from ingest.sink import Sink

CHECKPOINTS = "checkpoints"
LEDGER = "storage_ledger"
CHECKPOINT_COLUMNS = (
    Column("entity", "STRING", ""),
    Column("resume_token", "INT64", ""),
    Column("mode", "STRING", ""),
    Column("batch_id", "STRING", ""),
    Column("recorded_at", "TIMESTAMP", ""),
)
LEDGER_COLUMNS = (
    Column("recorded_at", "TIMESTAMP", ""),
    Column("step", "STRING", ""),
    Column("table_name", "STRING", ""),
    Column("bytes_written", "INT64", ""),
)
GIB = 1024**3
DEFAULT_LIMIT = 8 * GIB
FEED_PAGE_SIZE = 250


class NotBootstrapped(RuntimeError):
    pass


class RecoveryNeeded(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


class Loader:
    def __init__(
        self,
        api,
        sink: Sink,
        *,
        limit_bytes: int | None = None,
        pages_per_batch: int = 20,
        clock: Callable[[], datetime] = _now,
        log: Callable[[str], None] = print,
    ):
        self.api = api
        self.sink = sink
        self.limit = limit_bytes or int(os.getenv("STORAGE_LIMIT_BYTES", DEFAULT_LIMIT))
        self.pages_per_batch = pages_per_batch
        self.clock = clock
        self.log = log

    # -- bookkeeping -------------------------------------------------------------

    def _ensure_system_tables(self) -> None:
        self.sink.create_table(CHECKPOINTS, CHECKPOINT_COLUMNS)
        self.sink.create_table(LEDGER, LEDGER_COLUMNS)

    def written_bytes(self) -> int:
        if not self.sink.table_exists(LEDGER):
            return 0
        (total,) = self.sink.query(
            f"select coalesce(sum(bytes_written), 0) from {self.sink.ref(LEDGER)}"
        )[0]
        return int(total)

    def _guard(self) -> None:
        used = self.written_bytes()
        if used >= self.limit:
            raise BudgetExceeded(
                f"{used:,} bytes written so far, limit {self.limit:,}: refusing to write more"
            )

    def _record(self, step: str, table: str, written: int) -> None:
        row = {
            "recorded_at": _stamp(self.clock()),
            "step": step,
            "table_name": table,
            "bytes_written": written,
        }
        self.sink.append(LEDGER, LEDGER_COLUMNS, [row])

    def checkpoints(self) -> dict[str, int]:
        if not self.sink.table_exists(CHECKPOINTS):
            return {}
        rows = self.sink.query(
            f"select entity, max(resume_token) from {self.sink.ref(CHECKPOINTS)} group by entity"
        )
        return {entity: int(token) for entity, token in rows}

    def _checkpoint(self, entity: Entity, token: int, mode: str, batch_id: str) -> None:
        row = {
            "entity": entity.name,
            "resume_token": token,
            "mode": mode,
            "batch_id": batch_id,
            "recorded_at": _stamp(self.clock()),
        }
        self.sink.append(CHECKPOINTS, CHECKPOINT_COLUMNS, [row])

    def _write(self, step: str, entity: Entity, rows: list[dict]) -> None:
        self._guard()
        written = self.sink.append(entity.table, METADATA + entity.columns, rows)
        self._record(step, entity.table, written)

    def _batch_id(self, mode: str, entity: Entity, n: int) -> str:
        return f"{mode}-{entity.name}-{self.run_stamp}-{n}"

    def _start_run(self) -> None:
        self.run_stamp = f"{self.clock():%Y%m%dT%H%M%S}"

    # -- bootstrap ---------------------------------------------------------------

    def bootstrap(self, entities: Sequence[Entity], *, force: bool = False) -> int:
        """Snapshot through OData, then set each checkpoint to the head taken before it."""
        self._start_run()
        self._ensure_system_tables()
        existing = self.checkpoints()
        already = [e.name for e in entities if e.name in existing]
        if already and not force:
            raise RuntimeError(
                f"already bootstrapped: {', '.join(already)}. Use --force to reload them."
            )
        head = self.api.head()
        self.log(f"feed head {head:,}; snapshot starts")
        for entity in entities:
            self.sink.create_table(entity.table, METADATA + entity.columns)
            rows: list[dict] = []
            total = batches = 0
            for page in self.api.odata_pages(entity):
                loaded_at = _stamp(self.clock())
                batch = self._batch_id("snapshot", entity, batches)
                rows.extend(from_odata(entity, item, batch, loaded_at) for item in page)
                if len(rows) >= self.pages_per_batch * FEED_PAGE_SIZE:
                    self._write("snapshot", entity, rows)
                    total, rows, batches = total + len(rows), [], batches + 1
            if rows:
                self._write("snapshot", entity, rows)
                total += len(rows)
            self._checkpoint(entity, head, "bootstrap", self._batch_id("snapshot", entity, 0))
            self.log(f"{entity.name}: {total:,} rows, checkpoint {head:,}")
        return head

    # -- daily change run --------------------------------------------------------

    def _preflight(self, entities: Sequence[Entity]) -> dict[str, int]:
        checkpoints = self.checkpoints()
        missing = [e.name for e in entities if e.name not in checkpoints]
        if missing:
            raise NotBootstrapped(f"no checkpoint for {', '.join(missing)}: run bootstrap first")
        for entity in entities:
            if not self.sink.table_exists(entity.table):
                raise RecoveryNeeded(
                    f"{entity.table} is gone but its checkpoint exists (expired?): "
                    f"run `bootstrap --entity {entity.name} --force`"
                )
        return checkpoints

    def run_changes(self, entities: Sequence[Entity]) -> dict[str, int]:
        """Read each entity's feed from its checkpoint to the end. Returns rows per entity."""
        self._start_run()
        self._ensure_system_tables()
        checkpoints = self._preflight(entities)
        loaded = {}
        for entity in entities:
            token = checkpoints[entity.name]
            rows: list[dict] = []
            total = pages = batches = 0
            while True:
                page = self.api.feed_page(token, entity.name)
                loaded_at = _stamp(self.clock())
                batch = self._batch_id("feed", entity, batches)
                for change in page.changes:
                    if change.entity.lower() != entity.name.lower():
                        raise ValueError(f"{entity.name} feed returned a {change.entity}")
                    rows.append(from_feed(entity, change, batch, loaded_at))
                if page.changes:
                    token = page.changes[-1].resume_token
                    pages += 1
                last = len(page.changes) < FEED_PAGE_SIZE
                if rows and (last or pages % self.pages_per_batch == 0):
                    self._write("feed", entity, rows)
                    self._checkpoint(entity, token, "feed", batch)
                    total, rows, batches = total + len(rows), [], batches + 1
                if last:
                    break
            if total == 0:
                # A heartbeat: without it, a quiet day (recess, weekend) and a
                # stopped pipeline look the same to the freshness check.
                self._checkpoint(entity, token, "idle", self._batch_id("feed", entity, 0))
            loaded[entity.name] = total
            self.log(f"{entity.name}: {total:,} changes, checkpoint {token:,}")
        return loaded

    # -- renewal -----------------------------------------------------------------

    def renew(self, *, max_age: timedelta = timedelta(days=45)) -> list[str]:
        """Re-create every raw table together once any of them nears the 60-day expiry.

        Renewing all tables at once keeps data and checkpoints the same age, so
        they cannot expire separately and leave a checkpoint pointing past data
        that is gone.
        """
        tables = self.sink.tables()
        now = self.clock()
        oldest = min(tables.values(), default=now)
        if now - oldest < max_age:
            self.log(f"renewal not needed: oldest table is {(now - oldest).days} days old")
            return []
        self._guard()
        renewed = []
        for table in sorted(tables):
            written = self.sink.recreate(table)
            renewed.append(table)
            if table != LEDGER:
                self._record("renew", table, written)
        self._record("renew", LEDGER, 0)
        self.log(f"renewed {len(renewed)} tables")
        return renewed

    # -- status ------------------------------------------------------------------

    def status(self, entities: Sequence[Entity]) -> list[dict]:
        checkpoints = self.checkpoints()
        tables = self.sink.tables()
        now = self.clock()
        report = []
        for entity in entities:
            exists = self.sink.table_exists(entity.table)
            rows = (
                self.sink.query(f"select count(*) from {self.sink.ref(entity.table)}")[0][0]
                if exists
                else None
            )
            created = tables.get(entity.table)
            report.append(
                {
                    "entity": entity.name,
                    "rows": rows,
                    "checkpoint": checkpoints.get(entity.name),
                    "age_days": (now - created).days if created else None,
                }
            )
        return report
