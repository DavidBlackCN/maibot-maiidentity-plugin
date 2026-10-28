import pytest
from maiidentity.host.plugin import MaiIdentityPlugin
from maiidentity.host.vita_management import authorize
from maiidentity.shared.core import Denied,Scope,AccountKey
from .test_migration_lifecycle import context
from .test_self_service import command

@pytest.mark.asyncio
async def test_explicit_admin_finite_actions_policy_deny_and_removal(tmp_path):
    p=MaiIdentityPlugin();p._set_context(context(tmp_path)[0])
    p.set_plugin_config({'plugin':{'config_version':'3'},'management':{'vita_admin_accounts':['10001']}});await p.on_load()
    try:
        request=command('10001','/maivita wake')
        result=authorize(p,request)
        assert result['allowed'] and result['action']=='wake' and result['stream_id']=='s1'
        assert result==authorize(p,request)
        assert authorize(p,command('10001','/maivita 重新规划'))['action']=='enqueue_replan'
        for c in [command('10002','/maivita wake'),command('10001','/maivita configure'),
                  command('10001','/maivita wake',scope='another')]:
            with pytest.raises(Denied): authorize(p,c)
        binding=p.identity.lookup(AccountKey('qq','host-qq','10001'))
        scope=Scope('stream',p.active.plugin.instance_id,'default','qq','host-qq','life','default','s1')
        p.policy.grant_operator(binding['subject'],'maivita.wake',scope,key='deny',effect='deny')
        with pytest.raises(Denied,match='EXPLICIT_DENY'): authorize(p,request)
        assert authorize(p,command('10001','/maivita replan'))['allowed']
        await p.on_unload();p.set_plugin_config({});await p.on_load()
        with pytest.raises(Denied): authorize(p,command('10001','/maivita replan'))
        assert all(g['status']=='revoked' for g in p.db.records('grant') if g.get('management_config_origin'))
    finally: await p.on_unload()
