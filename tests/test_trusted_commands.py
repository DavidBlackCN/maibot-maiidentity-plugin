"""Transport rejection tests precede any persistent self-registration path."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from maiidentity.host.trusted import resolve_command
from maiidentity.shared.core import Denied

ID='davidblackcn.maibot-maiidentity-plugin'

def plugin(result):
    active=object()
    return SimpleNamespace(ready=True,active=active,
        ctx=SimpleNamespace(call_host_method=AsyncMock(return_value=result)))

@pytest.mark.asyncio
@pytest.mark.parametrize('result',[
    None,{}, {'success':False}, {'success':True,'context':{}},
    {'success':True,'context':{'version':1,'caller_plugin_id':'forged','recipient_plugin_id':ID}},
])
async def test_unproven_context_cannot_reach_write(result):
    p=plugin(result)
    with pytest.raises(Denied): await resolve_command(p,'fake',caller=ID,name='maiidentity_manage')

@pytest.mark.asyncio
async def test_unsupported_host_and_unload_deny():
    p=plugin(None);p.ctx.call_host_method.side_effect=RuntimeError('unknown capability')
    with pytest.raises(Denied): await resolve_command(p,'fake',caller=ID,name='maiidentity_manage')
    async def unload(*a,**k):
        p.ready=False
        return {'success':True,'context':{'version':1,'caller_plugin_id':ID,'recipient_plugin_id':ID,
            'command_plugin_id':ID,'command_name':'maiidentity_manage','command':{},'request_id':'native-ref'}}
    p.ctx.call_host_method.side_effect=unload
    with pytest.raises(Denied): await resolve_command(p,'fake',caller=ID,name='maiidentity_manage')

@pytest.mark.asyncio
async def test_original_host_command_only():
    command={'text':'/maiidentity register','user_id':'10001'}
    p=plugin({'success':True,'context':{'version':1,'caller_plugin_id':ID,'recipient_plugin_id':ID,
        'command_plugin_id':ID,'command_name':'maiidentity_manage','command':command,'request_id':'native-ref'}})
    assert await resolve_command(p,'opaque',caller=ID,name='maiidentity_manage') == command
    p.ctx.call_host_method.assert_awaited_once_with('cap.call',payload={
        'capability':'security.resolve_command','args':{'context_ref':'opaque'}})
