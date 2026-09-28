"""Build the static report (site/index.html) from the dbt marts.

Reads the marts from DuckDB (CI, the one-day sample) or BigQuery (the daily
run), embeds the numbers as JSON, and renders them with Observable Plot in the
browser. Every chart has a table with the same numbers, so nothing depends on
the CDN or on hovering.

    python -m report.build --out site
"""

import argparse
import html
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

from report.charts import SCRIPT

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/kaeldrin-gh/nl-parliament-warehouse"
MIN_SHARED = 20  # agreement cells with fewer shared votes stay blank
TERM_LABELS = {2021: "2021 term", 2023: "2023 term", 2025: "2025 term"}
# First month of each term after the first, for the monthly chart's markers.
TERM_STARTS = [("2023-12-01", "2023 term"), ("2025-11-01", "2025 term")]
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


class Marts:
    """Runs the report's queries against DuckDB or BigQuery."""

    def __init__(self):
        if os.getenv("WAREHOUSE", "duckdb") == "bigquery":
            from google.cloud import bigquery

            project = os.environ["GCP_PROJECT"]
            self.client = bigquery.Client(project=project, location=os.getenv("BQ_LOCATION", "EU"))
            self.prefix = f"`{project}.marts`."
            self.run = lambda sql: [dict(r) for r in self.client.query(sql).result()]
        else:
            import duckdb

            conn = duckdb.connect(
                os.getenv("DUCKDB_PATH", str(ROOT / "warehouse" / "raw.duckdb")), read_only=True
            )
            self.prefix = "marts."

            def run(sql):
                cursor = conn.execute(sql)
                names = [d[0] for d in cursor.description]
                return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

            self.run = run

    def query(self, sql: str) -> list[dict]:
        return self.run(sql.replace("marts.", self.prefix))


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _month_label(value: date) -> str:
    return f"{MONTHS[value.month - 1]} {value.year}"


def fetch(marts: Marts) -> dict:
    overview = marts.query("select * from marts.mart_overview")[0]
    participation = marts.query(
        """
        select term_id, party, sum(decisions) as decisions, sum(took_part) as took_part,
               sum(not_voted) as not_voted, sum(declared_mistakes) as declared_mistakes,
               max(month_start) as last_month
        from marts.mart_party_participation
        group by term_id, party
        """
    )
    seats = marts.query(
        """
        select p.term_id, p.party, p.seats
        from marts.mart_party_participation as p
        inner join (
            select term_id, party, max(month_start) as last_month
            from marts.mart_party_participation group by term_id, party
        ) as last using (term_id, party)
        where p.month_start = last.last_month
        """
    )
    agreement = marts.query(
        """
        select term_id, party_a, party_b, sum(decisions_both_voted) as both_voted,
               sum(decisions_same_vote) as same_vote
        from marts.mart_party_agreement
        group by term_id, party_a, party_b
        """
    )
    monthly = marts.query(
        """
        select month_start, sum(accepted) as accepted, sum(rejected) as rejected
        from marts.mart_outcomes_monthly
        where case_type = 'motion'
        group by month_start
        order by month_start
        """
    )
    submitters = marts.query(
        """
        select term_id, submitter_party, sum(accepted) as accepted, sum(rejected) as rejected
        from marts.mart_outcomes_by_submitter
        where case_type = 'motion'
        group by term_id, submitter_party
        """
    )
    return shape(overview, participation, seats, agreement, monthly, submitters)


def shape(overview, participation, seats, agreement, monthly, submitters) -> dict:
    """Turn mart rows into the report payload. Pure, so it is tested without a warehouse."""
    seat_of = {(r["term_id"], r["party"]): int(r["seats"] or 0) for r in seats}
    terms = []
    for term_id in sorted({r["term_id"] for r in participation if r["term_id"]}, reverse=True):
        rows = [r for r in participation if r["term_id"] == term_id]
        rows.sort(key=lambda r: (-seat_of.get((term_id, r["party"]), 0), r["party"]))
        parties = [r["party"] for r in rows]
        cells = []
        for r in agreement:
            if r["term_id"] != term_id:
                continue
            both, same = int(r["both_voted"]), int(r["same_vote"])
            share = _share(same, both) if both >= MIN_SHARED else None
            for a, b in ((r["party_a"], r["party_b"]), (r["party_b"], r["party_a"])):
                cells.append({"a": a, "b": b, "share": share, "both": both, "same": same})
        took = [
            {
                "party": r["party"],
                "seats": seat_of.get((term_id, r["party"]), 0),
                "decisions": int(r["decisions"]),
                "took_part": int(r["took_part"]),
                "share": _share(int(r["took_part"]), int(r["decisions"])),
            }
            for r in rows
        ]
        motions = {
            r["submitter_party"]: (int(r["accepted"]), int(r["rejected"]))
            for r in submitters
            if r["term_id"] == term_id
        }
        by_party = [
            {"party": p, "accepted": motions[p][0], "rejected": motions[p][1]}
            for p in parties
            if p in motions and sum(motions[p]) > 0
        ]
        terms.append(
            {
                "term_id": term_id,
                "label": TERM_LABELS.get(term_id, f"{term_id} term"),
                "parties": parties,
                "cells": cells,
                "participation": took,
                "motions_by_party": by_party,
            }
        )
    months = [
        {
            "month": str(r["month_start"]),
            "label": _month_label(r["month_start"]),
            "accepted": int(r["accepted"]),
            "rejected": int(r["rejected"]),
        }
        for r in monthly
    ]
    return {
        "overview": {k: (str(v) if isinstance(v, date) else v) for k, v in overview.items()},
        "terms": terms,
        "months": months,
        "term_starts": [{"month": m, "label": label} for m, label in TERM_STARTS],
        "min_shared": MIN_SHARED,
    }


def _json_script(payload: dict) -> str:
    # "</" would end the <script> element early; the JSON is identical once parsed.
    return json.dumps(payload, separators=(",", ":"), default=str).replace("</", "<\\/")


def _table(headers: list[str], rows: list[list]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>" for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value * 100:.0f}%"


def _long_date(value: str) -> str:
    d = date.fromisoformat(value)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def render(payload: dict, built_at: datetime | None = None) -> str:
    built_at = built_at or datetime.now(UTC)
    o = payload["overview"]
    current = payload["terms"][0] if payload["terms"] else None
    tiles = [
        (f"{o['decisions_voted']:,}", "decisions put to a party vote"),
        (f"{o['party_votes']:,}", "party votes"),
        (f"{o['roll_call_decisions']:,}", f"roll calls ({o['member_votes']:,} member votes)"),
        (_long_date(o["last_vote_on"]), f"latest vote (since {_long_date(o['first_vote_on'])})"),
    ]
    cards = "".join(
        f"<div class='card'><div class='num'>{v}</div><div class='lbl'>{html.escape(k)}</div></div>"
        for v, k in tiles
    )
    buttons = "".join(
        f"<button type='button' data-term='{t['term_id']}' aria-pressed="
        f"'{'true' if i == 0 else 'false'}'>{html.escape(t['label'])}</button>"
        for i, t in enumerate(payload["terms"])
    )
    agreement_rows = []
    participation_rows = []
    motion_rows = []
    if current:
        seen = set()
        for c in sorted(current["cells"], key=lambda c: (c["a"], c["b"])):
            key = tuple(sorted((c["a"], c["b"])))
            if key in seen:
                continue
            seen.add(key)
            agreement_rows.append([key[0], key[1], f"{c['both']:,}", _pct(c["share"])])
        participation_rows = [
            [p["party"], p["seats"], f"{p['decisions']:,}", _pct(p["share"])]
            for p in current["participation"]
        ]
        motion_rows = [
            [
                m["party"],
                f"{m['accepted']:,}",
                f"{m['rejected']:,}",
                _pct(m["accepted"] / (m["accepted"] + m["rejected"])),
            ]
            for m in current["motions_by_party"]
        ]
    month_rows = [
        [m["label"], f"{m['accepted']:,}", f"{m['rejected']:,}"] for m in payload["months"]
    ]
    term_label = html.escape(current["label"]) if current else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dutch parliament votes</title>
<meta name="description" content="How parties in the Dutch House of Representatives vote, from the Tweede Kamer's own open data.">
<style>{PAGE_STYLE}</style>
</head>
<body>
<header>
  <h1>Dutch parliament votes</h1>
  <p class="sub">Votes in the Tweede Kamer (House of Representatives) since the House
  elected in March 2021 took office, from the parliament's open data (CC0). Rebuilt
  daily from the <a href="{REPO}">nl-parliament-warehouse</a> marts; built
  {built_at:%d %b %Y %H:%M} UTC, newest source change {_long_date(o["latest_source_change_on"])}.</p>
</header>
<div class="cards">{cards}</div>

<h2>How often parties vote the same way</h2>
<p class="sub">Share of decisions on which both parties voted for or against and voted
the same way. Parties are ordered by seats at the end of the term (or today). Cells
with fewer than {payload["min_shared"]} shared votes are blank.</p>
<div class="terms" role="group" aria-label="Term">{buttons}</div>
<div class="chart">
  <div class="legend"><span class="key">30%<span class="swatch ramp"></span>100%</span>
  <span class="key">share of shared votes cast the same way</span></div>
  <div id="chart-agreement" class="plot" role="img"
       aria-label="Matrix of how often each pair of parties voted the same way"></div>
</div>
<details><summary>Table: agreement per pair, {term_label}</summary>
{_table(["Party", "Party", "Both voted", "Same vote"], agreement_rows)}</details>

<h2>Motions: accepted and rejected each month</h2>
<p class="sub">Votes on motions (moties) by month. Vertical lines mark the start of
each term.</p>
<div class="chart">
  <div class="legend">
    <span class="key"><span class="swatch" style="background:var(--series-1)"></span>accepted</span>
    <span class="key"><span class="swatch" style="background:var(--series-2)"></span>rejected</span>
  </div>
  <div id="chart-monthly" class="plot" role="img" aria-label="Motions accepted and rejected per month"></div>
</div>
<details><summary>Table: motions per month</summary>
{_table(["Month", "Accepted", "Rejected"], month_rows)}</details>

<h2>How often each party takes part in votes</h2>
<p class="sub">Share of party votes recorded as for or against, rather than as not
taking part (niet deelgenomen). The axis starts at the lowest share, not at zero.</p>
<div class="chart">
  <div id="chart-participation" class="plot" role="img" aria-label="Participation per party"></div>
</div>
<details><summary>Table: participation, {term_label}</summary>
{_table(["Party", "Seats", "Decisions", "Took part"], participation_rows)}</details>

<h2>Motions by submitting party</h2>
<p class="sub">Votes on motions whose first submitter (indiener) belongs to the party;
the label is the share accepted. A motion submitted by members of two parties counts
for both.</p>
<div class="chart">
  <div class="legend">
    <span class="key"><span class="swatch" style="background:var(--series-1)"></span>accepted</span>
    <span class="key"><span class="swatch" style="background:var(--series-2)"></span>rejected</span>
  </div>
  <div id="chart-submitters" class="plot" role="img" aria-label="Motions by submitting party"></div>
</div>
<details><summary>Table: motions by submitting party, {term_label}</summary>
{_table(["Party", "Accepted", "Rejected", "Accepted share"], motion_rows)}</details>

<h2>About the data</h2>
<ul class="notes">
  <li>A <b>party vote</b> is one party's vote on one decision; a <b>roll call</b>
  (hoofdelijke stemming) records every member's vote.</li>
  <li>Parties are counted by abbreviation. 50PLUS has two records in the source, and
  every 50PLUS vote since November 2025 is recorded under the older one; both are counted
  as 50PLUS. A party that changed its name appears under each name.</li>
  <li>These are counts from the source, not judgements: agreement says nothing about
  why parties voted as they did.</li>
  <li>How the data is loaded, modeled and tested:
  <a href="{REPO}#readme">README</a> ·
  <a href="{REPO}/blob/main/docs/design.md">design</a> ·
  <a href="{REPO}/blob/main/docs/data-quality.md">data quality</a> ·
  <a href="docs/">dbt docs</a></li>
</ul>
<noscript><p>The charts need JavaScript; every number is in the tables above.</p></noscript>
<script id="report-data" type="application/json">{_json_script(payload)}</script>
<script type="module">{SCRIPT}</script>
</body>
</html>
"""


PAGE_STYLE = """
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --border: rgba(11, 11, 11, 0.10);
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #898781;
  --grid: #e1e0d9; --baseline: #c3c2b7;
  --series-1: #2a78d6; --series-2: #eb6834;
  --ramp-lo: #e6eef8; --ramp-mid: #6ba3e6; --ramp-hi: #173f73;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --border: rgba(255, 255, 255, 0.10);
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #898781;
    --grid: #2c2c2a; --baseline: #383835;
    --series-1: #3987e5; --series-2: #d95926;
    --ramp-lo: #1b2533; --ramp-mid: #3987e5; --ramp-hi: #d6e7fb;
  }
}
* { box-sizing: border-box; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; max-width: 1100px;
       margin: 0 auto; padding: 2rem 16px 3rem; background: var(--page);
       color: var(--text-primary); line-height: 1.45; }
h1 { font-size: 1.6rem; margin: 0; }
h2 { font-size: 1.1rem; margin-top: 2.6rem; padding-bottom: 6px;
     border-bottom: 1px solid var(--grid); }
.sub { color: var(--text-secondary); font-size: 0.9rem; margin: 0.35rem 0 0.8rem; }
a { color: var(--series-1); }
table { border-collapse: collapse; margin-top: 8px; font-variant-numeric: tabular-nums;
        display: block; overflow-x: auto; max-width: 100%; }
td, th { border-bottom: 1px solid var(--grid); padding: 5px 12px; font-size: 0.88rem;
         text-align: right; white-space: nowrap; }
th { color: var(--text-secondary); font-weight: 600; }
th:nth-child(1), td:nth-child(1), th:nth-child(2), td:nth-child(2) { text-align: left; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
         gap: 12px; margin-top: 16px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
        padding: 12px 16px; }
.num { font-size: 1.4rem; font-weight: 600; }
.lbl { color: var(--text-secondary); font-size: 0.82rem; margin-top: 2px; }
.chart { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
         padding: 14px 16px 8px; margin: 14px 0 0; }
.plot { width: 100%; min-height: 60px; }
#chart-agreement { overflow-x: auto; }
.legend { display: flex; gap: 18px; flex-wrap: wrap; margin: 0 0 6px;
          color: var(--text-secondary); font-size: 0.85rem; }
.key { display: inline-flex; align-items: center; gap: 6px; }
.swatch { display: inline-block; width: 14px; height: 12px; border-radius: 2px; }
.ramp { width: 72px;
        background: linear-gradient(90deg, var(--ramp-lo), var(--ramp-mid), var(--ramp-hi)); }
.terms { display: flex; gap: 8px; flex-wrap: wrap; }
.terms button { font: inherit; font-size: 0.85rem; padding: 4px 12px; border-radius: 999px;
                border: 1px solid var(--border); background: var(--surface);
                color: var(--text-secondary); cursor: pointer; }
.terms button[aria-pressed="true"] { border-color: var(--series-1); color: var(--text-primary);
                                     box-shadow: inset 0 0 0 1px var(--series-1); }
details { margin-top: 8px; color: var(--text-secondary); font-size: 0.88rem; }
.notes { color: var(--text-secondary); font-size: 0.9rem; padding-left: 1.2rem; }
.notes li { margin: 0.35rem 0; }
noscript p { color: var(--text-secondary); }
"""


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python -m report.build")
    parser.add_argument("--out", default="site", help="output directory")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = fetch(Marts())
    (out / "index.html").write_text(render(payload), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(payload, default=str, indent=1), encoding="utf-8")
    print(
        f"wrote {out / 'index.html'}: {len(payload['terms'])} terms, {len(payload['months'])} months"
    )


if __name__ == "__main__":
    main()
