# SPDX-License-Identifier: GPL-3.0-or-later
"""The timing log: page and station-intervention records, pure logic."""

from datetime import UTC, datetime, timedelta

from custom_components.verdi.timing import KEEP, TimingLog

T0 = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
A1, A2 = "2026-06-15T11:59:50+00:00", "2026-06-15T12:30:00+00:00"
PAGE = {
    "station": "S",
    "crew_function": "D",
    "vehicle": "P",
    "alarm_time": A1,
    "incident": "F",
    "confirmation": None,
}
PAGE2 = {**PAGE, "alarm_time": A2}


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def iso(seconds: float) -> str:
    return at(seconds).isoformat()


def quiet() -> TimingLog:
    """A log that has seen one quiet fetch of every input at T0."""
    log = TimingLog()
    log.paged(at(0), None, [])
    log.own(at(0), False, False)
    log.vehicles(at(0), False)
    log.persons(at(0), 0, False, False)
    return log


def test_paged_first_then_own():
    log = quiet()
    log.paged(at(15), PAGE, ["station.name"])
    log.own(at(60), True, False)
    rec = log.page
    assert (rec["paged_on"], rec["paged_on_after"]) == (iso(15), iso(0))
    assert (rec["own_on"], rec["own_on_after"]) == (iso(60), iso(0))
    assert rec["alarm_time"] == A1 and rec["keys"] == ["station.name"]
    assert rec["fields"]["station"] is True and rec["fields"]["confirmation"] is False
    assert rec["startup"] is False and rec["paged_paused"] is False
    log.paged(at(600), None, [])
    assert log.page is not None  # your flag is still on
    log.own(at(660), False, False)
    assert log.page is None and log.pages[0]["own_off"] == iso(660)
    shown = log.diagnostics()["pages"][0]
    assert (shown["own_after_paged_s"], shown["paged_duration_s"]) == (45.0, 585.0)


def test_own_first_gives_a_negative_delay():
    log = quiet()
    log.own(at(30), True, False)
    log.paged(at(45), PAGE, [])
    assert log.diagnostics()["pages"][0]["own_after_paged_s"] == -15.0


def test_own_joins_late_while_the_page_is_open():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.own(at(15 + 1200), True, False)  # 20 minutes later, Paged still on
    assert log.pages == [] and log.page["own_on"] == iso(1215)


def test_own_never_turns_on():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.own(at(60), False, False)
    log.paged(at(300), None, [])
    assert log.page is None and log.pages[0]["own_on"] is None


def test_own_unknown_opens_nothing():
    log = quiet()
    log.own(at(10), None, False)
    assert log.page is None


def test_own_unknown_lets_the_page_close():
    log = quiet()
    log.own(at(10), True, False)
    log.paged(at(15), PAGE, [])
    log.own(at(60), None, False)  # your line went missing
    log.paged(at(300), None, [])
    assert log.page is None and log.pages[0]["own_off"] is None


def test_back_to_back_pages_split_on_alarm_time():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.paged(at(30), PAGE2, [])
    assert log.pages[0]["paged_off"] == iso(30)
    assert (log.page["paged_on"], log.page["paged_on_after"], log.page["alarm_time"]) == (
        iso(30),
        iso(15),
        A2,
    )


def test_short_off_blip_rejoins_within_ten_minutes():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.paged(at(300), None, [])
    assert log.page is None and len(log.pages) == 1
    log.paged(at(400), PAGE, [])
    assert log.pages == [] and log.page["paged_off"] is None and log.page["paged_on"] == iso(15)


def test_after_ten_minutes_a_new_record():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.paged(at(300), None, [])
    log.paged(at(1000), PAGE, [])
    assert len(log.pages) == 1 and log.page["paged_on"] == iso(1000)


def test_own_on_while_paging_paused():
    log = quiet()
    log.own(at(30), True, True)
    assert log.page["paged_paused"] is True


def test_resume_resets_the_paged_baseline():
    log = quiet()
    log.paging(True)
    log.paging(False)
    log.paged(at(900), PAGE, [])
    assert log.page["paged_on_after"] is None and log.page["startup"] is False


def test_same_run_in_either_order_gives_zero():
    for first_paged in (True, False):
        log = quiet()
        if first_paged:
            log.paged(at(60), PAGE, [])
            log.own(at(60), True, False)
        else:
            log.own(at(60), True, False)
            log.paged(at(60), PAGE, [])
        assert log.diagnostics()["pages"][0]["own_after_paged_s"] == 0.0


def test_startup_with_paged_already_on():
    log = TimingLog()
    log.paged(at(0), PAGE, [])
    assert log.page["startup"] is True and log.page["paged_on_after"] is None


def test_startup_with_own_already_on():
    log = TimingLog()
    log.own(at(0), True, False)
    assert log.page["startup"] is True and log.page["own_on_after"] is None


def test_startup_continues_the_saved_open_page():
    old = quiet()
    old.paged(at(15), PAGE, [])
    log = TimingLog()
    log.load(old.dump())
    log.paged(at(500), PAGE, [])
    assert log.pages == [] and log.page["paged_on"] == iso(15)


def test_startup_with_another_page_closes_the_saved_one():
    old = quiet()
    old.paged(at(15), PAGE, [])
    log = TimingLog()
    log.load(old.dump())
    log.paged(at(500), PAGE2, [])
    assert log.pages[0]["interrupted"] is True and log.pages[0]["paged_off"] == iso(500)
    assert log.page["startup"] is True and log.page["alarm_time"] == A2


def test_end_seen_after_downtime_is_interrupted():
    old = quiet()
    old.paged(at(15), PAGE, [])
    log = TimingLog()
    log.load(old.dump())
    log.paged(at(3600), None, [])
    assert log.page is None and log.pages[0]["interrupted"] is True


def test_page_times_out_after_six_hours():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.own(at(15 + 6 * 3600), False, False)
    assert log.page is None and log.pages[0]["paged_off"] is None


def test_persons_rise_after_the_vehicle():
    log = quiet()
    log.vehicles(at(60), True)
    log.persons(at(120), 3, False, False)
    rec = log.intervention
    assert (rec["vehicle_on"], rec["vehicle_on_after"], rec["persons_before"]) == (iso(60), iso(0), 0)
    assert (rec["persons_rise"], rec["persons_rise_after"]) == (iso(120), iso(0))
    log.persons(at(600), 0, False, False)
    log.vehicles(at(700), False)
    assert log.intervention is None
    shown = log.diagnostics()["station_interventions"][0]
    assert shown["persons_back"] == iso(600) and shown["persons_after_vehicle_s"] == 60.0


def test_persons_rise_before_the_vehicle():
    log = quiet()
    log.persons(at(60), 2, False, False)
    log.persons(at(120), 2, False, False)
    log.vehicles(at(120), True)
    rec = log.intervention
    assert (rec["persons_before"], rec["persons_rise"], rec["persons_rise_after"]) == (0, iso(60), iso(0))
    assert log.diagnostics()["station_interventions"][0]["persons_after_vehicle_s"] == -60.0


def test_persons_rise_in_the_same_run_either_order():
    station = quiet()  # station order: personnel, then vehicles
    station.persons(at(60), 2, False, False)
    station.vehicles(at(60), True)
    fast = quiet()  # fast-lane order: vehicles, then personnel
    fast.vehicles(at(60), True)
    fast.persons(at(60), 2, False, False)
    for log in (station, fast):
        assert log.diagnostics()["station_interventions"][0]["persons_after_vehicle_s"] == 0.0


def test_an_old_rise_is_not_this_intervention():
    log = quiet()
    log.persons(at(60), 2, False, False)
    log.vehicles(at(60 + 11 * 60), True)
    assert log.intervention["persons_rise"] is None and log.intervention["persons_before"] == 2


def test_nobody_rises():
    log = quiet()
    log.vehicles(at(60), True)
    log.persons(at(120), 0, False, False)
    log.vehicles(at(300), False)
    assert log.intervention is None and log.interventions[0]["persons_rise"] is None


def test_a_list_change_is_not_people():
    log = quiet()
    log.persons(at(30), 5, False, True)  # the availability list loaded late
    log.vehicles(at(60), True)
    assert log.intervention["persons_rise"] is None and log.intervention["persons_before"] == 5
    log.persons(at(90), 9, False, True)
    assert log.intervention["persons_rise"] is None and log.intervention["persons_before"] == 9
    log.persons(at(120), 10, False, False)
    assert log.intervention["persons_rise"] == iso(120)


def test_concurrent_when_the_count_stays_up():
    log = quiet()
    log.vehicles(at(60), True)
    log.persons(at(120), 3, False, False)
    log.vehicles(at(600), False)
    assert log.intervention is not None  # people still out
    log.persons(at(60 + 3 * 3600), 3, False, False)
    assert log.intervention is None and log.interventions[0]["concurrent"] is True


def test_truncated_is_remembered():
    log = quiet()
    log.vehicles(at(60), True)
    log.persons(at(120), 1, True, False)
    log.persons(at(180), 1, False, False)
    assert log.intervention["truncated"] is True


def test_keeps_the_last_ten():
    log = quiet()
    for i in range(KEEP + 2):
        start = 2000 * (i + 1)
        log.paged(at(start), PAGE, [])
        log.paged(at(start + 900), None, [])
        log.vehicles(at(start), True)
        log.vehicles(at(start + 900), False)
    assert len(log.pages) == KEEP == 10 and len(log.interventions) == 10
    assert log.pages[0]["paged_on"] == iso(2000 * (KEEP + 2))


def test_dump_and_load():
    log = quiet()
    log.paged(at(15), PAGE, ["station"])
    log.paged(at(300), None, [])
    log.vehicles(at(60), True)
    again = TimingLog()
    again.load(log.dump())
    assert again.dump() == log.dump()


def test_unknown_shapes_load_empty():
    for junk in (None, "x", [], {"pages": "y", "page": 3, "interventions": [1, "a"], "intervention": []}):
        log = TimingLog()
        log.load(junk)
        assert log.dump() == {"pages": [], "page": None, "interventions": [], "intervention": None}


def test_on_change_only_when_a_record_changes():
    log = quiet()
    changes: list[int] = []
    log.on_change = lambda: changes.append(1)
    log.paged(at(15), None, [])
    log.persons(at(15), 0, False, False)
    log.vehicles(at(15), False)
    assert changes == []
    log.paged(at(30), PAGE, [])
    assert changes
    count = len(changes)
    log.paged(at(45), PAGE, [])  # the same page, still on
    assert len(changes) == count


def test_own_rejoin_then_new_page_moves_the_own_flag():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.own(at(60), True, False)
    log.paged(at(600), None, [])
    log.own(at(660), False, False)
    assert log.page is None
    log.own(at(900), True, False)  # rejoins the page just closed
    log.paged(at(915), None, [])  # no page yet: still tentative
    log.own(at(930), True, False)
    log.paged(at(930), PAGE2, [])
    assert log.pages[0]["alarm_time"] == A1 and log.pages[0]["own_off"] == iso(660)
    assert (log.page["alarm_time"], log.page["own_on"], log.page["own_on_after"]) == (A2, iso(900), iso(660))
    log.own(at(1200), False, False)
    assert log.page["own_off"] == iso(1200)


def test_own_rejoin_then_new_page_in_the_same_run():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.own(at(60), True, False)
    log.paged(at(600), None, [])
    log.own(at(660), False, False)
    log.own(at(900), True, False)
    log.paged(at(900), PAGE2, [])
    assert log.pages[0]["own_off"] == iso(660)
    assert (log.page["own_on"], log.page["own_on_after"]) == (iso(900), iso(660))


def test_own_blip_on_open_page_then_new_page():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.own(at(60), True, False)
    log.own(at(120), False, False)
    log.own(at(180), True, False)
    log.paged(at(195), PAGE2, [])
    log.own(at(300), False, False)
    assert log.pages[0]["own_off"] == iso(120)
    assert (log.page["own_on"], log.page["own_off"]) == (iso(180), iso(300))


def test_own_rejoin_confirmed_by_same_page():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.own(at(60), True, False)
    log.paged(at(600), None, [])
    log.own(at(660), False, False)
    log.own(at(900), True, False)
    log.paged(at(915), PAGE, [])
    assert log.pages == [] and log.page["alarm_time"] == A1 and log.page["own_off"] is None
    log.paged(at(930), PAGE2, [])
    assert log.pages[0]["own_off"] is None and log.page["own_on"] is None


def test_new_page_after_a_timed_out_one():
    log = quiet()
    log.paged(at(15), PAGE, [])
    log.paged(at(15 + 6 * 3600), PAGE, [])  # Paged still on; the record timed out
    assert log.page is None
    log.paged(at(15 + 6 * 3600 + 60), PAGE2, [])
    assert log.page["alarm_time"] == A2
    assert log.page["paged_on_after"] == iso(15 + 6 * 3600)


def test_restart_then_own_joins_the_saved_page():
    old = quiet()
    old.paged(at(15), PAGE, [])
    log = TimingLog()
    log.load(old.dump())
    log.own(at(500), True, False)
    assert log.page["own_on"] == iso(500) and log.page["interrupted"] is True
    assert log.page["startup"] is False


def test_restart_mid_intervention_rise_is_interrupted():
    old = quiet()
    old.vehicles(at(60), True)
    log = TimingLog()
    log.load(old.dump())
    log.persons(at(500), 3, False, False)
    assert log.intervention["persons_rise"] == iso(500) and log.intervention["interrupted"] is True


def _saved(**changes):
    rec = {"opened": iso(0), "vehicle_on": iso(0), "persons_before": 3}
    return {**rec, **changes}


def test_load_drops_records_of_a_bad_shape():
    log = TimingLog()
    log.load(
        {
            "pages": [{"opened": iso(0)}],
            "page": {"opened": "not a time"},
            "interventions": [_saved(), _saved(persons_before="3"), _saved(persons_before=True)],
            "intervention": _saved(persons_before="3"),
        }
    )
    assert log.page is None and log.intervention is None
    assert log.pages == [{"opened": iso(0)}]
    assert [r["persons_before"] for r in log.interventions] == [3]


def test_load_drops_an_open_record_without_an_aware_time():
    for opened in (None, "2026-06-15T12:00:00", 5):
        log = TimingLog()
        log.load({"page": {"opened": opened}, "intervention": _saved(opened=opened)})
        assert log.page is None and log.intervention is None
    log = TimingLog()
    log.load({"intervention": _saved(persons_before=None)})
    assert log.intervention is not None


def test_load_drops_a_closed_record_without_an_aware_time():
    log = TimingLog()
    log.load(
        {
            "pages": [
                {"opened": None, "closed": iso(0)},
                {"opened": "2026-06-15T12:00:00"},
                {"opened": iso(0)},
            ],
            "interventions": [_saved(opened=5), _saved()],
        }
    )
    assert log.pages == [{"opened": iso(0)}]
    assert log.interventions == [_saved()]


def test_keys_grow_over_the_page_and_confirmation_is_timed():
    log = quiet()
    changes = []
    log.on_change = lambda: changes.append(1)
    log.paged(at(15), PAGE, ["alarmDate", "station.name"])
    assert log.page["confirmation_at"] is None
    before = len(changes)
    log.paged(at(30), {**PAGE, "confirmation": "Coming"}, ["alarmDate", "callConfirmation.description"])
    rec = log.page
    assert rec["keys"] == ["alarmDate", "callConfirmation.description", "station.name"]
    assert rec["confirmation_at"] == iso(30) and rec["fields"]["confirmation"] is True
    assert len(changes) > before
    log.paged(at(45), {**PAGE, "confirmation": "Coming"}, ["alarmDate"])
    assert log.page["confirmation_at"] == iso(30)  # first time only


def test_confirmed_at_the_first_fetch():
    log = quiet()
    log.paged(at(15), {**PAGE, "confirmation": "Coming"}, [])
    assert log.page["confirmation_at"] == iso(15)


def test_keys_union_is_capped():
    log = quiet()
    log.paged(at(15), PAGE, [f"a{i}" for i in range(40)])
    log.paged(at(30), PAGE, [f"b{i}" for i in range(40)])
    assert len(log.page["keys"]) == 60
