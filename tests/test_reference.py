"""Tests for the creative reference library (character/environment bibles)."""
import pytest
from dabwayo import reference as R


def test_create_get_list_update_remove():
    c = R.create("character", "Mina", "dark bob")
    assert c["id"].startswith("char_") and c["kind"] == "character"
    got = R.get("character", c["id"])
    assert got["name"] == "Mina"
    assert any(x["id"] == c["id"] for x in R.list_all("character"))
    R.update("character", c["id"], {"description": "calm"})
    assert R.get("character", c["id"])["description"] == "calm"
    # structural fields can't be clobbered via update
    R.update("character", c["id"], {"variants": "HACK", "id": "X"})
    assert isinstance(R.get("character", c["id"])["variants"], list)
    assert R.remove("character", c["id"]) is True


def test_variants_and_refs():
    e = R.create("environment", "Apt", "flat")
    v = R.add_variant("environment", e["id"], "dawn", prompt_fragment="cool light",
                      attributes={"time_of_day": "dawn", "lighting": "cool"})
    assert v["id"].startswith("v_") and v["time_of_day"] == "dawn"
    R.attach_ref("environment", e["id"], "ast_base")
    R.attach_ref("environment", e["id"], "ast_var", variant_id=v["id"])
    rec = R.get("environment", e["id"])
    assert rec["base_refs"] == ["ast_base"]
    assert rec["variants"][0]["refs"] == ["ast_var"]
    R.detach_ref("environment", e["id"], "ast_base")
    assert R.get("environment", e["id"])["base_refs"] == []
    R.remove_variant("environment", e["id"], v["id"])
    assert R.get("environment", e["id"])["variants"] == []


def test_bad_kind_and_id():
    with pytest.raises(ValueError):
        R.create("prop", "x")
    with pytest.raises(ValueError):
        R.get("character", "../etc/passwd")
