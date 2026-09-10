import json
import subprocess
import sys
from datetime import time

import pytest

from sleep_tracker.core.sleep_score import (
    HISTORY_WINDOW,
    NightData,
    bedtime_spread_minutes,
    calculate_sleep_score,
    categorize,
    duration_cap,
    minutes_between,
    piecewise,
)

# Отбой около 23:00 каждый день — стабильный режим.
STEADY_BEDTIMES = [time(23, 5), time(22, 55), time(23, 0), time(23, 10), time(22, 50), time(23, 0)]


def night(**overrides) -> NightData:
    """Хорошая ночь по умолчанию: 23:00–07:00, 7.6 ч сна, почти без пробуждений."""
    params = dict(
        bedtime=time(23, 0),
        wake_time=time(7, 0),
        total_sleep_hours=7.6,
        waso_minutes=10,
        awakenings=1,
    )
    params.update(overrides)
    return NightData(**params)


# --- основные сценарии из плана -------------------------------------------------------


def test_perfect_night_scores_100():
    result = calculate_sleep_score(
        night(deep_sleep_minutes=90, rem_sleep_minutes=110), STEADY_BEDTIMES
    )

    assert result.score == 100
    assert result.category == "excellent"
    assert all(c.score == 100 for c in result.components)
    assert result.penalties == []
    assert result.score_cap is None
    assert result.sleep_efficiency == 95.0
    assert result.time_in_bed_hours == 8.0


def test_short_night_is_capped_to_poor():
    # 4.2 ч сна, но в постели почти не бодрствовали: эффективность и непрерывность на 100.
    result = calculate_sleep_score(night(bedtime=time(1, 30), wake_time=time(6, 0), total_sleep_hours=4.2))

    assert result.component("duration").score == pytest.approx(6.7)
    assert result.component("efficiency").score == 100
    # Взвешенное среднее было бы 73 («good») — потолок при 4.2 ч опускает его до 34.
    assert result.score == 34
    assert result.score_cap == 34
    assert result.category == "poor"
    assert result.sleep_debt_hours == 3.8


def test_under_six_hours_cannot_be_better_than_fair():
    result = calculate_sleep_score(
        night(bedtime=time(0, 30), wake_time=time(6, 30), total_sleep_hours=5.8), STEADY_BEDTIMES
    )
    assert result.score == 66
    assert result.category == "fair"


def test_six_and_a_half_hours_cannot_be_excellent():
    # Всё остальное идеально, но 6.4 ч сна — это «хорошо», а не «отлично».
    result = calculate_sleep_score(
        night(wake_time=time(6, 0), total_sleep_hours=6.4, deep_sleep_minutes=80, rem_sleep_minutes=90),
        STEADY_BEDTIMES,
    )
    assert result.score == 82
    assert result.category == "good"


@pytest.mark.parametrize(
    ("hours", "cap"),
    [(3.0, 30), (4.2, 34), (4.99, 49), (5.0, 50), (5.99, 69), (6.4, 82), (6.9, 97), (7.0, None), (9.5, None)],
)
def test_duration_cap_is_a_smooth_curve(hours, cap):
    assert duration_cap(hours) == cap


def test_cap_is_not_reported_when_score_is_already_lower():
    result = calculate_sleep_score(
        night(
            bedtime=time(1, 0), wake_time=time(7, 0), total_sleep_hours=5.0, waso_minutes=60, awakenings=6,
            caffeine_after_14=True,
        )
    )
    assert result.score < 50
    assert result.score_cap is None


def test_many_awakenings_hurt_continuity():
    calm = calculate_sleep_score(night())
    restless = calculate_sleep_score(night(total_sleep_hours=6.5, waso_minutes=80, awakenings=7))

    continuity = restless.component("continuity")
    assert continuity.parts == {"waso": pytest.approx(14.3), "awakenings": pytest.approx(14.3)}
    assert continuity.score == pytest.approx(14.3)
    assert restless.score < calm.score - 30


def test_missing_stages_give_neutral_contribution():
    # Все известные компоненты на 100 — отсутствие стадий и истории не должно снижать балл.
    result = calculate_sleep_score(night())

    stages = result.component("stages")
    assert stages.score is None
    assert stages.applied_weight == 0
    assert result.component("consistency").score is None
    assert result.score == 100
    # Вес недоступных компонентов перераспределён: 0.20 / 0.70 и т. д.
    assert result.component("duration").applied_weight == pytest.approx(0.2857, abs=1e-4)
    assert sum(c.applied_weight for c in result.components) == pytest.approx(1.0, abs=1e-3)


def test_only_one_stage_given():
    # 40 мин глубокого сна из 7.6 ч — это 8.8 %, между 5 % (0 баллов) и 15 % (100).
    result = calculate_sleep_score(night(deep_sleep_minutes=40))
    stages = result.component("stages")
    assert set(stages.parts) == {"deep"}
    assert stages.score == pytest.approx(37.7)


def test_low_stages_lower_the_score():
    good = calculate_sleep_score(night(deep_sleep_minutes=90, rem_sleep_minutes=110))
    poor = calculate_sleep_score(night(deep_sleep_minutes=15, rem_sleep_minutes=30))
    assert poor.component("stages").score == 0
    assert poor.score < good.score


# --- регулярность режима --------------------------------------------------------------


def test_consistency_needs_at_least_two_previous_nights():
    result = calculate_sleep_score(night(), [time(23, 0)])
    assert result.component("consistency").score is None
    assert result.bedtime_sd_minutes is None
    assert result.history_nights_used == 1


def test_irregular_bedtime_lowers_consistency():
    chaotic = [time(21, 30), time(1, 30), time(23, 0), time(2, 0), time(22, 0)]
    steady = calculate_sleep_score(night(), STEADY_BEDTIMES)
    irregular = calculate_sleep_score(night(), chaotic)

    assert steady.component("consistency").score == 100
    assert irregular.bedtime_sd_minutes > 90
    assert irregular.component("consistency").score == 0
    assert irregular.score < steady.score


def test_only_last_seven_nights_are_used():
    history = STEADY_BEDTIMES + [time(23, 0)] + [time(3, 0)] * 5  # старые ночи с отбоем в 3:00
    result = calculate_sleep_score(night(), history)
    assert result.history_nights_used == HISTORY_WINDOW
    assert result.component("consistency").score == 100


def test_bedtime_spread_ignores_midnight_wrap():
    # 23:50, 00:10, 00:00 — разница в 20 минут, а не почти сутки.
    assert bedtime_spread_minutes([time(23, 50), time(0, 10), time(0, 0)]) == pytest.approx(8.16, abs=0.01)


# --- штрафы и категории ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("flags", "expected_drop"),
    [
        ({"caffeine_after_14": True}, 5),
        ({"screen_before_bed": True}, 3),
        ({"caffeine_after_14": True, "screen_before_bed": True}, 8),
    ],
)
def test_penalties(flags, expected_drop):
    base = calculate_sleep_score(night())
    penalized = calculate_sleep_score(night(**flags))
    assert base.score - penalized.score == expected_drop
    assert sum(p.points for p in penalized.penalties) == expected_drop


def test_score_never_goes_below_zero():
    awful = night(
        bedtime=time(3, 0), wake_time=time(9, 0), total_sleep_hours=3.0, waso_minutes=150,
        awakenings=12, deep_sleep_minutes=0, rem_sleep_minutes=0,
        caffeine_after_14=True, screen_before_bed=True,
    )
    assert calculate_sleep_score(awful).score == 0


@pytest.mark.parametrize(
    ("score", "category"),
    [(100, "excellent"), (85, "excellent"), (84, "good"), (70, "good"), (69, "fair"), (50, "fair"), (49, "poor"), (0, "poor")],
)
def test_categories(score, category):
    assert categorize(score) == category


def test_result_is_json_serializable():
    result = calculate_sleep_score(night(deep_sleep_minutes=90), STEADY_BEDTIMES)
    data = json.loads(json.dumps(result.to_dict()))
    assert data["score"] == result.score
    assert [c["name"] for c in data["components"]] == [
        "duration", "efficiency", "continuity", "stages", "consistency",
    ]


# --- валидация входа ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"total_sleep_hours": 0}, "больше 0"),
        ({"total_sleep_hours": 25}, "не больше 24"),
        ({"waso_minutes": -5}, "WASO"),
        ({"awakenings": -1}, "пробуждений"),
        ({"deep_sleep_minutes": -10}, "глубокого"),
        ({"wake_time": time(23, 0)}, "совпадают"),
        ({"total_sleep_hours": 8.5}, "больше, чем времени в постели"),
        ({"waso_minutes": 45}, "WASO не помещается"),
        ({"deep_sleep_minutes": 300, "rem_sleep_minutes": 200}, "больше общего времени сна"),
    ],
)
def test_invalid_nights_are_rejected(overrides, message):
    with pytest.raises(ValueError, match=message):
        night(**overrides)


def test_small_rounding_in_the_form_is_tolerated():
    # 8 ч в постели, пользователь округлил сон до 8.05 ч — это не ошибка ввода.
    assert night(total_sleep_hours=8.05, waso_minutes=0).time_in_bed_hours == 8


# --- вспомогательные функции ----------------------------------------------------------


def test_minutes_between_crosses_midnight():
    assert minutes_between(time(23, 30), time(7, 0)) == 450
    assert minutes_between(time(1, 0), time(9, 15)) == 495


def test_piecewise_interpolates_and_clamps():
    curve = [(4, 0), (7, 100), (9, 100), (12, 40)]
    assert piecewise(3, curve) == 0
    assert piecewise(5.5, curve) == 50
    assert piecewise(8, curve) == 100
    assert piecewise(10.5, curve) == 70
    assert piecewise(15, curve) == 40


def test_core_does_not_import_web_or_db_libraries():
    code = (
        "import sys, sleep_tracker.core.sleep_score; "
        "print(sorted(m for m in ('fastapi', 'sqlalchemy', 'pydantic') if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"
