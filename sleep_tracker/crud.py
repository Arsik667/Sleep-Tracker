"""Запросы к БД. Все функции принимают сессию и бросают SQLAlchemyError, если база недоступна."""

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.sleep_score import NightData, SleepScore
from .core.summary import NightRecord
from .models import SleepEntry


def previous_bedtimes(db: Session, before: date, limit: int) -> list[time]:
    """Отбой последних `limit` сохранённых ночей строго до даты `before`, от свежих к старым."""
    stmt = (
        select(SleepEntry.bedtime)
        .where(SleepEntry.sleep_date < before)
        .order_by(SleepEntry.sleep_date.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def upsert_entry(db: Session, sleep_date: date, night: NightData, result: SleepScore) -> tuple[SleepEntry, bool]:
    """Сохраняет ночь; если за эту дату запись уже есть — перезаписывает её.

    Возвращает (запись, была_ли_перезаписана).
    """
    entry = db.scalar(select(SleepEntry).where(SleepEntry.sleep_date == sleep_date))
    replaced = entry is not None
    if entry is None:
        entry = SleepEntry(sleep_date=sleep_date)
        db.add(entry)

    entry.bedtime = night.bedtime
    entry.wake_time = night.wake_time
    entry.total_sleep_hours = night.total_sleep_hours
    entry.waso_minutes = night.waso_minutes
    entry.awakenings = night.awakenings
    entry.deep_sleep_minutes = night.deep_sleep_minutes
    entry.rem_sleep_minutes = night.rem_sleep_minutes
    entry.caffeine_after_14 = night.caffeine_after_14
    entry.screen_before_bed = night.screen_before_bed
    entry.score = result.score
    entry.category = result.category

    db.commit()
    db.refresh(entry)
    return entry, replaced


def latest_entries(db: Session, limit: int) -> list[SleepEntry]:
    stmt = select(SleepEntry).order_by(SleepEntry.sleep_date.desc()).limit(limit)
    return list(db.scalars(stmt))


def night_records(db: Session, start: date, end: date) -> list[NightRecord]:
    """Ночи с `start` по `end` включительно — в том виде, что нужен core.summary."""
    stmt = (
        select(SleepEntry.sleep_date, SleepEntry.score, SleepEntry.total_sleep_hours)
        .where(SleepEntry.sleep_date.between(start, end))
        .order_by(SleepEntry.sleep_date)
    )
    return [NightRecord(*row) for row in db.execute(stmt)]
