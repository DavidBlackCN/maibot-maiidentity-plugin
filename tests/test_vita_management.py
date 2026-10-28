import pytest
from maiidentity.host.plugin import MaiIdentityPlugin
from maiidentity.shared.core import Scope,AccountKey
from .test_migration_lifecycle import context

@pytest.mark.asyncio
async def test_policy_is_read_only_minimal_and_deny_precedence(tmp_path):
    p=MaiIdentityPlugin();p._set_context(context(tmp_path)[0])
    p.set_plugin_config({'plugin':{'config_version':'3'},'management':{'vita_admin_accounts':['10001']}});await p.on_load()
    query={'account_id':'10001','bot_account_id':'99999','route_scope':None,'stream_id':'s1','action':'wake'}
    try:
        before=p.db.conn.total_changes
        assert await p.get_vita_policy(**query)=={'policy_version':1,'allowed':True}
        assert await p.get_vita_policy(**query)=={'policy_version':1,'allowed':True}
        assert p.db.conn.total_changes==before  # no binding, audit, token or command write
        for key,value in [('account_id','10002'),('account_id','99999'),('bot_account_id','88888'),
                          ('route_scope','another'),('action','configure'),('stream_id','')]:
            assert not (await p.get_vita_policy(**{**query,key:value}))['allowed']
        assert not (await p.get_vita_policy(**query,owner=True))['allowed']
        binding=p.identity.lookup(AccountKey('qq','host-qq','10001'))
        scope=Scope('stream',p.active.plugin.instance_id,'default','qq','host-qq','life','default','s1')
        p.policy.grant_operator(binding['subject'],'maivita.wake',scope,key='deny',effect='deny')
        assert not (await p.get_vita_policy(**query))['allowed']
        assert (await p.get_vita_policy(**{**query,'action':'enqueue_replan'}))['allowed']
        with pytest.raises(RuntimeError,match='RELOAD_REQUIRED'):
            await p.on_config_update('self',{},'2')
        assert not (await p.get_vita_policy(**query))['allowed']
        p.set_plugin_config({});await p.on_load()
        assert not (await p.get_vita_policy(**{**query,'action':'enqueue_replan'}))['allowed']
        assert all(g['status']=='revoked' for g in p.db.records('grant') if g.get('management_config_origin'))
    finally: await p.on_unload()
