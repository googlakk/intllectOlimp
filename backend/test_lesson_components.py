import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ai import component_generator
from llm.base import STOP_TOOL, ToolResult
from objectives import decompose_objectives
from services import lesson_components as service
from services.lessons import LessonServiceError
from test_lesson_versions import VersionSession


MATERIAL = {
    "textbook_id": 4, "title": "Математика", "student_display": "refs_only",
    "sections": [{"id": 11, "title": "Сложение", "number": "§ 2", "page_from": 5, "page_to": 7,
                  "text": "Сложение чисел", "items": [{"id": 101, "kind": "exercise", "label": "№ 7",
                  "page": 6, "text": "Условие " * 150 + "КОНЕЦ УПРАЖНЕНИЯ", "answer": "5"}]}],
}
BLOCK = {"component": "ShortExplanation", "content": {"title": "Сложение", "text": "Два плюс три равно пяти.",
                                                       "key_concepts": ["Сумма"]}}


class ComponentSession(VersionSession):
    def __init__(self):
        super().__init__()
        self.rolled_back = False
        self.locked = False

    async def rollback(self):
        self.rolled_back = True

    async def get(self, model, row_id):
        from models import Section, Subject
        if model is Section:
            return SimpleNamespace(subject_id=7)
        if model is Subject:
            return SimpleNamespace(name="Математика", grade=7, instruction_language="ky")
        return await super().get(model, row_id)

    async def scalar(self, statement):
        if "FOR UPDATE" in str(statement):
            self.locked = True
        return await super().scalar(statement)


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "only-a-fake-test-signing-key")
    loader = AsyncMock(return_value=deepcopy(MATERIAL))
    generator = AsyncMock(return_value=deepcopy(BLOCK))
    monkeypatch.setattr(service, "load_component_textbook_context", loader)
    monkeypatch.setattr(service, "generate_component", generator)
    return ComponentSession(), loader, generator


async def prepare(db, component="ShortExplanation"):
    return await service.prepare_component(
        2, component=component, objective_id=decompose_objectives(db.topic.learning_objectives)[0]["id"],
        base_revision=service.lesson_revision(db.lesson, db.topic), after_index=0,
        source_section_id=11, source_item_id=101, model=None, db=db,
    )


async def insert(db, result, request_id="first-request"):
    return await service.insert_component(
        2, block=result["block"], after_index=0, base_revision=result["base_revision"],
        context_fingerprint=result["context_fingerprint"], request_id=request_id, db=db,
    )


def test_prepare_releases_read_transaction_and_sends_full_source_without_saving(setup):
    db, loader, generator = setup
    before = deepcopy(db.lesson.blocks)
    async def generate(**kwargs):
        assert db.rolled_back
        assert kwargs["topic"]["language"] == "ky"
        assert kwargs["topic"]["subject"] == "Математика"
        context = kwargs["topic"]["existing_lesson"]
        assert context["after_index"] == 0 and context["insertion_index"] == 1
        assert len(context["outline"]) == len(before)
        assert [neighbor["position"] for neighbor in context["neighbors"]] == ["before", "after"]
        assert kwargs["topic"]["lesson_type"] == "study"
        assert kwargs["material"]["sections"][0]["items"][0]["text"].endswith("КОНЕЦ УПРАЖНЕНИЯ")
        return deepcopy(BLOCK)
    generator.side_effect = generate
    result = asyncio.run(prepare(db))
    assert db.lesson.blocks == before
    assert db.lesson.active_version_id == 10
    assert result["block"]["content"]["source_ref"]["item_id"] == 101
    assert "№ 7" in result["source_label"]
    assert result["base_revision"] == service.lesson_revision(db.lesson, db.topic)
    assert loader.await_args.kwargs == {"source_section_id": 11, "source_item_id": 101}


def test_insert_uses_versions_keeps_published_and_is_idempotent(setup):
    db, _, _ = setup
    original = deepcopy(db.versions[10].lesson_document)
    async def run():
        result = await prepare(db)
        count = len(db.lesson.blocks)
        await insert(db, result)
        assert db.locked
        assert len(db.lesson.blocks) == count + 1
        assert db.lesson.active_version_id == 11
        assert db.lesson.published_version_id == 10
        assert db.versions[10].lesson_document == original
        await insert(db, result)
        assert len(db.lesson.blocks) == count + 1
        assert db.lesson.active_version_id == 11
    asyncio.run(run())


@pytest.mark.parametrize("change", ["block", "source", "objective", "token"])
def test_modified_prepared_payload_rejected(setup, change):
    db, _, _ = setup
    async def run():
        result = await prepare(db)
        if change == "block":
            result["block"]["content"]["text"] = "Подмена"
        elif change == "source":
            result["block"]["content"]["source_ref"]["item_id"] = 999
        elif change == "objective":
            result["block"]["content"]["objective_ids"] = ["foreign"]
        else:
            result["context_fingerprint"] += "bad"
        with pytest.raises(LessonServiceError) as caught:
            await insert(db, result)
        assert caught.value.status_code == 422
        assert db.lesson.active_version_id == 10
    asyncio.run(run())


@pytest.mark.parametrize("change", ["lesson", "objective", "material", "revoked", "expired"])
def test_stale_context_is_not_inserted(setup, monkeypatch, change):
    db, loader, _ = setup
    async def run():
        result = await prepare(db)
        if change == "lesson":
            db.lesson.active_version_id = 12
        elif change == "objective":
            db.topic.learning_objectives = "Вычитать числа"
        elif change == "material":
            loader.return_value["sections"][0]["items"][0]["text"] = "Новое условие"
        elif change == "revoked":
            loader.return_value = None
        else:
            future = service.time.time() + service.TOKEN_TTL + 1
            monkeypatch.setattr(service.time, "time", lambda: future)
        with pytest.raises(LessonServiceError) as caught:
            await insert(db, result)
        assert caught.value.status_code in (409, 422)
        assert len(db.versions) == 1
    asyncio.run(run())


def test_missing_context_does_not_call_paid_generator(setup):
    db, loader, generator = setup
    loader.return_value = None
    with pytest.raises(LessonServiceError, match="Подтвердите"):
        asyncio.run(prepare(db))
    generator.assert_not_awaited()
    result = asyncio.run(service.component_context(2, db))
    assert result["sources"] == [] and result["reason"]


def test_model_forged_source_removed_and_objective_assigned_by_server(setup):
    db, _, generator = setup
    generator.return_value["content"]["source_ref"] = {"item_id": 999}
    generator.return_value["content"]["objective_ids"] = ["fake"]
    result = asyncio.run(prepare(db))
    assert result["block"]["content"]["source_ref"]["item_id"] == 101
    assert result["block"]["content"]["objective_ids"] == [decompose_objectives(db.topic.learning_objectives)[0]["id"]]


def test_required_component_fields_validated_before_preview(setup):
    db, _, generator = setup
    generator.return_value["content"].pop("text")
    with pytest.raises(LessonServiceError, match="обязательные"):
        asyncio.run(prepare(db))


def test_source_catalog_contains_no_text_or_answers(setup):
    db, _, _ = setup
    result = asyncio.run(service.component_context(2, db))
    assert result["sources"][0]["items"][0] == {"id": 101, "label": "№ 7", "kind": "exercise", "page": 6}
    assert "КОНЕЦ" not in str(result)
    assert "RuleDiscovery" in result["supported_components"]
    assert "GeneratedMedia" not in result["supported_components"]
    assert "HotspotInvestigation" not in result["supported_components"]


def test_component_provider_uses_single_block_tool_and_keeps_long_exercise(monkeypatch):
    provider = AsyncMock(return_value=ToolResult(data={"block": deepcopy(BLOCK)}, stop_reason=STOP_TOOL))
    monkeypatch.setattr(component_generator, "call_tool", provider)
    asyncio.run(component_generator.generate_component(
        component="ShortExplanation", schema=service._schema("ShortExplanation"),
        objective={"id": "obj", "text": "Складывать"}, topic={"name": "Сумма"}, material=MATERIAL,
    ))
    assert provider.await_count == 1
    call = provider.await_args.kwargs
    assert call["tool"]["name"] == "submit_component"
    assert "КОНЕЦ УПРАЖНЕНИЯ" in call["user"]
    assert "дословно НЕ копируй" in call["system"]


def test_routes_require_management_and_valid_uuid():
    from routes.lesson_components import InsertInput, PrepareInput, router
    from pydantic import ValidationError
    assert len(router.routes) == 3
    assert all(route.dependant.dependencies for route in router.routes)
    assert PrepareInput(component="RuleDiscovery", objective_id="obj", base_revision="rev", after_index=-1).after_index == -1
    with pytest.raises(ValidationError):
        InsertInput(block=BLOCK, base_revision="rev", context_fingerprint="token", request_id="invalid")


def test_route_denies_management_before_preparing(monkeypatch):
    from routes import lesson_components as routes
    from services.auth import AuthServiceError
    denial = AsyncMock(side_effect=AuthServiceError(status_code=404, detail="Чужой урок"))
    prepare_call = AsyncMock()
    monkeypatch.setattr(routes, "require_lesson_management", denial)
    monkeypatch.setattr(routes, "prepare_component", prepare_call)
    with pytest.raises(AuthServiceError):
        asyncio.run(routes.prepare(2, routes.PrepareInput(component="RuleDiscovery", objective_id="obj", base_revision="rev"),
                                   user=SimpleNamespace(role="teacher"), db=SimpleNamespace()))
    prepare_call.assert_not_awaited()


def test_stale_revision_rejected_before_paid_call(setup):
    db, _, generator = setup
    with pytest.raises(LessonServiceError) as caught:
        asyncio.run(service.prepare_component(2, component="ShortExplanation", objective_id="obj",
            after_index=None, base_revision="old", source_section_id=11, source_item_id=101, model=None, db=db))
    assert caught.value.status_code == 409
    generator.assert_not_awaited()


def test_neighbor_context_bounded_excludes_source_and_media():
    blocks = [deepcopy(BLOCK), deepcopy(BLOCK), deepcopy(BLOCK)]
    content = blocks[1]["content"]
    content.update(text="Смысл " * 1500 + " https://hidden.example/asset", source_ref={"text": "PRIVATE SOURCE"},
                   media={"text": "PRIVATE MEDIA", "url": "https://private.example"}, correct_answer="PRIVATE ANSWER")
    context = service._insertion_context(blocks, 1, "RuleDiscovery")
    assert len(context["outline"]) == 3
    assert [neighbor["index"] for neighbor in context["neighbors"]] == [1, 2]
    assert all(len(neighbor["excerpt"]) <= 1600 for neighbor in context["neighbors"])
    assert "PRIVATE" not in str(context) and "https://" not in str(context)
    assert service._insertion_context([], -1, "RuleDiscovery")["neighbors"] == []


def test_changed_neighbor_invalidates_prepared_preview(setup):
    db, _, _ = setup
    async def run():
        result = await prepare(db)
        db.lesson.blocks[0]["content"]["title"] = "Изменили соседний блок во время предпросмотра"
        with pytest.raises(LessonServiceError) as caught:
            await insert(db, result)
        assert caught.value.status_code == 409
    asyncio.run(run())


def test_model_choice_error_is_translated_without_saving(setup):
    from llm.catalog import ModelChoiceError
    db, _, generator = setup
    generator.side_effect = ModelChoiceError("Недоступная модель")
    with pytest.raises(LessonServiceError, match="Недоступная модель") as caught:
        asyncio.run(prepare(db))
    assert caught.value.status_code == 422 and db.lesson.active_version_id == 10


def test_schema_union_and_new_numeric_models():
    service._validate_schema(["-2", "2"], {"type": ["string", "array"]})
    content = {"title": "Найди правило", "prompt": "Проверь числа", "rule": {"kind": "affine", "multiplier": 2, "offset": 1},
               "examples": [1, 2], "challenge_inputs": [3, 4], "explanation": "Умножение и сложение"}
    service._validate_block({"component": "RuleDiscovery", "content": content}, service._schema("RuleDiscovery"))
    content["rule"]["kind"] = "javascript"
    with pytest.raises(LessonServiceError):
        service._validate_block({"component": "RuleDiscovery", "content": content}, service._schema("RuleDiscovery"))


@pytest.mark.parametrize("block", [
    {"component": "StepSolver", "content": {"title": "Найдите допустимые значения", "kind": "expression",
       "start": "y/(y^2-5*y)", "final_answer": ["y != 5"], "explanation": "Знаменатель не равен нулю"}},
    {"component": "FunctionExplorer", "content": {"formula": "k*x", "params": [
       {"name": "k", "min": -3, "max": 3, "step": 1, "default": 0}], "target": {"params": {"k": 9}}}},
])
def test_invalid_legacy_interactive_rejected_in_preview_and_insert(setup, block):
    db, _, generator = setup
    async def run():
        generator.return_value = deepcopy(block)
        with pytest.raises(LessonServiceError, match="корректный блок"):
            await prepare(db, block["component"])
        generator.return_value = deepcopy(BLOCK)
        result = await prepare(db)
        payload = service._verify(result["context_fingerprint"])
        result["block"] = deepcopy(block)
        payload["block"] = service._digest(block)
        result["context_fingerprint"] = service._sign(payload)
        with pytest.raises(LessonServiceError, match="корректный блок"):
            await insert(db, result)
        assert db.lesson.active_version_id == 10
    asyncio.run(run())


def test_addressed_loader_only_returns_linked_full_item(monkeypatch):
    from services import textbook_context
    from textbooks.models import Textbook, TextbookItem, TextbookSection
    class Savepoint:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
    section = SimpleNamespace(id=11, textbook_id=4, number="§2", title="Сумма", pdf_from=5, pdf_to=7)
    item = SimpleNamespace(id=101, section_id=11, textbook_id=4, kind="exercise", label="№7", page=6,
                           text="Длинное условие " * 100 + "ФИНИШ", answer="5", difficulty=1)
    book = SimpleNamespace(id=4, title="Математика", student_display="refs_only", page_offset=0)
    class DB:
        def begin_nested(self): return Savepoint()
        async def scalars(self, statement):
            model = statement.column_descriptions[0]["entity"]
            rows = [section] if model is TextbookSection else [item] if model is TextbookItem else []
            return SimpleNamespace(all=lambda: rows)
        async def get(self, model, row_id): return book if model is Textbook else None
    monkeypatch.setattr(textbook_context, "_confirmed_links", AsyncMock(return_value=[SimpleNamespace(section_id=11)]))
    topic = SimpleNamespace(id=1, lesson_type="study", covered_topic_ids=[])
    data = asyncio.run(textbook_context.load_component_textbook_context(DB(), topic, source_item_id=101))
    assert data["sections"][0]["items"][0]["text"] == item.text
    assert asyncio.run(textbook_context.load_component_textbook_context(DB(), topic, source_item_id=999)) is None
    assert asyncio.run(textbook_context.load_component_textbook_context(DB(), topic, source_section_id=99, source_item_id=101)) is None
