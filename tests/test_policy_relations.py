from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from maiidentity.policy.delegation import Delegations
from maiidentity.policy.service import ROLES, expand_roles
from maiidentity.shared.core import Denied, Scope
from .conftest import scope


def test_roles_deny_scope_self_escalation_and_revision(domain):
    db, identity, policy, _, accounts, subjects, _ = domain
    grant = policy.grant_operator(subjects[0], "maivita.wake", scope(kind="instance"), key="allow")
    role = policy.role_operator(subjects[1], "operator_admin", scope(kind="instance"), key="admin")
    actor = policy.actor(accounts[0])
    assert policy.authorize(actor, "maivita.wake", scope(), request_id="r")["reason_code"] == "POLICY_UNAVAILABLE"
    assert policy.authorize(actor, "maivita.wake", scope(), request_id="r", external_policy=False)["reason_code"] == "POLICY_DENIED"
    assert policy.authorize(actor, "maivita.wake", scope(), request_id="r", external_policy=True)["allowed"]
    assert not policy.authorize(actor, "maivita.wake", scope(resource="other"), request_id="r", external_policy=True)["allowed"]
    policy.grant_operator(subjects[0], "maivita.wake", scope(kind="instance"), key="deny", effect="deny")
    actor = policy.actor(accounts[0])
    assert policy.authorize(actor, "maivita.wake", scope(), request_id="r", external_policy=True)["reason_code"] == "EXPLICIT_DENY"
    admin = policy.actor(accounts[1])
    assert not policy.authorize(admin, "maivita.configure", scope(), request_id="r", external_policy=True)["allowed"]
    with pytest.raises(Denied, match="SELF_ESCALATION"):
        policy.assign_role(admin, subjects[1], "operator_admin", scope(), key="self", manageable_roles=["operator_admin"])
    policy.revoke("role", role["id"], expected=1, key="remove")
    assert policy.authorize(admin, "identity.role.manage", scope(), request_id="r")["reason_code"] == "STALE_REVISION"
    assert scope(kind="instance").intersection(scope()) == scope()
    assert scope().intersection(scope("other")) is None
    assert not scope().contains(scope("private"))
    with pytest.raises((TypeError, Denied)):
        Scope(kind="stream", instance_id="instance", character_id="default", platform="qq", adapter_namespace="adapter", resource_type="context", resource_id="default")
    with pytest.raises(Denied):
        expand_roles({"a": {"parents": ["b"]}, "b": {"parents": ["a"]}}, "a")
    with pytest.raises(Denied):
        policy.grant_operator(subjects[0], "unknown", scope(), key="unknown")


def seed_delegation(domain, *, uses=1, expires=1100):
    _, _, policy, _, accounts, subjects, _ = domain
    policy.grant_operator(subjects[0], "identity.self.read", scope(), key="allow", delegable=True, expires=1200)
    actor = policy.actor(accounts[0])
    delegation = Delegations(policy)
    grant = delegation.create(actor, delegatee=subjects[1], capability="identity.self.read", scope=scope(), purpose="read",
        expires=expires, max_uses=uses, budget=3, parameters={"view": "self"}, key="dg")
    return delegation, grant, actor


def reservation(delegation, grant, domain, **kw):
    return delegation.reserve(grant["id"], delegatee=domain[5][1], caller_plugin_id=None, capability="identity.self.read",
        scope=scope(), purpose="read", cost=1, parameters={"view": "self"}, **kw)


def test_delegation_concurrent_single_use_idempotency_unknown_receipt(domain):
    delegation, grant, actor = seed_delegation(domain)
    def attempt(i):
        try:
            return reservation(delegation, grant, domain, key=f"attempt:{i}")
        except Denied as error:
            return error.code
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(attempt, range(20)))
    successes = [r for r in results if type(r) is dict]
    assert len(successes) == 1
    attempt_ref = successes[0]["attempt_ref"]
    assert reservation(delegation, grant, domain, key=attempt_ref) == successes[0]
    delegation.receipt(attempt_ref, state="unknown", key="receipt")
    with pytest.raises(Denied, match="BUDGET_EXHAUSTED"):
        reservation(delegation, grant, domain, key="new-key")
    delegation.reconcile(attempt_ref, state="succeeded", evidence_ref="local-receipt", key="reconcile")
    assert domain[0].get("delegation", grant["id"])["used"] == 1


@pytest.mark.parametrize("change,expected", [("time", "EVIDENCE_EXPIRED"), ("binding", "STALE_REVISION"), ("role", "STALE_REVISION"), ("revoke", "STALE_REVISION")])
def test_queued_delegation_revalidation(domain, change, expected):
    delegation, grant, actor = seed_delegation(domain)
    db, identity, policy, _, accounts, subjects, clock = domain
    if change == "time":
        clock.value = 1101
    elif change == "binding":
        identity.revoke(accounts[0], expected_epoch=1, key="unbind")
    elif change == "role":
        policy.role_operator(subjects[0], "member", scope(), key="changed")
    else:
        delegation.revoke(grant["id"], actor, expected=1, key="revoked")
    with pytest.raises(Denied, match=expected):
        reservation(delegation, grant, domain, key="queued")


def test_delegation_cannot_expand_redelegate_or_change_parameters(domain):
    delegation, grant, actor = seed_delegation(domain)
    with pytest.raises(Denied, match="PARAMETERS_CHANGED"):
        delegation.reserve(grant["id"], delegatee=domain[5][1], caller_plugin_id=None, capability="identity.self.read", scope=scope(),
                           purpose="read", cost=1, parameters={"view": "private"}, key="changed")
    for values in ({"capability": "maivita.configure"}, {"parent_ref": "parent"}, {"expires": 1300}, {"scope": scope("other")}):
        args = dict(delegatee=domain[5][1], capability="identity.self.read", scope=scope(), purpose="read", expires=1100,
                    max_uses=1, budget=1, parameters={}, key="expand") | values
        with pytest.raises(Denied):
            delegation.create(actor, **args)
    with pytest.raises(Denied, match="BUDGET_EXHAUSTED"):
        delegation.reserve(grant["id"], delegatee=domain[5][1], caller_plugin_id=None, capability="identity.self.read", scope=scope(),
                           purpose="read", cost=4, parameters={"view": "self"}, key="overbudget")


def test_unknown_result_with_multiple_remaining_uses_requires_reconciliation(domain):
    delegation, grant, _ = seed_delegation(domain, uses=3)
    reservation(delegation, grant, domain, key="attempt")
    delegation.receipt("attempt", state="unknown", key="receipt")
    assert reservation(delegation, grant, domain, key="attempt")["state"] == "unknown"
    with pytest.raises(Denied, match="RECONCILIATION_REQUIRED"):
        reservation(delegation, grant, domain, key="new-key")


def test_nested_roles_expand_and_cycle_change_rolls_back(domain):
    _, _, policy, _, accounts, subjects, _ = domain
    policy.define_role_operator("reader", capabilities=["identity.self.read"], parents=[], key="def-reader")
    policy.define_role_operator("nested", capabilities=[], parents=["reader"], key="def-nested")
    policy.role_operator(subjects[0], "nested", scope(), key="assign-nested")
    actor = policy.actor(accounts[0])
    assert policy.authorize(actor, "identity.self.read", scope(), request_id="read")["allowed"]
    with pytest.raises(Denied, match="INVALID_ROLE_GRAPH"):
        policy.define_role_operator("reader", capabilities=[], parents=["nested"], expected=1, key="cycle")
    assert policy.authorize(actor, "identity.self.read", scope(), request_id="read")["allowed"]


def test_relations_bilateral_privacy_revision_no_permissions(domain):
    _, _, policy, relations, accounts, subjects, _ = domain
    a, b = policy.actor(accounts[0]), policy.actor(accounts[1])
    row = relations.propose(a, subjects[1], "partner", scope(), visibility="participants", domain="user_declared", key="proposal")
    with pytest.raises(Denied, match="PERMISSION_DENIED"):
        relations.confirm(row["id"], a, expected=1, evidence_ref="self-claim", key="bad")
    row = relations.confirm(row["id"], b, expected=1, evidence_ref="private-confirmation", key="confirmed")
    assert relations.visible(subjects[0], scope())["relation_state"] == "none_confirmed"
    assert relations.visible(subjects[0], scope(), viewer=subjects[1])["relation_state"] == "confirmed"
    assert relations.visible(subjects[0], scope("group-B"), viewer=subjects[1])["relation_state"] == "none_confirmed"
    assert not policy.authorize(a, "maivita.wake", scope(), request_id="r", external_policy=True)["allowed"]
    relations.revoke(row["id"], a, expected=2, key="revoked")
    assert relations.visible(subjects[0], scope(), viewer=subjects[0])["relation_state"] == "none_confirmed"
    assert relations.db.records("relation_event")[0]["relation_revision"] == 3


def test_relation_operator_character_and_conflict(domain):
    _, _, policy, relations, accounts, subjects, _ = domain
    a = policy.actor(accounts[0])
    row = relations.propose(a, "character:default", "partner", scope(), visibility="public", domain="character_roleplay", key="char")
    row = relations.confirm_operator(row["id"], expected=1, evidence_ref="local-config", key="char-confirm")
    assert row["confirmation_method"] == "operator_config"
    for i in (1, 2):
        r = relations.propose(a, subjects[i], "partner", scope(), visibility="public", domain="user_declared", key=f"p{i}")
        relations.confirm(r["id"], policy.actor(accounts[i]), expected=1, evidence_ref=f"confirmed-{i}", key=f"c{i}")
    assert relations.visible(subjects[0], scope())["relation_state"] == "disputed"
