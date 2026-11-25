# 已知限制与待核对问题

## 已由代码确认的当前限制（2026-11-25）

Step3a 已切换至原文节点选择；`aitx/evidence/step3a.py:add_established` 因 Ledger 适配未接入而抛错停止。独立来源选择结果不等于完整 Step3 账本或报告验收通过。

## 历史观察，当前是否解决尚未核实

以下来自旧 KMT2B 抽取实验，保留作核对线索，不表示当前实现一定仍有同样问题，也不代表患者医学结论。旧分块票数、模型档位及剩余预算不作为当前状态或新调用授权。


- Two available core-source responses still turn the rationale “because of the increased risk of pulmonary infections” into an existing manifestation for prophylactic antibiotics. This is a retained safety review item, not automatically applied to a patient. The absent third vote cannot be treated as a negative vote or used to remove this condition.
- 504 plan and explicit same-sentence eligibility constraints have been omitted in prior extractions. The uncompleted three-vote run does not close these issues. IEP service scope, pregnancy descriptions versus eligibility, and drug-name spelling variants also need source review.
- A provisional union of available responses covers 17 of 25 Accepted Step 3a action/branch rows directly and retains 7 as explicit source examples under their parents. The remaining historical `trihexyphenidyl` label differs from the frozen source's `trixhexyphenidyl` spelling. This is recorded as unresolved identity review, not silently converted into an approved drug synonym or not applicable result. This partial coverage is not the final three-vote union assessment.
- Source examples are grouped under the explicit source parent, with their original member extractions and restrictions preserved. These are examples/members, not interchangeable pharmacologic synonyms. Parent type/scope inferred only from a child remains unknown/needs_review and cannot yield unconditional applicability. The whole source sentence and Evidence IDs remain available when a formal report is generated.

