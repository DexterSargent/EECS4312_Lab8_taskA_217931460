import pytest
from datetime import date, datetime, time, timedelta

# Update import path to match your project structure:
from solution import TimeWindow, BusyInterval, Slot, suggest_slots


# ---------- Helpers ----------

def combine(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def in_window(win: TimeWindow, t: time) -> bool:
    return win.start <= t < win.end


def assert_slots_basic_constraints(
    slots,
    day,
    working_hours,
    busy_intervals,
    duration,
    n,
    buffer,
    candidate_window,
):
    # Return type / length
    assert isinstance(slots, list)
    assert len(slots) <= n

    # Deterministic ordering: start_time ascending
    assert slots == sorted(slots, key=lambda s: s.start_time)

    # Each slot start must be within working_hours and candidate_window (if any)
    for s in slots:
        assert in_window(working_hours, s.start_time)
        if candidate_window is not None:
            assert in_window(candidate_window, s.start_time)

    # Each slot must fit fully inside working_hours and candidate_window
    for s in slots:
        start_dt = combine(day, s.start_time)
        end_dt = start_dt + duration

        wh_end = combine(day, working_hours.end)
        assert end_dt <= wh_end

        if candidate_window is not None:
            cw_end = combine(day, candidate_window.end)
            assert end_dt <= cw_end

    # No overlap with busy intervals, considering buffer:
    # busy interval is expanded to [start-buffer, end+buffer)
    for s in slots:
        slot_start = combine(day, s.start_time)
        slot_end = slot_start + duration

        for b in busy_intervals:
            b_start = combine(day, b.start) - buffer
            b_end = combine(day, b.end) + buffer
            assert not overlaps(slot_start, slot_end, b_start, b_end)


# ---------- Tests ----------

def test_a1_no_busy_simple_slots():
    """
    Like original "single med exact times": here, no busy events.
    Expect earliest slots within working hours (we only assert constraints + non-empty).
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(12, 0))
    busy = []
    duration = timedelta(minutes=30)

    out = suggest_slots(
        day=day,
        working_hours=working,
        busy_intervals=busy,
        duration=duration,
        n=3,
        buffer=timedelta(0),
        candidate_window=None
    )

    assert_slots_basic_constraints(out, day, working, busy, duration, 3, timedelta(0), None)
    # Should at least return 1 slot if implementation uses a reasonable slot step
    assert len(out) > 0
    # Earliest slot should be at or after working start
    assert out[0].start_time >= time(9, 0)


def test_a2_deterministic_same_inputs_same_outputs():
    """
    Like original tie/determinism check: same inputs must return identical outputs.
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(17, 0))
    busy = [
        BusyInterval(time(10, 0), time(10, 30)),
        BusyInterval(time(13, 0), time(14, 0)),
    ]
    duration = timedelta(minutes=30)
    buffer = timedelta(minutes=0)

    out1 = suggest_slots(day, working, busy, duration, n=10, buffer=buffer, candidate_window=None)
    out2 = suggest_slots(day, working, busy, duration, n=10, buffer=buffer, candidate_window=None)

    assert [s.start_time for s in out1] == [s.start_time for s in out2]
    assert_slots_basic_constraints(out1, day, working, busy, duration, 10, buffer, None)


def test_a3_overlapping_and_unsorted_busy_intervals_handled():
    """
    Busy intervals may be unsorted/overlapping; suggestions must still avoid conflicts.
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(12, 0))
    busy = [
        BusyInterval(time(10, 30), time(11, 0)),
        BusyInterval(time(10, 0), time(10, 45)),   # overlaps with above
        BusyInterval(time(9, 30), time(9, 45)),    # unsorted relative order
    ]
    duration = timedelta(minutes=15)

    out = suggest_slots(day, working, busy, duration, n=8, buffer=timedelta(0), candidate_window=None)
    assert_slots_basic_constraints(out, day, working, busy, duration, 8, timedelta(0), None)


def test_a4_candidate_window_respected():
    """
    Like original allowed_window respected: here we add an extra candidate window restriction.
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(17, 0))
    candidate = TimeWindow(time(13, 0), time(15, 0))
    busy = []
    duration = timedelta(minutes=30)

    out = suggest_slots(day, working, busy, duration, n=5, buffer=timedelta(0), candidate_window=candidate)
    assert_slots_basic_constraints(out, day, working, busy, duration, 5, timedelta(0), candidate)

    # Every slot must start within candidate window
    assert all(candidate.start <= s.start_time < candidate.end for s in out)


def test_a5_buffer_eliminates_small_gaps():
    """
    Like original rate-limit constraint: here buffer is the key extra constraint.
    With buffer, some slots that would otherwise fit should be invalid.
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(11, 0))
    # Two busy intervals leaving a 20-minute gap between them
    busy = [
        BusyInterval(time(9, 30), time(9, 50)),
        BusyInterval(time(10, 10), time(10, 30)),
    ]
    duration = timedelta(minutes=20)

    # Without buffer: the gap 9:50–10:10 is exactly 20 minutes -> potentially valid
    out_no_buffer = suggest_slots(day, working, busy, duration, n=10, buffer=timedelta(0), candidate_window=None)
    assert_slots_basic_constraints(out_no_buffer, day, working, busy, duration, 10, timedelta(0), None)

    # With 5-min buffer: effective busy expands, gap shrinks -> should reduce or remove those slots
    buf = timedelta(minutes=5)
    out_with_buffer = suggest_slots(day, working, busy, duration, n=10, buffer=buf, candidate_window=None)
    assert_slots_basic_constraints(out_with_buffer, day, working, busy, duration, 10, buf, None)

    # Buffer should not increase number of available slots (monotonicity)
    assert len(out_with_buffer) <= len(out_no_buffer)


#################################################################################
# Add your own additional tests here to cover more cases and edge cases as needed.
#################################################################################

# -------------------------------------------------------------
# Additional Tests Covering Acceptance Criteria and Edge Cases
# -------------------------------------------------------------


def test_ac1_validate_working_hours_boundary():
    """
    AC1: All slots must stay within working hours.
    """
    day = date(2026, 2, 24)
    working = TimeWindow(time(9, 0), time(12, 0))
    duration = timedelta(minutes=30)

    out = suggest_slots(
        day=day,
        working_hours=working,
        busy_intervals=[],
        duration=duration,
        n=5,
        buffer=timedelta(0),
        candidate_window=None
    )

    assert_slots_basic_constraints(out, day, working, [], duration, 5, timedelta(0), None)

    for s in out:
        assert s.start_time >= time(9, 0)
        end_time = (combine(day, s.start_time) + duration).time()
        assert end_time <= time(12, 0)


def test_ac2_avoid_busy_intervals():
    """
    AC2: No slot may overlap a busy interval.
    """
    day = date(2026, 2, 24)

    working = TimeWindow(time(9, 0), time(17, 0))
    busy = [BusyInterval(time(10, 0), time(11, 0))]
    duration = timedelta(minutes=30)

    out = suggest_slots(
        day, working, busy, duration, n=10, buffer=timedelta(0), candidate_window=None
    )

    assert_slots_basic_constraints(out, day, working, busy, duration, 10, timedelta(0), None)

    for s in out:
        assert not (time(9, 31) <= s.start_time <= time(10, 59))


def test_ac3_insufficient_availability_returns_empty():
    """
    AC3: Meeting longer than available window -> empty list.
    """
    day = date(2026, 2, 24)

    working = TimeWindow(time(9, 0), time(10, 0))
    duration = timedelta(minutes=90)

    out = suggest_slots(
        day, working, [], duration, n=5, buffer=timedelta(0), candidate_window=None
    )

    assert out == []


def test_ac4_respect_buffer_after_busy():
    """
    AC4: Buffer must push earliest slot after busy interval.
    """
    day = date(2026, 2, 24)

    working = TimeWindow(time(9, 0), time(12, 0))
    busy = [BusyInterval(time(9, 30), time(10, 0))]

    duration = timedelta(minutes=30)
    buffer = timedelta(minutes=10)

    out = suggest_slots(
        day, working, busy, duration, n=5, buffer=buffer, candidate_window=None
    )

    assert_slots_basic_constraints(out, day, working, busy, duration, 5, buffer, None)

    if out:
        assert out[0].start_time >= time(10, 10)


def test_ac6_deterministic_and_limit_n():
    """
    AC6: deterministic output and respecting n.
    """
    day = date(2026, 2, 24)

    working = TimeWindow(time(9, 0), time(17, 0))
    busy = [
        BusyInterval(time(10, 0), time(10, 30)),
        BusyInterval(time(12, 0), time(13, 0)),
    ]

    duration = timedelta(minutes=30)

    out1 = suggest_slots(day, working, busy, duration, n=2)
    out2 = suggest_slots(day, working, busy, duration, n=2)

    assert len(out1) <= 2
    assert [s.start_time for s in out1] == [s.start_time for s in out2]


def test_ec1_zero_available_slots():
    """
    EC1: Busy intervals fill entire window.
    """
    day = date(2026, 2, 24)

    working = TimeWindow(time(9, 0), time(12, 0))
    busy = [BusyInterval(time(9, 0), time(12, 0))]

    duration = timedelta(minutes=30)

    out = suggest_slots(
        day, working, busy, duration, n=5
    )

    assert out == []


def test_ec2_n_equals_zero_returns_empty():
    """
    EC2: n=0 must return [].
    """
    day = date(2026, 2, 24)

    working = TimeWindow(time(9, 0), time(17, 0))

    out = suggest_slots(
        day,
        working,
        busy_intervals=[],
        duration=timedelta(minutes=30),
        n=0
    )

    assert out == []


def test_ec3_adjacent_busy_intervals_no_gap():
    """
    EC3: Adjacent intervals must not allow a slot at boundary.
    """
    day = date(2026, 2, 24)

    working = TimeWindow(time(9, 0), time(12, 0))

    busy = [
        BusyInterval(time(9, 0), time(10, 0)),
        BusyInterval(time(10, 0), time(11, 0)),
    ]

    duration = timedelta(minutes=30)

    out = suggest_slots(day, working, busy, duration, n=10)

    assert_slots_basic_constraints(out, day, working, busy, duration, 10, timedelta(0), None)

    assert all(s.start_time >= time(11, 0) for s in out)


def test_ec6_candidate_window_outside_working_hours():
    """
    EC6: candidate window outside working hours should raise error.
    """
    day = date(2026, 2, 24)

    working = TimeWindow(time(9, 0), time(17, 0))
    candidate = TimeWindow(time(8, 0), time(9, 0))

    with pytest.raises(ValueError):
        suggest_slots(
            day,
            working,
            [],
            duration=timedelta(minutes=30),
            n=5,
            candidate_window=candidate
        )
        
#------------------------------------------------


# Covers C3, C5, C9, AC2, EC4, EC5
def test_ac2_avoid_busy_intervals_and_buffers():
    """
    AC2: No returned slot may fall within a busy interval or its associated buffer period.
    EC4: Buffer eliminating a marginal gap.
    EC5: Normalization of overlapping busy intervals.
    """
    day = date(2026, 3, 14)
    working = TimeWindow(time(9, 0), time(17, 0))
    busy = [
        BusyInterval(time(10, 0), time(11, 0)),
        BusyInterval(time(10, 30), time(11, 30)) 
    ]
    duration = timedelta(minutes=30)
    buffer = timedelta(minutes=10) 

    out = suggest_slots(day, working, busy, duration, n=10, buffer=buffer)
    assert_slots_basic_constraints(out, day, working, busy, duration, 10, buffer, None)

    for s in out:
        slot_start = combine(day, s.start_time)
        assert not overlaps(slot_start, slot_start + duration, 
                           combine(day, time(9, 50)), combine(day, time(11, 40)))


# Covers C1, C12, AC3, AC5
def test_ac3_ac5_deterministic_and_limit_n():
    """
    AC3: Identical inputs must result in identical, deterministic outputs.
    AC5: The system must return exactly N slots if they exist.
    """
    day = date(2026, 3, 14)
    working = TimeWindow(time(9, 0), time(17, 0))
    busy = [BusyInterval(time(12, 0), time(13, 0))]
    duration = timedelta(minutes=60)
    n = 2

    out1 = suggest_slots(day, working, busy, duration, n=n)
    out2 = suggest_slots(day, working, busy, duration, n=n)

    assert len(out1) == 2
    assert [s.start_time for s in out1] == [s.start_time for s in out2]
    # Check 1-minute increment determinism (C7)
    assert out1[0].start_time == time(9, 0)
    assert out1[1].start_time == time(9, 1)


# Covers C6, C8, C13, AC4, EC6, EC7
def test_ac4_ec6_ec7_candidate_window_handling():
    """
    AC4: Slots restricted to candidate window.
    EC6: Window outside working hours raises ValueError.
    EC7: Window exactly matching duration returns one slot.
    """
    day = date(2026, 3, 14)
    working = TimeWindow(time(9, 0), time(17, 0))
    duration = timedelta(minutes=30)

    # EC7: Tight fit
    candidate_tight = TimeWindow(time(10, 0), time(10, 30))
    out = suggest_slots(day, working, [], duration, n=5, candidate_window=candidate_tight)
    assert len(out) == 1
    assert out[0].start_time == time(10, 0)

    # EC6: Outside working hours
    candidate_bad = TimeWindow(time(18, 0), time(19, 0))
    with pytest.raises(ValueError, match="completely outside working hours"):
        suggest_slots(day, working, [], duration, n=5, candidate_window=candidate_bad)


# Covers C14, AC7, EC2
def test_ac7_ec2_invalid_inputs():
    """
    AC7: Raise ValueError for invalid inputs.
    EC2: n = 0 returns empty list.
    """
    day = date(2026, 3, 14)
    working = TimeWindow(time(9, 0), time(17, 0))

    with pytest.raises(ValueError, match="duration must be positive"):
        suggest_slots(day, working, [], timedelta(0), n=5)

    with pytest.raises(ValueError, match="must be zero or greater"):
        suggest_slots(day, working, [], timedelta(minutes=30), n=-1)

    out = suggest_slots(day, working, [], timedelta(minutes=30), n=0)
    assert out == []


# Covers C15, EC3
def test_ec3_c15_boundary_touching():
    """
    C15: Slots can touch busy boundaries.
    EC3: Adjacent busy intervals with no gap.
    """
    day = date(2026, 3, 14)
    working = TimeWindow(time(9, 0), time(12, 0))
    busy = [
        BusyInterval(time(9, 0), time(10, 0)),
        BusyInterval(time(10, 0), time(11, 0))
    ]
    duration = timedelta(minutes=60)

    out = suggest_slots(day, working, busy, duration, n=1)
    
    assert len(out) == 1
    assert out[0].start_time == time(11, 0)