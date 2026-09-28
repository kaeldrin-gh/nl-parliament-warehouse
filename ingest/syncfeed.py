"""Parse Tweede Kamer SyncFeed pages into change records.

The SyncFeed is an Atom feed of changes, 250 per page. Each entry carries the
whole entity as it is now, or a tombstone (`tk:verwijderd="true"`, no fields)
when the entity was deleted. Each entry's `next` link holds the skiptoken that
resumes the feed directly after it, which is what a checkpoint stores.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

ATOM = "{http://www.w3.org/2005/Atom}"
TK = "{http://www.tweedekamer.nl/xsd/tkData/v1-0}"
XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


@dataclass(frozen=True)
class Change:
    entity: str
    id: str
    resume_token: int
    api_updated: str
    source_updated: str | None
    deleted: bool
    fields: dict[str, str | None]
    refs: dict[str, list[str]]


@dataclass(frozen=True)
class Page:
    changes: list[Change]
    next_token: int | None


def _skiptoken(element: ET.Element) -> int | None:
    for link in element.findall(f"{ATOM}link"):
        if link.get("rel") == "next":
            values = parse_qs(urlparse(link.get("href", "")).query).get("skiptoken")
            return int(values[0]) if values else None
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _fields(body: ET.Element) -> tuple[dict[str, str | None], dict[str, list[str]]]:
    # A reference element repeats once per linked entity (a decision linked to
    # two cases has two <zaak ref="…"/>), so references are always lists.
    fields: dict[str, str | None] = {}
    refs: dict[str, list[str]] = {}
    for child in body:
        name = _local(child.tag)
        if child.get("ref") is not None:
            refs.setdefault(name, []).append(child.get("ref"))
        elif child.get(XSI_NIL) == "true":
            fields[name] = None
        else:
            fields[name] = child.text
    return fields, refs


def parse_page(xml: bytes | str) -> Page:
    root = ET.fromstring(xml)
    changes = []
    for entry in root.findall(f"{ATOM}entry"):
        body = next(iter(entry.find(f"{ATOM}content")))
        deleted = body.get(f"{TK}verwijderd") == "true"
        token = _skiptoken(entry)
        if token is None:
            raise ValueError(f"entry {body.get('id')} has no next link to resume from")
        fields, refs = ({}, {}) if deleted else _fields(body)
        changes.append(
            Change(
                entity=_local(body.tag),
                id=body.get("id"),
                resume_token=token,
                api_updated=entry.findtext(f"{ATOM}updated"),
                source_updated=body.get(f"{TK}bijgewerkt"),
                deleted=deleted,
                fields=fields,
                refs=refs,
            )
        )
    return Page(changes=changes, next_token=_skiptoken(root))
