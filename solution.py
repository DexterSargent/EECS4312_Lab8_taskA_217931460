## Student Name: Dexter Sargent
## Student ID: 217931460

"""
Task A: Appointment Timeslot Recommender (Stub)

In this lab, you will design and implement an Appointment Slot Recommender using an LLM assistant
as your primary programming collaborator.

You are asked to implement a Python module that recommends available meeting slots within a
defined working window.

The system must:
  • Accept working hours (start and end time).
  • Accept a list of existing busy intervals.
  • Accept a required meeting duration.
  • Accept an optional buffer time between meetings.
  • Optionally restrict suggestions to a candidate time window.
  • Return chronologically ordered appointment slots that satisfy all constraints.

The system must ensure that:
  • Suggested slots fall within working hours.
  • Suggested slots do not overlap busy intervals.
  • Buffer time is respected when evaluating availability.
  • Output ordering is deterministic under identical inputs.

The module must preserve the following invariants:
  • Returned slots must be at least as long as the required duration.
  • No returned slot may violate buffer constraints.
  • The returned list must reflect the current system state.

The system must correctly handle non-trivial scenarios such as:
  • Adjacent busy intervals.
  • Very small gaps between meetings.
  • Buffers eliminating otherwise valid availability.
  • Overlapping or unsorted busy intervals.
  • A meeting duration longer than any available gap.
  • No availability within the working window.

Output:
  The output consists of the next N valid appointment suggestions in chronological order.
  Behavior must be deterministic under ties (if any).

See the lab handout for full requirements.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from typing import List, Optional, Tuple


# ---------------- Data Models ----------------

@dataclass(frozen=True)
class TimeWindow:
    """
    A daily time window.
    Assumption (unless stated otherwise in handout): non-wrapping window where start < end.
    """
    start: time
    end: time


@dataclass(frozen=True)
class BusyInterval:
    """
    A busy interval on the given day.
    Invariant: start < end
    """
    start: time
    end: time


@dataclass(frozen=True)
class Slot:
    """
    A recommended appointment slot.

    start_time is a time-of-day within the working window.
    Deterministic ordering: sort by start_time ascending.
    """
    start_time: time


class InfeasibleSchedule(Exception):
    """Raised when no valid slots can be produced (if required by handout)."""
    pass


# ---------------- Helper Functions ----------------

def _to_datetime(day: date, t: time) -> datetime:
    return datetime.combine(day, t)


def _merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    """Merge overlapping or adjacent intervals."""
    if not intervals:
        return []

    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]

    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]

        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def _clip_interval(start: datetime, end: datetime, low: datetime, high: datetime):
    """Clip interval to bounds."""
    start = max(start, low)
    end = min(end, high)

    if start >= end:
        return None

    return (start, end)


# ---------------- Core Function ----------------

def suggest_slots(
    day: date,
    working_hours: TimeWindow,
    busy_intervals: List[BusyInterval],
    duration: timedelta,
    n: int,
    buffer: timedelta = timedelta(0),
    candidate_window: Optional[TimeWindow] = None
) -> List[Slot]:
    """
    Suggest up to the next n valid appointment slots (start times) for the given day.
    """

    # ---------------- Validation ----------------

    if duration <= timedelta(0):
        raise ValueError("duration must be positive")

    if buffer < timedelta(0):
        raise ValueError("buffer must be non-negative")

    if n < 0:
        raise ValueError("n must be >= 0")

    if working_hours.start >= working_hours.end:
        raise ValueError("working_hours must satisfy start < end")

    if n == 0:
        return []

    working_start = _to_datetime(day, working_hours.start)
    working_end = _to_datetime(day, working_hours.end)

    if duration > (working_end - working_start):
        return []

    # candidate window validation
    if candidate_window is not None:
        if candidate_window.start >= candidate_window.end:
            raise ValueError("candidate_window must satisfy start < end")

        if candidate_window.start < working_hours.start or candidate_window.end > working_hours.end:
            raise ValueError("candidate_window must lie within working_hours")

        working_start = _to_datetime(day, candidate_window.start)
        working_end = _to_datetime(day, candidate_window.end)

    # ---------------- Normalize Busy Intervals ----------------

    normalized = []

    for b in busy_intervals:

        if b.start >= b.end:
            raise ValueError("BusyInterval must satisfy start < end")

        start = _to_datetime(day, b.start)
        end = _to_datetime(day, b.end)

        clipped = _clip_interval(start, end, working_start, working_end)

        if clipped:
            normalized.append(clipped)

    # ---------------- Apply Buffer ----------------

    buffered = []

    for start, end in normalized:
        buffered_start = start - buffer
        buffered_end = end + buffer

        clipped = _clip_interval(buffered_start, buffered_end, working_start, working_end)

        if clipped:
            buffered.append(clipped)

    # ---------------- Merge Intervals ----------------

    merged_busy = _merge_intervals(buffered)

    # ---------------- Compute Free Gaps ----------------

    free_gaps = []

    cursor = working_start

    for start, end in merged_busy:

        if cursor < start:
            free_gaps.append((cursor, start))

        cursor = max(cursor, end)

    if cursor < working_end:
        free_gaps.append((cursor, working_end))

    # ---------------- Generate Slots ----------------

    slots: List[Slot] = []

    for gap_start, gap_end in free_gaps:

        slot_start = gap_start

        while slot_start + duration <= gap_end:

            slots.append(Slot(start_time=slot_start.time()))

            if len(slots) == n:
                return slots

            slot_start += duration

    return slots