import pytest

from app.services.templating import TemplateError, render


def test_single_expression_preserves_type():
    ctx = {"input": {"n": 5, "obj": {"a": 1}}, "steps": {}}
    assert render("{{ input.n }}", ctx) == 5
    assert render("{{ input.obj }}", ctx) == {"a": 1}


def test_string_interpolation_stringifies():
    ctx = {"input": {"name": "Ada", "n": 3}, "steps": {}}
    assert render("Hello {{ input.name }} ({{ input.n }})", ctx) == "Hello Ada (3)"


def test_list_index_navigation():
    ctx = {"input": {}, "steps": {"s": {"output": {"items": [{"t": "x"}, {"t": "y"}]}}}}
    assert render("{{ steps.s.output.items.1.t }}", ctx) == "y"


def test_renders_recursively_through_dicts_and_lists():
    ctx = {"input": {"a": "A"}, "steps": {}}
    out = render({"k": "{{ input.a }}", "l": ["{{ input.a }}", 2]}, ctx)
    assert out == {"k": "A", "l": ["A", 2]}


def test_missing_reference_raises():
    with pytest.raises(TemplateError):
        render("{{ input.nope }}", {"input": {}, "steps": {}})
