"""Synthetic peer tests the real SDK public API call, never installed."""
from maibot_sdk import API, HookHandler, MaiBotPlugin


class Consumer(MaiBotPlugin):
    async def on_load(self):
        pass

    async def on_unload(self):
        pass

    async def on_config_update(self, scope, config_data, version):
        pass

    @API("call_peer", public=True, version="1")
    async def call_peer(self, route, payload=None, **kwargs):
        return await self.ctx.api.call(route, version="1", **(payload or {}))

    @HookHandler("maisaka.replyer.before_request", name="synthetic_other_context", order="early")
    async def other_context(self, **kwargs):
        existing = kwargs.get("extra_prompt")
        if isinstance(existing, str) and "[Synthetic other context]" not in existing:
            return {"action": "continue", "modified_kwargs": {**kwargs, "extra_prompt": existing+"\n[Synthetic other context]"}}
        return None


def create_plugin():
    return Consumer()
