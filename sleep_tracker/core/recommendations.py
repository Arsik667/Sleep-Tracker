"""Рекомендации: 2–4 совета по самым слабым местам ночи.

Логика отделена от скоринга: sleep_score только считает, этот модуль только
объясняет. Как выбираются советы:

1. Кандидаты — компоненты с баллом ниже WEAK_SCORE и сработавшие штрафы.
2. Каждый кандидат ранжируется по тому, сколько баллов он стоил итоговой оценке:
   для компонента это applied_weight × (100 − балл), для штрафа — его размер.
3. Берём до MAX_TIPS самых «дорогих». Если набралось меньше MIN_TIPS — добиваем
   общими советами (например, сохранять записи, чтобы появилась регулярность режима).
"""

from __future__ import annotations

from dataclasses import dataclass

from .sleep_score import PENALTIES, ComponentScore, NightData, SleepScore

WEAK_SCORE = 80  # компонент ниже этого балла считаем слабым местом
MIN_TIPS = 2
MAX_TIPS = 4

TIPS: dict[str, str] = {
    "duration_short": (
        "Сна меньше 7 часов. Сдвиньте отбой на 15–30 минут раньше и продержитесь "
        "на новом времени неделю, прежде чем сдвигать дальше."
    ),
    "duration_long": (
        "Сна больше 9 часов. Если это не отсыпание после недосыпа, держите фиксированное "
        "время подъёма и не оставайтесь в постели после пробуждения."
    ),
    "efficiency": (
        "Много времени в постели без сна. Ложитесь, только когда клонит в сон, а если "
        "не уснули минут за 20 — встаньте и займитесь чем-то спокойным при тусклом свете."
    ),
    "continuity_waso": (
        "Долго не спите посреди ночи. Уберите часы из поля зрения, держите в спальне "
        "прохладно (18–20 °C) и темно, не берите телефон при пробуждении."
    ),
    "continuity_awakenings": (
        "Частые пробуждения. Меньше жидкости и алкоголя за 2–3 часа до сна, "
        "беруши или белый шум, плотные шторы."
    ),
    "stages_deep": (
        "Мало глубокого сна. Помогают физическая активность днём (но не позже чем "
        "за 3 часа до сна), прохладная спальня и отказ от алкоголя вечером."
    ),
    "stages_rem": (
        "Мало REM-сна. Больше всего его под утро, поэтому поздний отбой и ранний подъём "
        "срезают REM первым — нужен полный сон в стабильном режиме."
    ),
    "consistency": (
        "Время отбоя сильно «гуляет». Выберите одно время отбоя и держитесь его "
        "±30 минут каждый день, включая выходные."
    ),
    "caffeine_after_14": (
        f"Кофеин после 14:00 (−{PENALTIES['caffeine_after_14']} баллов). Он выводится "
        "из организма 5–6 часов — переносите последнюю чашку кофе или чая на первую половину дня."
    ),
    "screen_before_bed": (
        f"Экран перед сном (−{PENALTIES['screen_before_bed']} балла). За 30–60 минут до сна "
        "отложите телефон и ноутбук — лучше книга, душ или спокойная музыка."
    ),
    # Общие советы — ими добиваем список до MIN_TIPS.
    "log_more": (
        "Сохраняйте оценку каждое утро: когда в истории будет хотя бы две ночи до сегодняшней, "
        "в оценке появится регулярность режима, а на графике — тренд."
    ),
    "track_stages": (
        "Если у вас есть фитнес-трекер, вносите минуты глубокого и REM-сна — "
        "оценка станет точнее."
    ),
    "keep_it_up": "Сон в хорошей форме — сохраняйте тот же режим, в том числе в выходные.",
    "morning_light": (
        "Выходите на дневной свет в первый час после подъёма — это помогает "
        "внутренним часам удерживать режим."
    ),
}


@dataclass(frozen=True)
class Recommendation:
    component: str  # к какому компоненту или штрафу относится совет; general — общий
    text: str


def build_recommendations(night: NightData, result: SleepScore) -> list[Recommendation]:
    candidates: list[tuple[float, Recommendation]] = []  # (сколько баллов стоила проблема, совет)
    for component in result.components:
        if component.score is None or component.score >= WEAK_SCORE:
            continue
        lost = component.applied_weight * (100 - component.score)
        candidates.append((lost, Recommendation(component.name, TIPS[_tip_key(component, night)])))
    for penalty in result.penalties:
        candidates.append((penalty.points, Recommendation(penalty.name, TIPS[penalty.name])))

    candidates.sort(key=lambda item: item[0], reverse=True)  # sort стабильный: при равенстве — порядок формулы
    tips = [rec for _, rec in candidates[:MAX_TIPS]]

    for filler in _fillers(result):
        if len(tips) >= MIN_TIPS:
            break
        tips.append(filler)
    return tips


def _tip_key(component: ComponentScore, night: NightData) -> str:
    """Выбирает вариант совета по тому, что именно просело внутри компонента."""
    if component.name == "duration":
        return "duration_short" if night.total_sleep_hours < 7 else "duration_long"
    if component.name == "continuity":
        parts = component.parts
        return "continuity_waso" if parts["waso"] <= parts["awakenings"] else "continuity_awakenings"
    if component.name == "stages":
        weakest = min(component.parts, key=component.parts.get)
        return f"stages_{weakest}"
    return component.name  # efficiency, consistency


def _fillers(result: SleepScore) -> list[Recommendation]:
    fillers = []
    if result.component("consistency").score is None:
        fillers.append(Recommendation("consistency", TIPS["log_more"]))
    if result.component("stages").score is None:
        fillers.append(Recommendation("stages", TIPS["track_stages"]))
    fillers.append(Recommendation("general", TIPS["keep_it_up"]))
    fillers.append(Recommendation("general", TIPS["morning_light"]))
    return fillers
