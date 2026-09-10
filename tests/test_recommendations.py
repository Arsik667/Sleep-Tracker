from datetime import time
from itertools import product

import pytest

from sleep_tracker.core.recommendations import MAX_TIPS, MIN_TIPS, TIPS, build_recommendations
from sleep_tracker.core.sleep_score import NightData, calculate_sleep_score

STEADY_BEDTIMES = [time(23, 0), time(23, 10), time(22, 50), time(23, 0)]


def tips_for(previous_bedtimes=(), **overrides):
    params = dict(bedtime=time(23, 0), wake_time=time(7, 0), total_sleep_hours=7.6, waso_minutes=10, awakenings=1)
    params.update(overrides)
    night = NightData(**params)
    return build_recommendations(night, calculate_sleep_score(night, previous_bedtimes))


def texts(tips):
    return [tip.text for tip in tips]


def test_great_night_gets_two_general_tips():
    tips = tips_for(STEADY_BEDTIMES, deep_sleep_minutes=90, rem_sleep_minutes=110)
    assert texts(tips) == [TIPS["keep_it_up"], TIPS["morning_light"]]


def test_without_history_and_stages_suggests_to_log_more():
    tips = tips_for()
    assert texts(tips) == [TIPS["log_more"], TIPS["track_stages"]]


def test_short_and_long_sleep_get_different_tips():
    short = tips_for(bedtime=time(1, 30), wake_time=time(6, 0), total_sleep_hours=4.2)
    long = tips_for(bedtime=time(21, 0), wake_time=time(8, 0), total_sleep_hours=10.5)
    assert short[0].text == TIPS["duration_short"]
    assert long[0].text == TIPS["duration_long"]


def test_tips_are_ranked_by_points_lost():
    # continuity стоит ~31 балл, efficiency ~12, кофеин — 5; duration (83) слабым не считается.
    tips = tips_for(total_sleep_hours=6.5, waso_minutes=80, awakenings=7, caffeine_after_14=True)
    assert [tip.component for tip in tips] == ["continuity", "efficiency", "caffeine_after_14"]


def test_no_more_than_four_tips():
    tips = tips_for(
        [time(21, 0), time(2, 0), time(0, 30)],
        bedtime=time(3, 0), wake_time=time(9, 0), total_sleep_hours=3.5, waso_minutes=100, awakenings=9,
        deep_sleep_minutes=5, rem_sleep_minutes=10, caffeine_after_14=True, screen_before_bed=True,
    )
    # Все компоненты на нуле — порядок решают веса: 25 % > 20 % > 15 %, штрафы не влезли.
    assert [tip.component for tip in tips] == ["efficiency", "continuity", "duration", "stages"]
    assert len(tips) == MAX_TIPS


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"total_sleep_hours": 7.0, "waso_minutes": 60, "awakenings": 1}, "continuity_waso"),
        ({"waso_minutes": 10, "awakenings": 6}, "continuity_awakenings"),
        ({"deep_sleep_minutes": 90, "rem_sleep_minutes": 40}, "stages_rem"),
        ({"deep_sleep_minutes": 20, "rem_sleep_minutes": 110}, "stages_deep"),
    ],
)
def test_tip_variant_matches_what_went_wrong(overrides, expected):
    assert TIPS[expected] in texts(tips_for(**overrides))


def test_penalty_tips_mention_points():
    tips = tips_for(STEADY_BEDTIMES, deep_sleep_minutes=90, rem_sleep_minutes=110, screen_before_bed=True)
    assert tips[0].component == "screen_before_bed"
    assert "−3" in tips[0].text


@pytest.mark.parametrize(
    ("sleep_hours", "waso", "awakenings", "stages", "history", "caffeine"),
    list(product([4.5, 6.0, 7.5], [0, 30], [0, 5], [None, (60, 60)], [(), STEADY_BEDTIMES], [False, True])),
)
def test_always_between_two_and_four_unique_tips(sleep_hours, waso, awakenings, stages, history, caffeine):
    deep, rem = stages or (None, None)
    tips = tips_for(
        history, total_sleep_hours=sleep_hours, waso_minutes=waso, awakenings=awakenings,
        deep_sleep_minutes=deep, rem_sleep_minutes=rem, caffeine_after_14=caffeine,
    )
    assert MIN_TIPS <= len(tips) <= MAX_TIPS
    assert len(set(texts(tips))) == len(tips)
