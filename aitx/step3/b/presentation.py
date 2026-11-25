"""Convert saved Ledger verdicts to viewer cards without screening or inference."""
from pathlib import Path
from aitx.evidence.trials import clinical_priority_key as priority_key


def ledger_view(ledger: dict, case: dict, ledger_path: Path) -> dict:
    """Render the actual formal Ledger verdicts, not experimental candidate lists."""
    if ledger['schema_version'] != 'evidence-ledger-v3' or not ledger['ok']:
        raise ValueError('A checked evidence-ledger-v3 is required')
    case_id = ledger['patient_id']
    evidence = {e['id']: e for e in ledger['evidence']}
    candidates, excluded = [], []
    labels = {'age': '年龄', 'diagnosis': '疾病诊断', 'genetic_confirmation': '分子诊断',
              'variant': '遗传变异', 'lab': '实验室指标', 'egfr': '肾功能', 'weight': '体重',
              'current_medication': '当前用药', 'prior_therapy': '既往治疗',
              'other_trial': '其他研究参与情况', 'pregnancy': '生育及妊娠相关要求'}
    for action in ledger['actions']:
        if action['section'] != 'clinical_trial_eligibility' or not action.get('nct'):
            continue
        retained = any(s['status'] in ('applicable', 'conditional') for s in action['status_by_branch'].values())
        rules = action['requirements']
        record = {'nct_id': action['nct'], 'title': action['title'], 'display_name': action['label'],
                  'status': action['overall_status'], 'study_type': action['protocolSection']['designModule']['studyType'],
                  'decision': 'candidate' if retained else 'exclude', 'pathway': action['pathway'],
                  'clinical_path_supported': None, 'eligibility_text': action['protocolSection']['eligibilityModule']['eligibilityCriteria'],
                  'ledger_action': action}
        if not retained:
            failed = [r for r in rules if r['result'] == 'fail']
            record.update(reason='；'.join(dict.fromkeys(s['reason'] for s in action['status_by_branch'].values())),
                          display_evidence=[{'trial_quote': r['requirement'],
                                             'patient_quote': r['patient_fact']['quote']} for r in failed])
            excluded.append(record)
            continue
        known = list(dict.fromkeys(labels[r['fact']] for r in rules if r['result'] == 'pass' and r['kind']=='inclusion'
                                   and 'fact' in r and r['fact'] in labels))
        pending = list(dict.fromkeys(labels[r['fact']]+'相关要求待核实' for r in rules if r['result']=='unknown'
                                     and 'fact' in r and r['fact'] in labels))
        if any(r['result'] in ('unknown','not_assessed') and ('fact' not in r or r['fact'] not in labels) for r in rules):
            pending.append('其余医学及研究筛查要求详见原文，需由研究团队核实')
        record.update(card_known='、'.join(known)+'条件已有病例依据；完整资格仍需筛查' if known else '已保留供进一步筛查，完整入组路径尚待确认',
                      card_pending=pending[:5], prerequisites=[
                          {'prerequisite':r['requirement'], 'status':{'pass':'confirmed','fail':'conflict','unknown':'unknown','not_assessed':'not_assessed'}[r['result']],
                           'scope':r['alternative'] if 'alternative' in r else '共同条件',
                           'route':'alternative' if 'alternative' in r else 'required',
                           'kind':r['fact'] if 'fact' in r else 'other',
                           'trial_quote':evidence[r['requirement_evidence']]['quote'],
                           'patient_evidence':[{'quote':r['patient_fact']['quote']}] if r['patient_fact'] and r['patient_fact']['quote'] else [],
                           'explanation':r['note'], 'ledger_requirement':r} for r in rules])
        candidates.append(record)
    candidates.sort(key=priority_key)
    plans = ledger['trial_searches'].values()
    counts = {'api_query_returned_with_duplicates':sum(s['n_retrieved'] for p in plans for s in p['searches']),
              'api_unique':sum(p['n_unique'] for p in plans), 'sent_to_deepseek':sum(len(p['analysed']) for p in plans),
              'final_candidates':len(candidates), 'final_excluded':len(excluded)}
    result = {'case_id':case_id, 'patient':case, 'source':str(ledger_path.resolve()), 'source_kind':'formal_ledger',
              'counts':counts, 'candidates':candidates, 'excluded':excluded, 'trial_searches':ledger['trial_searches']}
    return result
