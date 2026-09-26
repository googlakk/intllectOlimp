import json
import os
import re
from typing import TYPE_CHECKING, Any

import tempfile
from pathlib import Path

from ai.planner import build_topic_contract, split_component_plan
from objectives import GENERATION_COMPONENTS, decompose_objectives

if TYPE_CHECKING:
    from llm import Route

MODEL = "claude-sonnet-4-6"

# Потолок ответа. Урок по литературе с тремя целями и четырьмя этапами на цель
# в 8192 токена не помещался: ответ обрывался посередине, JSON переставал быть
# JSON, и оба захода падали с «некорректный JSON урока». Выше 21333 поднимать
# нельзя — SDK потребует стриминг (см. ktp/mapper.py).
MAX_TOKENS = 16000

LESSON_TOOL = {
    "name": "submit_lesson",
    "description": "Передать готовый урок — массив блоков.",
    "input_schema": {
        "type": "object",
        "properties": {
            "blocks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "component": {"type": "string", "enum": sorted(GENERATION_COMPONENTS)},
                        "content": {"type": "object"},
                    },
                    "required": ["component", "content"],
                },
            },
            "intro": {
                "type": "object",
                "description": "Титульная страница урока: заинтересовать до первого вопроса.",
                "properties": {
                    "kicker": {"type": "string"},
                    "title": {"type": "string"},
                    "accent": {"type": "string"},
                    "hook": {"type": "string"},
                    "cta": {"type": "string"},
                },
            },
        },
        "required": ["blocks"],
    },
}

INTRO_LIMITS = {"kicker": 60, "title": 80, "accent": 60, "hook": 280, "cta": 40}


class GeneratedBlocks(list):
    """Блоки урока; титул (intro) едет рядом, не ломая тех, кто ждёт список."""

    intro: dict[str, str] | None = None


def clean_intro(value: Any) -> dict[str, str] | None:
    """Оставляет только строковые поля титула разумной длины; битое — отбрасывает."""
    if not isinstance(value, dict):
        return None
    intro = {
        key: text.strip()
        for key, limit in INTRO_LIMITS.items()
        if isinstance(text := value.get(key), str) and text.strip() and len(text.strip()) <= limit
    }
    return intro if intro.get("title") and intro.get("hook") else None

SUBJECT_FAMILY_PROFILES = {
    "mathematical": {
        "label": "математические науки",
        "keywords": ("математ", "алгебр", "геометр", "арифмет", "статист"),
        "archetypes": ("concept_and_procedure", "problem_solving", "investigation"),
        "route": "объяснение → разобранный пример → практика с поддержкой → самостоятельная задача → проверка",
        "show_path": "раскрой запись (степень — это умножение, дробь — деление на части), подставляй числа, одно действие на шаг, в конце проверка",
    },
    "natural_science": {
        "label": "естественные науки",
        "keywords": ("физик", "хими", "биолог", "географ", "естествозн", "природовед", "астроном"),
        "archetypes": ("phenomenon_inquiry", "experiment_and_evidence", "system_model"),
        "route": "явление или вопрос → прогноз → наблюдение, модель или эксперимент → интерпретация данных → вывод → проверка",
        "show_path": "что значит каждая буква формулы и её единицы → подставь числа с единицами → вычисли → проверь, разумен ли ответ",
    },
    "language": {
        "label": "языки и речевое развитие",
        "keywords": ("русский язык", "кыргыз тили", "киргизский язык", "английск", "немецк", "француз", "иностранный язык", "граммат", "родной язык", "кыргызча"),
        "archetypes": ("language_practice", "text_comprehension", "communication"),
        "route": "языковой образец → распознавание → управляемая практика → понимание или создание текста/речи → обратная связь → применение",
        "show_path": "возьми слово или предложение → выдели нужную часть → примени правило → результат → «вот почему»",
    },
    "humanities_social_science": {
        "label": "гуманитарные и общественные науки",
        "keywords": ("литератур", "истори", "тарых", "адабият", "обществозн", "человек и обществ", "адам жана коом", "право", "эконом", "граждан"),
        "archetypes": ("source_analysis", "historical_context", "argumentation"),
        "route": "контекст → первичный текст или источник → анализ свидетельств → аргументация или интерпретация → сопоставление → рефлексия",
        "show_path": "факт → следствие → вывод: цепочка «потому что… поэтому…», без готовых оценок",
    },
    "computing_technology": {
        "label": "информатика и технологии",
        "keywords": ("информат", "программ", "робот", "цифров", "компьютер"),
        "archetypes": ("algorithm_design", "debugging", "digital_project"),
        "route": "демонстрация → выполнение процедуры → самостоятельное создание результата → проверка по критериям → улучшение",
        "show_path": "выполни программу по шагам и покажи значения переменных после каждой строки",
    },
    "arts_practical_physical": {
        "label": "искусство, практика и физическое воспитание",
        "keywords": ("музык", "изобразитель", "рисован", "искусств", "труд", "технолог", "физическ культур", "спорт", "черчени", "дене тарбия"),
        "archetypes": ("demonstration_and_practice", "creative_project", "performance_and_reflection"),
        "route": "показ и критерии → безопасная практика → выполнение или создание → самооценка по критериям → рефлексия",
        "show_path": "разложи действие на видимые шаги и скажи, на что смотреть на каждом",
    },
    "general": {
        "label": "общий предмет (требует проверки учителем)",
        "keywords": (),
        "archetypes": ("general_explanation_and_practice",),
        "route": "цель → короткое объяснение → активная практика → проверка → рефлексия",
        "show_path": "от знакомого случая к правилу, одно действие на шаг",
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

Урок передавай вызовом инструмента submit_lesson: массив blocks, в каждом
элементе component и content. Ничего не пиши текстом.
Каждый элемент массива имеет ровно такую оболочку:
{"component": "ИмяКомпонента", "content": { ... }}

Допустимы только следующие 27 компонентов и их точные схемы content:

1. ShortExplanation:
{"title": string, "text": string, "key_concepts": string[], "callout"?: string}
Поле text поддерживает Markdown и формулы KaTeX: $формула$ внутри строки и $$формула$$ отдельным блоком.
Всегда заключай LaTeX-команды, включая \\sqrt и \\frac, в $...$ или $$...$$; не пиши sqrt как обычный текст.
После каждой новой формулы или правила сразу раскрой его на маленьком примере прямо в text.

2. KeyConcept:
{"term": string, "definition": string, "example": string, "non_example": string, "visual_hint"?: string}
example показывает раскрытие, а не только готовую запись: «$2^3 = 2 \\cdot 2 \\cdot 2 = 8$», а не «$2^3 = 8$».
non_example показывает типичную ошибку с тем же раскрытием: «$2^3 \\ne 2 \\cdot 3 = 6$».

3. WorkedExample:
{"problem": string, "steps": [{"description": string, "math"?: string, "hint"?: string}], "final_answer": string}
3–6 шагов, каждый шаг — одно действие. description говорит, что делаем и почему; math показывает
переход «было = стало». Последний шаг связывает результат с вопросом задачи. final_answer — ответ
и короткая цепочка, которая к нему привела, а не одно число.

4. GuidedPractice:
{"question": string, "hints": string[], "input_type": "numeric"|"expression"|"text", "correct_answer": string, "answer_unit"?: string, "explanation": string}

5. IndependentProblem:
{"question": string, "type": "multiple_choice"|"numeric"|"expression", "options"?: [string, string, string, string], "correct_answer": string, "answer_unit"?: string, "tolerance"?: number, "explanation": string, "difficulty": "basic"|"advanced"}
Для multiple_choice обязательно дай ровно 4 варианта.
Числовой ответ (GuidedPractice, IndependentProblem, вопросы MasteryCheck типа numeric): в correct_answer
только число без единиц («8.9»), единица — в answer_unit («г/см³»). Запиши correct_answer ровно с той
точностью, которую просит вопрос («до десятых» → «8.9»): ответ ученика засчитывается с точностью до
половины последнего записанного разряда, запятая и точка равны. Если ответ приближённый (измерение,
округление по ходу решения), добавь "tolerance" — относительный допуск, например 0.02.

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
{"title": string, "slides": [{"id": string, "heading": string, "body": string, "learning_point": string, "avatar_script": string, "visual"?: string, "media_slot"?: {"id": string, "role": "demonstrate"|"compare"|"show_process"|"clarify", "placement": "slide_visual", "learning_purpose": string, "must_show": string[], "must_not_show": string[]}}]}
Каждый id уникален внутри презентации (slide-1, slide-2...). learning_point — одна проверяемая
мысль слайда. avatar_script — короткое устное дополнение именно к этому слайду: причинная связь,
аналогия, акцент или предупреждение об ошибке; оно не должно зачитывать heading/body. media_slot
добавляй только там, где визуализация действительно помогает понять learning_point. Медиа —
иллюстрация без текста: must_show перечисляет предметы, явления и действия в кадре, а не надписи,
формулы или числа (они остаются в heading/body). Не выдумывай
URL: после генерации учитель привяжет реальный asset к этому слоту.

Места под иллюстрации в других блоках. В content блоков ShortExplanation, KeyConcept,
WorkedExample, GuidedPractice, IndependentProblem, PredictionLab, BranchingScenario и Timeline
можно добавить "media_slot": {"id": string, "role": "demonstrate"|"compare"|"show_process"|"clarify",
"placement": "block_visual", "learning_purpose": string, "must_show": string[], "must_not_show": string[]}.
Ставь слот в каждом таком блоке, где сцена помогает понять или представить условие, и на каждый
слайд презентации, кроме мини-проверки понимания и слайдов, где картинка подсказала бы ответ.
Для задач (WorkedExample, GuidedPractice, IndependentProblem), опытов (PredictionLab) и ситуаций
(BranchingScenario) картинка показывает только условие: must_not_show обязательно содержит
ответ, решение и результат. Никогда не ставь media_slot в RetrievalCheck, MasteryCheck, Reflection,
схемы, сортировку, графики и симуляции.

13. Illustration:
{"title": string, "description": string, "svg_content": string, "caption"?: string}
svg_content — безопасный автономный inline SVG без script, event-атрибутов и внешних ресурсов.

В content любого блока допускаются служебные поля objective_ids (массив строк),
evidence_stage ("diagnostic", "explanation", "practice" или "assessment") и
avatar_script (короткая разговорная реплика ведущего, не дублирующая весь текст). Реплика объясняет
причину, аналогию или ход мысли простыми словами и добавляет то, чего нет на экране. Не вставляй в неё
Markdown, символы $ и LaTeX-команды. Формулы записывай словами так, как их должен произнести учитель,
например «квадратный корень из сорока девяти равен семи». Одна реплика — 2–4 коротких предложения.
Эти поля не отображаются ученику. Каждый блок, кроме Reflection, должен указывать objective_ids. В MasteryCheck
каждый вопрос также должен иметь objective_ids (или dimension равный ID цели).
Если в запросе передан component_plan, структура урока должна следовать этому плану:
роль, objective_ids, evidence_stage и allowed_components для каждого шага являются
контрактом. Если в allowed_components шага один компонент — используй именно его.
Не делай один и тот же шаблон для маленькой и большой темы.

14. MasteryCheck:
{"questions": [{"question": string, "type": "multiple_choice"|"numeric", "options"?: string[], "correct_answer": string, "answer_unit"?: string, "explanation": string, "dimension": string, "objective_ids": string[]}]}
MasteryCheck должен содержать столько вопросов, чтобы каждая цель имела хотя бы один
независимо оцениваемый итоговый вопрос; для multiple_choice дай ровно 4 варианта.

15. Reflection:
{"prompt": string, "scale_question": string, "scale_labels": [string, string, string, string]}
scale_labels всегда содержит ровно 4 подписи.

16. SortAndClassify:
{"title": string, "instruction": string, "groups": [{"id": string, "label": string, "hint"?: string}], "items": [{"id": string, "label": string, "correct_group": string}], "explanation": string}
Используй для классификаций, сопоставлений и группировки понятий.

17. ProcessBuilder:
{"title": string, "instruction": string, "steps": [{"id": string, "label": string, "description"?: string}], "correct_edges": [{"from": string, "to": string, "label"?: string}], "explanation": string}
Используй для циклов, процессов, алгоритмов и причинных цепочек.

18. ArgumentMap:
{"title": string, "prompt": string, "nodes": [{"id": string, "label": string, "kind": "claim"|"evidence"|"reasoning"|"counterargument"}], "correct_links": [{"from": string, "to": string}], "explanation": string}
Используй для тезиса, доказательств, контраргумента и вывода.

19. BranchingScenario:
{"title": string, "context": string, "start_node_id": string, "nodes": [{"id": string, "title": string, "text": string, "choices"?: [{"label": string, "next": string, "feedback"?: string}], "terminal"?: boolean, "success"?: boolean}], "success_feedback": string, "failure_feedback": string}
Используй для техники безопасности, гражданского выбора, общения и лабораторных решений.

20. MisconceptionDebugger:
{"title": string, "prompt": string, "steps": [{"id": string, "text": string, "is_error"?: boolean}], "repair_steps": string[], "explanation": string}
Ровно один step должен иметь is_error=true. repair_steps идут в правильном порядке.

21. PredictionLab:
{"title": string, "question": string, "options": [{"id": string, "label": string}], "correct_prediction": string, "observation_title": string, "observations": [{"label": string, "value": string}], "explanation": string}
correct_prediction должен совпадать с id одного варианта.

22. DataInvestigation:
{"title": string, "description": string, "vega_lite_spec": object, "question": {"question": string, "options": [string, string, string, string], "correct_answer": string}, "explanation": string}
vega_lite_spec должен быть простой Vega-Lite спецификацией с data.values, mark и encoding.

23. PhysicsSandbox:
{"title": string, "prompt": string, "bodies": [{"shape": "circle"|"rectangle", "x": number, "y": number, "width"?: number, "height"?: number, "radius"?: number, "is_static"?: boolean}], "params": [{"name": "gravity"|"restitution", "label": string, "min": number, "max": number, "step": number, "default": number}], "question": string, "options": [string, string, string, string], "correct_answer": string, "explanation": string}
Используй только для простых 2D физических моделей.

24. CodeBlocksLab:
{"title": string, "task": string, "toolbox_xml": string, "expected_block_types": string[], "explanation": string, "starter_xml"?: string}
Используй для информатики и алгоритмов. toolbox_xml должен содержать только стандартные Blockly block type.

25. ChronologyLine:
{"title": string, "instruction": string, "events": [{"id": string, "label": string, "year": integer, "explanation": string, "lane"?: string}], "lanes"?: [{"id": string, "label": string}], "tolerance_years"?: integer, "explanation": string}
Лента событий: ученик сам расставляет события по годам. 4–7 событий, годы — только из учебника или
материала урока (до нашей эры — отрицательное число). label — короткое название без года; explanation
у события — почему оно стоит здесь (что было причиной или что из него следует). lanes — параллельные
линии (например, «Кокандское ханство» и «Российская империя»), у события тогда lane = id линии.
Используй в истории для хронологии; в других предметах — для этапов открытий и развития.

26. CauseEffectMap:
{"title": string, "instruction": string, "event": {"label": string, "year"?: integer}, "factors": [{"id": string, "label": string, "role": "cause"|"trigger"|"consequence"|"unrelated", "kind"?: "political"|"economic"|"social"|"external"|"cultural", "term"?: "short"|"long", "explanation": string}], "explanation": string}
Причины и следствия одного события: ученик определяет роль каждого фактора. 5–8 факторов: хотя бы
2 причины (разных видов), ровно 1 повод, 1–3 последствия (ближайшее и долгосрочное) и 1 правдоподобный
отвлекающий фактор (unrelated). explanation у фактора — почему роль именно такая. Факты — из учебника.
Используй в истории для причин и последствий; в обществознании — для анализа ситуаций.

27. GeneratedMedia:
{"title": string, "description"?: string, "media_kind": "image"|"video", "url"?: string, "data_url"?: string, "poster_url"?: string, "alt_text"?: string, "caption"?: string, "pedagogical_role"?: string, "visual_intent"?: string, "success_check"?: string, "job_id"?: string, "generation_id"?: string, "prompt"?: string, "model"?: string}
Не используй GeneratedMedia при обычной генерации урока: этот блок вставляется только после
реального вызова OpenRouter media API из редактора. Никогда не выдумывай url, data_url или
base64-контент.

Как объяснять: покажи путь, а не только результат. Ученик должен видеть, откуда взялся ответ.
1) От конкретного к общему: сначала маленький знакомый случай, потом правило.
2) Раскрой запись: запиши то же самое более простыми действиями или словами.
3) Одно действие на шаг: в каждом шаге видно «было → стало» и сказано, почему.
4) Получи результат и назови его: «…это и есть …».
5) Ответ появляется только после шага, который его даёт.
Эталон: $3^2$ → «три в квадрате — это три, умноженное само на себя» → $3^2 = 3 \\cdot 3$ →
$3 \\cdot 3 = 9$ → «значит, $3^2 = 9$». Нельзя: «формула → сразу ответ», пропуск промежуточных
вычислений, термин без случая, который он называет. Поле explanation в любом блоке с ответом
(GuidedPractice, IndependentProblem, RetrievalCheck, MasteryCheck, PredictionLab, SortAndClassify
и других) показывает путь к ответу, а не повторяет ответ. Как именно показывать ход мысли в этом
предмете, передаётся в запросе.

Следуй переданному предметному маршруту, а не одной универсальной последовательности.
Для математических задач используй разобранные примеры, MisconceptionDebugger,
SortAndClassify или ProcessBuilder; для наук — PredictionLab, DataInvestigation,
PhysicsSandbox и ProcessBuilder; для языков — SortAndClassify,
BranchingScenario и ArgumentMap; для гуманитарных предметов — источники,
ArgumentMap, BranchingScenario, ProcessBuilder, ChronologyLine (хронология) и CauseEffectMap (причины и последствия в истории); для информатики —
CodeBlocksLab, MisconceptionDebugger и ProcessBuilder; для практических предметов —
BranchingScenario и самооценку. Цифровой тест не должен подменять
физическое или творческое выполнение. Заверши урок Reflection и MasteryCheck с вопросом
по каждой цели. В уроке должно быть не менее пяти оцениваемых действий с учётом отдельных
вопросов MasteryCheck.

Не добавляй поля вне описанных схем, кроме трёх служебных полей выше. Каждый обязательный
Presentation состоит из коротких слайдов, число которых задаёт содержание: одна мысль или один шаг
рассуждения — один слайд (micro — 3–5, standard — 4–8, extended и unit — 6–10). Порядок: вопрос или
опора на опыт → наглядная модель → разобранная связь по шагам, как в разделе «Как объяснять»
(можно несколько слайдов) → мини-проверка понимания. У каждого слайда обязательны id, learning_point и
avatar_script. Послайдовая реплика должна добавлять объяснение своими словами и не зачитывать
слайд. Она не должна повторять заголовок, списки, таблицу или формулу со слайда дословно. Блочный
avatar_script для Presentation не используй. Правильные ответы должны точно совпадать с одним из
вариантов там, где варианты предусмотрены. Урок должен соответствовать теме, целям,
навыкам и ресурсам из запроса пользователя.
""".strip()


def _extract_text(response: Any) -> str:
    return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")


def _blocks_from_tool(response: Any) -> list[dict[str, Any]] | None:
    """Блоки из вызова инструмента. None — инструмент не заполнен."""
    tool_block = next(
        (b for b in response.content if getattr(b, "type", "") == "tool_use"), None
    )
    if tool_block is None:
        return None
    blocks = dict(tool_block.input).get("blocks")
    if not isinstance(blocks, list):
        return None
    return _validate_blocks(blocks)


def _validate_blocks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("Урок должен быть непустым массивом блоков")
    for block in value:
        if (
            not isinstance(block, dict)
            or not isinstance(block.get("component"), str)
            or not isinstance(block.get("content"), dict)
        ):
            raise ValueError("Некорректная структура блока")
    return value


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


# Большой урок в один ответ модели не помещается (MAX_TOKENS) и упирается
# в тайм-аут поставщика, поэтому его генерируем по частям — по целям урока.
PARTS_VOLUMES = {"extended", "unit"}
PARTS_MIN_OBJECTIVES = 3
PARTS_MIN_STEPS = 12
# У контрольной план короткий, а в проекте все шаги общие — делить незачем.
SINGLE_CALL_SHAPES = {"assessment_only", "project_or_practical"}
PART_SUMMARY_LIMIT = 1500
# Компоненты, которые модель должна ставить только в свою часть урока.
FINAL_PART_COMPONENTS = {"MasteryCheck", "Reflection"}


class LessonTruncated(RuntimeError):
    """Ответ модели оборвался на лимите токенов."""


def should_generate_in_parts(topic_contract: dict[str, Any], objective_count: int, step_count: int = 0) -> bool:
    if str(topic_contract.get("lesson_shape") or "") in SINGLE_CALL_SHAPES:
        return False
    return (
        str(topic_contract.get("volume") or "") in PARTS_VOLUMES
        or objective_count >= PARTS_MIN_OBJECTIVES
        or step_count >= PARTS_MIN_STEPS
    )


def _is_timeout(exc: BaseException) -> bool:
    """Тайм-аут поставщика (httpx или SDK) где-то в цепочке причин ошибки."""
    current: BaseException | None = exc
    while current is not None:
        if "timeout" in type(current).__name__.lower():
            return True
        current = current.__cause__ or current.__context__
    return False


def summarize_blocks(blocks: list[dict[str, Any]], limit: int = PART_SUMMARY_LIMIT) -> str:
    """Что уже есть в уроке: термины, слайды, разобранные примеры — для связности частей."""
    terms: list[str] = []
    slides: list[str] = []
    examples: list[str] = []
    used: dict[str, int] = {}
    for block in blocks:
        content = block.get("content") if isinstance(block.get("content"), dict) else {}
        component = block.get("component")
        used[str(component)] = used.get(str(component), 0) + 1
        if component == "KeyConcept" and content.get("term"):
            terms.append(str(content["term"]))
        elif component == "ShortExplanation" and content.get("title"):
            terms.append(str(content["title"]))
        elif component == "Presentation" and isinstance(content.get("slides"), list):
            slides.extend(str(slide.get("heading")) for slide in content["slides"] if isinstance(slide, dict) and slide.get("heading"))
        elif component in {"WorkedExample", "GuidedPractice", "IndependentProblem"}:
            text = content.get("problem") or content.get("question")
            if text:
                examples.append(str(text)[:160])
    sections = (
        ("Разобранные примеры и задачи", examples),
        ("Введённые термины", terms),
        ("Слайды", slides),
        ("Уже использованные компоненты", [f"{name} ×{count}" for name, count in used.items()]),
    )
    # У каждой строки свой бюджет: длинный список слайдов не вытесняет примеры.
    share = limit // len(sections)
    return "\n".join(f"{label}: {'; '.join(items)}"[:share] for label, items in sections if items)


def _part_prompt(
    user_prompt: str, index: int, total: int, steps: list[dict[str, Any]], summary: str, objective_ids: list[str],
) -> str:
    first, last = index == 0, index == total - 1
    rules = [
        f"ГЕНЕРАЦИЯ ПО ЧАСТЯМ. Сейчас ты генерируешь только часть {index + 1} из {total} этого урока; "
        "части склеиваются по порядку в один урок. Правила этой части важнее общих требований "
        "к полному уроку выше. Если lesson_shape=unit_part, весь этот урок — первая часть темы, "
        "а «часть» здесь — только порция генерации.",
        f"Шаги этой части (по одному блоку на шаг, ровно эти шаги, по порядку): {json.dumps(steps, ensure_ascii=False)}",
        "Остальные шаги плана уже созданы или будут созданы в других частях — не повторяй их.",
    ]
    if not first:
        rules.append("Не добавляй титул intro. Разминку добавляй, только если шаг diagnose есть среди шагов этой части.")
    if not last:
        rules.append(
            "Не добавляй MasteryCheck и Reflection и не делай блоков с evidence_stage \"assessment\": "
            "итоговая проверка каждой цели — вопросом MasteryCheck в последней части."
        )
    else:
        rules.append(f"MasteryCheck содержит отдельный итоговый вопрос по каждой цели урока: {', '.join(objective_ids)}.")
    if summary:
        rules.append(
            "Уже есть в уроке (не повторяй эти примеры, опирайся на введённые термины, продолжай ту же историю):\n"
            + summary
        )
    return user_prompt + "\n\n" + "\n".join(rules)


def _part_label(steps: list[dict[str, Any]], objectives: list[dict[str, Any]]) -> str:
    if any(step.get("role") in {"assess", "reflect"} for step in steps):
        return "итоговая проверка и рефлексия"
    ids = {objective_id for step in steps for objective_id in step.get("objective_ids") or []}
    if len(ids) == 1:
        objective_id = next(iter(ids))
        text = next((item.get("text") for item in objectives if item.get("id") == objective_id), objective_id)
        return f"цель: {text}"
    return "итоговая проверка и рефлексия"


class _BlocksRequest:
    """Один запрос урока (или его части) к модели с повтором при неразборчивом ответе."""

    def __init__(self, *, call_tool: Any, task: str, route: "Route | None", textbook_block: str | None = None) -> None:
        self.call_tool = call_tool
        self.task = task
        self.route = route
        # Учебник — кэшируемым системным блоком: при генерации по частям не оплачивается заново.
        self.system_options: dict[str, Any] = (
            {"system": "", "system_blocks": [{"text": SYSTEM_PROMPT, "cache": True}, {"text": textbook_block, "cache": True}]}
            if textbook_block else {"system": SYSTEM_PROMPT}
        )

    async def blocks(self, user_prompt: str) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        retry_prompt = user_prompt
        result = None
        for attempt in range(2):
            result = await self.call_tool(
                self.task,
                **self.system_options,
                user=retry_prompt,
                tool=LESSON_TOOL,
                max_tokens=MAX_TOKENS,
                route=self.route,
            )

            # Обрыв по лимиту — не «некорректный JSON». Повтор тем же запросом
            # ничего не даст, поэтому говорим прямо, что урок не поместился.
            if result.truncated:
                raise LessonTruncated(
                    f"Урок не поместился в ответ модели {result.model} "
                    f"({MAX_TOKENS} токенов). Тема слишком объёмная: уменьшите число "
                    "целей обучения у темы или выберите модель с большим лимитом."
                )

            try:
                if result.ok:
                    blocks = GeneratedBlocks(_validate_blocks(result.data.get("blocks")))
                    blocks.intro = clean_intro(result.data.get("intro"))
                    return blocks
                # Инструмент не заполнен — пробуем разобрать текст, как раньше.
                return _validate_blocks(_parse_blocks(result.text))
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt == 0:
                    retry_prompt = (
                        user_prompt
                        + "\nПредыдущий ответ не удалось разобрать. "
                        "Передай урок вызовом инструмента submit_lesson."
                    )

        # Второй заход тоже не дал структуры — сохраняем сырой ответ, чтобы
        # не гадать вслепую, и называем поставщика и модель.
        dump = Path(tempfile.gettempdir()) / "lesson-raw.txt"
        try:
            data = json.dumps(result.data, ensure_ascii=False)[:20000] if result.data else ""
            dump.write_text(
                f"provider={result.provider} model={result.model} "
                f"stop={result.stop_reason}\n\ntext:\n{result.text}\n\ntool input:\n{data}",
                encoding="utf-8",
            )
            where = f" Сырой ответ: {dump}"
        except OSError:
            where = ""
        raise RuntimeError(
            f"Модель {result.model} дважды вернула урок в неожиданном виде: "
            f"{last_error}.{where}"
        ) from last_error


async def _generate_in_parts(
    request: _BlocksRequest,
    user_prompt: str,
    parts: list[list[dict[str, Any]]],
    objectives: list[dict[str, Any]],
) -> GeneratedBlocks:
    """Урок по частям, последовательно: каждая часть знает, что уже создано.

    Если часть не удалась, падает весь урок — половину урока не сохраняем.
    """
    # ID целей берём из плана: при пустых целях там obj-general, а каталог пуст.
    objective_ids = list(dict.fromkeys(
        str(objective_id) for steps in parts for step in steps for objective_id in step.get("objective_ids") or []
    ))
    lesson = GeneratedBlocks()
    for index, steps in enumerate(parts):
        try:
            prompt = _part_prompt(user_prompt, index, len(parts), steps, summarize_blocks(lesson), objective_ids)
            blocks = await request.blocks(prompt)
        except Exception as exc:
            raise RuntimeError(
                f"Не удалось сгенерировать часть {index + 1} из {len(parts)} "
                f"({_part_label(steps, objectives)}): {exc}"
            ) from exc
        if index == 0:
            lesson.intro = getattr(blocks, "intro", None)
        # Страховка от ослушания: итоговая проверка и рефлексия — только в своей части.
        allowed = {name for step in steps for name in step.get("allowed_components") or []}
        lesson.extend(
            block for block in blocks
            if block.get("component") not in FINAL_PART_COMPONENTS or block.get("component") in allowed
        )
    return lesson


async def generate_lesson(
    topic_name: str,
    subject_name: str,
    learning_objectives: str | None,
    skills: list[str] | None,
    resources: str | None,
    grade: int | None = None,
    hours: int | None = None,
    lesson_type: str | None = None,
    content_language: str = "ru",
    topic_contract: dict[str, Any] | None = None,
    component_plan: list[dict[str, Any]] | None = None,
    model_route: "Route | None" = None,
    textbook: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    from ai.textbook_grounding import textbook_system_block
    from llm import TASK_LESSON, call_tool

    profile = classify_subject(subject_name)
    archetype = select_archetype(
        str(profile["family"]), topic_name, lesson_type, learning_objectives
    )
    route = SUBJECT_FAMILY_PROFILES[str(profile["family"])]["route"]
    objective_catalog = decompose_objectives(learning_objectives)
    if topic_contract is None or component_plan is None:
        plan = build_topic_contract(
            topic_name=topic_name,
            subject_name=subject_name,
            learning_objectives=learning_objectives,
            skills=skills,
            resources=resources,
            grade=grade,
            hours=hours,
            lesson_type=lesson_type,
            content_language=content_language,
        )
        topic_contract = topic_contract or plan["topic_contract"]
        component_plan = component_plan or plan["component_plan"]
    from ai.subject_profiles import subject_profile, subject_prompt

    subject_profile_data = subject_profile(subject_name)
    language_label = "кыргызском" if content_language == "ky" else "русском"
    teaching_requirement = (
        'Это контрольная без таймера. Используй только RetrievalCheck, IndependentProblem и MasteryCheck. '
        'Не добавляй объяснения, подсказки, обратную связь до сдачи или Reflection. '
        'Каждый вопрос проверяет ровно одну цель и содержит objective_ids, правильный ответ и объяснение для разбора после сдачи.'
        if lesson_type == "assessment" else
        'Урок открывается титулом intro, затем ровно один лёгкий RetrievalCheck-разминка '
        '(evidence_stage "diagnostic") по первой цели: вопрос о знакомом из жизни или прошлых тем, без новых терминов. '
        'Для каждой цели обязательно дай объяснение, разобранный пример, самостоятельную практику и независимую итоговую проверку. '
        'В повторении и разборе ошибок закрепляй навыки указанных изученных тем, не придумывай новые навыки для названия занятия.'
    )
    user_prompt = f"""
Создай полный урок.
Семейство предмета: {profile["family_label"]} ({profile["family"]})
Архетип урока: {archetype}
Предметный маршрут: {route}
Как показывать ход мысли: {subject_profile_data["show_path"] if subject_profile_data else SUBJECT_FAMILY_PROFILES[str(profile["family"])]["show_path"]}
{subject_prompt(subject_profile_data) if subject_profile_data else ""}
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
Контракт темы: {json.dumps(topic_contract, ensure_ascii=False)}
План компонентов: {json.dumps(component_plan, ensure_ascii=False)}

Каждый блок, кроме Reflection, ОБЯЗАН содержать objective_ids и явный evidence_stage.
Свяжи каждый блок и каждый вопрос MasteryCheck с ID из структурированных целей.
{teaching_requirement}
Каждый диагностический блок и каждый отдельный итоговый вопрос проверяет ровно одну цель.
Количество блоков должно попасть в block_budget из контракта. Если lesson_shape=unit_part,
сгенерируй только первую часть темы и не пытайся вместить весь модуль. Media через
GeneratedMedia является только опциональным усилением объяснения; урок должен быть
полноценным и без OpenRouter media. Не заменяй обязательный Presentation картинкой или видео.
Титул intro (обязательно, короткий, на языке урока):
- kicker: предмет и класс или образ-подзаголовок, до 60 символов;
- title: короткая большая идея урока, до 80 символов (не копия названия темы из КТП);
- accent: образ или метафора урока одной фразой, до 60 символов, например «Квадратный сад.»;
- hook: жизненная загадка или ситуация, 1–2 предложения, без терминов урока, до 280 символов;
- cta: глагол на кнопке, до 40 символов, например «Спроектировать сад».
Передай урок вызовом инструмента submit_lesson.
""".strip()

    request = _BlocksRequest(
        call_tool=call_tool, task=TASK_LESSON, route=model_route,
        textbook_block=textbook_system_block(textbook) if textbook else None,
    )
    parts = split_component_plan(component_plan)
    if len(parts) > 1 and should_generate_in_parts(topic_contract, len(objective_catalog), len(component_plan)):
        return await _generate_in_parts(request, user_prompt, parts, objective_catalog)
    try:
        return await request.blocks(user_prompt)
    except Exception as exc:
        # Одним ответом урок не поместился или не успел за тайм-аут поставщика —
        # собираем его по частям: каждая короче и укладывается в лимиты.
        if len(parts) > 1 and (isinstance(exc, LessonTruncated) or _is_timeout(exc)):
            return await _generate_in_parts(request, user_prompt, parts, objective_catalog)
        raise
