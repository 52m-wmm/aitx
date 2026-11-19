# KMT2B staged v6.1 phase 1 v1.0 — 2026-11-19

## Outcome

$0 source-examples code and tests completed. Authorized new vote 2 stopped on truncation and request-budget reservation; vote 3 was not run. No AGXT execution/quotation and no engineering freeze. No Prompt changes (same 3a-v6.1 messages), no clinical Ledger refresh or Accepted update.

## Source examples rule

`X (e.g., A, B)` / `X such as A, B` is represented as action X plus literal examples A/B. Exact original sentence is retained and quoted in report rendering. Examples are source members, not chemical/RxCUI equivalences. Member-specific restrictions and original kind/name/quote are retained separately; they are not silently applied as eligibility for every member of X. An inferred parent type/scope remains unknown and requires review.

Actual frozen KMT2B source examples:

> Adaptive aids (e.g., ankle-foot orthoses, walkers) can support and maintain ambulation.

Parent `Adaptive aids`, examples `ankle-foot orthoses`, `walkers`. Hence these specific items are no longer considered missing separate actions solely because they are examples under that parent.

> Use of levodopa and other agents (e.g., trihexiphenidyl, baclofen, gabapentin, tetrabenazine, benzodiazepines) has not resulted in long-term benefit for most individuals with KMT2B-related disorders [Zech et al 2016, Meyer et al 2017, Zech et al 2017a, Lange et al 2021, Aksoy et al 2022]; nonetheless, a trial of these anti-dystonia agents would be considered reasonable.

`levodopa` remains independent; the parent of the explicit examples is the source's `other agents`, not a model-invented class. All five example names and their original conditions remain available. Drug-class type and applicability are not assumed from member identity. Formal drug normalization is unchanged.

The source's `accommodations or modifications such as ...` also records the listed assistive devices as examples. This does not turn it into a recalled 504 plan: parent-action/plan identity remains distinct and reviewable. Unknown or ambiguous structures are retained rather than guessed. Prompt remains unchanged; the same new postprocessing is applied offline to the prior vote and both planned new votes.

Offline tests cover e.g./such-as, parent qualifiers, Oxford comma, non-example actions, restriction preservation, drug-member versus primary-drug separation and full-source report quotation. Full suite 1303 passed.

## Authorized run and budget

The completed prior v6.1 chunked run is vote 1, not rerun. New votes 2 and 3 were each independently capped at $0.035 including retries. Same four fixed source inputs, seven lossless chunks, same model/Prompt/parameters, response cache bypassed. The two new votes had an identical request order, with the historically largest-output block last to reduce unused reservation overhead; no source text or Prompt changed. Offpeak, nohup+caffeinate; balance verified before paid execution.

Vote 2 made seven physical requests: six returned complete parsed responses and one truncated. No retry was sent. Known cost $0.031091418; usage complete, peak calls 0, no overspend or unplanned source. The final executed block was the original DD/ID first chunk (offset 0–3191), not the DD/ID second chunk. All 16,384 output tokens were reasoning; usable final content tokens 0. Retry reservation $0.020963500 was above the remaining $0.003908582.

The source inputs were present and hash-verified. The gate additionally recorded `response/input cache gap` because a complete response file for the truncated block was absent; this was not an independent source/database cache failure. No new FDA/RxNav/context requests were made. Missing responses and unexecuted votes are never treated as empty action lists or negative votes.

Phase stopped exactly on the operational anomaly. Vote 3 contains only a prepared input/proposal, no started marker, response or paid journal. No unused cap was transferred. New total spend for this phase $0.031091418; parent $0.50 campaign now $0.330854937 used / $0.169145063 remaining. Historical vote 1 fee was not charged again.

## Shared stop criteria, item by item

The user-approved contract is docs/step3a_v6_1_stop_criteria.md v1.0.

| Criterion | Status | Evidence |
|---|---|---|
| Three votes complete, no truncation | **Not met** | Vote 1 7/7; vote 2 6/7 with truncation; vote 3 unexecuted |
| All Accepted actions in union or explained | **Unscored for three votes** | Partial projection: 17 direct + 7 examples-grouping explanations, 1 spelling identity unresolved; all 25 rows preserved |
| No majority condition mistakes prevention/risk for existing disease | **Unscored for three votes; unresolved safety observation retained** | Available vote 1 and vote 2 core responses both retain the antibiotics infection-risk error; no absent-vote deletion or majority-as-truth inference |
| AGXT high oral fluid intake and IV fluids | **Not run** | KMT2B incomplete, AGXT stage not authorized/quoted |

Medical gaps did not interrupt vote 2, and would not by themselves block vote 3. The actual stopping trigger was truncation/incomplete block plus insufficient retry reservation. No medical Prompt edits were made after observing the result. This run cannot qualify KMT2B for the AGXT stage or engineering freeze.

## Trace, unchanged clinical state and limitations

runs/kmt2b-v6_1-phase1-20261119 contains plan, per-vote frozen inputs/SHA, usage, stop gate, responses, partial shadow union and all Accepted coverage rows. Partial condition voting distinguishes source-example member scope; every raw restriction is retained, kinds without a majority remain unresolved. The partial shadow output explicitly leaves medical stop criteria unscored; it is not a completed three-vote comparison.

Formal 15-case Ledgers and all historical/current baseline hashes remain unchanged. since-before status_diff is zero; current-vs-Accepted preserves existing differences. No clinical status changed, and no real patient report was rewritten. docs/known_limitations.md records the failed engineering criterion, unresolved content and draft submission-system-description material. Await a new user decision; do not automatically resume, expand limits, modify Prompt, or update Accepted.
