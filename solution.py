## Student Name: Dexter Sargent
## Student ID: 217931460

from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from typing import List, Optional, Tuple


# ---------------- Data Models ----------------

@dataclass(frozen=True)
class TimeWindow:
    start: time
    end: time


@dataclass(frozen=True)
class BusyInterval:
    start: time
    end: time


@dataclass(frozen=True)
class Slot:
    start_time: time


class InfeasibleSchedule(Exception):
    pass


# ---------------- Decision Log ----------------

class DecisionLog:
    """
    Stores automated scheduling decisions for transparency (FR11 / AC8).
    """

    def __init__(self):
        self.entries: List[str] = []

    def record(self, message: str):
        self.entries.append(message)

    def get_entries(self) -> List[str]:
        return list(self.entries)


decision_log = DecisionLog()


# ---------------- Helper Functions ----------------

def _to_datetime(day: date, t: time) -> datetime:
    return datetime.combine(day, t)


def _merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
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

    decision_log.entries.clear()

    # ---------------- Validation ----------------

    if duration <= timedelta(0):
        raise ValueError("Meeting duration must be positive.")

    if buffer < timedelta(0):
        raise ValueError("Buffer time cannot be negative.")

    if n < 0:
        raise ValueError("Requested number of slots must be zero or greater.")

    if working_hours.start >= working_hours.end:
        raise ValueError("Working hours must have a start time before the end time.")

    if n == 0:
        return []

    working_start = _to_datetime(day, working_hours.start)
    working_end = _to_datetime(day, working_hours.end)

    # ---------------- Candidate Window Handling ----------------

    if candidate_window is not None:

        if candidate_window.start >= candidate_window.end:
            raise ValueError("Candidate window must have a start time before the end time.")

        candidate_start = _to_datetime(day, candidate_window.start)
        candidate_end = _to_datetime(day, candidate_window.end)

        # completely outside working hours
        if candidate_end <= working_start or candidate_start >= working_end:
            raise ValueError("Candidate window lies completely outside working hours.")

        # clip to working hours
        working_start = max(working_start, candidate_start)
        working_end = min(working_end, candidate_end)

    if duration > (working_end - working_start):
        return []

    # ---------------- Normalize Busy Intervals ----------------

    normalized: List[Tuple[datetime, datetime]] = []

    for b in busy_intervals:

        if b.start >= b.end:
            raise ValueError("Busy intervals must have start < end.")

        start = _to_datetime(day, b.start)
        end = _to_datetime(day, b.end)

        clipped = _clip_interval(start, end, working_start, working_end)

        if clipped:
            normalized.append(clipped)

    # ---------------- Apply Buffer ----------------

    buffered: List[Tuple[datetime, datetime]] = []

    for start, end in normalized:

        buffered_start = start - buffer
        buffered_end = end + buffer

        clipped = _clip_interval(buffered_start, buffered_end, working_start, working_end)

        if clipped:
            buffered.append(clipped)

    # ---------------- Merge Busy Intervals ----------------

    merged_busy = _merge_intervals(buffered)

    # ---------------- Compute Free Gaps ----------------

    free_gaps: List[Tuple[datetime, datetime]] = []

    cursor = working_start

    for start, end in merged_busy:

        if cursor < start:
            free_gaps.append((cursor, start))

        cursor = max(cursor, end)

    if cursor < working_end:
        free_gaps.append((cursor, working_end))

    # ---------------- Generate Slots ----------------
    # FR14: deterministic 1-minute resolution

    slots: List[Slot] = []

    for gap_start, gap_end in free_gaps:

        slot_start = gap_start

        while slot_start + duration <= gap_end:

            # check overlap with busy intervals (safety)
            conflict = False

            for busy_start, busy_end in merged_busy:
                if slot_start < busy_end and (slot_start + duration) > busy_start:
                    conflict = True
                    decision_log.record(
                        f"Slot at {slot_start.time()} excluded due to busy interval or buffer constraint."
                    )
                    break

            if not conflict:
                slots.append(Slot(start_time=slot_start.time()))

                if len(slots) == n:
                    return slots

            # advance by one minute (FR14)
            slot_start += timedelta(minutes=1)

    return slots