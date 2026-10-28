"""Finite management policy applied only to a Host-resolved Vita command."""
from ..shared.core import Scope,digest,require

COMMANDS={'/maivita wake':'wake','/maivita 醒来':'wake',
          '/maivita replan':'enqueue_replan','/maivita 重新规划':'enqueue_replan'}

def authorize(plugin,command):
    require(plugin.ready,'NOT_READY')
    text=command.get('text')
    require(type(text) is str and text.strip() in COMMANDS,'UNSUPPORTED_COMMAND')
    evidence=plugin._parse(command.get('message'))
    require(evidence.account.account_id==command.get('user_id') and evidence.stream_id==command.get('stream_id'),'UNTRUSTED_CONTEXT')
    action=COMMANDS[text.strip()]
    capability='maivita.wake' if action=='wake' else 'maivita.replan'
    key=digest([evidence.instance_id,evidence.account.key,evidence.stream_id,evidence.message_id])
    with plugin.db.guard:
        actor=plugin.policy.actor(evidence.account)
        scope=Scope('stream',evidence.instance_id,'default','qq',evidence.account.adapter_namespace,'life','default',evidence.stream_id)
        decision=plugin.policy.authorize(actor,capability,scope,request_id=key,external_policy=True)
        require(decision['allowed'],decision['reason_code'])
        return {'allowed':True,'action':action,'stream_id':evidence.stream_id,'request_key':'host-command:'+key,
                'authorization_revision':decision['authorization_revision'],'policy_revision':decision['policy_revision']}
