"""Conservative demographic OR across explicitly enumerated populations.

Unparsed populations are never silently dropped. This is not full eligibility:
one non-conflicting or unknown route prevents a whole-study exclusion here.
"""
import re

from aitx.evidence import trials as T


_HEAD = re.compile(r"^['\"]?([^\n:]+?)['\"]?\s+(?:sub-study|cohort|group):\s*$", re.I | re.M)
_WORDS = dict(zip(('zero one two three four five six seven eight nine ten eleven twelve '
                   'thirteen fourteen fifteen sixteen seventeen eighteen').split(), range(19)))


def _demographics(text, facts):
    checks = []
    for raw in text.splitlines():
        line = re.sub(r'^\s*[*\-]\s*', '', raw).strip()
        if re.search(r'\b(?:if|unless|except|either)\b|\bor\s+(?!(?:older|above)\b)', line, re.I):
            continue  # Conditional or alternative subjects are not a mandatory bound.
        age_line = re.sub(r'\b(' + '|'.join(_WORDS) + r')\b',
                          lambda m: str(_WORDS[m[0].lower()]), line, flags=re.I)
        # Only the participant's direct age clause, never a parent's age,
        # disease duration, treatment window, or a nested conditional sentence.
        prefix = r'(?:Age\s+|(?:Children|Infants|Participants) aged\s+)'
        tail = r'(?:\s+(?:of age)?\s*(?:at\b.*|with\b.*))?\.?'
        span = re.fullmatch(prefix + r'(\d+)\s*(?:to|[-–])\s*(\d+)\s+(years?|months?)' + tail, age_line, re.I)
        minimum = re.fullmatch(r'Age\s+(\d+)\s+(years?|months?)\s+or\s+(?:above|older)' + tail, age_line, re.I)
        maximum = re.fullmatch(r'Less than\s+(\d+)\s+(years?|months?)' + tail, age_line, re.I)
        allowed = None
        months = facts['age_months']
        if span and int(span[1]) <= int(span[2]):
            lo, hi = (T.age_months(f'{span[i]} {span[3]}') for i in (1, 2))
            allowed = None if months is None else lo <= months <= hi
        elif minimum:
            allowed = None if months is None else months >= T.age_months(f'{minimum[1]} {minimum[2]}')
        elif maximum:
            allowed = None if months is None else months < T.age_months(f'{maximum[1]} {maximum[2]}')
        elif re.match(r'^Newborn infant\b', line, re.I):
            # Conservative upper bound, NOT a definition of the neonatal period:
            # a person >= 12 months is certainly not a newborn. Younger stays unknown.
            allowed = False if months is not None and months >= 12 else None
        if span or minimum or maximum or re.match(r'^Newborn infant\b', line, re.I):
            checks.append({'field': 'age', 'quote': line, 'result':
                           'unknown' if allowed is None else 'pass' if allowed else 'fail'})
        sex = re.match(r'^(Woman|Women|Females|Men|Males)\b', line, re.I)
        if sex:
            wanted = 'female' if sex[1].lower() in ('woman', 'women', 'females') else 'male'
            known = facts['sex']
            checks.append({'field': 'sex', 'quote': line, 'result':
                           'unknown' if known not in ('male', 'female') else 'pass' if known == wanted else 'fail'})
    return checks


def evaluate(study, facts):
    """Return complete supported population coverage, or None for unresolved scope."""
    text = study['criteria']
    match = re.fullmatch(r'\s*Inclusion Criteria:\s*(.*?)\s*Exclusion Criteria:.*', text, re.S | re.I)
    if not match:
        return None
    inclusion = match[1]
    groups = study['population_groups']
    if any('type' in g and g['type'] in ('EXPERIMENTAL', 'ACTIVE_COMPARATOR',
           'PLACEBO_COMPARATOR', 'SHAM_COMPARATOR') for g in groups):
        return None  # Randomized treatment arms are not alternative eligibility populations.
    headings = list(_HEAD.finditer(inclusion))
    populations = []
    if headings:
        if inclusion[:headings[0].start()].strip():
            return None
        for i, heading in enumerate(headings):
            body = inclusion[heading.end():headings[i + 1].start() if i + 1 < len(headings) else len(inclusion)]
            if re.search(r'^\s*[^*\n]+:\s*$', body, re.M):
                return None  # Another population/header was not understood.
            populations.append({'label': heading[1].strip("'\" "), 'text': body.strip()})
        labels = [p['label'].casefold() for p in populations]
        if len(set(labels)) != len(labels):
            return None
        if any(g['label'].casefold() not in labels for g in groups):
            return None
    else:
        # Explicit mother/newborn subject sentences, not an AND list of criteria.
        sentences = [s.strip() for s in re.split(r'\.\s+', inclusion) if s.strip()]
        if len(sentences) != 2 or not re.match(r'^Woman\b', sentences[0], re.I) or not re.match(r'^Newborn infant\b', sentences[1], re.I):
            return None
        if len(groups) != 1 or not re.fullmatch(r'mother[- ]infant (?:dyads|pairs)', groups[0]['label'], re.I):
            return None
        populations = [{'label': 'mother', 'text': sentences[0]}, {'label': 'newborn infant', 'text': sentences[1]}]
    if len(populations) < 2:
        return None
    for population in populations:
        checks = _demographics(population['text'], facts)
        descriptions = [g['description'] for g in groups
                        if g['label'].casefold() == population['label'].casefold() and 'description' in g]
        metadata = [c for description in descriptions for c in _demographics(description, facts)]
        # Broader age/sex in registry cohort descriptions can rescue a possible
        # route; never pick the narrower source silently.
        failed_fields = {c['field'] for c in checks if c['result'] == 'fail'}
        inconsistent = any(c['result'] == 'pass' and c['field'] in failed_fields for c in metadata)
        population.update(checks=checks, metadata_checks=metadata,
                          result='conflict' if failed_fields and not inconsistent else 'unknown')
    return {'populations': populations, 'all_conflict': all(p['result'] == 'conflict' for p in populations),
            'trial_quote': inclusion}
