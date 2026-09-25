"""Когда тьютор молчит, говорит готовой фразой или зовёт модель. Чистая логика.

Модель вызывается, только когда нужно думать: сообщение ученика или
подсказка сверх заранее написанных. Всё остальное — шаблоны, бесплатно и
предсказуемо.
"""

from __future__ import annotations

from dataclasses import dataclass

EVENTS = ("answer_submitted", "hint_requested", "idle", "message")


@dataclass(frozen=True)
class RuleState:
    outcome: str | None = None            # correct | incorrect | wrong_unit — по проверке сервера
    consecutive_wrong: int = 0            # включая текущую попытку
    offer_after_errors: int = 2           # из профиля класса
    assessment: bool = False              # итоговое задание: тьютор молчит
    idle_offered: bool = False            # предложение по бездействию уже было на этом шаге
    hint_level: int = 0                   # какую подсказку просят (с нуля)
    authored_hints: int = 0               # сколько подсказок написано в уроке
    llm_calls_last_minute: int = 0
    burst_limit: int = 6
    distress: bool = False


@dataclass(frozen=True)
class Decision:
    kind: str                             # silent | template | authored_hint | llm
    template_key: str | None = None
    offer: bool = False                   # показать ученику «Помочь?»
    hint_index: int | None = None
    action: str | None = None             # open_theory | call_teacher


def decide(event: str, state: RuleState) -> Decision:
    if event == "message" and state.distress:
        return Decision("template", "distress", action="call_teacher")
    if state.assessment:
        if event == "answer_submitted":
            return Decision("silent")
        return Decision("template", "assessment_locked", action="open_theory")
    if event == "answer_submitted":
        if state.outcome == "correct":
            return Decision("template", "correct")
        if state.outcome == "incorrect" and state.consecutive_wrong >= state.offer_after_errors:
            return Decision("template", "offer_help", offer=True)
        return Decision("silent")
    if event == "idle":
        return Decision("silent") if state.idle_offered else Decision("template", "idle_offer", offer=True)
    if event == "hint_requested" and state.hint_level < state.authored_hints:
        return Decision("authored_hint", hint_index=state.hint_level)
    if event in {"hint_requested", "message"}:
        if state.llm_calls_last_minute >= state.burst_limit:
            return Decision("template", "burst_limit")
        return Decision("llm")
    return Decision("silent")
