"""Оценка качества одной ночи — чистые функции, без FastAPI и SQLAlchemy.

Итоговый балл 0–100 — взвешенное среднее пяти компонентов минус штрафы:

    duration     20%  общее время сна, оптимум 7–9 ч
    efficiency   25%  время сна / время в постели
    continuity   25%  время без сна посреди ночи (WASO) и число пробуждений
    stages       15%  доля глубокого и REM-сна — если указаны
    consistency  15%  разброс времени отбоя по последним сохранённым ночам

    штрафы: кофеин после 14:00 −5, экран перед сном −3

    потолок: при коротком сне балл не выше кривой — 50 при 5 ч, 70 при 6 ч,
             с 7 ч потолка нет (меньше 5 ч — всегда poor, меньше 6 ч — не выше fair)

Потолок нужен из-за того, что у длительности всего 20% веса: без него ночь
на 4 часа с хорошей эффективностью набирала бы ~80 баллов и получала «good»,
а 6 часов сна легко дотягивали бы до «excellent». Потолок — тоже кривая,
а не ступеньки: 6 ч 59 мин и 7 ч не должны отличаться на полкатегории.

Компонент, который посчитать нельзя (стадии не указаны, истории мало), не тянет
оценку ни вверх, ни вниз: его вес делится между остальными пропорционально.
Это и есть «нейтральный вклад» — балл равен среднему по тому, что известно.

Каждый компонент — кусочно-линейная функция по нескольким опорным точкам
(кривые *_CURVE ниже). Так формулу легко прочитать, объяснить и поменять.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import time
from statistics import pstdev

WEIGHTS: dict[str, float] = {
    "duration": 0.20,
    "efficiency": 0.25,
    "continuity": 0.25,
    "stages": 0.15,
    "consistency": 0.15,
}
PENALTIES: dict[str, int] = {
    "caffeine_after_14": 5,
    "screen_before_bed": 3,
}
# Категория — первая, чей порог не выше балла.
CATEGORIES: list[tuple[int, str]] = [(85, "excellent"), (70, "good"), (50, "fair"), (0, "poor")]

SLEEP_NORM_HOURS = 8.0  # норма для расчёта недосыпа
HISTORY_WINDOW = 7  # сколько последних сохранённых ночей берём для consistency
MIN_HISTORY_NIGHTS = 2  # меньше — разброс не считаем: по одной точке режим не оценить
TOLERANCE_HOURS = 5 / 60  # люфт на округление в форме при сверке полей между собой

# Опорные точки (x, балл). Между точками — линейно, за краями — значение крайней точки.
DURATION_CURVE = [(4, 0), (7, 100), (9, 100), (12, 40)]  # часы сна
EFFICIENCY_CURVE = [(65, 0), (85, 80), (90, 100)]  # % времени в постели, проведённого во сне
WASO_CURVE = [(20, 100), (90, 0)]  # минуты без сна после засыпания
AWAKENINGS_CURVE = [(1, 100), (8, 0)]  # число пробуждений
DEEP_CURVE = [(5, 0), (15, 100)]  # % глубокого сна от общего сна
REM_CURVE = [(10, 0), (20, 100)]  # % REM-сна от общего сна
BEDTIME_SD_CURVE = [(15, 100), (90, 0)]  # стандартное отклонение отбоя, минуты
DURATION_CAP_CURVE = [(4, 30), (5, 50), (6, 70), (7, 100)]  # часы сна → максимальный итоговый балл

CONTINUITY_WASO_SHARE = 0.6  # в continuity WASO важнее числа пробуждений

MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class NightData:
    """Параметры одной ночи. Проверяет себя при создании и бросает ValueError с понятным текстом."""

    bedtime: time
    wake_time: time
    total_sleep_hours: float
    waso_minutes: int = 0
    awakenings: int = 0
    deep_sleep_minutes: int | None = None
    rem_sleep_minutes: int | None = None
    caffeine_after_14: bool = False
    screen_before_bed: bool = False

    def __post_init__(self) -> None:
        problems = self._problems()
        if problems:
            raise ValueError("; ".join(problems))

    @property
    def time_in_bed_hours(self) -> float:
        return minutes_between(self.bedtime, self.wake_time) / 60

    def _problems(self) -> list[str]:
        problems = []
        if not 0 < self.total_sleep_hours <= 24:
            problems.append("общее время сна должно быть больше 0 и не больше 24 часов")
        if self.waso_minutes < 0:
            problems.append("WASO не может быть отрицательным")
        if self.awakenings < 0:
            problems.append("число пробуждений не может быть отрицательным")
        for name, value in (("глубокого", self.deep_sleep_minutes), ("REM", self.rem_sleep_minutes)):
            if value is not None and value < 0:
                problems.append(f"минуты {name} сна не могут быть отрицательными")
        if problems:
            return problems  # дальше сверяем поля между собой — с мусором это бессмысленно

        in_bed = self.time_in_bed_hours
        if in_bed == 0:
            return ["время отбоя и подъёма совпадают"]
        if self.total_sleep_hours > in_bed + TOLERANCE_HOURS:
            problems.append(
                f"сна {self.total_sleep_hours:g} ч — больше, чем времени в постели ({in_bed:.2f} ч)"
            )
        elif self.total_sleep_hours + self.waso_minutes / 60 > in_bed + TOLERANCE_HOURS:
            problems.append("сон вместе с WASO не помещается во время в постели")
        stages_minutes = (self.deep_sleep_minutes or 0) + (self.rem_sleep_minutes or 0)
        if stages_minutes / 60 > self.total_sleep_hours + TOLERANCE_HOURS:
            problems.append("глубокий и REM-сон вместе больше общего времени сна")
        return problems


@dataclass(frozen=True)
class ComponentScore:
    name: str
    score: float | None  # None — компонент посчитать нельзя
    weight: float  # вес из формулы
    applied_weight: float  # вес после перераспределения недоступных компонентов
    parts: dict[str, float] = field(default_factory=dict)  # подоценки внутри компонента


@dataclass(frozen=True)
class Penalty:
    name: str
    points: int  # сколько баллов снято (положительное число)


@dataclass(frozen=True)
class SleepScore:
    score: int
    category: str
    components: list[ComponentScore]
    penalties: list[Penalty]
    score_cap: int | None  # потолок из-за короткого сна, если сработал
    time_in_bed_hours: float
    sleep_efficiency: float  # %
    bedtime_sd_minutes: float | None
    history_nights_used: int
    sleep_debt_hours: float  # недосып этой ночи относительно SLEEP_NORM_HOURS

    def component(self, name: str) -> ComponentScore:
        return next(c for c in self.components if c.name == name)

    def to_dict(self) -> dict:
        return asdict(self)


def minutes_between(start: time, end: time) -> int:
    """Минуты от start до end; если end «раньше» — значит, перешли через полночь."""
    return (_minutes(end) - _minutes(start)) % MINUTES_PER_DAY


def piecewise(x: float, points: Sequence[tuple[float, float]]) -> float:
    """Линейная интерполяция по опорным точкам, за краями — значение крайней точки."""
    if x <= points[0][0]:
        return float(points[0][1])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(points[-1][1])


def bedtime_spread_minutes(bedtimes: Sequence[time]) -> float:
    """Стандартное отклонение времени отбоя в минутах.

    Отбой бывает и в 23:40, и в 00:20. Если считать минуты от полуночи, это 1420 и 20 —
    разброс получится огромным, хотя разница всего 40 минут. Поэтому отсчитываем минуты
    от полудня: 23:40 → 700, 00:20 → 740, и полночь перестаёт быть разрывом.
    """
    shifted = [(_minutes(t) - 12 * 60) % MINUTES_PER_DAY for t in bedtimes]
    return pstdev(shifted)


def score_duration(total_sleep_hours: float) -> float:
    return piecewise(total_sleep_hours, DURATION_CURVE)


def score_efficiency(efficiency_percent: float) -> float:
    return piecewise(efficiency_percent, EFFICIENCY_CURVE)


def score_continuity(waso_minutes: int, awakenings: int) -> tuple[float, dict[str, float]]:
    parts = {
        "waso": piecewise(waso_minutes, WASO_CURVE),
        "awakenings": piecewise(awakenings, AWAKENINGS_CURVE),
    }
    score = CONTINUITY_WASO_SHARE * parts["waso"] + (1 - CONTINUITY_WASO_SHARE) * parts["awakenings"]
    return score, parts


def score_stages(night: NightData) -> tuple[float | None, dict[str, float]]:
    """Средняя подоценка по тем стадиям, что указаны; если ни одной — None."""
    sleep_minutes = night.total_sleep_hours * 60
    parts = {}
    if night.deep_sleep_minutes is not None:
        parts["deep"] = piecewise(night.deep_sleep_minutes / sleep_minutes * 100, DEEP_CURVE)
    if night.rem_sleep_minutes is not None:
        parts["rem"] = piecewise(night.rem_sleep_minutes / sleep_minutes * 100, REM_CURVE)
    if not parts:
        return None, parts
    return sum(parts.values()) / len(parts), parts


def categorize(score: int) -> str:
    return next(name for threshold, name in CATEGORIES if score >= threshold)


def duration_cap(total_sleep_hours: float) -> int | None:
    """Максимальный итоговый балл при таком сне; None — потолка нет (7 ч и больше)."""
    if total_sleep_hours >= DURATION_CAP_CURVE[-1][0]:
        return None
    # floor, чтобы 4.99 ч давали 49 (poor), а не 50; round убирает хвосты float вроде 65.9999999.
    return math.floor(round(piecewise(total_sleep_hours, DURATION_CAP_CURVE), 6))


def calculate_sleep_score(night: NightData, previous_bedtimes: Sequence[time] = ()) -> SleepScore:
    """Считает оценку ночи.

    previous_bedtimes — время отбоя прошлых сохранённых ночей, от свежих к старым.
    Берутся первые HISTORY_WINDOW; разброс считается по ним вместе с сегодняшним отбоем.
    """
    in_bed = night.time_in_bed_hours
    efficiency = min(100.0, night.total_sleep_hours / in_bed * 100)

    history = list(previous_bedtimes[:HISTORY_WINDOW])
    spread = bedtime_spread_minutes([night.bedtime, *history]) if len(history) >= MIN_HISTORY_NIGHTS else None

    continuity, continuity_parts = score_continuity(night.waso_minutes, night.awakenings)
    stages, stages_parts = score_stages(night)
    raw: dict[str, tuple[float | None, dict[str, float]]] = {
        "duration": (score_duration(night.total_sleep_hours), {}),
        "efficiency": (score_efficiency(efficiency), {}),
        "continuity": (continuity, continuity_parts),
        "stages": (stages, stages_parts),
        "consistency": (piecewise(spread, BEDTIME_SD_CURVE) if spread is not None else None, {}),
    }

    # Перераспределяем вес недоступных компонентов между доступными.
    available_weight = sum(WEIGHTS[name] for name, (score, _) in raw.items() if score is not None)
    components = [
        ComponentScore(
            name=name,
            score=_r(score) if score is not None else None,
            weight=WEIGHTS[name],
            applied_weight=round(WEIGHTS[name] / available_weight, 4) if score is not None else 0.0,
            parts={key: _r(value) for key, value in parts.items()},
        )
        for name, (score, parts) in raw.items()
    ]
    weighted = sum(WEIGHTS[name] * score for name, (score, _) in raw.items() if score is not None) / available_weight

    penalties = [
        Penalty(name, points)
        for name, points in PENALTIES.items()
        if getattr(night, name)
    ]
    final = _round_half_up(weighted) - sum(p.points for p in penalties)
    final = max(0, min(100, final))
    cap = duration_cap(night.total_sleep_hours)
    if cap is not None and final > cap:
        final = cap
    else:
        cap = None  # потолок есть, но оценка и так ниже — не показываем его

    return SleepScore(
        score=final,
        category=categorize(final),
        components=components,
        penalties=penalties,
        score_cap=cap,
        time_in_bed_hours=round(in_bed, 2),
        sleep_efficiency=_r(efficiency),
        bedtime_sd_minutes=_r(spread) if spread is not None else None,
        history_nights_used=len(history),
        sleep_debt_hours=round(max(0.0, SLEEP_NORM_HOURS - night.total_sleep_hours), 2),
    )


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _r(value: float) -> float:
    return round(value, 1)


def _round_half_up(value: float) -> int:
    # Встроенный round() округляет 82.5 до 82 («банковское» округление) — для баллов это странно.
    return math.floor(value + 0.5)
