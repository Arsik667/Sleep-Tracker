"""Консольная оценка сна — без веб-сервера и без БД.

    python -m sleep_tracker.cli --bedtime 23:30 --wake 07:00 --sleep-hours 7 \\
        --waso 20 --awakenings 2 --deep 80 --rem 95 --caffeine

    --json                       тот же JSON, что отдаёт API (удобно для скриптов и cron)
    --prev-bedtimes 23:10 23:45  отбой прошлых ночей → появится компонент регулярности

Это тонкая обёртка над sleep_tracker.core: argparse → NightData → скоринг → вывод.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from dataclasses import asdict
from datetime import time

from .core.recommendations import build_recommendations
from .core.sleep_score import (
    MIN_HISTORY_NIGHTS,
    SLEEP_NORM_HOURS,
    NightData,
    SleepScore,
    calculate_sleep_score,
)

COMPONENT_LABELS = {
    "duration": "Длительность",
    "efficiency": "Эффективность",
    "continuity": "Непрерывность",
    "stages": "Стадии сна",
    "consistency": "Регулярность",
}
CATEGORY_LABELS = {"excellent": "отлично", "good": "хорошо", "fair": "средне", "poor": "плохо"}
PENALTY_LABELS = {"caffeine_after_14": "кофеин после 14:00", "screen_before_bed": "экран перед сном"}
MISSING_REASONS = {
    "stages": "не указаны",
    "consistency": f"нужно ≥ {MIN_HISTORY_NIGHTS} прошлых ночей",
}
BAR_WIDTH = 20


def parse_time(value: str) -> time:
    try:
        hours, minutes = value.split(":")
        return time(int(hours), int(minutes))
    except ValueError:
        raise argparse.ArgumentTypeError(f"«{value}» — ожидается время ЧЧ:ММ, например 23:30") from None


def parse_hours(value: str) -> float:
    """Часы сна: 7.5, 7,5 или 7:30."""
    try:
        if ":" in value:
            hours, minutes = value.split(":")
            return int(hours) + int(minutes) / 60
        return float(value.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"«{value}» — ожидаются часы: 7.5 или 7:30") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sleep_tracker.cli",
        description="Оценка качества сна за одну ночь (0–100) с рекомендациями.",
    )
    parser.add_argument("--bedtime", type=parse_time, required=True, metavar="ЧЧ:ММ", help="время отбоя")
    parser.add_argument("--wake", type=parse_time, required=True, metavar="ЧЧ:ММ", help="время подъёма")
    parser.add_argument(
        "--sleep-hours", type=parse_hours, required=True, metavar="ЧАСЫ", help="общее время сна: 7.5 или 7:30"
    )
    parser.add_argument("--waso", type=int, default=0, metavar="МИН", help="минуты без сна после засыпания (WASO)")
    parser.add_argument("--awakenings", type=int, default=0, metavar="N", help="число пробуждений")
    parser.add_argument("--deep", type=int, metavar="МИН", help="минуты глубокого сна (если известны)")
    parser.add_argument("--rem", type=int, metavar="МИН", help="минуты REM-сна (если известны)")
    parser.add_argument("--caffeine", action="store_true", help="был кофеин после 14:00")
    parser.add_argument("--screen", action="store_true", help="смотрели в экран перед сном")
    parser.add_argument(
        "--prev-bedtimes",
        type=parse_time,
        nargs="+",
        default=[],
        metavar="ЧЧ:ММ",
        help="отбой прошлых ночей, от свежих к старым — для компонента регулярности",
    )
    parser.add_argument("--json", action="store_true", help="вывести JSON вместо текста")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        night = NightData(
            bedtime=args.bedtime,
            wake_time=args.wake,
            total_sleep_hours=args.sleep_hours,
            waso_minutes=args.waso,
            awakenings=args.awakenings,
            deep_sleep_minutes=args.deep,
            rem_sleep_minutes=args.rem,
            caffeine_after_14=args.caffeine,
            screen_before_bed=args.screen,
        )
    except ValueError as exc:
        parser.error(str(exc))  # печатает usage и выходит с кодом 2

    result = calculate_sleep_score(night, args.prev_bedtimes)
    recommendations = build_recommendations(night, result)

    if args.json:
        payload = {**result.to_dict(), "recommendations": [asdict(r) for r in recommendations]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(night, result, [r.text for r in recommendations]))
    return 0


def render_text(night: NightData, result: SleepScore, tips: list[str]) -> str:
    lines = [
        "SleepTrack · оценка сна",
        f"Отбой {night.bedtime:%H:%M} → подъём {night.wake_time:%H:%M} · "
        f"в постели {_hm(result.time_in_bed_hours)} · сон {_hm(night.total_sleep_hours)} · "
        f"эффективность {result.sleep_efficiency:g}%",
        "",
        f"  {result.score} / 100  —  {result.category} ({CATEGORY_LABELS[result.category]})",
        "",
    ]
    for c in result.components:
        label = f"  {COMPONENT_LABELS[c.name]:<14}"
        if c.score is None:
            lines.append(f"{label}{'—':>6}  {'·' * BAR_WIDTH}  {MISSING_REASONS[c.name]}")
        else:
            lines.append(
                f"{label}{c.score:>6.1f}  {_bar(c.score)}  вес {c.weight:.0%} → {c.applied_weight:.0%}"
            )
    lines.append("")

    if result.penalties:
        lines.append("Штрафы: " + ", ".join(f"{PENALTY_LABELS[p.name]} −{p.points}" for p in result.penalties))
    if result.score_cap is not None:
        lines.append(f"Потолок: при {night.total_sleep_hours:g} ч сна оценка не выше {result.score_cap}")
    if result.bedtime_sd_minutes is not None:
        lines.append(
            f"Разброс отбоя: ±{result.bedtime_sd_minutes:g} мин по {result.history_nights_used + 1} ночам"
        )
    lines.append(f"Недосып за ночь: {result.sleep_debt_hours:g} ч (норма {SLEEP_NORM_HOURS:g} ч)")
    lines.append("")

    lines.append("Рекомендации:")
    for i, tip in enumerate(tips, start=1):
        lines.append(textwrap.fill(tip, width=88, initial_indent=f"  {i}. ", subsequent_indent="     "))
    return "\n".join(lines)


def _bar(score: float) -> str:
    filled = round(score / 100 * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def _hm(hours: float) -> str:
    total = round(hours * 60)
    h, m = divmod(total, 60)
    return f"{h} ч {m:02d} мин" if m else f"{h} ч"


if __name__ == "__main__":
    sys.exit(main())
