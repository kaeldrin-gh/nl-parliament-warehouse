# nl-parliament-warehouse

[![ci](https://github.com/kaeldrin-gh/nl-parliament-warehouse/actions/workflows/ci.yml/badge.svg)](https://github.com/kaeldrin-gh/nl-parliament-warehouse/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A warehouse of Dutch House of Representatives (Tweede Kamer) votes and
decisions, kept current from the parliament's own change feed and modeled in
dbt on BigQuery.

**Status:** in development. Milestone M1 is done: the raw layer loads into
BigQuery and stays current from the change feed. dbt models (M2) and the
report (M3) come next. The design is in [docs/design.md](docs/design.md).

**Stack:** Python · BigQuery (sandbox, no billing) · Terraform · GitHub Actions
· dbt (M2)

## What is here so far

- **Change capture from a public source.** The Tweede Kamer SyncFeed is read
  from a stored checkpoint; updates arrive as whole entities and deletions as
  tombstones. A one-off OData snapshot bootstraps each entity from a feed
  position taken before the snapshot, so nothing between the two is lost.
- **An append-only raw layer on BigQuery's sandbox.** The sandbox refuses
  `INSERT`, `UPDATE` and `MERGE`, expires tables after 60 days and grants
  10 GiB of lifetime storage. The loader writes with load jobs only, renews
  tables before they expire, and stops at 8 GiB of logged writes.
- **Personal data never leaves the source.** Each entity is an allowlist in
  [ingest/entities.py](ingest/entities.py); OData requests select only those
  columns, and tests fail if a private field appears.
- **Keyless CI access.** [terraform/](terraform/) creates the dataset, a
  least-privilege service account and a Workload Identity Federation provider
  limited to this repository.

| Where | What |
| --- | --- |
| [ingest/loader.py](ingest/loader.py) | bootstrap, change run, renewal, storage guard |
| [tests/test_loader.py](tests/test_loader.py) | replay, crash between write and checkpoint, snapshot/feed overlap, expiry recovery, renewal, budget |
| [tests/test_records.py](tests/test_records.py) | feed and OData rows compare equal on real fixtures |
| [docs/operations.md](docs/operations.md) | commands and what to do when something breaks |

## Run the tests

```bash
pip install -e ".[test]"
python -m pytest -q
ruff check . && ruff format --check .
```

## License

MIT, see [LICENSE](LICENSE). Data from the Tweede Kamer der Staten-Generaal, published
under [CC0 1.0](https://opendata.tweedekamer.nl/disclaimer).
