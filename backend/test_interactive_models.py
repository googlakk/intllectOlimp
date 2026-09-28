"""Pure model checks: no providers, database, or lesson mutations."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from services.interactive_models import interactive_model_problem, rule_output
from objectives import component_content_warnings, PRACTICE_COMPONENTS, INDEPENDENT_ASSESSMENT_COMPONENTS
from ai.planner import build_topic_contract


RULE = {"title": "Машина", "prompt": "Найди правило", "rule": {"kind": "affine", "multiplier": 2, "offset": 3},
        "examples": [0, 1, 2], "challenge_inputs": [3, 4, 5], "explanation": "Умножь на 2, прибавь 3"}
MACHINE = {"title": "Машина", "prompt": "Собери действия", "inputs": [1, 2, 3], "target_outputs": [5, 7, 9],
           "operations": [{"id": "double", "label": "×2", "kind": "multiply", "value": 2},
                          {"id": "plus", "label": "+3", "kind": "add", "value": 3}],
           "solution": ["double", "plus"], "max_steps": 3, "explanation": "Сначала удвоить, затем прибавить 3"}


def test_shared_browser_server_numeric_fixtures():
    fixtures = json.loads((Path(__file__).parent / "fixtures" / "number_machine_cases.json").read_text())
    for group, component in (("rule", "RuleDiscovery"), ("machine", "TransformationMachine")):
        for case in fixtures[group]["cases"]:
            content = {**fixtures[group]["base"], **case["patch"]}
            assert (interactive_model_problem(component, content) is None) is case["valid"], case["name"]


@pytest.mark.parametrize("component,content", [("RuleDiscovery", RULE), ("TransformationMachine", MACHINE)])
def test_valid_numeric_models_are_classified_and_pass_quality(component, content):
    assert interactive_model_problem(component, content) is None
    assert component in PRACTICE_COMPONENTS & INDEPENDENT_ASSESSMENT_COMPONENTS
    assert component_content_warnings([{"component": component, "content": content}]) == []


@pytest.mark.parametrize("kind,expected", [("affine", -3), ("square", 21), ("absolute", 9)])
def test_rule_forms(kind, expected):
    assert rule_output({"kind": kind, "multiplier": 2, "offset": 3}, -3) == expected


@pytest.mark.parametrize("field,value", [("examples", []), ("examples", [True]), ("examples", [101]),
    ("challenge_inputs", [1, 4]), ("challenge_inputs", [3, 3]), ("challenge_inputs", [float("nan")]),
    ("rule", {"kind": [], "multiplier": 2, "offset": 1}),
    ("rule", {"kind": "affine", "multiplier": 10**1000, "offset": 0}), ("prompt", " ")])
def test_bad_rule_data_rejected_without_crash(field, value):
    content = deepcopy(RULE)
    content[field] = value
    assert interactive_model_problem("RuleDiscovery", content)
    assert component_content_warnings([{"component": "RuleDiscovery", "content": content}])[0]["code"] == "rule_discovery_invalid"


@pytest.mark.parametrize("field,value", [("inputs", [False]), ("inputs", [1] * 7), ("target_outputs", [5]),
    ("target_outputs", [5, 7, 10]), ("solution", []), ("solution", ["unknown"]),
    ("max_steps", True), ("max_steps", 9), ("solution", ["double"] * 4),
    ("operations", [{"id": "double", "label": "divide", "kind": "divide", "value": 0}]),
    ("operations", [MACHINE["operations"][0]] * 2)])
def test_bad_machine_data_rejected(field, value):
    content = deepcopy(MACHINE)
    content[field] = value
    assert interactive_model_problem("TransformationMachine", content)


def test_machine_uses_absolute_tolerance_and_checks_every_input():
    content = deepcopy(MACHINE)
    content["target_outputs"][-1] += 0.0000005
    assert interactive_model_problem("TransformationMachine", content) is None
    content["target_outputs"][-1] += 0.000002
    assert interactive_model_problem("TransformationMachine", content)


def test_intermediate_overflow_cannot_be_hidden_by_final_operation():
    content = {**MACHINE, "inputs": [100], "target_outputs": [100],
               "operations": [{"id": "up", "label": "×100", "kind": "multiply", "value": 100},
                              {"id": "down", "label": "÷100", "kind": "divide", "value": 100}],
               "solution": ["up", "up", "up", "down", "down", "down"], "max_steps": 6}
    assert "промежуточный" in interactive_model_problem("TransformationMachine", content)


def candidates(objective, grounded=False, subject="Алгебра"):
    planned = build_topic_contract(topic_name="Практика", subject_name=subject, learning_objectives=objective,
                                  skills=[], resources=None, grade=7, hours=1, lesson_type="study",
                                  textbook_grounded=grounded)
    return {component for step in planned["component_plan"] for component in step["allowed_components"]}


def test_new_candidates_require_grounding_and_matching_objective():
    assert "RuleDiscovery" not in candidates("Исследовать линейную функцию")
    assert "RuleDiscovery" in candidates("Исследовать линейную функцию", True)
    assert "TransformationMachine" in candidates("Применять порядок действий в числовых выражениях", True)
    assert "RuleDiscovery" not in candidates("Решать квадратные уравнения", True)
    assert "TransformationMachine" not in candidates("Преобразовывать многочлены", True)
    assert "RuleDiscovery" not in candidates("Исследовать линейную функцию", True, "История")
    assert "RuleDiscovery" not in candidates("Исследовать линейную функцию. Решать уравнения.", True)
