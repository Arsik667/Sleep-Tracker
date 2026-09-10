"""Демо-данные: заполняет историю синтетическими ночами, чтобы было на что посмотреть на графике.

    python -m sleep_tracker.seed_demo                # 30 ночей по сегодняшнюю дату
    python -m sleep_tracker.seed_demo --days 45 --seed 1
    python -m sleep_tracker.seed_demo --overwrite    # перезаписать ночи, которые уже есть

Сюжет данных: человек постепенно налаживает режим — отбой становится раньше и ровнее,
сна больше, кофеина и экранов вечером меньше. Оценка считается тем же core, что и в API.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from . import crud
from .core.sleep_score import HISTORY_WINDOW, NightData, calculate_sleep_score
from .database import SessionLocal, ensure_schema
from .models import SleepEntry


@dataclass(frozen=True)
class DemoNight:
    sleep_date: date
    night: NightData


def generate_nights(days: int, end: date, seed: int = 11) -> list[DemoNight]:
    """Ночи с (end − days + 1) по end, от старых к новым."""
    rng = random.Random(seed)
    nights = []
    for i in range(days):
        sleep_date = end - timedelta(days=days - 1 - i)
        progress = i / max(days - 1, 1)  # 0 — начало истории, 1 — сегодня
        weekend = sleep_date.weekday() in (5, 6)  # ночи на субботу и воскресенье

        # Отбой: от ~23:55 к ~23:15, разброс сужается; в выходные — позже.
        bedtime_minutes = 23 * 60 + 55 - 40 * progress + rng.gauss(0, 40 - 25 * progress) + (50 if weekend else 0)
        sleep_hours = min(9.0, max(4.5, rng.gauss(5.9 + 1.5 * progress, 0.5)))
        waso = max(0, round(rng.gauss(45 - 28 * progress, 12)))
        awakenings = max(0, round(rng.gauss(4 - 2.5 * progress, 1)))
        latency = rng.randint(8, 25)  # засыпание — в постели, но ещё не сон
        in_bed_minutes = sleep_hours * 60 + waso + latency

        bedtime = _clock(bedtime_minutes)
        wake_time = _clock(bedtime_minutes + in_bed_minutes)
        sleep_minutes = sleep_hours * 60
        nights.append(
            DemoNight(
                sleep_date,
                NightData(
                    bedtime=bedtime,
                    wake_time=wake_time,
                    total_sleep_hours=round(sleep_hours, 2),
                    waso_minutes=waso,
                    awakenings=awakenings,
                    deep_sleep_minutes=round(sleep_minutes * rng.uniform(0.12, 0.2)),
                    rem_sleep_minutes=round(sleep_minutes * rng.uniform(0.15, 0.24)),
                    caffeine_after_14=rng.random() < 0.45 - 0.35 * progress,
                    screen_before_bed=rng.random() < 0.7 - 0.45 * progress,
                ),
            )
        )
    return nights


def seed(session, nights: list[DemoNight], overwrite: bool = False) -> int:
    """Пишет ночи в БД. Без overwrite отказывается трогать даты, за которые уже есть записи."""
    ensure_schema(session)
    dates = [n.sleep_date for n in nights]
    existing = session.scalars(select(SleepEntry.sleep_date).where(SleepEntry.sleep_date.in_(dates))).all()
    if existing and not overwrite:
        raise SystemExit(
            f"В истории уже есть {len(existing)} ноч(ей) в этом диапазоне — ничего не записано. "
            "Запустите с --overwrite, чтобы заменить их демо-данными."
        )

    for demo in nights:
        # Регулярность — по уже записанным ночам до этой даты, ровно как в API.
        previous = crud.previous_bedtimes(session, before=demo.sleep_date, limit=HISTORY_WINDOW)
        result = calculate_sleep_score(demo.night, previous)
        crud.upsert_entry(session, demo.sleep_date, demo.night, result)
    return len(nights)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sleep_tracker.seed_demo", description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=30, help="сколько ночей сгенерировать (по умолчанию 30)")
    parser.add_argument("--seed", type=int, default=11, help="seed генератора — одинаковые данные при повторном запуске")
    parser.add_argument("--overwrite", action="store_true", help="заменить уже сохранённые ночи в этом диапазоне")
    args = parser.parse_args(argv)

    nights = generate_nights(args.days, end=date.today(), seed=args.seed)
    with SessionLocal() as session:
        count = seed(session, nights, overwrite=args.overwrite)
    print(f"Записано ночей: {count} ({nights[0].sleep_date} — {nights[-1].sleep_date})")
    return 0


def _clock(minutes: float) -> time:
    minutes = round(minutes) % (24 * 60)
    return (datetime.min + timedelta(minutes=minutes)).time()


if __name__ == "__main__":
    raise SystemExit(main())
