"""Configuration, shared rendering, private APIs and read-only workspace behavior."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from maiidentity.host.config import MaiIdentityConfig
from maiidentity.host.plugin import MaiIdentityPlugin
from maiidentity.context.projection import match_person, snapshot, Projector
from .test_identity import evidence
from .test_lifecycle import context


def config():
    return {"plugin": {"config_version": "4"}, "identity": {
        "styles": [{"name": "家人", "prompt": "与{nickname}自然相处"}],
        "people": [
            {"qq": "10001", "nickname": "妈妈", "style": "家人"},
            {"qq": "10001", "nickname": "朋友", "style": "家人", "group_id": "20001", "prompt_template": "在群里轻松聊天"},
            {"qq": "10001", "nickname": "姐姐", "group_id": "20002", "enabled": False},
        ]}, "management": {"admin_accounts": ["10002"]}}


@pytest.mark.parametrize("change", [
    lambda c: c["identity"].update(styles=[]),
    lambda c: c["identity"]["styles"].append({"name": "家人", "prompt": "重复"}),
    lambda c: c["identity"]["styles"][0].update(name=" 家人"),
    lambda c: c["identity"]["styles"][0].update(prompt="  "),
    lambda c: c["identity"]["people"][0].update(style="不存在", enabled=False),
])
def test_reject_missing_in_use_duplicate_and_invalid_templates(change):
    raw = config(); change(raw)
    with pytest.raises(ValueError):
        MaiIdentityConfig.model_validate(raw)


def test_templates_same_matching_and_one_pass_rendering():
    cfg = MaiIdentityConfig.model_validate(config())
    for group, expected in [(None, "与妈妈自然相处"), ("20001", "在群里轻松聊天"), ("20002", "与妈妈自然相处")]:
        e = replace(evidence(), group_id=group)
        person = match_person(cfg.identity.people, e)
        assert snapshot(e, person, styles=cfg.identity.styles)["prompt"] == expected
    cfg.identity.people[0].nickname = "{nickname}"
    assert snapshot(evidence(), cfg.identity.people[0], styles=cfg.identity.styles)["prompt"] == "与{nickname}自然相处"


def test_official_config_schema_contains_editable_template_drafts():
    schema = MaiIdentityPlugin.build_config_schema()
    text = json.dumps(schema, ensure_ascii=False)
    assert '共用相处模板' in text and '共用模板' in text and '相处说明' in text
    assert MaiIdentityConfig.model_validate({}).identity.styles == []


@pytest.mark.asyncio
async def test_workspace_preview_runtime_parity_hot_update_and_no_side_effects(tmp_path):
    p = MaiIdentityPlugin(); ctx, calls = context(tmp_path); p._set_context(ctx)
    p.set_plugin_config(config()); await p.on_load()
    try:
        before_calls = list(calls)
        before_db = list(p.db.conn.iterdump())
        state = await p.workspace_state()
        original = deepcopy(p.active.model_dump())
        for group in ("", "20001", "20002"):
            result = await p.workspace_preview("10001", group, state["revision"])
            e = replace(evidence(), group_id=group or None)
            facts = snapshot(e, match_person(p.active.identity.people, e), styles=p.active.identity.styles)
            assert result["text"] == p.projector.block(facts).split("\n", 2)[2].rsplit("\n", 1)[0]
            assert "10001" not in result["text"]
        assert (await p.workspace_preview("10002", "", state["revision"]))["state"] == "unlisted"
        assert p.active.model_dump() == original and calls == before_calls
        assert list(p.db.conn.iterdump()) == before_db
        state["identity"]["people"].clear()
        assert len((await p.workspace_state())["identity"]["people"]) == 3
        updated = config(); updated["identity"]["styles"][0]["prompt"] = "更新的模板"
        await p.on_config_update("self", updated, "4")
        with pytest.raises(ValueError, match="CONFIG_CHANGED_REFRESH"):
            await p.workspace_preview("10001", "", state["revision"])
        new = await p.workspace_state()
        assert "更新的模板" in (await p.workspace_preview("10001", "", new["revision"]))["text"]
        assert new["admin_accounts"] == ["10002"]
        await p.on_unload()
        with pytest.raises(ValueError, match="NOT_READY"):
            await p.workspace_state()
    finally:
        await p.on_unload()


@pytest.mark.asyncio
async def test_preview_disabled_budget_and_invalid_input(tmp_path):
    p = MaiIdentityPlugin(); p._set_context(context(tmp_path)[0]); raw = config()
    raw["identity"]["styles"][0]["prompt"] = "很长的相处说明" * 140
    raw["context"] = {"budget_bytes": 1200}
    p.set_plugin_config(raw); await p.on_load()
    try:
        state = await p.workspace_state()
        result = await p.workspace_preview("10001", "", state["revision"])
        assert result["truncated"] and "固定身份只来自" in result["text"]
        for account, group in [("abc", ""), ("10001", "*"), (10001, ""), ("10001", None)]:
            with pytest.raises(ValueError):
                await p.workspace_preview(account, group, state["revision"])
        raw["context"]["enabled"] = False
        await p.on_config_update("self", raw, "4")
        state = await p.workspace_state()
        result = await p.workspace_preview("10001", "", state["revision"])
        assert result["text"] == "" and not result["context_enabled"]
    finally:
        await p.on_unload()


def test_page_and_package_keep_workspace_reads_private():
    from tools.package import files, fingerprint
    root = Path(__file__).resolve().parents[1]
    page = json.loads((root / "webui.json").read_text(encoding="utf-8"))["pages"][0]
    assert page["actions"] == {}
    names = {p.relative_to(root).as_posix() for p in files()}
    assert {"webui.json", "webui/identity.html"} <= names
    assert {"webui.json", "webui/identity.html"} <= fingerprint().keys()


@pytest.mark.asyncio
async def test_workspace_full_roster_fits_host_response_budget(tmp_path):
    raw = config()
    raw['identity']['people'] = [{'qq': str(10000 + i), 'nickname': '😀' * 40,
        'prompt_template': '\u0001' * 1000} for i in range(200)]
    raw['identity']['styles'] = [{'name': str(i), 'prompt': '\u0001' * 1000} for i in range(40)]
    p = MaiIdentityPlugin(); p._set_context(context(tmp_path)[0]); p.set_plugin_config(raw)
    await p.on_load()
    try:
        result = await p.workspace_state()
        assert len(json.dumps(result, ensure_ascii=False).encode('utf-8')) < 524288
        assert result['identity']['people'][0]['prompt_truncated']
        assert result['identity']['styles'][0]['truncated']
    finally:
        await p.on_unload()
