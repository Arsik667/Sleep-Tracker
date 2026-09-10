"""ORM-модель одной сохранённой ночи."""

from datetime import UTC, date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SleepEntry(Base):
    """Запись дневника сна: всё, что ввели в форму, плюс посчитанная оценка.

    Одна ночь — одна запись: sleep_date уникальна, повторное сохранение за ту же
    дату перезаписывает запись, а не создаёт дубль (иначе поехали бы средние и недосып).
    """

    __tablename__ = "sleep_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Дата утра, когда проснулись: ночь с 9 на 10 сентября — это 10 сентября.
    sleep_date: Mapped[date] = mapped_column(Date, unique=True, index=True)

    bedtime: Mapped[time] = mapped_column(Time)
    wake_time: Mapped[time] = mapped_column(Time)
    total_sleep_hours: Mapped[float] = mapped_column(Float)
    waso_minutes: Mapped[int] = mapped_column(Integer, default=0)
    awakenings: Mapped[int] = mapped_column(Integer, default=0)
    deep_sleep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rem_sleep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    caffeine_after_14: Mapped[bool] = mapped_column(Boolean, default=False)
    screen_before_bed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Оценка на момент сохранения: если формулу потом поменяют, старые записи не «переедут».
    score: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SleepEntry {self.sleep_date} score={self.score}>"
