"""MaiIdentity SDK entry. Original authors: khiqwq, 风花叶; GPL-3.0-or-later."""
if __package__:
    from .maiidentity.host.plugin import MaiIdentityPlugin
else:
    from maiidentity.host.plugin import MaiIdentityPlugin


def create_plugin():
    return MaiIdentityPlugin()
