"""FastAPI-приложение SleepTrack.

    POST /api/sleep-check        оценка ночи; с ?save=true — ещё и сохранение в историю
    GET  /api/history?limit=30   последние N сохранённых ночей, от свежих к старым
    GET  /api/history/summary    средний балл за 7/30 дней, тренд, недосып за неделю
    GET  /health                 состояние сервиса и БД
    GET  /                       приветствие

Скоринг, советы и агрегаты считаются в sleep_tracker.core — здесь только HTTP и БД.
База нужна лишь для истории: если она недоступна, /api/sleep-check продолжает
работать, просто без компонента регулярности режима (история не читается).
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from . import crud
from .core.recommendations import build_recommendations
from .core.sleep_score import HISTORY_WINDOW, calculate_sleep_score
from .core.summary import summarize_history
from .database import SessionLocal, ensure_schema, get_session
from .schemas import HistoryEntry, HistorySummary, SleepCheckRequest, SleepCheckResponse

logger = logging.getLogger("sleep_tracker")

# Фронтенд в dev-режиме (npm start) открывается на :3000.
CORS_ORIGINS = os.getenv("SLEEPTRACK_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Пробуем создать таблицы сразу, но не падаем, если базы нет: ensure_schema
    # повторит попытку при первом запросе к истории.
    with SessionLocal() as session:
        try:
            ensure_schema(session)
        except SQLAlchemyError as exc:
            logger.warning("БД недоступна, история отключена до восстановления: %s", exc)
    yield


app = FastAPI(
    title="SleepTrack API",
    description="Оценка качества сна за ночь, рекомендации и тренд по истории.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])


def _db_unavailable() -> HTTPException:
    return HTTPException(503, "База данных недоступна — история временно не работает.")


@app.get("/")
def root() -> dict:
    return {"message": "SleepTrack API — оценка качества сна. Документация: /docs"}


@app.get("/health")
def health(db: Session = Depends(get_session)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unavailable"
    # Сервис жив и без БД — поэтому всегда 200, а состояние базы отдельным полем.
    return {"status": "ok", "database": database}


@app.post("/api/sleep-check", response_model=SleepCheckResponse)
def sleep_check(
    payload: SleepCheckRequest,
    save: bool = Query(False, description="Сохранить ночь в историю"),
    db: Session = Depends(get_session),
) -> SleepCheckResponse:
    night = payload.to_night()
    sleep_date = payload.sleep_date or date.today()

    try:
        ensure_schema(db)
        previous = crud.previous_bedtimes(db, before=sleep_date, limit=HISTORY_WINDOW)
    except SQLAlchemyError as exc:
        db.rollback()
        if save:
            raise _db_unavailable() from exc
        logger.warning("История недоступна, считаем без регулярности режима: %s", exc)
        previous = []

    result = calculate_sleep_score(night, previous)
    recommendations = build_recommendations(night, result)

    entry_id, replaced = None, False
    if save:
        try:
            entry, replaced = crud.upsert_entry(db, sleep_date, night, result)
        except SQLAlchemyError as exc:
            db.rollback()
            raise _db_unavailable() from exc
        entry_id = entry.id

    return SleepCheckResponse(
        sleep_date=sleep_date,
        **result.to_dict(),
        recommendations=[{"component": r.component, "text": r.text} for r in recommendations],
        saved=save,
        entry_id=entry_id,
        replaced_existing=replaced,
    )


@app.get("/api/history", response_model=list[HistoryEntry])
def history(
    limit: int = Query(30, ge=1, le=365, description="Сколько последних ночей вернуть"),
    db: Session = Depends(get_session),
) -> list:
    try:
        ensure_schema(db)
        return crud.latest_entries(db, limit)
    except SQLAlchemyError as exc:
        raise _db_unavailable() from exc


@app.get("/api/history/summary", response_model=HistorySummary)
def history_summary(
    as_of: date | None = Query(
        None, description="На какую дату считать окна 7/30 дней. По умолчанию — сегодня по часам сервера."
    ),
    db: Session = Depends(get_session),
):
    today = as_of or date.today()
    try:
        ensure_schema(db)
        records = crud.night_records(db, start=today - timedelta(days=29), end=today)
    except SQLAlchemyError as exc:
        raise _db_unavailable() from exc
    return summarize_history(records, today)
