# nl-parliament-warehouse

[![ci](https://github.com/kaeldrin-gh/nl-parliament-warehouse/actions/workflows/ci.yml/badge.svg)](https://github.com/kaeldrin-gh/nl-parliament-warehouse/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A warehouse of Dutch House of Representatives (Tweede Kamer) votes and
decisions, kept current from the parliament's own change feed and modeled in
dbt on BigQuery.

**Status:** in development. The design is in [docs/design.md](docs/design.md);
the feed parser and its tests are the first code.

**Stack:** Python · BigQuery (sandbox, no billing) · dbt · GitHub Actions ·
Terraform

## What is here so far

- [docs/design.md](docs/design.md): the source, the tested limits of the
  BigQuery sandbox, the change-capture design, the dimensional model, the
  personal-data policy and the milestones.
- [ingest/syncfeed.py](ingest/syncfeed.py): parses SyncFeed pages into change
  records, including deletions, with the resume token for each change.
- [tests/test_syncfeed.py](tests/test_syncfeed.py): tests against a real feed
  page.

## Run the tests

```bash
pip install -e ".[test]"
python -m pytest -q
ruff check . && ruff format --check .
```

## License

MIT, see [LICENSE](LICENSE). Data from the Tweede Kamer der Staten-Generaal, published
under [CC0 1.0](https://opendata.tweedekamer.nl/disclaimer).
