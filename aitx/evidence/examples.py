"""Literal source examples are members of a named action, never drug-identity synonyms."""
import copy
import re


def norm(text):return ' '.join(text.lower().split())


def source_groups(quote, names=()):
    out=[]
    for m in re.finditer(r'\(\s*e\.g\.\s*,?\s*([^()]*)\)|\bsuch as\s+([^.;:]+)',quote,re.I):
        prefix=quote[:m.start()].rstrip()
        members=m[1] if m[1] is not None else re.split(r'\s+(?:can|may|should|will|are|is|help|helps|support|supports)\b',m[2],maxsplit=1,flags=re.I)[0]
        candidates=[n for n in names if norm(prefix)==norm(n)]
        if candidates:parent=max(candidates,key=len)
        else:
            other=re.search(r'\band\s+(other\s+[\w -]+)$',prefix,re.I)
            parent=other[1] if other else re.split(r'[.;:]|\b(?:require|requires|using|receive|receives|use of|benefit from|prevent)\s+',prefix,flags=re.I)[-1].strip()
            if len(parent.split())>7 or not re.search(r'\b(?:aids|agents|devices|drugs|medications|therapies|interventions|programs|braces|orthoses|foods|supplements|fluids|accommodations|modifications)\b',parent,re.I):continue
        members=[re.sub(r'^(?:and|or)\s+','',x.strip(' ,'),flags=re.I) for x in re.split(r',\s*|\s+(?:and|or)\s+',members) if x.strip(' ,')]
        if not parent or len(members)<2:continue
        out.append({'parent':parent,'examples':members,'quote':quote})
    return out


def group_items(items):
    """Keep full raw members and their restrictions for review; no model inference or identity lookup."""
    names=[it['name'] for it in items];out=[]
    for item in items:
        groups=source_groups(item['quote'],names)
        eligible=[g for g in groups if norm(item['name'])==norm(g['parent']) or norm(item['name']) in {norm(n) for n in g['examples']}]
        if len(eligible)!=1:
            out.append(copy.deepcopy(item));continue
        g=eligible[0];it=copy.deepcopy(item);is_parent=norm(item['name'])==norm(g['parent'])
        it['name']=g['parent'];it['examples']=g['examples'];it['examples_quote']=g['quote']
        it['example_member']=None if is_parent else copy.deepcopy(item)
        if not is_parent:
            # A member's kind/requirements do not establish those of the whole class.
            parents=[p for p in items if norm(p['name'])==norm(g['parent']) and p['quote']==item['quote']]
            it['kind']=parents[0]['kind'] if parents and len({p['kind'] for p in parents})==1 else 'other'
            it['requirements']=[];it['manifestation']='';it['example_review_pending']=True
        out.append(it)
    return out
