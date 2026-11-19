# Step 3a-v6.1 phased stop criteria v1.0 — 2026-11-19

## Stage authorization

KMT2B uses the completed chunked v6.1 observation as vote 1 and adds vote 2 (cap $0.035). If vote 2 has no operational anomaly, proceed directly to vote 3 (separate cap $0.035). Each cap includes retries and cannot borrow from the other. Offpeak only; verify balance before execution. Same four fixed sources, seven lossless chunks, Prompt/model/parameters/rules fixed for all votes; raw response cache bypassed. Completed vote 1 is not regenerated. No AGXT calls at this stage.

Only operational anomalies stop before vote 3: any truncation (including one later repaired by a retry), incomplete/missing required input or response block, an unplanned request/source, provider/model mismatch, unknown usage, or request reservation exceeding the stage cap. Unexpected paid work outside source extraction also stops. Planned cache-only context checks that were explicitly outside this experiment remain untested; they are not silently called or counted as passed. No new 81-call context work.

Medical gaps such as missing 504 plan or one vote misreading infection risk do not stop vote 3. Aggregate them after three votes. Do not select a preferred vote or rerun for agreement.

## Shared KMT2B and AGXT engineering completion criteria

1. All three votes complete without truncation or incomplete blocks.
2. Every real Step 3a action in the current Accepted snapshot is found in the union, or has an explicit item-by-item difference explanation (for example an examples grouping). A placeholder such as None found is not a real action. Include complete coverage rows, provenance and unresolved cases; a missing action is not silently treated as not applicable. Explanation is not medical approval.
3. No condition receiving at least two votes for activation treats a prevention purpose or risk rationale as a current patient manifestation. Report minority conditions separately. Safety/eligibility disagreements remain needs_review and block unconditional applicability; no deleting a minority condition just to pass.
4. AGXT additionally requires high oral fluid intake and intravenous fluids in the union.

## Aggregation and freeze

Shadow only: actions union; each vote counts once per normalized condition, not once per duplicate mention; at least two votes form majority. Keep single-vote conditions, source quotes and existing Evidence IDs. Keep source-supported necessary conditions even without majority. Kind without a majority remains disputed. Equivalent age bounds may combine only with compatible explicit source range. Examples remain source members, not independently applicable therapies or pharmacologic synonyms.

KMT2B completion permits quoting AGXT only; AGXT requires separate approval. Freeze the engineering version only after both cases meet criteria; freeze does not mean medical conclusions are reviewed. Record unmet items in docs/known_limitations.md as material for the submission system description. Do not automatically edit Prompt or Accepted Baseline to pass. Any future update requires a new explicit task.
