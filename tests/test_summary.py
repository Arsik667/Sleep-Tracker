from datetime import date, timedelta

import pytest

from sleep_tracker.core.summary import NightRecord, summarize_history, weekly_sleep_debt

TODAY = date(2026, 9, 10)


def rec(days_ago: int, score: int, hours: float = 8.0) -> NightRecord:
    return NightRecord(sleep_date=TODAY - timedelta(days=days_ago), score=score, total_sleep_hours=hours)


def test_empty_history():
    summary = summarize_history([], TODAY)
    assert summary.avg_score_7d is None
    assert summary.avg_score_30d is None
    assert summary.nights_7d == summary.nights_30d == 0
    assert summary.sleep_debt_week_hours == 0
    assert summary.trend.direction is None


def test_windows_include_today_and_are_exactly_7_and_30_days():
    records = [rec(0, 90), rec(6, 70), rec(7, 10), rec(29, 50), rec(30, 0)]
    summary = summarize_history(records, TODAY)

    assert summary.nights_7d == 2  # 0 и 6 дней назад; 7 дней назад — уже прошлая неделя
    assert summary.avg_score_7d == 80
    assert summary.nights_30d == 4  # 30 дней назад в окно не входит
    assert summary.avg_score_30d == pytest.approx(55.0)


def test_future_nights_are_ignored():
    summary = summarize_history([rec(0, 80), rec(-1, 10)], TODAY)
    assert summary.nights_7d == 1
    assert summary.avg_score_7d == 80


def test_sleep_debt_counts_only_shortfall_in_the_last_week():
    records = [
        rec(0, 60, hours=6.0),  # −2 ч
        rec(1, 70, hours=7.5),  # −0.5 ч
        rec(2, 90, hours=10.0),  # пересып не гасит недосып
        rec(8, 40, hours=4.0),  # прошлая неделя — не считается
    ]
    assert summarize_history(records, TODAY).sleep_debt_week_hours == 2.5


def test_sleep_debt_uses_custom_norm():
    assert weekly_sleep_debt([rec(0, 80, hours=7.0)], norm_hours=7.5) == 0.5


@pytest.mark.parametrize(
    ("this_week", "last_week", "direction", "delta"),
    [
        ([80, 84], [70, 72], "up", 11.0),
        ([60, 62], [75, 77], "down", -15.0),
        ([75, 76], [74, 75], "flat", 1.0),
    ],
)
def test_trend_compares_this_week_with_previous(this_week, last_week, direction, delta):
    records = [rec(i, s) for i, s in enumerate(this_week)] + [rec(7 + i, s) for i, s in enumerate(last_week)]
    trend = summarize_history(records, TODAY).trend
    assert trend.direction == direction
    assert trend.delta == delta


def test_trend_is_unknown_without_previous_week():
    trend = summarize_history([rec(0, 80), rec(3, 70)], TODAY).trend
    assert trend.direction is None
    assert trend.delta is None
    assert trend.avg_score_prev_7d is None


def test_to_dict_keeps_dates():
    data = summarize_history([rec(0, 80)], TODAY).to_dict()
    assert data["as_of"] == TODAY
    assert data["trend"] == {"direction": None, "delta": None, "avg_score_prev_7d": None}
