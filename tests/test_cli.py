import json
import subprocess
import sys
from datetime import time
from pathlib import Path

import pytest

from sleep_tracker.cli import main, parse_hours
from sleep_tracker.core.sleep_score import NightData, calculate_sleep_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_ARGS = ["--bedtime", "23:30", "--wake", "07:00", "--sleep-hours", "7", "--waso", "20", "--awakenings", "2"]


def run_json(capsys, *extra):
    assert main([*BASE_ARGS, *extra, "--json"]) == 0
    return json.loads(capsys.readouterr().out)


def test_text_report(capsys):
    assert main([*BASE_ARGS, "--caffeine"]) == 0
    out = capsys.readouterr().out

    assert "/ 100" in out
    assert "Длительность" in out
    assert "кофеин после 14:00 −5" in out
    assert "Рекомендации:" in out
    assert "  1. " in out


def test_json_matches_core(capsys):
    data = run_json(capsys, "--deep", "80", "--rem", "95")

    night = NightData(
        bedtime=time(23, 30), wake_time=time(7, 0), total_sleep_hours=7, waso_minutes=20, awakenings=2,
        deep_sleep_minutes=80, rem_sleep_minutes=95,
    )
    expected = calculate_sleep_score(night)
    assert data["score"] == expected.score
    assert data["category"] == expected.category
    assert [c["name"] for c in data["components"]] == [c.name for c in expected.components]
    assert 2 <= len(data["recommendations"]) <= 4
    assert set(data["recommendations"][0]) == {"component", "text"}


def test_previous_bedtimes_enable_consistency(capsys):
    without = run_json(capsys)
    with_history = run_json(capsys, "--prev-bedtimes", "23:15", "23:40", "00:05")

    assert without["bedtime_sd_minutes"] is None
    assert with_history["history_nights_used"] == 3
    consistency = next(c for c in with_history["components"] if c["name"] == "consistency")
    assert consistency["score"] is not None


def test_short_sleep_cap_is_explained(capsys):
    assert main(["--bedtime", "01:30", "--wake", "06:00", "--sleep-hours", "4.2"]) == 0
    assert "Потолок: при 4.2 ч сна оценка не выше 34" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--bedtime", "25:30", "--wake", "07:00", "--sleep-hours", "7"], "ЧЧ:ММ"),
        (["--bedtime", "23:30", "--wake", "07:00", "--sleep-hours", "семь"], "ожидаются часы"),
        (["--bedtime", "23:30", "--wake", "07:00", "--sleep-hours", "9"], "больше, чем времени в постели"),
        (["--bedtime", "23:30", "--wake", "07:00"], "--sleep-hours"),
    ],
)
def test_bad_input_exits_with_code_2(capsys, args, message):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(("value", "hours"), [("7.5", 7.5), ("7,5", 7.5), ("7:30", 7.5), ("6:45", 6.75)])
def test_parse_hours(value, hours):
    assert parse_hours(value) == hours


def test_module_runs_without_fastapi_and_sqlalchemy():
    # CLI должен работать там, где нет веб-стека: проверяем, что он его даже не импортирует.
    code = (
        "import sys; from sleep_tracker.cli import main; "
        f"main({[*BASE_ARGS, '--json']!r}); "
        "print(sorted(m for m in ('fastapi', 'sqlalchemy', 'pydantic') if m in sys.modules), file=sys.stderr)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=PROJECT_ROOT)
    assert json.loads(out.stdout)["score"] > 0
    assert out.stderr.strip() == "[]"


def test_python_dash_m_entrypoint():
    out = subprocess.run(
        [sys.executable, "-m", "sleep_tracker.cli", *BASE_ARGS, "--json"],
        capture_output=True, text=True, check=True, cwd=PROJECT_ROOT,
    )
    assert "score" in json.loads(out.stdout)
