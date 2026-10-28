"""Public group-level relationship facts; no actor proof or private data."""
from ..shared.core import opaque,require,digest,Scope

def public_context(plugin,stream_id,bot_account_id,route_scope):
    require(plugin.ready and bool(plugin.bot_account),'NOT_READY')
    opaque(stream_id)
    require(bot_account_id==plugin.bot_account and route_scope==(plugin.active.identity.route_scope or None),'SCOPE_MISMATCH')
    counts={kind:0 for kind in ('friend','family','partner')}
    disputed=False
    with plugin.db.guard:
        rows=[r for r in plugin.db.records('relation') if r['visibility']=='public'
            and r['scope']==Scope('stream',plugin.active.plugin.instance_id,'default','qq',plugin.active.identity.adapter_namespace,'context','default',stream_id).data()
            and r['status'] in ('confirmed','disputed') and (r['expires'] is None or r['expires']>plugin.db.clock.now())]
        partners={}
        for r in rows:
            if r['relation_type']=='partner':
                for a,b in ((r['left'],r['right']),(r['right'],r['left'])):partners.setdefault(a,set()).add(b)
        disputed=any(r['status']=='disputed' for r in rows) or any(len(v)>1 for v in partners.values())
        if not disputed:
            for r in rows:
                if r['relation_type'] in counts:counts[r['relation_type']]=min(20,counts[r['relation_type']]+1)
    facts={'stream_id':stream_id,'counts':counts,'relation_state':'disputed' if disputed else 'confirmed' if any(counts.values()) else 'none_confirmed',
        'completeness':'public_group_scope_only','style':'neutral' if disputed or not any(counts.values()) else 'friendly',
        'rule':'These are confirmed relationships between group participants, not relationships with the bot. Never infer identity, authority, intimacy with the bot or private facts.'}
    return {**facts,'revision':digest(facts)}
