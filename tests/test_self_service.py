import uuid
import pytest
from maiidentity.host.plugin import MaiIdentityPlugin
from maiidentity.host.self_service import apply
from maiidentity.shared.core import Denied,AccountKey
from .test_migration_lifecycle import context

def command(user,text,stream='s1',scope=None):
    return {'text':text,'user_id':user,'stream_id':stream,'platform':'qq','group_id':'20001','message':{
        'processed_plain_text':text,
        'platform':'qq','account_id':'99999','scope':scope,'message_id':uuid.uuid4().hex,
        'session_id':stream,'message_info':{'user_info':{'user_id':user},'group_info':{'group_id':'20001'}}}}

@pytest.mark.asyncio
async def test_self_only_no_roles_revocation_and_bilateral_scope(tmp_path):
    p=MaiIdentityPlugin();p._set_context(context(tmp_path)[0]);p.set_plugin_config({});await p.on_load()
    try:
        first=command('10001','/maiidentity register')
        assert apply(p,first)==apply(p,first)
        apply(p,command('10002','/maiidentity register'))
        apply(p,command('10003','/maiidentity register'))
        assert not p.db.records('role') and not p.db.records('grant')
        text=apply(p,command('10001','/maiidentity relation propose 10002 friend'))
        ref=text.split()[-1]
        with pytest.raises(Denied): apply(p,command('10003','/maiidentity relation confirm '+ref))
        with pytest.raises(Denied): apply(p,command('10001','/maiidentity relation confirm '+ref))
        with pytest.raises(Denied): apply(p,command('10002','/maiidentity relation confirm '+ref,stream='other'))
        assert '双方' in apply(p,command('10002','/maiidentity relation confirm '+ref))
        assert 'friend' in apply(p,command('10001','/maiidentity relations'))
        with p.db.transaction():
            item=p.db.get('relation',ref)
            item['visibility']='participants'
            p.db.put('relation',ref,item,item['revision'])
        assert '暂无' in apply(p,command('10001','/maiidentity relations'))
        with pytest.raises(Denied): apply(p,command('10002','/maiidentity relation revoke '+ref))
        with p.db.transaction():
            item=p.db.get('relation',ref);item['visibility']='public'
            p.db.put('relation',ref,item,item['revision'])
        assert '撤销' in apply(p,command('10002','/maiidentity relation revoke '+ref))
        assert not p.db.records('grant') and not p.db.records('role')
        account=AccountKey('qq','host-qq','10001')
        p.identity.revoke(account,expected_epoch=1,key='local-revoke')
        with pytest.raises(Denied,match='LOCAL_REVIEW_REQUIRED'): apply(p,command('10001','/maiidentity register'))
        assert p.identity.lookup(account) is None
    finally: await p.on_unload()

@pytest.mark.asyncio
async def test_incomplete_command_and_forged_actor_rejected(tmp_path):
    p=MaiIdentityPlugin();p._set_context(context(tmp_path)[0]);p.set_plugin_config({});await p.on_load()
    try:
        result=await p.self_command(text='/maiidentity register',stream_id='s1',
            message=command('10001','/maiidentity register')['message'],__maibot_command_ref__='forged')
        assert 'UNTRUSTED_CONTEXT' in result[1]
        assert p.db.conn.execute('SELECT count(*) FROM bindings').fetchone()[0]==0
        raw=command('10001','/maiidentity register');raw['user_id']='10002'
        with pytest.raises(Denied,match='UNTRUSTED_CONTEXT'): apply(p,raw)
        for user,scope in [('99999',None),('10001','named')]:
            with pytest.raises(Denied): apply(p,command(user,'/maiidentity register',scope=scope))
        assert p.db.conn.execute('SELECT count(*) FROM bindings').fetchone()[0]==0
    finally: await p.on_unload()
