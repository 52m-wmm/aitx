# Known limitations v1.0 — 2026-11-19

Status: candidate engineering version 3a-v6.1, **not frozen**. Accepted Baseline and medical conclusions have not been changed. AGXT stage has not been run or quoted because KMT2B has not met the shared stop criteria.

## KMT2B phase 1: incomplete independent executions

- The existing chunked vote completed 7/7 blocks without truncation. The newly authorized vote 2 completed only 6/7; the DD/ID first source block (3,191 characters, scheduled last) exhausted 16,384 output tokens entirely in reasoning, yielding no usable final response.
- Vote 2 cost $0.031091418 of its $0.035 cap. A necessary retry required $0.020963500 reservation, exceeding $0.003908582 remaining. It was not sent. Vote 3 was not started, as explicitly required after any operational anomaly.
- Fixed source inputs were complete. The missing complete response is caused by truncation, not a newly discovered FDA/RxNav/input cache gap. The gate's generic `response/input cache gap` label refers here to the absent completed raw block. No downstream context/FDA cache completeness is claimed: this was source extraction only, with no new context checks.
- The three-complete-votes/no-truncation criterion is not met. Other medical criteria are unscored for the planned three-vote experiment; partial results are not evidence of stability. Chunking at 3,500 characters reduces source size but does not bound model reasoning tokens.

## Unresolved content observations (not three-vote medical validation)

- Two available core-source responses still turn the rationale “because of the increased risk of pulmonary infections” into an existing manifestation for prophylactic antibiotics. This is a retained safety review item, not automatically applied to a patient. The absent third vote cannot be treated as a negative vote or used to remove this condition.
- 504 plan and explicit same-sentence eligibility constraints have been omitted in prior extractions. The uncompleted three-vote run does not close these issues. IEP service scope, pregnancy descriptions versus eligibility, and drug-name spelling variants also need source review.
- A provisional union of available responses covers 17 of 25 Accepted Step 3a action/branch rows directly and retains 7 as explicit source examples under their parents. The remaining historical `trihexyphenidyl` label differs from the frozen source's `trixhexyphenidyl` spelling. This is recorded as unresolved identity review, not silently converted into an approved drug synonym or not applicable result. This partial coverage is not the final three-vote union assessment.
- Source examples are grouped under the explicit source parent, with their original member extractions and restrictions preserved. These are examples/members, not interchangeable pharmacologic synonyms. Parent type/scope inferred only from a child remains unknown/needs_review and cannot yield unconditional applicability. The whole source sentence and Evidence IDs remain available when a formal report is generated.

## Draft material for the submission system description

The pipeline uses deterministic source chunking, provenance-preserving evidence assembly, and per-request budget reservations. Source examples are represented as members of a parent action rather than separate interchangeable therapies. Large reasoning outputs may still truncate, and incomplete source extractions are explicitly marked incomplete rather than accepted as empty results. Source-level omissions and misinterpretations of prevention or risk rationale remain possible and require clinical review. Engineering version freezing, when justified by predefined checks, does not certify medical conclusions.

These limitations are recorded without automatically revising the Prompt, rules, or Accepted Baseline. A future attempt or AGXT experiment requires a new user decision and the applicable separate budget approval.
