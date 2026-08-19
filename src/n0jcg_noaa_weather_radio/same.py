from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re


@dataclass
class SameFilter:
    counties: set[str] = field(default_factory=set)
    events: set[str] = field(default_factory=set)
    min_priority: str = "all"


@dataclass(frozen=True)
class SameAlert:
    originator: str
    event: str
    locations: tuple[str, ...]
    purge: str
    received_at: str
    raw: str


HEADER_RE = re.compile(r"^ZCZC-(?P<originator>[A-Z0-9]{3})-(?P<event>[A-Z0-9]{3})-(?P<locations>[A-Z0-9-]+)\+(?P<purge>\d{4})-(?P<julian>\d{7})-", re.IGNORECASE)


def parse_same_header(text: str) -> SameAlert | None:
    match = HEADER_RE.search(text.strip())
    if not match:
        return None
    return SameAlert(
        originator=match.group("originator").upper(),
        event=match.group("event").upper(),
        locations=tuple(part.upper() for part in match.group("locations").split("-")),
        purge=match.group("purge"),
        received_at=datetime.now(timezone.utc).isoformat(),
        raw=text.strip(),
    )


def alert_matches(alert: SameAlert, config: SameFilter) -> bool:
    county_ok = not config.counties or bool(set(alert.locations) & {c.upper() for c in config.counties})
    normalized_events = {e.upper() for e in config.events}
    event_ok = not normalized_events or "ALL" in normalized_events or alert.event in normalized_events
    return county_ok and event_ok
