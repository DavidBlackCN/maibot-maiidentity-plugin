"""Participant-only commands behind Host command-context verification.

No roles, grants, account merges, owner labels or Hush/Vita privileges can be
created here. A revoked identity requires local operator review to restore.
"""
import uuid
from ..shared.core import AccountKey, Scope, digest, require

def apply(plugin, command):
    require(plugin.ready,'NOT_READY')
    evidence=plugin._parse(command.get('message'))
    require(command.get('user_id')==evidence.account.account_id
        and command.get('stream_id')==evidence.stream_id,'UNTRUSTED_CONTEXT')
    text=command.get('text')
    require(type(text) is str and len(text)<=256,'INVALID_ARGUMENT')
    words=text.strip().split()
    require(len(words)>=2 and words[0]=='/maiidentity','INVALID_ARGUMENT')
    key='host-self:'+digest([evidence.account.key,evidence.stream_id,evidence.message_id])
    db=plugin.db
    # Keep revisions stable across reads; domain methods own transactions.
    with db.guard:
        if words==['/maiidentity','register']:
            def register():
                existing=db.conn.execute('SELECT * FROM bindings WHERE account=?',(evidence.account.key,)).fetchone()
                if existing:
                    require(plugin.identity.lookup(evidence.account) is not None,'LOCAL_REVIEW_REQUIRED')
                else:
                    subject=uuid.uuid4().hex
                    db.conn.execute("INSERT INTO subjects VALUES(?,'active',1)",(subject,))
                    db.conn.execute("INSERT INTO bindings VALUES(?,?,'active',1,'host_self')",(evidence.account.key,subject))
                    db.audit('binding.self_registered',subject,{'method':'host_command_context_v1'})
                return '当前账号已登记；没有授予管理员或跨插件权限。'
            return db.once(key,['self_register',evidence.account.key],register)
        actor=plugin.policy.actor(evidence.account)
        scope=Scope('stream',plugin.active.plugin.instance_id,'default','qq',
                    plugin.active.identity.adapter_namespace,'context','default',evidence.stream_id)
        if words==['/maiidentity','relations']:
            rows=[r for r in db.records('relation') if actor.subject_id in (r['left'],r['right'])
                and r['visibility']=='public'
                and r['scope']==scope.data() and r['status'] in ('confirmed','pending_confirmation')
                and (r['expires'] is None or r['expires']>db.clock.now())
                and (r['status']=='confirmed' or r.get('confirm_before',float('inf'))>db.clock.now())]
            return '本群公开关系：\n'+'\n'.join(f"{r['id']} {r['relation_type']} {r['status']}" for r in rows[:20]) if rows else '本群暂无公开关系。'
        require(len(words)>=3 and words[1]=='relation','INVALID_ARGUMENT')
        action=words[2]
        if action=='propose':
            require(len(words)==5 and words[4] in ('friend','family','partner'),'INVALID_ARGUMENT')
            target=AccountKey('qq',evidence.account.adapter_namespace,words[3])
            right=plugin.identity.lookup(target)
            require(right is not None,'TARGET_NOT_REGISTERED')
            pending=[r for r in db.records('relation') if r['status']=='pending_confirmation'
                and (r['expires'] is None or r['expires']>db.clock.now())
                and r.get('confirm_before',float('inf'))>db.clock.now()
                and (actor.subject_id in (r['left'],r['right']) or right['subject'] in (r['left'],r['right']))]
            require(len(pending)<20,'RATE_LIMITED')
            result=plugin.relations.propose(actor,right['subject'],words[4],scope,
                visibility='public',domain='user_declared',key=key,confirm_before=db.clock.now()+86400)
            return '公开关系待对方在 24 小时内确认（确认后持续有效，任一方可撤销）：/maiidentity relation confirm '+result['id']
        require(len(words)==4 and action in ('confirm','revoke'),'INVALID_ARGUMENT')
        item=db.get('relation',words[3])
        require(item is not None and item['scope']==scope.data(),'SCOPE_MISMATCH')
        require(item['visibility']=='public' and actor.subject_id in (item['left'],item['right']),'PERMISSION_DENIED')
        if action=='confirm':
            plugin.relations.confirm(item['id'],actor,expected=item['revision'],evidence_ref=evidence.message_id,key=key)
            return '双方已确认公开关系；此关系不授予任何执行权限。'
        plugin.relations.revoke(item['id'],actor,expected=item['revision'],key=key)
        return '已撤销这项关系。'
