from datetime import date
from statistics import mean

import pytest
from sqlalchemy.orm import sessionmaker

from sleep_tracker import crud
from sleep_tracker.database import make_engine
from sleep_tracker.seed_demo import generate_nights, seed

END = date(2026, 9, 10)


@pytest.fixture
def session(tmp_path):
    factory = sessionmaker(bind=make_engine(f"sqlite:///{tmp_path / 'demo.db'}"), expire_on_commit=False)
    with factory() as s:
        yield s


def test_generated_nights_are_valid_and_consecutive():
    nights = generate_nights(60, end=END, seed=3)  # NightData сам бы упал на невалидной ночи
    assert len(nights) == 60
    assert nights[-1].sleep_date == END
    assert all((b.sleep_date - a.sleep_date).days == 1 for a, b in zip(nights, nights[1:]))


def test_same_seed_gives_same_data():
    assert generate_nights(10, END, seed=5) == generate_nights(10, END, seed=5)


def test_seed_writes_history_with_improving_trend(session):
    assert seed(session, generate_nights(30, END)) == 30

    entries = crud.latest_entries(session, limit=100)
    assert len(entries) == 30
    scores = [e.score for e in reversed(entries)]  # от старых к новым
    assert mean(scores[-7:]) > mean(scores[:7])


def test_seed_refuses_to_overwrite_existing_nights(session):
    seed(session, generate_nights(5, END))
    with pytest.raises(SystemExit, match="уже есть 5"):
        seed(session, generate_nights(10, END, seed=99))
    assert seed(session, generate_nights(10, END, seed=99), overwrite=True) == 10
    assert len(crud.latest_entries(session, limit=100)) == 10
