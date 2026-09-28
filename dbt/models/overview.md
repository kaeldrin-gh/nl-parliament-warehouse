{% docs __overview__ %}
# nl-parliament-warehouse

Votes in the Dutch House of Representatives (Tweede Kamer) since 31 March 2021,
from the parliament's open data (CC0).

- **raw** (source): an append-only change log written by `ingest/` from the
  SyncFeed and an OData snapshot. Every row is one version of one entity;
  `deleted` marks a tombstone.
- **staging**: views with the latest version of each entity, in English.
- **core**: dimensions (`dim_party`, `dim_member`, `dim_case`, `dim_decision`,
  `dim_date`, `dim_term`), bridges (`bridge_party_membership`,
  `bridge_decision_case`, `bridge_case_submitter`) and facts (`fct_party_vote`,
  `fct_member_vote`). All views, all contract-enforced.
- **marts**: small tables of counts behind the
  [report](https://kaeldrin-gh.github.io/nl-parliament-warehouse/).

Open the lineage graph (bottom right) to follow a vote from the raw change log
to the report. Design, data-quality findings and the runbook are in the
[repository](https://github.com/kaeldrin-gh/nl-parliament-warehouse).
{% enddocs %}
