"""Untrusted read-only policy query, never an execution token or actor proof.

Installed plugins can ask this boolean question. No identity/role list, command
proof or transferable key is returned. Vita obtains the actual actor locally.
"""
from ..shared.core import AccountKey, Scope, opaque, require, qq


def evaluate(plugin, *, account_id, bot_account_id, route_scope, stream_id, action):
    require(plugin.ready and plugin.active is not None, 'NOT_READY')
    capabilities={'wake':'maivita.wake','enqueue_replan':'maivita.replan',
        **{kind:'maivita.life.manage' for kind in ('start_sleep','start_activity','end_activity','apply_plan_patch','manage_goal')}}
    require(action in capabilities, 'UNSUPPORTED_COMMAND')
    # The API adapter has verified this bot/stream pair against Host routes.
    qq(bot_account_id)
    require(route_scope == (plugin.active.identity.route_scope or None), 'SCOPE_MISMATCH')
    account = AccountKey('qq', plugin.active.identity.adapter_namespace, account_id)
    require(account.account_id != bot_account_id, 'PERMISSION_DENIED')
    opaque(stream_id)
    capability = capabilities[action]
    with plugin.db.guard:
        actor = plugin.policy.actor(account)
        scope = Scope('stream', plugin.active.plugin.instance_id, 'default', 'qq',
            account.adapter_namespace, 'life', 'default', stream_id)
        decision = plugin.policy.authorize(actor, capability, scope,
            request_id='read-only-vita-policy', external_policy=True)
        return {'policy_version': 1, 'allowed': decision['allowed'] is True}
