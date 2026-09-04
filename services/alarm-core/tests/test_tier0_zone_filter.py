from aivideoalarm.alarm_state import AlarmState
from aivideoalarm.config import ZoneRule
from aivideoalarm.pipeline.tier0_zone_filter import evaluate
from aivideoalarm.pipeline.types import Decision, FrigateEvent


def make_event(camera="backyard_cam", label="cat", zones=None) -> FrigateEvent:
    return FrigateEvent(
        event_id="abc123",
        camera=camera,
        label=label,
        zones=zones or ["backyard"],
        top_score=0.9,
        has_snapshot=True,
        has_clip=True,
    )


def test_cat_in_backyard_is_suppressed():
    """The literal false-positive case from the backlog."""
    rules = [
        ZoneRule(camera="*", zone="backyard", label="cat", decision="suppress"),
    ]
    result = evaluate(make_event(), rules, AlarmState.ARMED_AWAY)
    assert result.decision == Decision.SUPPRESS


def test_person_on_front_porch_while_away_alarms():
    rules = [
        ZoneRule(camera="*", zone="backyard", label="cat", decision="suppress"),
        ZoneRule(
            camera="*",
            zone="front_porch",
            label="person",
            decision="alarm",
            alarm_states=["armed_away"],
        ),
    ]
    event = make_event(camera="front_porch_cam", label="person", zones=["front_porch"])
    result = evaluate(event, rules, AlarmState.ARMED_AWAY)
    assert result.decision == Decision.ALARM


def test_no_matching_rule_is_ambiguous():
    result = evaluate(make_event(label="raccoon"), [], AlarmState.ARMED_HOME)
    assert result.decision == Decision.AMBIGUOUS


def test_rule_scoped_to_wrong_alarm_state_does_not_match():
    rules = [
        ZoneRule(
            camera="*",
            zone="front_porch",
            label="person",
            decision="alarm",
            alarm_states=["armed_away"],
        ),
    ]
    event = make_event(camera="front_porch_cam", label="person", zones=["front_porch"])
    result = evaluate(event, rules, AlarmState.ARMED_HOME)
    assert result.decision == Decision.AMBIGUOUS
