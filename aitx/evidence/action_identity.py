"""Approved, reversible export aliases. Clinical calculations retain their original identities."""
from __future__ import annotations
import copy
from functools import lru_cache
import json
from pathlib import Path

REGISTRY=Path(__file__).resolve().parents[2]/'data/action_key_registry.json'
KEY_FIELDS={'action_key','key','implements'}


@lru_cache(maxsize=1)
def registry():
    return json.loads(REGISTRY.read_text())


def case_map(cid,reverse=False):
    data=registry()
    if cid not in data['cases'] or (not data['active'] and not reverse):return {}
    mapping=data['cases'][cid]
    return {new:old for old,new in mapping.items()} if reverse else mapping


def rewrite(value,mapping):
    """Change only exact identity references; evidence remains immutable provenance."""
    if isinstance(value,list):return [rewrite(v,mapping) for v in value]
    if not isinstance(value,dict):return value
    out={}
    for field,item in value.items():
        if field=='evidence':out[field]=copy.deepcopy(item)
        elif field in KEY_FIELDS and isinstance(item,str) and item in mapping:out[field]=mapping[item]
        else:out[field]=rewrite(item,mapping)
    return out


def export(ledger):
    mapping=case_map(ledger['patient_id'])
    return rewrite(ledger,mapping) if mapping else ledger


def is_drug(action,ledger):
    key=action.get('action_key')
    if not key:return False
    if key.startswith(('source_sentence:','source:')):
        cid=ledger['patient_id']
        inverse=case_map(cid,reverse=True)
        if key not in inverse:raise KeyError('unregistered action identity: '+key)
        key=inverse[key]
    return key.startswith('drug:')
