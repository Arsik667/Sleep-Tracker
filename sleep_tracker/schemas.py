"""Pydantic-модели запросов и ответов API.

Проверка входа в два слоя:
- диапазоны отдельных полей (WASO ≥ 0, сон ≤ 24 ч и т. п.) — здесь, через Field,
  чтобы фронтенд получил ошибку, привязанную к конкретному полю;
- связи между полями (сон не больше времени в постели и т. п.) — в core.NightData,
  одна реализация на API и CLI. ValueError оттуда Pydantic превращает в ответ 422.
"""

from datetime import date, datetime, time, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .core.sleep_score import NightData

MINUTES_PER_DAY = 24 * 60
Category = Literal["excellent", "good", "fair", "poor"]


class SleepCheckRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sleep_date": "2026-09-10",
                "bedtime": "23:30",
                "wake_time": "07:00",
                "total_sleep_hours": 6.9,
                "waso_minutes": 20,
                "awakenings": 2,
                "deep_sleep_minutes": 80,
                "rem_sleep_minutes": 95,
                "caffeine_after_14": True,
                "screen_before_bed": False,
            }
        }
    )

    sleep_date: date | None = Field(
        None, description="Дата утра после ночи. По умолчанию — сегодня по часам сервера."
    )
    bedtime: time = Field(description="Время отбоя, ЧЧ:ММ")
    wake_time: time = Field(description="Время подъёма, ЧЧ:ММ")
    total_sleep_hours: float = Field(gt=0, le=24, description="Общее время сна, часы")
    waso_minutes: int = Field(0, ge=0, le=MINUTES_PER_DAY, description="Минуты без сна после засыпания")
    awakenings: int = Field(0, ge=0, le=100, description="Число пробуждений")
    deep_sleep_minutes: int | None = Field(None, ge=0, le=MINUTES_PER_DAY, description="Минуты глубокого сна")
    rem_sleep_minutes: int | None = Field(None, ge=0, le=MINUTES_PER_DAY, description="Минуты REM-сна")
    caffeine_after_14: bool = Field(False, description="Кофеин после 14:00")
    screen_before_bed: bool = Field(False, description="Экран перед сном")

    @field_validator("sleep_date")
    @classmethod
    def _not_in_future(cls, value: date | None) -> date | None:
        # +1 день — запас на часовые пояса: у пользователя может быть уже «завтра».
        if value is not None and value > date.today() + timedelta(days=1):
            raise ValueError("дата ночи не может быть в будущем")
        return value

    @field_validator("bedtime", "wake_time")
    @classmethod
    def _minutes_precision(cls, value: time) -> time:
        # Секунды и часовой пояс для дневника сна не нужны, а в БД хранится время без зоны.
        return value.replace(second=0, microsecond=0, tzinfo=None)

    @model_validator(mode="after")
    def _check_fields_together(self) -> "SleepCheckRequest":
        self.to_night()  # NightData сам проверит связи между полями
        return self

    def to_night(self) -> NightData:
        return NightData(
            bedtime=self.bedtime,
            wake_time=self.wake_time,
            total_sleep_hours=self.total_sleep_hours,
            waso_minutes=self.waso_minutes,
            awakenings=self.awakenings,
            deep_sleep_minutes=self.deep_sleep_minutes,
            rem_sleep_minutes=self.rem_sleep_minutes,
            caffeine_after_14=self.caffeine_after_14,
            screen_before_bed=self.screen_before_bed,
        )


class ComponentOut(BaseModel):
    name: str
    score: float | None
    weight: float
    applied_weight: float
    parts: dict[str, float]


class PenaltyOut(BaseModel):
    name: str
    points: int


class RecommendationOut(BaseModel):
    component: str
    text: str


class SleepCheckResponse(BaseModel):
    sleep_date: date
    score: int = Field(ge=0, le=100)
    category: Category
    components: list[ComponentOut]
    penalties: list[PenaltyOut]
    score_cap: int | None
    time_in_bed_hours: float
    sleep_efficiency: float
    bedtime_sd_minutes: float | None
    history_nights_used: int
    sleep_debt_hours: float
    recommendations: list[RecommendationOut]
    saved: bool = Field(description="Записана ли ночь в историю (?save=true)")
    entry_id: int | None = None
    replaced_existing: bool = Field(False, description="За эту дату уже была запись, и она перезаписана")


class HistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sleep_date: date
    bedtime: time
    wake_time: time
    total_sleep_hours: float
    waso_minutes: int
    awakenings: int
    deep_sleep_minutes: int | None
    rem_sleep_minutes: int | None
    caffeine_after_14: bool
    screen_before_bed: bool
    score: int
    category: Category
    created_at: datetime
    updated_at: datetime


class TrendOut(BaseModel):
    direction: Literal["up", "down", "flat"] | None
    delta: float | None
    avg_score_prev_7d: float | None


class HistorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    as_of: date
    avg_score_7d: float | None
    avg_score_30d: float | None
    nights_7d: int
    nights_30d: int
    sleep_debt_week_hours: float
    sleep_norm_hours: float
    trend: TrendOut
