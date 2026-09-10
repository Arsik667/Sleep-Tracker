# 🌙 SleepTrack

A sleep quality tracker and analyzer. Enter one night — bedtime, wake time, how long you
actually slept, awakenings, optional deep/REM minutes from a fitness tracker — and get a
0–100 score, a breakdown by component and 2–4 tips aimed at the weakest spots. Nights can
be saved, so you also get **history and a trend**: average score over 7/30 days,
week-over-week change and accumulated sleep debt.

![SleepTrack: the night form, the score card and the history chart](docs/screenshot.png)

<sub>History in the screenshot is synthetic (`python -m sleep_tracker.seed_demo`). The UI is available in
English and Russian — switch in the header or open the app with `?lang=en` / `?lang=ru`.</sub>

## Features

| | |
|---|---|
| **Night form** | bedtime / wake time (time in bed is computed, midnight is handled), total sleep, WASO, awakenings, deep and REM minutes (optional), caffeine after 14:00, screen before bed |
| **Score** | 0–100 and a category (excellent / good / fair / poor) from five weighted components, penalties and a short-sleep cap |
| **Tips** | 2–4 tips for the components that cost the most points; the variant depends on what exactly went wrong (too short vs too long, WASO vs frequent awakenings, deep vs REM) |
| **History** | `save=true` stores the night in PostgreSQL (SQLite locally); one night per date — saving again replaces it |
| **Trend** | 7/30-day average, this week vs the previous one, weekly sleep debt vs 8 h; SVG chart of nightly scores and the 7-day rolling average, with a table view |
| **CLI** | the same scoring from the terminal (`--json` for scripts and cron jobs) — no web server, no database |
| **Works without a DB** | if the database is down, scoring still works (just without the consistency component); history endpoints return 503 |
| **Two languages** | English and Russian UI; tips come from the API in the chosen language (`?lang=en`), validation errors carry a stable code in `type`, so the frontend shows them in the UI language |

## How the score works

Every component is a piecewise-linear curve over a few breakpoints (see `*_CURVE` in
[`core/sleep_score.py`](sleep_tracker/core/sleep_score.py)) — easy to read, explain and tune.

| Component | Weight | Input | 0 points | 100 points |
|---|---|---|---|---|
| Duration | 20% | total sleep | ≤ 4 h | 7–9 h (then down to 40 at 12 h+) |
| Efficiency | 25% | sleep ÷ time in bed | ≤ 65% | ≥ 90% (80 at 85%) |
| Continuity | 25% | 60% WASO + 40% awakenings | WASO ≥ 90 min, ≥ 8 awakenings | WASO ≤ 20 min, ≤ 1 awakening |
| Sleep stages | 15% | deep and REM as % of sleep | deep ≤ 5%, REM ≤ 10% | deep ≥ 15%, REM ≥ 20% |
| Consistency | 15% | SD of bedtime: tonight + last 7 saved nights | ≥ 90 min | ≤ 15 min |

Then:

- **Penalties:** caffeine after 14:00 −5, screen before bed −3.
- **Short-sleep cap:** the final score can't go above a curve — 50 at 5 h of sleep, 70 at
  6 h, no cap from 7 h. Duration has only 20% weight, so without the cap a 4-hour night with
  good efficiency would score ~80, and 6 hours could reach "excellent". The cap is a curve,
  not steps, so 6 h 59 min and 7 h don't differ by half a category.
- **Categories:** excellent ≥ 85, good ≥ 70, fair ≥ 50, poor below.

**Missing data is neutral.** If stages aren't given or there are fewer than 2 saved nights
before this one, the component is skipped and its weight is split proportionally between
the others — the score is the weighted average of what is known, so missing data neither
helps nor hurts.

**Bedtime spread across midnight.** Bedtimes are counted in minutes from *noon*, not
midnight: 23:40 → 700 and 00:20 → 740, so a 40-minute difference stays 40 minutes instead
of ~23 hours.

**Sleep debt** is the sum of nightly shortfalls vs 8 h over the last 7 days. It is
deliberately conservative: oversleeping one night doesn't cancel the debt, and nights
without a record aren't guessed. **Trend** is the 7-day average minus the previous 7-day
average; less than ±3 points is "flat".

## Quick start

### Docker

```bash
docker compose up --build
```

- frontend: http://localhost:3000 (nginx serves the React build and proxies `/api` to the backend)
- API docs: http://localhost:8000/docs
- PostgreSQL lives inside the compose network with a named volume, so history survives
  `docker compose down`. Ports are bound to `127.0.0.1` only.

Fill the history with 30 demo nights:

```bash
docker compose exec api python -m sleep_tracker.seed_demo
```

### Locally, without Docker

No PostgreSQL needed: without `SLEEPTRACK_DATABASE_URL` the backend uses a SQLite file
`sleeptrack.db` in the current folder.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn sleep_tracker.main:app --reload          # http://localhost:8000
python -m sleep_tracker.seed_demo                # optional: 30 demo nights
```

```bash
cd frontend
npm install
npm start                                        # http://localhost:3000
```

| Variable | Default | |
|---|---|---|
| `SLEEPTRACK_DATABASE_URL` | `sqlite:///./sleeptrack.db` | any SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host/db` |
| `SLEEPTRACK_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | comma-separated |
| `REACT_APP_API_URL` (frontend, build time) | `http://localhost:8000` | empty string = same origin (used in Docker) |

## CLI

The CLI calls the same `core` package as the API, and imports neither FastAPI nor SQLAlchemy.
Pass previous bedtimes to get the consistency component without a database.

```bash
python -m sleep_tracker.cli --bedtime 23:40 --wake 06:50 --sleep-hours 6:20 \
    --waso 35 --awakenings 3 --deep 55 --rem 70 --caffeine \
    --prev-bedtimes 23:10 00:30 23:50 01:05
```

```
SleepTrack · оценка сна
Отбой 23:40 → подъём 06:50 · в постели 7 ч 10 мин · сон 6 ч 20 мин · эффективность 88.4%

  76 / 100  —  good (хорошо)

  Длительность    77.8  ████████████████░░░░  вес 20% → 20%
  Эффективность   93.5  ███████████████████░  вес 25% → 25%
  Непрерывность   75.7  ███████████████░░░░░  вес 25% → 25%
  Стадии сна      89.5  ██████████████████░░  вес 15% → 15%
  Регулярность    66.4  █████████████░░░░░░░  вес 15% → 15%

Штрафы: кофеин после 14:00 −5
Разброс отбоя: ±40.2 мин по 5 ночам
Недосып за ночь: 1.67 ч (норма 8 ч)

Рекомендации:
  1. Частые пробуждения. Меньше жидкости и алкоголя за 2–3 часа до сна, беруши или белый
     шум, плотные шторы.
  2. Время отбоя сильно «гуляет». Выберите одно время отбоя и держитесь его ±30 минут
     каждый день, включая выходные.
  ...
```

`--json` prints the same JSON as the API, minus `sleep_date` and the save-related fields.
Sleep hours can be written as `7.5`, `7,5` or `7:30`. Invalid input exits with code 2.

## API

| Method | Path | |
|---|---|---|
| `POST` | `/api/sleep-check` | score + tips for one night; `?save=true` also stores it, `?lang=en` returns tips in English (default `ru`) |
| `GET` | `/api/history?limit=30` | last N saved nights, newest first (1–365) |
| `GET` | `/api/history/summary?as_of=YYYY-MM-DD` | 7/30-day averages, trend, weekly sleep debt |
| `GET` | `/health` | always 200; `"database": "ok"` or `"unavailable"` |
| `GET` | `/` | welcome message |

```bash
curl -X POST "http://localhost:8000/api/sleep-check?lang=en" \
  -H "Content-Type: application/json" \
  -d '{"sleep_date": "2026-09-10", "bedtime": "23:30", "wake_time": "07:00",
       "total_sleep_hours": 6.9, "waso_minutes": 20, "awakenings": 2,
       "deep_sleep_minutes": 80, "rem_sleep_minutes": 95, "caffeine_after_14": true}'
```

Response (with the demo history loaded, so consistency is available):

```jsonc
{
  "sleep_date": "2026-09-10",
  "score": 91,
  "category": "excellent",
  "components": [
    {"name": "duration", "score": 96.7, "weight": 0.2, "applied_weight": 0.2, "parts": {}},
    {"name": "continuity", "score": 94.3, "weight": 0.25, "applied_weight": 0.25,
     "parts": {"waso": 100.0, "awakenings": 85.7}},
    // … efficiency, stages, consistency
  ],
  "penalties": [{"name": "caffeine_after_14", "points": 5}],
  "score_cap": null,
  "time_in_bed_hours": 7.5,
  "sleep_efficiency": 92.0,
  "bedtime_sd_minutes": 25.8,
  "history_nights_used": 7,
  "sleep_debt_hours": 1.1,
  "recommendations": [
    {"component": "caffeine_after_14", "text": "Caffeine after 2 pm (−5 points). It takes 5–6 hours to clear — …"},
    {"component": "general", "text": "Your sleep is in good shape — keep the same schedule, weekends included."}
  ],
  "saved": false,
  "entry_id": null,
  "replaced_existing": false
}
```

With `?save=true` the night is stored: `saved` becomes `true`, `entry_id` is filled, and
`replaced_existing` tells whether a record for that date was overwritten.
`sleep_date` is the date of the morning after the night (defaults to today). Field ranges
(non-negative WASO and awakenings, sleep ≤ 24 h, …) are checked by Pydantic and come back
as 422 errors pointing at the field; cross-field rules (sleep fits into time in bed, deep +
REM ≤ total sleep, …) live in `core.NightData`, so the API and the CLI share one
implementation. These come back with their own `type` (`sleep_exceeds_bed`,
`stages_exceed_sleep`, `same_bed_and_wake`, …) and numbers in `ctx`, so a client can show
the message in any language.

## Project structure

```
sleep-tracker/
├── sleep_tracker/
│   ├── core/                  # pure Python, no web or DB imports
│   │   ├── sleep_score.py     #   NightData, components, penalties, cap, categories
│   │   ├── recommendations.py #   tips ranked by the points each problem cost (ru / en)
│   │   └── summary.py         #   7/30-day averages, trend, weekly sleep debt
│   ├── main.py                # FastAPI routes
│   ├── schemas.py             # Pydantic request/response models
│   ├── crud.py                # queries: previous bedtimes, upsert, history
│   ├── models.py              # SleepEntry ORM model
│   ├── database.py            # engine, sessions, lazy table creation
│   ├── cli.py                 # python -m sleep_tracker.cli
│   └── seed_demo.py           # python -m sleep_tracker.seed_demo
├── frontend/                  # Create React App, no UI kits
│   └── src/                   #   SleepForm, ResultCard, HistoryChart (hand-written SVG), i18n.js
├── tests/                     # pytest: scoring, tips, summary, CLI, API, demo data
├── Dockerfile                 # API image
├── frontend/Dockerfile        # React build → nginx
└── docker-compose.yml         # db (PostgreSQL) + api + frontend
```

## Tests

```bash
pytest
```

200+ tests: scoring scenarios (perfect night, sleep deprivation, many awakenings, missing
stages, bedtimes across midnight), input validation, tip selection, history aggregates, the
CLI (including a check that it doesn't import FastAPI/SQLAlchemy/Pydantic) and the API on a
temporary SQLite database — including the "database is down" scenario.

## Limitations and ideas

- **Not medical advice.** The formula is a transparent heuristic based on common sleep
  hygiene guidelines, not a validated clinical instrument.
- Single user, no authentication — it's a personal diary.
- Tables are created with `create_all`; schema changes would need Alembic migrations.
- Ideas: import from Apple Health / Google Fit / Oura exports into the CLI, per-weekday
  patterns, a correlation view (caffeine or screens vs score), a configurable sleep norm.
