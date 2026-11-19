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

## DD/ID 块持续推理失控（3/3次）— 2026-11-19新增诊断

保留用户指定的问题名；这里的“3/3”指三次记录均由reasoning占据绝大多数输出，**不是三次都截断**，也不是完全相同输入的三次严格重复：

| 记录 | 输入范围 | reasoning / 总输出 | 结果 |
|---|---|---:|---|
| v5历史首发 | DD/ID整节3677字符 | 15931 / 16384 | 截断，后续曾放大上限完成 |
| v6.1首票 | DD/ID第一块3191字符 | 15549 / 16107 | 完成，但距16384仅277 tokens |
| v6.1第二票 | 同3191字符块 | 16384 / 16384 | 截断，重试预留不足停止 |

因此分块仍未消除高推理消耗；不能把首票完成当成稳定性保证。当前新任务另授权一次low档诊断（$0.01），只有完成且源内行动无明显遗漏才允许后续默认档位变更及$0.05续跑。诊断开始前已固定目标行动与比较范围，不通过则停止，不改Prompt。

### Low诊断结果：未满足后续授权条件

一次low请求完成：6832 reasoning / 569内容tokens，$0.004644600，无截断；为遵守$0.01预留，本次输出上限14000（原档16384），已在执行前披露。缺少同Prompt完整第一票返回的独立IEP及其资格条件，504计划也未独立返回。PT/OT/speech学业访问限定有所恢复，但不能抵销明确行动遗漏。默认档位不改、重试策略不改，第二票仍未补完，第三票未执行；后续$0.05未启用。详见docs/kmt2b_low_diagnostic_20261119.md。不可依据一次低档完成宣称稳定性或临床完整性通过。
