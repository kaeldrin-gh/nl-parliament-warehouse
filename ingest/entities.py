"""The entities this warehouse loads, with the only columns it may land.

Each entity is an allowlist: a column that is not listed here is never
requested from OData, never kept from the feed, and never written. This is
where the personal-data policy is enforced (see docs/design.md, Governance).
"""

from dataclasses import dataclass

SCOPE_START = "2021-03-31T00:00:00Z"
_IN_SCOPE_SITTING = f"Activiteit/Datum ge {SCOPE_START}"
_IN_SCOPE_DECISION = f"Besluit/any(b: b/Agendapunt/{_IN_SCOPE_SITTING})"


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    source: str
    repeated: bool = False


@dataclass(frozen=True)
class Entity:
    name: str
    columns: tuple[Column, ...]
    scope: str | None = None

    @property
    def table(self) -> str:
        return f"{_snake(self.name)}_changes"


def _snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _s(source: str, name: str | None = None, type: str = "STRING") -> Column:
    return Column(name=name or _snake(source).replace("__", "_"), type=type, source=source)


def _ref(source: str) -> Column:
    return Column(name=f"{_snake(source)}_id", type="STRING", source=f"{source}_Id")


def _links(source: str) -> Column:
    return Column(name=f"{_snake(source)}_ids", type="STRING", source=source, repeated=True)


# Every raw table starts with these, in this order.
METADATA = (
    Column("id", "STRING", "Id"),
    Column("deleted", "BOOL", "Verwijderd"),
    Column("source_updated", "TIMESTAMP", "GewijzigdOp"),
    Column("api_updated", "TIMESTAMP", "ApiGewijzigdOp"),
    Column("resume_token", "INT64", ""),
    Column("origin", "STRING", ""),
    Column("batch_id", "STRING", ""),
    Column("loaded_at", "TIMESTAMP", ""),
)

ENTITIES = (
    Entity(
        "Stemming",
        (
            _ref("Besluit"),
            _s("Soort"),
            _s("FractieGrootte", type="INT64"),
            _s("ActorNaam"),
            _s("ActorFractie"),
            _s("Vergissing", type="BOOL"),
            _ref("Persoon"),
            _ref("Fractie"),
        ),
        scope=f"Besluit/Agendapunt/{_IN_SCOPE_SITTING}",
    ),
    Entity(
        "Besluit",
        (
            _ref("Agendapunt"),
            _s("StemmingsSoort"),
            _s("BesluitSoort"),
            _s("BesluitTekst"),
            _s("Opmerking"),
            _s("Status"),
            _s("AgendapuntZaakBesluitVolgorde", type="INT64"),
            _links("Zaak"),
        ),
        scope=f"Agendapunt/{_IN_SCOPE_SITTING}",
    ),
    Entity(
        "Agendapunt",
        (
            _ref("Activiteit"),
            _s("Nummer"),
            _s("Onderwerp"),
            _s("Aanvangstijd", type="TIMESTAMP"),
            _s("Eindtijd", type="TIMESTAMP"),
            _s("Volgorde", type="INT64"),
            _s("Rubriek"),
            _s("Status"),
        ),
        scope=_IN_SCOPE_SITTING,
    ),
    Entity(
        "Activiteit",
        (
            _s("Soort"),
            _s("Nummer"),
            _s("Onderwerp"),
            _s("DatumSoort"),
            _s("Datum", type="TIMESTAMP"),
            _s("Aanvangstijd", type="TIMESTAMP"),
            _s("Eindtijd", type="TIMESTAMP"),
            _s("Besloten", type="BOOL"),
            _s("Status"),
            _s("Vergaderjaar"),
            _s("Kamer"),
            _s("Voortouwnaam"),
            _s("Voortouwafkorting"),
        ),
        scope=f"Datum ge {SCOPE_START}",
    ),
    Entity(
        "Zaak",
        (
            _s("Nummer"),
            _s("Soort"),
            _s("Titel"),
            _s("Citeertitel"),
            _s("Status"),
            _s("Onderwerp"),
            _s("GestartOp", type="TIMESTAMP"),
            _s("Organisatie"),
            _s("Vergaderjaar"),
            _s("Volgnummer", type="INT64"),
            _s("Afgedaan", type="BOOL"),
            _s("HuidigeBehandelstatus"),
        ),
        scope=f"GestartOp ge {SCOPE_START} or {_IN_SCOPE_DECISION}",
    ),
    Entity(
        "ZaakActor",
        (
            _ref("Zaak"),
            _s("ActorNaam"),
            _s("ActorFractie"),
            _s("ActorAfkorting"),
            _s("Functie"),
            _s("Relatie"),
            _ref("Persoon"),
            _ref("Fractie"),
            _ref("Commissie"),
        ),
        scope=f"Zaak/GestartOp ge {SCOPE_START} or Zaak/{_IN_SCOPE_DECISION}",
    ),
    # Public-role fields only: no birth, death, residence, gender, gifts,
    # travel, side jobs or contact details.
    Entity(
        "Persoon",
        (
            _s("Nummer", type="INT64"),
            _s("Initialen"),
            _s("Roepnaam"),
            _s("Tussenvoegsel"),
            _s("Achternaam"),
            _s("Functie"),
            _s("Fractielabel"),
        ),
    ),
    Entity(
        "Fractie",
        (
            _s("Nummer", type="INT64"),
            _s("Afkorting"),
            _s("NaamNL", name="naam_nl"),
            _s("NaamEN", name="naam_en"),
            _s("AantalZetels", type="INT64"),
            _s("DatumActief", type="TIMESTAMP"),
            _s("DatumInactief", type="TIMESTAMP"),
        ),
    ),
    Entity("FractieZetel", (_ref("Fractie"), _s("Gewicht", type="INT64"))),
    Entity(
        "FractieZetelPersoon",
        (
            _ref("FractieZetel"),
            _ref("Persoon"),
            _s("Functie"),
            _s("Van", type="TIMESTAMP"),
            _s("TotEnMet", type="TIMESTAMP"),
        ),
    ),
)

BY_NAME = {e.name: e for e in ENTITIES}
