"""Extract one real voting day from BigQuery raw into JSONL fixtures for CI.

CI builds the dbt project on DuckDB from these files, so pull requests are
tested without cloud credentials. The slice keeps every raw version of every
row it selects, and every row those rows reference, so relationships hold.

    WAREHOUSE is not used here; this reads BigQuery directly:
    python scripts/make_sample.py --day 2026-06-02
"""

import argparse
import json
from pathlib import Path

from google.cloud import bigquery

from ingest.entities import ENTITIES

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample"

# For each raw table, the ids to keep, as SQL over the selected day's decisions.
SELECTIONS = {
    "activiteit_changes": "select id from {raw}.activiteit_changes "
    "where date(datum, 'Europe/Amsterdam') = @day",
    "agendapunt_changes": "select id from {raw}.agendapunt_changes "
    "where activiteit_id in (select id from activiteit)",
    "besluit_changes": "select id from {raw}.besluit_changes "
    "where agendapunt_id in (select id from agendapunt)",
    "stemming_changes": "select id from {raw}.stemming_changes "
    "where besluit_id in (select id from besluit)",
    "zaak_changes": "select z as id from {raw}.besluit_changes, unnest(zaak_ids) z "
    "where id in (select id from besluit)",
    "zaak_actor_changes": "select id from {raw}.zaak_actor_changes "
    "where zaak_id in (select id from zaak)",
    "fractie_changes": "select id from {raw}.fractie_changes",
    "fractie_zetel_changes": "select id from {raw}.fractie_zetel_changes",
    "fractie_zetel_persoon_changes": "select id from {raw}.fractie_zetel_persoon_changes "
    "where van >= '2021-01-01' or tot_en_met is null or tot_en_met >= '2021-01-01'",
    "persoon_changes": "select persoon_id from {raw}.fractie_zetel_persoon_changes "
    "where id in (select id from fractie_zetel_persoon) "
    "union distinct select persoon_id from {raw}.stemming_changes "
    "where id in (select id from stemming) and persoon_id is not null "
    "union distinct select persoon_id from {raw}.zaak_actor_changes "
    "where id in (select id from zaak_actor) and persoon_id is not null",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="project-510017")
    parser.add_argument("--day", default="2026-06-02")
    args = parser.parse_args()

    client = bigquery.Client(project=args.project, location="EU")
    raw = f"`{args.project}.raw`"
    ctes = []
    for table, sql in SELECTIONS.items():
        ctes.append(f"{table.removesuffix('_changes')} as ({sql.format(raw=raw)})")
    with_clause = "with " + ",\n".join(ctes)
    params = [bigquery.ScalarQueryParameter("day", "DATE", args.day)]

    OUT.mkdir(parents=True, exist_ok=True)
    scanned = 0
    for entity in ENTITIES:
        name = entity.table.removesuffix("_changes")
        job = client.query(
            f"{with_clause}\nselect * from {raw}.{entity.table} "
            f"where id in (select * from {name}) order by id, source_updated",
            job_config=bigquery.QueryJobConfig(query_parameters=params),
        )
        rows = [dict(row) for row in job.result()]
        scanned += job.total_bytes_processed or 0
        with (OUT / f"{entity.table}.jsonl").open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")
        print(f"{entity.table}: {len(rows):,} rows")
    print(f"{scanned / 1e6:.0f} MB scanned")


if __name__ == "__main__":
    main()
