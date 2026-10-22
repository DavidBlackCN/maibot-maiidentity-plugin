import re


def single_pass(template: str, values: dict) -> str:
    """Archive utility only; legacy templates are not activated at runtime."""
    return re.sub(r"\{(\w+)\}", lambda match: str(values.get(match[1], match[0])), template)
