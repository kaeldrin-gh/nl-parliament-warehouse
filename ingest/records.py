"""Turn feed changes and OData rows into landing rows of one shape.

The two APIs describe the same entity differently: the feed uses camelCase
elements, local times without an offset and repeated `ref` elements; OData
uses PascalCase properties, times with an offset and expanded navigation
lists. Both end up here as the same row, so a snapshot row and a feed row for
the same version compare equal apart from their load metadata.
"""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from ingest.entities import METADATA, Column, Entity
from ingest.syncfeed import Change

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
_FRACTION = re.compile(r"(\.\d{1,6})\d*")


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def timestamp(value: str | None) -> str | None:
    """ISO 8601 in UTC. A value without an offset is Amsterdam local time."""
    if value is None:
        return None
    text = _FRACTION.sub(r"\1", value.replace("Z", "+00:00"))
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=AMSTERDAM)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _convert(column: Column, value):
    if value is None:
        return None
    if column.type == "TIMESTAMP":
        return timestamp(value)
    if column.type == "INT64":
        return int(value)
    if column.type == "BOOL":
        return value if isinstance(value, bool) else value == "true"
    return str(value)


def _row(entity: Entity, values: dict, meta: dict) -> dict:
    row = dict(meta)
    for column in entity.columns:
        row[column.name] = values.get(column.name)
    return row


def from_feed(entity: Entity, change: Change, batch_id: str, loaded_at: str) -> dict:
    fields = {_key(k): v for k, v in change.fields.items()}
    refs = {_key(k): v for k, v in change.refs.items()}
    values = {}
    for column in entity.columns:
        if column.repeated:
            values[column.name] = sorted(refs.get(_key(column.source), []))
        elif column.source.endswith("_Id"):
            linked = refs.get(_key(column.source.removesuffix("_Id")), [])
            if len(linked) > 1:
                raise ValueError(f"{entity.name} {change.id}: {len(linked)} links in {column.name}")
            values[column.name] = linked[0] if linked else None
        else:
            values[column.name] = _convert(column, fields.get(_key(column.source)))
    meta = {
        "id": change.id,
        "deleted": change.deleted,
        "source_updated": timestamp(change.source_updated),
        "api_updated": timestamp(change.api_updated),
        "resume_token": change.resume_token,
        "origin": "feed",
        "batch_id": batch_id,
        "loaded_at": loaded_at,
    }
    return _row(entity, values, meta)


def from_odata(entity: Entity, item: dict, batch_id: str, loaded_at: str) -> dict:
    values = {}
    for column in entity.columns:
        if column.repeated:
            values[column.name] = sorted(link["Id"] for link in item.get(column.source) or [])
        else:
            values[column.name] = _convert(column, item.get(column.source))
    meta = {
        "id": item["Id"],
        "deleted": bool(item.get("Verwijderd")),
        "source_updated": timestamp(item.get("GewijzigdOp")),
        "api_updated": timestamp(item.get("ApiGewijzigdOp")),
        "resume_token": None,
        "origin": "snapshot",
        "batch_id": batch_id,
        "loaded_at": loaded_at,
    }
    return _row(entity, values, meta)


def odata_query(entity: Entity) -> dict[str, str]:
    """Query options that request only the allowlisted columns."""
    scalar = [c.source for c in METADATA if c.source] + [
        c.source for c in entity.columns if not c.repeated
    ]
    query = {"$select": ",".join(scalar)}
    links = [c.source for c in entity.columns if c.repeated]
    if links:
        query["$expand"] = ",".join(f"{link}($select=Id)" for link in links)
    if entity.scope:
        query["$filter"] = entity.scope
    return query
