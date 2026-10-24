import pytest
from dataclasses import replace
from maiidentity.policy.service import MAIHUSH,ROLES
from maiidentity.integrations.api import PublicAPI
from maiidentity.shared.core import Denied
from .conftest import scope


@pytest.mark.parametrize('capability',sorted(MAIHUSH))
def test_hush_catalogue_is_not_a_grant_and_requires_business_policy(domain,capability):
    _,_,policy,_,accounts,subjects,_=domain
    group=replace(scope(),resource_type='group',resource_id='20001')
    assert all(capability not in caps for caps in ROLES.values())
    assert not policy.authorize(policy.actor(accounts[0]),capability,group,request_id='r',external_policy=True)['allowed']
    with pytest.raises(Denied,match='NONDELEGABLE'):
        policy.grant_operator(subjects[0],capability,group,key='bad',delegable=True)
    policy.grant_operator(subjects[0],capability,group,key='allow')
    actor=policy.actor(accounts[0])
    assert policy.authorize(actor,capability,group,request_id='r')['reason_code']=='POLICY_UNAVAILABLE'
    assert policy.authorize(actor,capability,group,request_id='r',external_policy=True)['allowed']
    assert not policy.authorize(actor,capability,replace(group,stream_id='other'),request_id='r',external_policy=True)['allowed']
    assert policy.authorize(actor,capability,scope(),request_id='r',external_policy=True)['reason_code']=='SCOPE_MISMATCH'
    assert PublicAPI().call('authorize',owner=True,capability=capability,proof='fake')['error']['code']=='UNTRUSTED_CONTEXT'


def test_wire_dates_use_json_mode_without_relaxing_strict_python_models():
    from maiidentity.integrations.contracts import PolicyDecision
    payload={'request_id':'r','allowed':False,'reason_code':'DENIED','state_version':0,'config_revision':0,
             'expires_at':'2026-10-24T12:00:00+00:00'}
    assert PolicyDecision.from_wire(payload).expires_at.utcoffset() is not None
    with pytest.raises(ValueError): PolicyDecision.model_validate(payload)
    with pytest.raises(ValueError): PolicyDecision.from_wire(payload|{'owner':True})
    with pytest.raises(ValueError): PolicyDecision.from_wire(payload|{'allowed':'true'})
    with pytest.raises(ValueError): PolicyDecision.from_wire(payload|{'expires_at':'2026-10-24T12:00:00'})
