from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from sleep_tracker.database import get_session, make_engine
from sleep_tracker.main import app

TODAY = date.today()
NIGHT = {
    "bedtime": "23:30",
    "wake_time": "07:00",
    "total_sleep_hours": 6.9,
    "waso_minutes": 20,
    "awakenings": 2,
}


def use_database(url: str) -> None:
    factory = sessionmaker(bind=make_engine(url), autoflush=False, expire_on_commit=False)

    def override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override


@pytest.fixture
def client(tmp_path):
    use_database(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_without_db(tmp_path):
    # Папки не существует — SQLite не сможет открыть файл, как будто Postgres лежит.
    use_database(f"sqlite:///{tmp_path / 'missing' / 'test.db'}")
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def check(client, save=False, **overrides):
    return client.post("/api/sleep-check", params={"save": save}, json={**NIGHT, **overrides})


def save_night(client, **overrides) -> dict:
    response = check(client, save=True, **overrides)
    assert response.status_code == 200, response.text
    return response.json()


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


# --- служебные роуты ------------------------------------------------------------------


def test_root_and_health(client):
    assert "SleepTrack" in client.get("/").json()["message"]
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


# --- оценка ---------------------------------------------------------------------------


def test_sleep_check_without_saving(client):
    response = check(client, caffeine_after_14=True)
    assert response.status_code == 200
    data = response.json()

    assert 0 <= data["score"] <= 100
    assert data["category"] in {"excellent", "good", "fair", "poor"}
    assert data["sleep_date"] == TODAY.isoformat()
    assert data["penalties"] == [{"name": "caffeine_after_14", "points": 5}]
    assert 2 <= len(data["recommendations"]) <= 4
    assert data["saved"] is False and data["entry_id"] is None
    assert client.get("/api/history").json() == []


def test_response_matches_cli_contract(client):
    # Одни и те же поля в API и в `cli --json` — фронтенд и скрипты читают одинаково.
    data = check(client).json()
    assert [c["name"] for c in data["components"]] == [
        "duration", "efficiency", "continuity", "stages", "consistency",
    ]
    assert set(data["recommendations"][0]) == {"component", "text"}


def test_save_writes_history(client):
    data = save_night(client, sleep_date=days_ago(1))
    assert data["saved"] is True
    assert isinstance(data["entry_id"], int)
    assert data["replaced_existing"] is False

    history = client.get("/api/history").json()
    assert len(history) == 1
    assert history[0]["sleep_date"] == days_ago(1)
    assert history[0]["bedtime"] == "23:30:00"
    assert history[0]["score"] == data["score"]


def test_saving_same_night_twice_replaces_entry(client):
    first = save_night(client, sleep_date=days_ago(0))
    second = save_night(client, sleep_date=days_ago(0), total_sleep_hours=5.0)

    assert second["replaced_existing"] is True
    assert second["entry_id"] == first["entry_id"]
    history = client.get("/api/history").json()
    assert len(history) == 1
    assert history[0]["total_sleep_hours"] == 5.0


def test_saved_history_feeds_consistency(client):
    for n, bedtime in [(3, "23:20"), (2, "23:40"), (1, "23:30")]:
        save_night(client, sleep_date=days_ago(n), bedtime=bedtime)

    data = check(client, sleep_date=days_ago(0)).json()
    consistency = next(c for c in data["components"] if c["name"] == "consistency")

    assert data["history_nights_used"] == 3
    assert data["bedtime_sd_minutes"] < 15
    assert consistency["score"] == 100


def test_history_only_looks_at_earlier_nights(client):
    # Ночи после проверяемой даты в регулярность не попадают — можно вносить задним числом.
    for n in (1, 2, 3):
        save_night(client, sleep_date=days_ago(n))
    data = check(client, sleep_date=days_ago(2)).json()
    assert data["history_nights_used"] == 1


def test_timezone_and_seconds_are_dropped(client):
    save_night(client, bedtime="23:30:45+05:00")
    assert client.get("/api/history").json()[0]["bedtime"] == "23:30:00"


# --- валидация ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"waso_minutes": -5}, "waso_minutes"),
        ({"awakenings": -1}, "awakenings"),
        ({"total_sleep_hours": 25}, "total_sleep_hours"),
        ({"total_sleep_hours": 0}, "total_sleep_hours"),
        ({"bedtime": "25:00"}, "bedtime"),
        ({"deep_sleep_minutes": -1}, "deep_sleep_minutes"),
    ],
)
def test_field_errors_point_to_the_field(client, overrides, field):
    response = check(client, **overrides)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == field


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"total_sleep_hours": 9}, "больше, чем времени в постели"),
        ({"deep_sleep_minutes": 300, "rem_sleep_minutes": 200}, "больше общего времени сна"),
        ({"wake_time": "23:30"}, "совпадают"),
    ],
)
def test_cross_field_errors(client, overrides, message):
    response = check(client, **overrides)
    assert response.status_code == 422
    assert message in response.json()["detail"][0]["msg"]


def test_future_date_is_rejected(client):
    response = check(client, sleep_date=(TODAY + timedelta(days=5)).isoformat())
    assert response.status_code == 422


@pytest.mark.parametrize("limit", [0, 1000])
def test_history_limit_is_bounded(client, limit):
    assert client.get("/api/history", params={"limit": limit}).status_code == 422


def test_history_limit_and_order(client):
    for n in range(5):
        save_night(client, sleep_date=days_ago(n))
    history = client.get("/api/history", params={"limit": 3}).json()
    assert [h["sleep_date"] for h in history] == [days_ago(0), days_ago(1), days_ago(2)]


# --- сводка ---------------------------------------------------------------------------


def test_summary_empty(client):
    data = client.get("/api/history/summary").json()
    assert data["avg_score_7d"] is None
    assert data["nights_7d"] == 0
    assert data["sleep_debt_week_hours"] == 0
    assert data["trend"]["direction"] is None


def test_summary_with_history(client):
    as_of = date(2026, 9, 10)
    nights = [
        (as_of - timedelta(days=n), hours)
        for n, hours in [(0, 7.0), (1, 6.0), (2, 7.2), (8, 5.0), (9, 5.5)]
    ]
    for day, hours in nights:
        save_night(client, sleep_date=day.isoformat(), total_sleep_hours=hours)

    data = client.get("/api/history/summary", params={"as_of": as_of.isoformat()}).json()
    assert data["as_of"] == "2026-09-10"
    assert data["nights_7d"] == 3
    assert data["nights_30d"] == 5
    assert data["sleep_debt_week_hours"] == pytest.approx(1.0 + 2.0 + 0.8)
    assert data["trend"]["direction"] == "up"  # прошлая неделя — по 5 часов, эта — лучше


# --- без базы данных ------------------------------------------------------------------


def test_sleep_check_works_without_database(client_without_db):
    response = check(client_without_db)
    assert response.status_code == 200
    data = response.json()
    assert data["history_nights_used"] == 0
    assert next(c for c in data["components"] if c["name"] == "consistency")["score"] is None


def test_endpoints_that_need_database_return_503(client_without_db):
    assert check(client_without_db, save=True).status_code == 503
    assert client_without_db.get("/api/history").status_code == 503
    assert client_without_db.get("/api/history/summary").status_code == 503
    assert client_without_db.get("/health").json() == {"status": "ok", "database": "unavailable"}
