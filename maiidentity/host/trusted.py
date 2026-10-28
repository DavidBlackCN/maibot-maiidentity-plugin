"""Optional Host command-context v1 extension; unsupported Host always denies.

The Host capability authenticates its RPC caller and resolves an opaque, live
recipient-bound reference. Neither ordinary API arguments nor a chat actor
dictionary can substitute for that capability response.
"""
import asyncio
from ..shared.core import Denied, require

IDENTITY='davidblackcn.maibot-maiidentity-plugin'
FIELD='__maibot_command_ref__'

async def resolve_command(plugin, ref, *, caller, name):
    active=plugin.active
    require(plugin.ready and active is not None and type(ref) is str and 1<=len(ref)<=128,'HOST_CONTEXT_REQUIRED')
    try:
        result=await asyncio.wait_for(plugin.ctx.call_host_method('cap.call',payload={
            'capability':'security.resolve_command','args':{'context_ref':ref}}),2)
    except Exception:
        raise Denied('HOST_CONTEXT_REQUIRED') from None
    require(plugin.ready and plugin.active is active,'NOT_READY')
    require(type(result) is dict and result.get('success') is True,'UNTRUSTED_CONTEXT')
    context=result.get('context')
    require(type(context) is dict and context.get('version')==1
        and context.get('caller_plugin_id')==caller and context.get('recipient_plugin_id')==IDENTITY
        and context.get('command_plugin_id')==caller and context.get('command_name')==name
        and type(context.get('request_id')) is str and bool(context['request_id'])
        and type(context.get('command')) is dict,'UNTRUSTED_CONTEXT')
    return context['command']
