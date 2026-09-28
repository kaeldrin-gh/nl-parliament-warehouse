"""Where raw rows are written: BigQuery in production, DuckDB for tests and local runs.

Both sinks only create tables, append rows and re-create tables. None of them
updates or deletes rows, because the BigQuery sandbox refuses DML; keeping
DuckDB to the same operations means the tests exercise the same design.
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from ingest.entities import Column


class Sink(Protocol):
    def ref(self, table: str) -> str: ...
    def table_exists(self, table: str) -> bool: ...
    def create_table(self, table: str, columns: Sequence[Column]) -> None: ...
    def append(self, table: str, columns: Sequence[Column], rows: list[dict]) -> int: ...
    def recreate(self, table: str) -> int: ...
    def tables(self) -> dict[str, datetime]: ...
    def query(self, sql: str) -> list[tuple]: ...


_DUCKDB_TYPES = {
    "STRING": "VARCHAR",
    "INT64": "BIGINT",
    "BOOL": "BOOLEAN",
    "TIMESTAMP": "TIMESTAMPTZ",
}


class DuckDBSink:
    """A local stand-in with the same operations as the sandbox."""

    def __init__(self, path: str = ":memory:", schema: str = "raw", clock=None):
        import duckdb

        self.conn = duckdb.connect(path)
        self.schema = schema
        self.clock = clock or (lambda: datetime.now(UTC))
        self.conn.execute(f"create schema if not exists {schema}")
        # DuckDB keeps no creation time, which renewal needs, so track it here.
        self.conn.execute(
            f"create table if not exists {schema}.__created (name varchar, created timestamptz)"
        )

    def ref(self, table: str) -> str:
        return f"{self.schema}.{table}"

    def table_exists(self, table: str) -> bool:
        return bool(
            self.conn.execute(
                "select count(*) from information_schema.tables "
                "where table_schema = ? and table_name = ?",
                [self.schema, table],
            ).fetchone()[0]
        )

    def create_table(self, table: str, columns: Sequence[Column]) -> None:
        if self.table_exists(table):
            return
        cols = ", ".join(
            f"{c.name} {_DUCKDB_TYPES[c.type]}{'[]' if c.repeated else ''}" for c in columns
        )
        self.conn.execute(f"create table {self.ref(table)} ({cols})")
        self._stamp(table)

    def append(self, table: str, columns: Sequence[Column], rows: list[dict]) -> int:
        if not rows:
            return 0
        names = [c.name for c in columns]
        marks = ", ".join("?" for _ in names)
        self.conn.executemany(
            f"insert into {self.ref(table)} ({', '.join(names)}) values ({marks})",
            [[row.get(n) for n in names] for row in rows],
        )
        return len(json.dumps(rows, default=str).encode())

    def recreate(self, table: str) -> int:
        # Row count stands in for bytes here; only BigQuery reports real sizes.
        ref = self.ref(table)
        size = self.conn.execute(f"select count(*) from {ref}").fetchone()[0]
        self.conn.execute(f"create or replace table {ref} as select * from {ref}")
        self._stamp(table)
        return int(size)

    def tables(self) -> dict[str, datetime]:
        rows = self.conn.execute(f"select name, created from {self.schema}.__created").fetchall()
        return {name: created for name, created in rows if self.table_exists(name)}

    def query(self, sql: str) -> list[tuple]:
        return self.conn.execute(sql).fetchall()

    def age(self, table: str, created: datetime) -> None:
        """Test helper: pretend a table was created at `created`."""
        self._stamp(table, created)

    def drop(self, table: str) -> None:
        """Test helper: simulate a table that expired."""
        self.conn.execute(f"drop table {self.ref(table)}")

    def _stamp(self, table: str, created: datetime | None = None) -> None:
        # Bookkeeping for the stand-in, not warehouse data, so replacing is fine.
        self.conn.execute(f"delete from {self.schema}.__created where name = ?", [table])
        self.conn.execute(
            f"insert into {self.schema}.__created values (?, ?)", [table, created or self.clock()]
        )


class BigQuerySink:
    """Load jobs and CREATE TABLE AS SELECT only: what the sandbox allows."""

    def __init__(self, project: str, dataset: str = "raw", location: str = "EU"):
        from google.cloud import bigquery

        self.bq = bigquery
        self.client = bigquery.Client(project=project, location=location)
        self.project = project
        self.dataset = dataset

    def ref(self, table: str) -> str:
        return f"`{self.project}.{self.dataset}.{table}`"

    def _id(self, table: str) -> str:
        return f"{self.project}.{self.dataset}.{table}"

    def _schema(self, columns: Sequence[Column]):
        return [
            self.bq.SchemaField(c.name, c.type, mode="REPEATED" if c.repeated else "NULLABLE")
            for c in columns
        ]

    def table_exists(self, table: str) -> bool:
        from google.api_core.exceptions import NotFound

        try:
            self.client.get_table(self._id(table))
            return True
        except NotFound:
            return False

    def create_table(self, table: str, columns: Sequence[Column]) -> None:
        self.client.create_table(
            self.bq.Table(self._id(table), schema=self._schema(columns)), exists_ok=True
        )

    def append(self, table: str, columns: Sequence[Column], rows: list[dict]) -> int:
        if not rows:
            return 0
        config = self.bq.LoadJobConfig(
            schema=self._schema(columns),
            source_format=self.bq.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=self.bq.WriteDisposition.WRITE_APPEND,
        )
        job = self.client.load_table_from_json(rows, self._id(table), job_config=config)
        job.result()
        return int(job.output_bytes or 0)

    def recreate(self, table: str) -> int:
        self.client.query(
            f"create or replace table {self.ref(table)} as select * from {self.ref(table)}"
        ).result()
        return int(self.client.get_table(self._id(table)).num_bytes or 0)

    def tables(self) -> dict[str, datetime]:
        return {
            t.table_id: self.client.get_table(t.reference).created
            for t in self.client.list_tables(f"{self.project}.{self.dataset}")
        }

    def query(self, sql: str) -> list[tuple]:
        return [tuple(row.values()) for row in self.client.query(sql).result()]
