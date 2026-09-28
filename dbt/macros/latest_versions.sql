{#
  The newest version of each entity from an append-only change log, without
  deleted entities. The version key is the source's own change time; on a tie,
  a feed row (with a resume token) beats a snapshot row, and a later load
  beats an earlier replay of the same batch. See docs/design.md, Ingestion.
#}
{% macro latest_versions(table) %}
    select *
    from (
        select
            *,
            row_number() over (
                partition by id
                order by source_updated desc, resume_token desc nulls last, loaded_at desc
            ) as version_rank
        from {{ source('raw', table) }}
    ) as versions
    where version_rank = 1 and not deleted
{% endmacro %}
