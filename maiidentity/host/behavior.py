"""Host-only authorization. Fixed identities never grant command permissions."""
from .vita_management import administrator


def evaluate(plugin):
    reader = getattr(plugin._ctx, 'behavior_context', None)
    request = reader().get('request') if reader is not None else None
    result = {'version': 1, 'decision': 'deny', 'reason': 'untrusted_request'}
    if not isinstance(request, dict) or request.get('category') != 'management':
        return result
    origin = request.get('origin', {})
    if origin.get('kind') != 'command' or origin.get('stream_id') != request.get('stream_id'):
        return result
    route = request.get('route', {})
    try:
        allowed = administrator(plugin, account_id=origin.get('actor'),
            bot_account_id=route.get('account_id'), route_scope=route.get('scope'),
            stream_id=request.get('stream_id'))
    except Exception:
        allowed = False
    return {**result, 'decision': 'allow' if allowed else 'deny', 'reason': 'administrator_policy'}
