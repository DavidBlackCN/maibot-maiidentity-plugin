"""Official Command envelope validation; never authenticates API input.

The stock Host constructs this envelope from the incoming SessionMessage.
Only the @Command handler calls this adapter. This trusts Host/Runner, not
arbitrary installed Python code as an isolated security principal.
"""
from copy import deepcopy
from ..shared.core import require


def validate(plugin, command):
    require(plugin.ready and plugin.active is not None, 'NOT_READY')
    evidence = plugin._parse(command.get('message'))
    text = command.get('text')
    require(type(text) is str and 0 < len(text) <= 256
        and command['message'].get('processed_plain_text') == text, 'UNTRUSTED_CONTEXT')
    require(command.get('user_id') == evidence.account.account_id
        and command.get('stream_id') == evidence.stream_id
        and command.get('platform') == 'qq'
        and command.get('group_id') == (evidence.group_id or ''), 'UNTRUSTED_CONTEXT')
    return deepcopy(command)
