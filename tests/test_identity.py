import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from maiidentity.identity.messages import AliasHistory, MessageEvidence, MessageResolver, host_message, short_alias
from maiidentity.identity.service import BindingChallenges
from maiidentity.shared.core import AccountKey, Denied, qq
from .conftest import FakeClock


@pytest.mark.parametrize("value", ["abc123", " 123", "123 ", "１２３", "0", "00123", "-123", "1.0", 123, True, None, "1\n"])
def test_strict_qq(value):
    with pytest.raises(Denied):
        qq(value)


def test_namespace_binding_unique_revoke_rebind(domain):
    db, identity, policy, _, accounts, subjects, _ = domain
    assert AccountKey("other", "adapter", "10001") != accounts[0]
    assert AccountKey("qq", "different", "10001") != accounts[0]
    with pytest.raises(Denied, match="BINDING_CONFLICT"):
        identity.bind_operator(accounts[0], subject=subjects[1], key="conflict")
    actor = policy.actor(accounts[0])
    identity.revoke(accounts[0], expected_epoch=1, key="revoke")
    assert identity.lookup(accounts[0]) is None
    with pytest.raises(Denied, match="STALE_REVISION"):
        policy.current(actor)
    assert identity.bind_operator(accounts[0], key="rebind")["epoch"] == 3
    with pytest.raises(Denied, match="STALE_REVISION"):
        policy.current(actor)
    with pytest.raises(Denied, match="IDEMPOTENCY_CONFLICT"):
        identity.bind_operator(accounts[1], key="rebind")


def test_concurrent_binding(domain):
    _, identity, _, _, _, _, _ = domain
    account = AccountKey("qq", "adapter", "77777")
    def attempt(i):
        return identity.bind_operator(account, key=f"parallel:{i}")["subject_id"]
    with ThreadPoolExecutor(8) as pool:
        assert len(set(pool.map(attempt, range(20)))) == 1


def test_bilateral_challenge_source_expiry_replay(domain):
    db, identity, _, _, accounts, _, clock = domain
    challenges = BindingChallenges(identity)
    candidate = AccountKey("qq", "adapter", "88888")
    ref, tokens = challenges.request(accounts[0], candidate, instance="i", request_id="r")
    assert tokens["original"] not in str(db.records("challenge"))
    with pytest.raises(Denied, match="RATE_LIMITED"):
        challenges.request(accounts[0], candidate, instance="i", request_id="r2")
    with pytest.raises(Denied, match="UNTRUSTED_CONTEXT"):
        challenges.confirm(ref, controlled_account=candidate, token=tokens["candidate"], instance="other", request_id="r")
    assert not challenges.confirm(ref, controlled_account=accounts[0], token=tokens["original"], instance="i", request_id="r")["confirmed"]
    with pytest.raises(Denied, match="CHALLENGE_REPLAY"):
        challenges.confirm(ref, controlled_account=accounts[0], token=tokens["original"], instance="i", request_id="r")
    assert challenges.confirm(ref, controlled_account=candidate, token=tokens["candidate"], instance="i", request_id="r")["confirmed"]
    assert identity.lookup(candidate)["subject"] == identity.lookup(accounts[0])["subject"]
    ref2, tokens2 = challenges.request(accounts[0], AccountKey("qq", "adapter", "99999"), instance="i", request_id="r2")
    clock.value += 301
    with pytest.raises(Denied, match="EVIDENCE_EXPIRED"):
        challenges.confirm(ref2, controlled_account=accounts[0], token=tokens2["original"], instance="i", request_id="r2")


def test_challenge_failure_limit_and_unload(domain):
    db, identity, _, _, accounts, _, _ = domain
    challenges = BindingChallenges(identity)
    ref, _ = challenges.request(accounts[0], AccountKey("qq", "adapter", "88888"), instance="i", request_id="r")
    for _ in range(5):
        assert not challenges.confirm(ref, controlled_account=accounts[0], token="bad", instance="i", request_id="r")["confirmed"]
    assert db.get("challenge", ref)["status"] == "expired"
    challenges.close()


def evidence(mid="long-original-message-id", account="10001", stream="s"):
    return MessageEvidence("i", AccountKey("qq", "ns", account), stream, mid, None, "ordinary")


async def resolve(resolver, value=None, original=None, **kw):
    async def query(mid, stream):
        if isinstance(value, Exception):
            raise value
        return value
    return await resolver.resolve(instance="i", platform="qq", namespace="ns", stream="s", message_id=original or "long-original-message-id",
                                  query=query, parse=lambda raw: raw, **kw)


@pytest.mark.asyncio
async def test_exact_api_cache_conflicts_missing_ids_and_ttl():
    clock = FakeClock()
    resolver = MessageResolver(clock, ttl=300, capacity=2)
    a = evidence()
    resolver.observe(a)
    assert (await resolve(resolver, RuntimeError()))[0] == a
    assert (await resolve(resolver, evidence(account="10002")))[0] is None
    assert (await resolve(resolver, a))[0] is None
    clock.value += 301
    assert (await resolve(resolver))[0] is None
    assert (await resolve(resolver, a))[0] == a
    assert (await resolve(resolver, replace(a, message_id="")))[0] is None
    assert (await resolve(resolver, replace(a, stream_id="other")))[0] is None
    resolver.observe(evidence("1")); resolver.observe(evidence("2")); resolver.observe(evidence("3"))
    assert len(resolver.cache) == 2
    resolver.close()
    assert not resolver.cache


@pytest.mark.asyncio
async def test_alias_unique_collision_short_original_same_shape_and_history():
    original = "long-original-message-id"
    alias = short_alias(original)
    history = AliasHistory(instance="i", platform="qq", namespace="ns", stream="s", revision="r", originals=[original], complete=True)
    found, _ = await resolve(MessageResolver(), evidence(), original=alias, id_kind="alias", history=history, history_revision="r")
    assert found.message_id == original  # alias != original is correct.
    assert (await resolve(MessageResolver(), evidence(), original=alias, id_kind="alias", history=history, history_revision="old"))[0] is None
    conflict = AliasHistory(instance="i", platform="qq", namespace="ns", stream="s", revision="r", originals=[original, alias], complete=True)
    assert (await resolve(MessageResolver(), evidence(), original=alias, id_kind="alias", history=conflict, history_revision="r"))[0] is None
    assert (await resolve(MessageResolver(), evidence(alias), original=alias))[0].message_id == alias
    with pytest.raises(Denied):
        AliasHistory(instance="i", platform="qq", namespace="ns", stream="s", revision="r", originals=[original], complete=False)


def test_host_message_missing_fields_bot_system():
    raw = {"platform": "qq", "account_id": "99999", "scope": "route", "session_id": "s", "message_id": "m", "message_info": {"user_info": {"user_id": "10001"}, "group_info": None}}
    parse = lambda value, bot="99999": host_message(value, instance="i", namespace="ns", bot_account=bot, route_scope="route")
    assert parse(raw).account.account_id == "10001"
    for name in ("platform", "session_id", "message_id", "message_info", "account_id", "scope"):
        with pytest.raises(Denied):
            parse({k: v for k, v in raw.items() if k != name})
    for name in ("is_bot", "is_system", "is_mai_message"):
        with pytest.raises(Denied):
            parse(raw | {name: True})
    for bot in ("", "10001"):
        with pytest.raises(Denied):
            parse(raw, bot)
