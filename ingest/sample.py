"""Load the committed one-day sample (tests/fixtures/sample) into a DuckDB raw schema."""

import json
from pathlib import Path

from ingest.entities import ENTITIES, METADATA
from ingest.sink import DuckDBSink

SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample"


def load_sample(sink: DuckDBSink, path: Path = SAMPLE) -> dict[str, int]:
    loaded = {}
    for entity in ENTITIES:
        columns = METADATA + entity.columns
        sink.create_table(entity.table, columns)
        lines = (path / f"{entity.table}.jsonl").read_text(encoding="utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line]
        sink.append(entity.table, columns, rows)
        loaded[entity.table] = len(rows)
    return loaded
