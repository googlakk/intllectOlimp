import json
import os
import re
from typing import Any

from anthropic import AsyncAnthropic
from objectives import decompose_objectives

MODEL = "claude-sonnet-4-6"

SUBJECT_FAMILY_PROFILES = {
    "mathematical": {
        "label": "математические науки",
        "keywords": ("математ", "алгебр", "геометр", "арифмет", "статист"),
        "archetypes": ("concept_and_procedure", "problem_solving", "investigation"),
        "route": "объяснение → разобранный пример → практика с поддержкой → самостоятельная задача → проверка",
    },
    "natural_science": {
        "label": "естественные науки",
        "keywords": ("физик", "хими", "биолог", "географ", "естествозн", "природовед", "астроном"),
        "archetypes": ("phenomenon_inquiry", "experiment_and_evidence", "system_model"),
        "route": "явление или вопрос → прогноз → наблюдение, модель или эксперимент → интерпретация данных → вывод → проверка",
    },
    "language": {
        "label": "языки и речевое развитие",
        "keywords": ("русский язык", "кыргыз тили", "киргизский язык", "английск", "немецк", "француз", "иностранный язык", "граммат", "родной язык", "кыргызча"),
        "archetypes": ("language_practice", "text_comprehension", "communication"),
        "route": "языковой образец → распознавание → управляемая практика → понимание или создание текста/речи → обратная связь → применение",
    },
    "humanities_social_science": {
        "label": "гуманитарные и общественные науки",
        "keywords": ("литератур", "истори", "тарых", "адабият", "обществозн", "человек и обществ", "адам жана коом", "право", "эконом", "граждан"),
        "archetypes": ("source_analysis", "historical_context", "argumentation"),
        "route": "контекст → первичный текст или источник → анализ свидетельств → аргументация или интерпретация → сопоставление → рефлексия",
    },
    "computing_technology": {
        "label": "информатика и технологии",
        "keywords": ("информат", "программ", "робот", "цифров", "компьютер"),
        "archetypes": ("algorithm_design", "debugging", "digital_project"),
        "route": "демонстрация → выполнение процедуры → самостоятельное создание результата → проверка по критериям → улучшение",
    },
    "arts_practical_physical": {
        "label": "искусство, практика и физическое воспитание",
        "keywords": ("музык", "изобразитель", "рисован", "искусств", "труд", "технолог", "физическ культур", "спорт", "черчени", "дене тарбия"),
        "archetypes": ("demonstration_and_practice", "creative_project", "performance_and_reflection"),
        "route": "показ и критерии → безопасная практика → выполнение или создание → самооценка по критериям → рефлексия",
    },
    "general": {
        "label": "общий предмет (требует проверки учителем)",
        "keywords": (),
        "archetypes": ("general_explanation_and_practice",),
        "route": "цель → короткое объяснение → активная практика → проверка → рефлексия",
    },
}


def classify_subject(subject_name: str) -> dict[str, str | bool]:
    normalized = subject_name.casefold().replace("ё", "е")
    matches: list[tuple[int, str, dict[str, Any]]] = []
    for family, profile in SUBJECT_FAMILY_PROFILES.items():
        for keyword in profile["keywords"]:
            if keyword in normalized:
                matches.append((len(keyword), family, profile))
    if matches:
        _, family, profile = max(matches, key=lambda match: match[0])
        return {"family": family, "family_label": profile["label"], "archetype": profile["archetypes"][0], "teacher_review_required": False}
    return {"family": "general", "family_label": SUBJECT_FAMILY_PROFILES["general"]["label"], "archetype": "general_explanation_and_practice", "teacher_review_required": True}


def select_archetype(
    family: str,
    topic_name: str,
    lesson_type: str | None,
    learning_objectives: str | None,
) -> str:
    profile = SUBJECT_FAMILY_PROFILES[family]
    haystack = " ".join((topic_name, lesson_type or "", learning_objectives or "")).casefold()
    if lesson_type == "project":
        project_by_family = {
            "computing_technology": "digital_project",
            "arts_practical_physical": "creative_project",
            "natural_science": "experiment_and_evidence",
        }
        return project_by_family.get(family, profile["archetypes"][-1])
    if lesson_type == "assessment":
        return "retrieval_and_assessment"
    if any(word in haystack for word in ("эксперимент", "исследован", "опыт", "тажрыйба")):
        return "experiment_and_evidence"
    if any(word in haystack for word in ("текст", "чтени", "окуу", "пониман")) and family == "language":
        return "text_comprehension"
    return profile["archetypes"][0]

SYSTEM_PROMPT = """
Ты создаёшь готовые интерактивные уроки для школьной образовательной платформы Кыргызстана.
Язык всего учебного текста, инструкций, вариантов ответов, объяснений, подписей и обратной
связи передаётся в запросе. Строго используй только этот язык.

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

В content любого блока допускаются служебные поля objective_ids (массив строк)
и evidence_stage ("diagnostic", "explanation", "practice" или "assessment"). Они не отображаются
ученику. Каждый блок, кроме Reflection, должен указывать objective_ids. В MasteryCheck
каждый вопрос также должен иметь objective_ids (или dimension равный ID цели).

14. MasteryCheck:
{"questions": [{"question": string, "type": "multiple_choice"|"numeric", "options"?: string[], "correct_answer": string, "explanation": string, "dimension": string, "objective_ids": string[]}]}
MasteryCheck должен содержать столько вопросов, чтобы каждая цель имела хотя бы один
независимо оцениваемый итоговый вопрос; для multiple_choice дай ровно 4 варианта.

15. Reflection:
{"prompt": string, "scale_question": string, "scale_labels": [string, string, string, string]}
scale_labels всегда содержит ровно 4 подписи.

Следуй переданному предметному маршруту, а не одной универсальной последовательности.
Для математических задач используй разобранные примеры; для наук — прогноз, модель,
данные и вывод; для языков — образец и создание речи/текста; для гуманитарных предметов —
источник, свидетельства и аргументацию; для практических предметов — показ, критерии,
выполнение и самооценку. Цифровой тест не должен подменять физическое или творческое
выполнение. Заверши урок Reflection и MasteryCheck с вопросом по каждой цели. В уроке должно быть
не менее пяти оцениваемых действий с учётом отдельных вопросов MasteryCheck.

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
    grade: int | None = None,
    lesson_type: str | None = None,
    content_language: str = "ru",
) -> list[dict[str, Any]]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не настроен")
    workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
    if not workspace_id:
        raise RuntimeError(
            "ANTHROPIC_WORKSPACE_ID не настроен. "
            "Для этого ключа Anthropic требуется ID workspace."
        )

    profile = classify_subject(subject_name)
    archetype = select_archetype(
        str(profile["family"]), topic_name, lesson_type, learning_objectives
    )
    route = SUBJECT_FAMILY_PROFILES[str(profile["family"])]["route"]
    objective_catalog = decompose_objectives(learning_objectives)
    language_label = "кыргызском" if content_language == "ky" else "русском"
    user_prompt = f"""
Создай полный урок.
Семейство предмета: {profile["family_label"]} ({profile["family"]})
Архетип урока: {archetype}
Предметный маршрут: {route}
Язык всего учебного содержания: на {language_label} языке.
Проверка учителем: {"обязательна — предмет не распознан" if profile["teacher_review_required"] else "не требуется"}
Предмет: {subject_name}
Тема: {topic_name}
Класс: {grade if grade is not None else "не указан"}
Тип урока: {lesson_type or "не указан"}
Цели обучения (исходный текст): {learning_objectives or "не указаны"}
Структурированные цели с ID: {json.dumps(objective_catalog, ensure_ascii=False)}
Навыки: {", ".join(skills or []) or "не указаны"}
Ресурсы: {resources or "не указаны"}

Каждый блок, кроме Reflection, ОБЯЗАН содержать objective_ids и явный evidence_stage.
Свяжи каждый блок и каждый вопрос MasteryCheck с ID из структурированных целей.
До объяснения дай по одному диагностическому RetrievalCheck с evidence_stage
"diagnostic" на каждую цель. Каждый диагностический блок и каждый отдельный итоговый
вопрос проверяет ровно одну цель. Для каждой цели обязательно дай объяснение, практику и
независимую итоговую проверку.
Ответь только JSON-массивом блоков.
""".strip()

    client = AsyncAnthropic(
        api_key=api_key,
        default_headers={"anthropic-workspace-id": workspace_id},
    )
    last_error: Exception | None = None
    retry_prompt = user_prompt
    for attempt in range(2):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=8192,
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