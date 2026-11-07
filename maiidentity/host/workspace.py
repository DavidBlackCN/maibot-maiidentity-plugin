"""Private, read-only workspace views. No message, model or config writes."""
from datetime import datetime, timezone
import json

from .. import PLUGIN_VERSION
from ..context.projection import configured, match_profile
from ..shared.core import digest, qq, require


def current(plugin):
    require(plugin.ready and plugin.active is not None, "NOT_READY")
    return plugin.active


def revision(config):
    return digest(config.model_dump())


def state(plugin):
    config = current(plugin)
    identity = config.identity.model_dump()
    # Keep a full 200-person / 40-template view below the Host's 512 KiB
    # response limit even for escaped control characters. Preview uses originals.
    for person in identity["people"]:
        prompt = person.pop("prompt_template")
        person.update(prompt_summary=prompt[:160], has_personal_prompt=bool(prompt.strip()),
                      prompt_truncated=len(prompt) > 160)
    for style in identity["styles"]:
        prompt = style["prompt"]
        style.update(prompt=prompt[:500], truncated=len(prompt) > 500)
    return {
        "version": 1,
        "plugin_version": PLUGIN_VERSION,
        "revision": revision(config),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "context_enabled": config.context.enabled,
        "identity": identity,
        "admin_accounts": list(config.management.admin_accounts),
        "editing": "host_config",
    }


def preview(plugin, account_id, group_id, expected_revision):
    config = current(plugin)
    require(expected_revision == revision(config), "CONFIG_CHANGED_REFRESH")
    qq(account_id)
    if group_id != "":
        qq(group_id)
    person = match_profile(config.identity.people, account_id, group_id)
    facts = configured(person, config.identity.styles) if person else {"state": "unlisted", "stage": "replyer"}
    # Render through the same byte budget and text path as actual Replyer hooks.
    block = plugin.projector.block(facts) if config.context.enabled else None
    text = block.split("\n", 2)[2].rsplit("\n", 1)[0] if block else ""
    source = "none"
    if person:
        source = "personal" if person.prompt_template.strip() else "template" if person.style else "default"
    return {
        "version": 1, "revision": expected_revision, "state": facts["state"],
        "context_enabled": config.context.enabled,
        "matched_scope": person.group_id if person else None,
        "nickname": person.nickname if person else None,
        "source": source, "style": person.style if person else "",
        "text": text, "truncated": bool(block and facts.get("prompt") and
            json.dumps(facts["prompt"], ensure_ascii=False) not in text),
    }
