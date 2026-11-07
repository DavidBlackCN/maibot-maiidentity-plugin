"""Real WebUI authentication, config save/watcher, private APIs and browser."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path

import httpx
import tomlkit

from .support import PLUGIN_ID, CONSUMER


async def run_cases(work, manager, supervisor, call):
    from .webui_host import serve
    from src.common.runtime_loop import set_main_loop
    from playwright.async_api import async_playwright

    cases = []
    original = tomlkit.parse((work / "plugins/candidate/config.toml").read_text(encoding="utf-8")).unwrap()
    manager._started = True
    set_main_loop(asyncio.get_running_loop())
    await manager._plugin_catalog.start([], [work / "plugins"])
    await manager._start_plugin_file_watcher()
    host = serve(work)
    url, proxy, password, cookie_name = await host.__aenter__()
    root = proxy + "/api/webui/plugins/runtime/webui/" + PLUGIN_ID + "/identity"

    async def until(predicate):
        async with asyncio.timeout(20):
            while not await predicate():
                await asyncio.sleep(.15)

    async with httpx.AsyncClient(base_url=url, timeout=15) as client:
        async def save(config):
            response = await client.put(proxy + "/api/webui/plugins/config/" + PLUGIN_ID, json={"config": config})
            assert response.status_code == 200, response.text
            return response

        async def preview(state, account="10001", group=""):
            return await client.post(root + "/queries/preview", json={"args": {
                "account_id": account, "group_id": group, "revision": state["revision"]}})

        try:
            response = await client.post(root + "/queries/load", json={"args": {}})
            assert response.status_code in (401, 403)
            login = await client.post("/api/webui/auth/verify", json={"token": password})
            assert login.status_code == 200 and login.json()["valid"]
            token = client.cookies.get(cookie_name)
            response = await client.post(root + "/queries/load", json={"args": {}})
            assert response.status_code == 200, response.text
            before = response.json()["result"]
            assert before["identity"]["people"][0]["nickname"] == "妈妈"
            for name in ("workspace_state", "workspace_preview"):
                entry = supervisor.api_registry.get_api(PLUGIN_ID, name, version="1")
                assert entry is not None and not entry.public
                denied = await supervisor.invoke_api(CONSUMER, "call_peer", args={"route": PLUGIN_ID + "." + name}, timeout_ms=5000)
                assert denied.error or not denied.payload.get("success") or denied.payload.get("result", {}).get("success") is False, denied
            assert (await client.post(root + "/actions/save", json={"args": {}})).status_code == 403
            cases.append("webui_authentication_private_api_peer_denial_no_write_endpoint")

            updated = deepcopy(original)
            updated["identity"]["styles"] = [{"name": "家人", "prompt": "与{nickname}轻松相处"}]
            updated["identity"]["people"][0].update(style="家人", prompt_template="")
            updated["identity"]["people"].extend([
                {"qq": "10001", "nickname": "朋友", "group_id": "20001", "prompt_template": "群专属说明"},
                {"qq": "10001", "nickname": "姐姐", "group_id": "20002", "enabled": False},
                {"qq": "10003", "nickname": "<img src=x onerror=alert(1)>", "enabled": False},
            ])
            await save(updated)
            async def applied():
                return len((await call("workspace_state"))["identity"]["people"]) == 4
            await until(applied)
            state = await call("workspace_state")
            assert state["revision"] != before["revision"]
            assert (await preview(before)).status_code == 502
            rendered = (await preview(state)).json()["result"]
            assert "与妈妈轻松相处" in rendered["text"] and rendered["source"] == "template"
            actual = await manager.invoke_hook("maisaka.replyer.before_request", session_id="test-stream", reply_message_id="native-A", extra_prompt="")
            assert rendered["text"] in actual.kwargs["extra_prompt"]
            group = (await preview(state, group="20001")).json()["result"]
            assert group["matched_scope"] == "20001" and "群专属说明" in group["text"]
            assert (await preview(state, group="20002")).json()["result"]["matched_scope"] == ""
            assert (await preview(state, account="10002")).json()["result"]["state"] == "unlisted"
            invalid = deepcopy(updated); invalid["identity"]["styles"] = []
            response = await client.put(proxy + "/api/webui/plugins/config/" + PLUGIN_ID, json={"config": invalid})
            assert response.status_code == 400, response.text
            assert (await call("workspace_state"))["revision"] == state["revision"]
            cases.append("official_config_save_watcher_template_scope_preview_parity_and_invalid_rejection")

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=os.environ["MAIIDENTITY_BROWSER"], headless=True)
                try:
                    context = await browser.new_context(viewport={"width": 1440, "height": 1000})
                    await context.route("**/*", lambda route: route.continue_() if route.request.url.startswith((url + "/", "data:", "blob:")) else route.abort())
                    await context.add_cookies([{"name": cookie_name, "value": token, "url": url}])
                    page = await context.new_page(); errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    await page.goto(url + "/extensions/" + PLUGIN_ID + "/identity")
                    frame = page.frame_locator("iframe")
                    try:
                        await frame.locator("#content").wait_for(state="visible", timeout=25000)
                    except Exception:
                        await page.screenshot(path=str(work / "workspace-failure.png"), full_page=True)
                        (work / "browser-failure.txt").write_text(
                            page.url + "\n" + await page.locator("body").inner_text() + "\n" + repr(errors), encoding="utf-8")
                        raise
                    await frame.get_by_label("搜索名单").fill("20001")
                    assert await frame.locator("tbody tr").count() == 1
                    await frame.get_by_role("button", name="预览", exact=True).click()
                    await frame.locator("#preview-text").wait_for(state="visible")
                    assert "群专属说明" in await frame.locator("#preview-text").inner_text()
                    await frame.get_by_label("搜索名单").fill("")
                    assert await frame.locator("#roster img").count() == 0
                    await page.screenshot(path=str(work / "workspace-desktop.png"), full_page=True)
                    await frame.get_by_role("tab", name="相处模板").click()
                    await frame.get_by_role("heading", name="家人", exact=True).wait_for()
                    await frame.get_by_role("tab", name="管理员", exact=True).click()
                    assert "10001" in await frame.locator("#admin-list").inner_text()
                    await frame.get_by_role("button", name="如何编辑").click()
                    await frame.locator("#help").wait_for(state="visible")
                    config_page = await context.new_page()
                    await config_page.goto(url + "/plugin-config?plugin=" + PLUGIN_ID)
                    try:
                        await config_page.get_by_text("共用相处模板", exact=True).wait_for(timeout=20000)
                    except Exception:
                        (work / "config-failure.txt").write_text(
                            config_page.url + "\n" + await config_page.locator("body").inner_text(), encoding="utf-8")
                        await config_page.screenshot(path=str(work / "config-failure.png"), full_page=True)
                        raise
                    editor = None
                    for field in await config_page.locator("textarea,input").all():
                        if await field.input_value() == "与{nickname}轻松相处":
                            editor = field
                            break
                    assert editor is not None, "Official config form must expose template text"
                    await editor.fill("与{nickname}自在相处")
                    await config_page.get_by_role("button", name="保存", exact=True).click()
                    async def browser_saved():
                        return (await call("workspace_state"))["identity"]["styles"][0]["prompt"] == "与{nickname}自在相处"
                    await until(browser_saved)
                    await config_page.close()
                    await frame.get_by_role("button", name="刷新状态").click()
                    await frame.get_by_role("tab", name="相处模板").click()
                    await frame.locator("#style-list").get_by_text("与{nickname}自在相处", exact=True).wait_for()
                    cases.append("official_config_form_template_edit_save_and_workspace_refresh")
                    await page.set_viewport_size({"width": 390, "height": 844})
                    await frame.get_by_role("tab", name="身份名单").click()
                    assert await frame.locator("body").evaluate("e=>e.scrollWidth<=innerWidth+1")
                    await page.screenshot(path=str(work / "workspace-mobile.png"), full_page=True)
                    assert not errors, errors
                    # Remove configuration through the same official save route.
                    empty = deepcopy(updated); empty["identity"]["people"] = []
                    empty["management"]["admin_accounts"] = []
                    await save(empty)
                    async def empty_applied():
                        return not (await call("workspace_state"))["identity"]["people"]
                    await until(empty_applied)
                    await frame.get_by_role("button", name="刷新状态").click()
                    await frame.get_by_text("还没有固定身份。在官方配置页添加 QQ 和固定称呼即可开始。").wait_for()
                    assert not await frame.locator("#preview-text").inner_text()
                    await frame.get_by_role("tab", name="管理员", exact=True).click()
                    assert "未设置管理员" in await frame.locator("#admin-list").inner_text()
                finally:
                    await browser.close()
            cases.append("official_dashboard_browser_search_tabs_preview_escaping_mobile_empty_refresh")
            assert await supervisor.reload_plugins([PLUGIN_ID], reason="workspace-restart")
            assert not (await call("workspace_state"))["identity"]["people"]
            cases.append("workspace_restart_uses_single_official_config")
        finally:
            await manager._stop_plugin_file_watcher()
            await manager._plugin_catalog.stop()
            # Only isolated fixture configuration is restored.
            (work / "plugins/candidate/config.toml").write_text(tomlkit.dumps(original), encoding="utf-8")
            await supervisor.reload_plugins([PLUGIN_ID], reason="workspace-fixture-restore")
            manager._started = False
            await host.__aexit__(None, None, None)
    return cases


if __name__ == "__main__":
    from .host_scenario import run
    from src.common.logger import shutdown_logging
    work = Path(os.environ["MAIBOT_INSTANCE_DIR"])
    try:
        result = asyncio.run(asyncio.wait_for(run(work, workspace=True), 150))
        result["scope"] = "native_host_sdk_runner_webui_browser"
        (work / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        shutdown_logging()
