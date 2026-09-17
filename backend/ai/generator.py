import json
import os
import re
from typing import Any

from anthropic import AsyncAnthropic

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """
Ты создаёшь готовые интерактивные уроки для русскоязычной образовательной платформы.
Весь учебный текст, инструкции, варианты ответов, объяснения, подписи и обратная связь
должны быть только на русском языке.

Верни ТОЛЬКО корректный JSON-массив без Markdown, комментариев и пояснений.
Каждый элемент массива имеет ровно такую оболочку:
{"component": "ИмяКомпонента", "content": { ... }}

Допустимы только следующие 15 компонентов и их точные схемы content:

1. ShortExplanation:
{"title": string, "text": string, "key_concepts": string[], "callout"?: string}
Поле text поддерживает формулы KaTeX: $формула$ внутри строки и $$формула$$ отдельным блоком.

2. KeyConcept:
{"term": string, "definition": string, "example": string, "non_example": string, "visual_hint"?: string}

3. WorkedExample:
{"problem": string, "steps": [{"description": string, "math"?: string, "hint"?: string}], "final_answer": string}

4. GuidedPractice:
{"question": string, "hints": string[], "input_type": "numeric"|"expression"|"text", "correct_answer": string, "explanation": string}

5. IndependentProblem:
{"question": string, "type": "multiple_choice"|"numeric"|"expression", "options"?: [string, string, string, string], "correct_answer": string, "explanation": string, "difficulty": "basic"|"advanced"}
Для multiple_choice обязательно дай ровно 4 варианта.

6. RetrievalCheck:
{"question": string, "type": "multiple_choice", "options": [string, string, string, string], "correct_answer": string, "explanation": string}
Всегда дай ровно 4 варианта.

7. MindMap:
{"title": string, "central_concept": string, "branches": [{"label": string, "children": string[]}]}

8. Timeline:
{"title": string, "events": [{"date": string, "label": string, "description"?: string}]}

9. TextEvidencePicker:
{"passage": string, "claim": string, "correct_segments": string[], "explanation": string}
correct_segments должны дословно совпадать с предложениями из passage.

10. ArgumentBuilder:
{"prompt": string, "thesis_options": string[], "evidence_pool": string[], "correct_thesis": string, "correct_evidence": string[], "model_reasoning": string}

11. InteractiveGraph:
{"title": string, "description": string, "graph_type": "line"|"bar"|"scatter", "data_points": [{"x": number, "y": number, "label"?: string}], "x_label": string, "y_label": string, "interactive_params"?: [{"name": string, "label": string, "min": number, "max": number, "step": number, "default": number, "formula_description": string}]}

12. Presentation:
{"title": string, "slides": [{"heading": string, "body": string, "visual"?: string}]}

13. Illustration:
{"title": string, "description": string, "svg_content": string, "caption"?: string}
svg_content — безопасный автономный inline SVG без script, event-атрибутов и внешних ресурсов.

14. MasteryCheck:
{"questions": [{"question": string, "type": "multiple_choice"|"numeric", "options"?: string[], "correct_answer": string, "explanation": string, "dimension": string}]}
MasteryCheck всегда должен содержать РОВНО 3 вопроса. Для multiple_choice дай ровно 4 варианта.

15. Reflection:
{"prompt": string, "scale_question": string, "scale_labels": [string, string, string, string]}
scale_labels всегда содержит ровно 4 подписи.

Правила сборки урока по математике:
- последовательность: explain → model → represent (необязательно) → practice → assess → reflect;
- обязательны ShortExplanation, WorkedExample и MasteryCheck;
- рекомендуется использовать InteractiveGraph, GuidedPractice и IndependentProblem;
- всего в уроке должно быть не менее 5 оцениваемых заданий. Каждый отдельный вопрос
  внутри MasteryCheck считается одним заданием, остальные assessment-компоненты — по одному.

Правила сборки урока по литературе:
- последовательность: explain → represent (необязательно) → interact → assess → reflect;
- обязательны ShortExplanation и MasteryCheck;
- рекомендуется использовать Timeline, Presentation, TextEvidencePicker и RetrievalCheck;
- всего в уроке должно быть не менее 5 оцениваемых заданий по тому же правилу подсчёта.

Не добавляй поля вне описанных схем. Правильные ответы должны точно совпадать с одним из
вариантов там, где варианты предусмотрены. Урок должен соответствовать теме, целям,
навыкам и ресурсам из запроса пользователя.
""".strip()


def _extract_text(response: Any) -> str:
    return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")


def _parse_blocks(raw: str) -> list[dict[str, Any]]:
    cleaned = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, flags=re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    value = json.loads(cleaned)
    if not isinstance(value, list):
        raise ValueError("Ответ модели должен быть JSON-массивом")
    for block in value:
        if (
            not isinstance(block, dict)
            or not isinstance(block.get("component"), str)
            or not isinstance(block.get("content"), dict)
        ):
            raise ValueError("Некорректная структура блока")
    return value


async def generate_lesson(
    topic_name: str,
    subject_name: str,
    learning_objectives: str | None,
    skills: list[str] | None,
    resources: str | None,
) -> list[dict[str, Any]]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не настроен")

    subject_type = "math" if "математика" in subject_name.casefold() else "literature"
    user_prompt = f"""
Создай полный урок.
Тип предмета: {subject_type}
Предмет: {subject_name}
Тема: {topic_name}
Цели обучения: {learning_objectives or "не указаны"}
Навыки: {", ".join(skills or []) or "не указаны"}
Ресурсы: {resources or "не указаны"}

Ответь только JSON-массивом блоков.
""".strip()

    client = AsyncAnthropic(api_key=api_key)
    last_error: Exception | None = None
    retry_prompt = user_prompt
    for attempt in range(2):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": retry_prompt}],
        )
        try:
            return _parse_blocks(_extract_text(response))
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            retry_prompt = (
                user_prompt
                + "\nПредыдущий ответ не удалось разобрать как требуемый JSON. "
                "Исправь структуру и снова верни только JSON-массив без Markdown."
            )

    raise RuntimeError("Модель дважды вернула некорректный JSON урока") from last_error