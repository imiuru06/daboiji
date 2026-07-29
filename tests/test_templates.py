"""Tests for template placeholder filling."""
from dabwayo.templates import fill, placeholders, list_builtin, load


def test_whole_value_token_preserves_type():
    spec = {"duration": "{{duration}}", "title": "{{title}}"}
    filled, missing = fill(spec, {"duration": 4, "title": "Hi"})
    assert filled["duration"] == 4 and isinstance(filled["duration"], int)
    assert filled["title"] == "Hi"
    assert missing == []


def test_embedded_token_interpolates_and_reports_missing():
    spec = {"text": "Hello {{name}} from {{city}}"}
    filled, missing = fill(spec, {"name": "Ann"})
    assert filled["text"] == "Hello Ann from {{city}}"
    assert missing == ["city"]


def test_placeholders_walks_nested():
    spec = {"a": ["{{x}}", {"b": "{{y}} {{x}}"}], "c": 3}
    assert placeholders(spec) == {"x", "y"}


def test_builtin_templates_load_and_have_specs():
    names = list_builtin()
    assert "title_card" in names and "quote" in names
    for n in names:
        tpl = load(n)
        assert "spec" in tpl and isinstance(tpl.get("defaults", {}), dict)
