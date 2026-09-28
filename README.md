# nl-parliament-warehouse

[![ci](https://github.com/kaeldrin-gh/nl-parliament-warehouse/actions/workflows/ci.yml/badge.svg)](https://github.com/kaeldrin-gh/nl-parliament-warehouse/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A warehouse of Dutch House of Representatives (Tweede Kamer) votes and
decisions, kept current from the parliament's own change feed and modeled in
dbt on BigQuery.

**Status:** in development. Milestones M1 (the raw layer on BigQuery, kept
current from the change feed) and M2 (the dbt model) are done; the report (M3)
comes next. The design is in [docs/design.md](docs/design.md).

**Stack:** Python · BigQuery (sandbox, no billing) · dbt · DuckDB · Terraform ·
GitHub Actions

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
- **Keyless CI access.** [terraform/](terraform/) creates the datasets, a
  least-privilege service account and a Workload Identity Federation provider
  limited to this repository.
- **A dimensional model with history.** dbt turns the change log into party
  and member votes, decisions, cases, submitters and party membership over
  time, with enforced contracts and 110 checks. Every model is a view, so the
  model costs no storage.
- **The same dbt project on two engines.** CI builds it on DuckDB from one
  real voting day committed as fixtures; the daily run builds it on BigQuery
  with 1.2 million rows.
- **Source problems written up, not hidden.** A closed party record that the
  source still uses for new votes, and empty person records, are tested and
  documented in [docs/data-quality.md](docs/data-quality.md).

| Where | What |
| --- | --- |
| [ingest/loader.py](ingest/loader.py) | bootstrap, change run, renewal, storage guard |
| [tests/test_loader.py](tests/test_loader.py) | replay, crash between write and checkpoint, snapshot/feed overlap, expiry recovery, renewal, budget |
| [tests/test_records.py](tests/test_records.py) | feed and OData rows compare equal on real fixtures |
| [dbt/models/core](dbt/models/core) | dimensions, bridges and facts with contracts |
| [dbt/macros/latest_versions.sql](dbt/macros/latest_versions.sql) | the change log's "latest version" rule, with a dbt unit test |
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
