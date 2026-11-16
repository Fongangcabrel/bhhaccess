"""When an authorisation is usable: validity dates and weekly time slots (SRS FR-43, PRD F11).

Pure functions, no database. Times are compared in the site's local time (Africa/Douala):
a slot "07:00-18:00" means 07:00 at the gate, whatever the phone's settings.

* No slot at all: the zone is open 24 h / 24 (the default, as before).
* A slot whose end is before its start crosses midnight (night shift 22:00-06:00): it starts
  on the ticked day and ends the next morning.
* A slot whose start equals its end covers the whole day.
* Exits are never checked: a person still inside after the slot can always leave.
"""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

DAY_SHORT = {1: "lun", 2: "mar", 3: "mer", 4: "jeu", 5: "ven", 6: "sam", 7: "dim"}


class WindowRefusal(StrEnum):
    """Internal reason written in the journal; the agent sees ``AGENT_MESSAGE``."""

    NOT_YET = "acces_pas_encore_valable"
    EXPIRED = "acces_expire"
    OUTSIDE_HOURS = "hors_horaire"


AGENT_MESSAGE = {
    WindowRefusal.NOT_YET: "Accès pas encore valable",
    WindowRefusal.EXPIRED: "Accès à cette zone expiré",
    WindowRefusal.OUTSIDE_HOURS: "Hors des horaires autorisés",
}


@dataclass(frozen=True)
class Slot:
    weekdays: tuple[int, ...]  # 1 = Monday ... 7 = Sunday (ISO)
    start: time
    end: time

    def contains(self, local: datetime) -> bool:
        day, clock = local.isoweekday(), local.time().replace(tzinfo=None)
        if self.start == self.end:  # whole day
            return day in self.weekdays
        if self.start < self.end:
            return day in self.weekdays and self.start <= clock < self.end
        # Crosses midnight: evening part on the ticked day, morning part on the next day.
        yesterday = (local - timedelta(days=1)).isoweekday()
        return (day in self.weekdays and clock >= self.start) or (yesterday in self.weekdays and clock < self.end)


def check(now: datetime, tz: ZoneInfo, valid_from: datetime | None, valid_until: datetime | None,
          slots: Iterable[Slot]) -> WindowRefusal | None:
    """None when the authorisation is usable at ``now`` (an aware datetime)."""
    if valid_from is not None and now < valid_from:
        return WindowRefusal.NOT_YET
    if valid_until is not None and now >= valid_until:
        return WindowRefusal.EXPIRED
    slots = list(slots)
    if slots and not any(slot.contains(now.astimezone(tz)) for slot in slots):
        return WindowRefusal.OUTSIDE_HOURS
    return None


def describe_days(weekdays: Iterable[int]) -> str:
    """(1, 2, 3, 4, 5) -> "lun–ven"; (1, 3, 5) -> "lun, mer, ven"; all -> "tous les jours"."""
    days = sorted(set(weekdays))
    if days == list(range(1, 8)):
        return "tous les jours"
    if len(days) >= 3 and days == list(range(days[0], days[-1] + 1)):
        return f"{DAY_SHORT[days[0]]}–{DAY_SHORT[days[-1]]}"
    return ", ".join(DAY_SHORT[d] for d in days)


def describe_slot(slot: Slot) -> str:
    hours = "toute la journée" if slot.start == slot.end else f"{slot.start:%H:%M}–{slot.end:%H:%M}"
    return f"{describe_days(slot.weekdays)} {hours}"


def describe(valid_from: datetime | None, valid_until: datetime | None, slots: Iterable[Slot], tz: ZoneInfo) -> str:
    """Short summary for the console and the agent: « du 15/11 au 30/11 · lun–ven 07:00–18:00 »."""
    parts = []
    if valid_from and valid_until:
        parts.append(f"du {valid_from.astimezone(tz):%d/%m/%Y} au {valid_until.astimezone(tz):%d/%m/%Y}")
    elif valid_from:
        parts.append(f"à partir du {valid_from.astimezone(tz):%d/%m/%Y}")
    elif valid_until:
        parts.append(f"jusqu'au {valid_until.astimezone(tz):%d/%m/%Y}")
    parts += [describe_slot(s) for s in slots]
    return " · ".join(parts)
