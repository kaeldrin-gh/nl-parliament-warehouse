"""Command line: python -m ingest.cli {head,bootstrap,changes,renew,status}.

The warehouse defaults to a local DuckDB file, so nothing reaches BigQuery (and
its storage quota) unless WAREHOUSE=bigquery is set explicitly.
"""

import argparse
import os
import sys
from pathlib import Path

from ingest.entities import BY_NAME, ENTITIES
from ingest.loader import Loader
from ingest.sink import BigQuerySink, DuckDBSink
from ingest.source import TkApi

ROOT = Path(__file__).resolve().parent.parent


def _sink():
    if os.getenv("WAREHOUSE", "duckdb") == "bigquery":
        return BigQuerySink(
            project=os.environ["GCP_PROJECT"],
            dataset=os.getenv("BQ_RAW_DATASET", "raw"),
            location=os.getenv("BQ_LOCATION", "EU"),
        )
    path = Path(os.getenv("DUCKDB_PATH", ROOT / "warehouse" / "raw.duckdb"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return DuckDBSink(str(path))


def _entities(names):
    if not names:
        return ENTITIES
    unknown = [n for n in names if n not in BY_NAME]
    if unknown:
        sys.exit(f"unknown entity: {', '.join(unknown)} (choose from {', '.join(BY_NAME)})")
    return tuple(BY_NAME[n] for n in names)


def _markdown(report: list[dict], written: int) -> str:
    lines = [
        "| Entity | Raw rows | Checkpoint | Table age (days) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for r in report:
        rows = f"{r['rows']:,}" if r["rows"] is not None else "missing"
        token = f"{r['checkpoint']:,}" if r["checkpoint"] is not None else "none"
        age = r["age_days"] if r["age_days"] is not None else "-"
        lines.append(f"| {r['entity']} | {rows} | {token} | {age} |")
    lines.append("")
    lines.append(f"Bytes written to the warehouse so far: {written:,}")
    return "\n".join(lines)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m ingest.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("head", help="print the newest feed position")
    for name, text in [
        ("bootstrap", "snapshot entities through OData and set their checkpoints"),
        ("changes", "read the change feed from each checkpoint"),
        ("status", "row counts, checkpoints and storage used"),
    ]:
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("--entity", action="append", help="limit to one entity (repeatable)")
        if name == "bootstrap":
            cmd.add_argument("--force", action="store_true", help="reload bootstrapped entities")
    sub.add_parser("renew", help="re-create raw tables before the 60-day expiry")
    args = parser.parse_args(argv)

    api = TkApi()
    if args.command == "head":
        print(api.head())
        return
    loader = Loader(api, _sink())
    if args.command == "bootstrap":
        loader.bootstrap(_entities(args.entity), force=args.force)
    elif args.command == "changes":
        loader.run_changes(_entities(args.entity))
    elif args.command == "renew":
        loader.renew()
    elif args.command == "status":
        print(_markdown(loader.status(_entities(args.entity)), loader.written_bytes()))


if __name__ == "__main__":
    main()
