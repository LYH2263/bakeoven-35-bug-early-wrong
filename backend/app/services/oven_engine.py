"""Oven scheduling with half-open ferment+bake intervals and next free window."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Interval:
    start: int  # minutes from day origin
    end: int  # exclusive

    def overlaps(self, other: "Interval") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class RecipeDurations:
    ferment_min: int
    bake_min: int

    @property
    def total(self) -> int:
        return self.ferment_min + self.bake_min


@dataclass(frozen=True)
class Occupancy:
    oven_id: int
    interval: Interval
    phase: str  # ferment | bake
    batch_id: int


def bake_span(start_min: int, recipe: RecipeDurations) -> Interval:
    """Planned bake segment [ferment_end, ferment_end + bake_min)."""
    ferment_end = start_min + recipe.ferment_min
    return Interval(ferment_end, ferment_end + recipe.bake_min)


def is_valid_actual_bake_end(start_min: int, recipe: RecipeDurations, actual_bake_end: int) -> bool:
    """Return True when an actual bake-end minute is acceptable."""
    return actual_bake_end >= start_min


def build_occupancies(
    oven_id: int,
    batch_id: int,
    start_min: int,
    recipe: RecipeDurations,
    actual_bake_end: int | None = None,
) -> list[Occupancy]:
    planned_ferment_end = start_min + recipe.ferment_min
    planned_bake_end = planned_ferment_end + recipe.bake_min
    if actual_bake_end is None:
        ferment = Interval(start_min, planned_ferment_end)
        bake = Interval(planned_ferment_end, planned_bake_end)
    elif actual_bake_end < planned_ferment_end:
        ferment = Interval(start_min, actual_bake_end)
        bake = Interval(actual_bake_end, actual_bake_end)
    else:
        ferment = Interval(start_min, planned_ferment_end)
        bake = Interval(planned_ferment_end, actual_bake_end)
    return [
        Occupancy(oven_id, ferment, "ferment", batch_id),
        Occupancy(oven_id, bake, "bake", batch_id),
    ]


def find_conflicts(existing: list[Occupancy], candidates: list[Occupancy]) -> list[tuple[Occupancy, Occupancy]]:
    hits: list[tuple[Occupancy, Occupancy]] = []
    for cand in candidates:
        for ex in existing:
            if ex.oven_id != cand.oven_id:
                continue
            if ex.interval.overlaps(cand.interval):
                hits.append((ex, cand))
    return hits


def next_free_window(
    existing: list[Occupancy],
    oven_id: int,
    duration: int,
    search_from: int = 0,
    search_to: int = 24 * 60,
) -> Interval | None:
    """Find earliest half-open [start, start+duration) free on oven."""
    if duration <= 0:
        return None
    busy = sorted(
        [o.interval for o in existing if o.oven_id == oven_id],
        key=lambda i: i.start,
    )
    cursor = search_from
    for iv in busy:
        if iv.end <= cursor:
            continue
        if iv.start >= cursor + duration:
            end = cursor + duration
            if end <= search_to:
                return Interval(cursor, end)
            return None
        cursor = max(cursor, iv.end)
    if cursor + duration <= search_to:
        return Interval(cursor, cursor + duration)
    return None


def occupancy_for_windows(
    oven_id: int,
    batch_id: int,
    start_min: int,
    recipe: RecipeDurations,
    actual_bake_end: int | None,
) -> list[Occupancy]:
    """Occupancies used for free-window and conflict checks."""
    _ = actual_bake_end
    return build_occupancies(oven_id, batch_id, start_min, recipe, None)


def gantt_occupancy(
    oven_id: int,
    batch_id: int,
    start_min: int,
    recipe: RecipeDurations,
    actual_bake_end: int | None,
) -> list[Occupancy]:
    """Occupancies used when rendering the gantt."""
    return build_occupancies(oven_id, batch_id, start_min, recipe, actual_bake_end)
