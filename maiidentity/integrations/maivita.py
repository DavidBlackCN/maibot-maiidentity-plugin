"""Strict shape conversion. Real H03/policy transports remain unbound."""
from datetime import datetime, timedelta, timezone

from .. import PLUGIN_ID
from .contracts import IdentityRequest, IdentityDecision, PolicyRequest, PolicyDecision


class MaiVitaBridge:
    def identity(self, payload):
        request = IdentityRequest.model_validate(payload)
        now = datetime.now(timezone.utc)
        return IdentityDecision(request_id=request.request_id, verified=False, subject_ref=None,
            issuer=PLUGIN_ID, stream_id=request.stream_id, issued_at=now, expires_at=now+timedelta(seconds=1), proof_ref=None)

    def policy(self, payload):
        request = PolicyRequest.model_validate(payload)
        return PolicyDecision(request_id=request.request_id, allowed=False, reason_code="POLICY_UNAVAILABLE",
            state_version=request.state_version, config_revision=request.config_revision,
            expires_at=datetime.now(timezone.utc)+timedelta(seconds=1))
