from datetime import datetime
from pathlib import Path

from aivideoalarm.config import EscalationPolicy
from aivideoalarm.pipeline.tier2_cloud import DailyCallBudget, is_night


def test_is_night_within_same_day_window():
    policy = EscalationPolicy(night_start_hour=20, night_end_hour=23)
    assert is_night(policy, datetime(2024, 1, 1, 21, 0)) is True
    assert is_night(policy, datetime(2024, 1, 1, 12, 0)) is False


def test_is_night_spanning_midnight():
    policy = EscalationPolicy(night_start_hour=20, night_end_hour=7)
    assert is_night(policy, datetime(2024, 1, 1, 23, 0)) is True  # late evening
    assert is_night(policy, datetime(2024, 1, 1, 3, 0)) is True  # early morning
    assert is_night(policy, datetime(2024, 1, 1, 12, 0)) is False  # midday


def test_daily_call_budget_enforces_cap(tmp_path: Path):
    db_path = tmp_path / "budget.sqlite3"
    budget = DailyCallBudget(daily_cap=2, db_path=db_path)
    assert budget.try_consume() is True
    assert budget.try_consume() is True
    assert budget.try_consume() is False  # cap reached


def test_daily_call_budget_persists_across_instances(tmp_path: Path):
    db_path = tmp_path / "budget.sqlite3"
    DailyCallBudget(daily_cap=1, db_path=db_path).try_consume()
    # A fresh instance (simulating a restart) sees the same day's count.
    second = DailyCallBudget(daily_cap=1, db_path=db_path)
    assert second.try_consume() is False
