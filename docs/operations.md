# Operations

How to run, check and repair the raw layer. The design behind each step is in
[design.md](design.md).

## Commands

All commands write to a local DuckDB file (`warehouse/raw.duckdb`) unless
`WAREHOUSE=bigquery` is set, so a local experiment cannot use the BigQuery
storage quota by accident.

```bash
python -m ingest.cli head                        # newest position in the change feed
python -m ingest.cli bootstrap                   # snapshot every entity, set checkpoints
python -m ingest.cli bootstrap --entity Persoon  # one entity (repeatable)
python -m ingest.cli changes                     # read the feed from each checkpoint
python -m ingest.cli renew                       # re-create tables before the 60-day expiry
python -m ingest.cli status                      # rows, checkpoints, table age, bytes written
```

For BigQuery from a workstation:

```bash
gcloud auth application-default login
export WAREHOUSE=bigquery GCP_PROJECT=project-510017 BQ_LOCATION=EU
python -m ingest.cli status
```

## dbt

Set up a project environment once, so dbt's dependencies stay out of other
Python installations:

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; source .venv/bin/activate elsewhere
pip install -e ".[test,dbt,bigquery]"
```

On DuckDB, from the committed one-day sample (what CI runs):

```bash
export DUCKDB_PATH=warehouse/sample.duckdb
python -m ingest.cli load-sample
dbt build --project-dir dbt --profiles-dir dbt
```

On BigQuery, with all data (what the daily run does):

```bash
export DBT_TARGET=bigquery GCP_PROJECT=project-510017
dbt build --project-dir dbt --profiles-dir dbt
dbt source freshness --project-dir dbt --profiles-dir dbt   # when did the loader last run?
```

To refresh the sample from BigQuery (it scans about 0.5 GB):

```bash
python scripts/make_sample.py --day 2026-06-02
```

## Infrastructure

`terraform/` creates the `raw`, `staging` and `core` datasets, the ingest
service account and the
Workload Identity Federation provider that lets this repository's workflows
act as that account without a key. State is local, because the usual remote
backend (Cloud Storage) needs a billing account:

```bash
cd terraform
terraform init
terraform apply
```

## The daily run

The `ingest` workflow runs at 04:30 UTC: `changes`, `renew`, `dbt build` on
BigQuery, then `status` into the run summary. A failed run opens one GitHub
issue labeled `ingest-failure`; later failures stay red without opening
duplicates.

GitHub disables scheduled workflows in a public repository after 60 days
without activity, which is also when the sandbox expires raw tables. If the
schedule stops, re-enable it in the Actions tab and follow the
`RecoveryNeeded` row below.

## When something breaks

| Symptom | Cause | Fix |
| --- | --- | --- |
| `NotBootstrapped: no checkpoint for …` | The entity was never loaded, or its checkpoints table expired. | `bootstrap --entity <Name>` |
| `RecoveryNeeded: … is gone but its checkpoint exists` | The raw table expired (the run stopped for more than 60 days) while the checkpoint survived. | `bootstrap --entity <Name> --force`. The source is the system of record, so a fresh snapshot restores the table. |
| `BudgetExceeded` | The storage ledger reached `STORAGE_LIMIT_BYTES` (8 GiB by default) of the sandbox's 10 GiB lifetime quota. | Stop scheduled runs. Check `storage_ledger` for the step that wrote most. Raising the limit uses the last 2 GiB of headroom. |
| `gave up after 6 retries (HTTP 429)` | The Tweede Kamer API throttled this IP address. | Rerun later; the checkpoint has not moved, so nothing is lost. |
| `403 … getAccessToken denied` in the workflow | New IAM bindings take a few minutes to apply, or the provider does not match the repository name. | Wait five minutes and rerun; check `github_repository` in `terraform/variables.tf`. |
| dbt warns `assert_votes_recorded_for_active_parties` or `assert_member_votes_with_a_seat` | Known source problems, see [data-quality.md](data-quality.md). | Nothing, unless the count grows or a new party appears in the warning. |
| `Billing has not been enabled … DML queries are not allowed` | Code tried `INSERT`, `UPDATE` or `MERGE`. | The sandbox refuses DML; use a load job or `CREATE OR REPLACE TABLE … AS SELECT`. |

## Checking the raw layer

Storage written so far, by step:

```sql
select step, count(*) as jobs, round(sum(bytes_written) / 1e6, 1) as mb
from raw.storage_ledger
group by step
order by mb desc;
```

Checkpoint history for one entity:

```sql
select resume_token, mode, batch_id, recorded_at
from raw.checkpoints
where entity = 'Stemming'
order by recorded_at desc
limit 20;
```
