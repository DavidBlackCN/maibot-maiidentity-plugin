"""Official 1.4 WebUI, authentication and IPC proxy around the test Bot.

The Bot's Supervisor/Runner is started by host_scenario. Only the outer Bot
process registration is seeded: this fixture does not start the full bot CLI.
"""
import asyncio
from contextlib import asynccontextmanager
import socket

import uvicorn


@asynccontextmanager
async def serve(work):
    from src.common.ipc import IpcHTTPServer, allocate_endpoint, release_endpoint
    from src.webui.app import create_app
    from src.host.authentication import HostCredentials
    from src.host.config import HostConfig
    from src.host.layout import Workspace
    from src.host.registry import Registry
    from src.host.sessions import HostSessions
    from src.host.supervisor import BotSupervisor
    from src.host.maintenance import HostMaintenance
    from src.host.webui import create_host_app
    from src.host.static import resolve_static_path

    registry = Registry(work / "webui-host")
    registry.create()
    config = HostConfig(anti_crawler_mode="false")
    workspace = Workspace(registry.root, registry, config)
    bot = registry.add_bot("Identity test", work, owned=False, initialization="initialized")
    credentials = HostCredentials(workspace.host_directory / "webui.json")
    password = "Isolated-Identity-141-password"
    credentials.update(password)
    credentials.complete_setup()
    sessions = HostSessions(workspace.root, credentials=credentials)
    endpoint = allocate_endpoint("identity-test")
    bot_server = IpcHTTPServer(uvicorn.Config(create_app(), log_level="error", lifespan="off"), endpoint)
    outer = BotSupervisor(workspace, public_base_url="")
    runtime = await outer._runtime(bot.bot_id)
    runtime.status = "running"
    runtime.endpoint = endpoint
    app = create_host_app(outer, HostMaintenance(outer), sessions, credentials, asyncio.Event(),
                          config=config, static_path=resolve_static_path())
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); sock.listen(128)
    url = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off", timeout_graceful_shutdown=3))
    tasks = [asyncio.create_task(bot_server.serve()), asyncio.create_task(server.serve(sockets=[sock]))]
    try:
        async with asyncio.timeout(15):
            while not (bot_server.started and server.started):
                for task in tasks:
                    if task.done():
                        task.result()
                await asyncio.sleep(.05)
        yield url, f"/api/host/bots/{bot.bot_id}/proxy", password, sessions.cookie_name
    finally:
        server.should_exit = bot_server.should_exit = True
        await asyncio.wait_for(asyncio.gather(*tasks), 10)
        release_endpoint(endpoint)
        sock.close()
