"""Online acceptance for step 3.0 (evidence ledger skeleton; contract docs/step3_0_contract.md, section 9).

  HARD  every case builds a ledger from the step 1/2 outputs on disk (STALE if they do not match) and all
        ledger checks pass
  HARD  branches: at most 3, ambiguous practice cases keep several branches, umbrellas expanded or marked
  HARD  every background quote verified; every source link resolves (HTTP 200)
  HARD  every loaded rule has re-verified quotes; the DMD reading-frame rule applies to PRAC-DMD-del,
        Becker is promoted to a branch and Duchenne is kept
  HARD  ClinicalTrials.gov cache: refetched when forced, served from cache within the day
  SOFT  printed for review: AITX-40003 branches and SPTLC1 rule outcome, dropped branches, skipped rules
          (evaluation cases are reported only, never tuned on)

Usage:  python3 scripts/acceptance_step3_0.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from aitx import http, runmeta  # noqa: E402
from aitx.evidence import pipeline  # noqa: E402
from aitx.evidence.rules import load_rules  # noqa: E402
from run_pipeline import load_cases  # noqa: E402

AMBIGUOUS_PRACTICE = ["PRAC-COL1A1", "PRAC-DMD-del", "PRAC-GRIN2B"]
BECKER, DUCHENNE = "OMIM:300376", "OMIM:310200"


_last_hit: dict[str, float] = {}
HOST_INTERVAL_S = 1.0          # be polite: at most one request per second to the same host


def url_ok(url: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": http.USER_AGENT})
    host = urllib.parse.urlparse(url).netloc
    for attempt in range(4):                       # many links in a row get rate-limited: pace, back off, retry
        wait = _last_hit.get(host, 0) + HOST_INTERVAL_S - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status == 200
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503):
                return False
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(3 * (attempt + 1))
    return False


def main() -> int:
    fails = []

    def hard(ok, what):
        print(f"  [{'PASS' if ok else 'FAIL'}] {what}")
        if not ok:
            fails.append(what)

    print("== ledgers (HARD) ==")
    ledgers = {}
    for case in load_cases(None, None):
        try:
            s1, h1 = runmeta.load_output(1, case)
            s2, _ = runmeta.load_output(2, case)
            runmeta.check_upstream(s2, 2, {1: h1})
        except runmeta.StaleOutput as e:
            hard(False, f"{case['id']}: {e}")
            continue
        led = pipeline.run_case(case, s1, s2)
        ledgers[case["id"]] = led
        bad = [f"{c['name']}: {c['detail']}" for c in led["checks"] if c["status"] == "fail"]
        hard(not bad, f"{case['id']}: {len(led['branches'])} branch(es), {len(led['evidence'])} items, checks"
                      + (f" -> {bad}" if bad else " pass"))

    print("\n== branches (HARD) ==")
    hard(all(len(l["branches"]) <= 3 for l in ledgers.values()), "every ledger has at most 3 branches")
    for cid in AMBIGUOUS_PRACTICE:
        n = len(ledgers[cid]["branches"])
        hard(n >= 2, f"{cid}: ambiguous in step 2 -> {n} branches")
    um = [f"{cid} {b['id']}" for cid, l in ledgers.items() for b in l["branches"]
          if b.get("umbrella") and not (b.get("expanded_from") or b.get("not_expandable"))]
    hard(not um, "umbrella branches expanded or marked not expandable" + (f" -> {um}" if um else ""))

    print("\n== background evidence and links (HARD) ==")
    items = [e for l in ledgers.values() for e in l["evidence"] if e["section"] == "background"]
    unver = [e["id"] for e in items if e["status"] != "verified"]
    hard(not unver, f"{len(items)} background items verified" + (f" -> not verified {unver[:5]}" if unver else ""))
    urls = sorted({(e.get("source") or {}).get("url") for e in items} - {None})
    bad_urls = [u for u in urls if not url_ok(u)]
    hard(not bad_urls, f"{len(urls)} distinct source links resolve" + (f" -> {bad_urls[:6]}" if bad_urls else ""))

    print("\n== rules (HARD) ==")
    rules = load_rules()
    hard(bool(rules["loaded"]), f"{len(rules['loaded'])} rule(s) loaded with re-verified quotes; "
                                f"{len(rules['skipped'])} skipped")
    files = {r["id"]: r for f in (ROOT / "data" / "rules").glob("*.json") for r in json.loads(f.read_text())["rules"]}
    for rid in ("NF1-1", "CFTR-1"):          # reverse test: rules the reviewer vetoed must fail the support check
        sc = (files.get(rid) or {}).get("support_check") or {}
        hard(sc.get("overall") in ("partially_supported", "not_supported"),
             f"support check stops {rid} on its own -> {sc.get('overall')}")
    dmd = ledgers["PRAC-DMD-del"]
    applied = [r for r in dmd["rules_applied"] if r["rule_id"].startswith("DMD-")]
    hard(bool(applied), f"PRAC-DMD-del: DMD rule applied -> {[r['rule_id'] for r in applied]}")
    omims = {o: b for b in dmd["branches"] if b["diagnosis"] for o in b["diagnosis"]["omim"]}
    hard(BECKER in omims and omims[BECKER].get("promoted_by"),
         f"PRAC-DMD-del: Becker promoted to a branch (promoted_by {omims.get(BECKER, {}).get('promoted_by')})")
    hard(DUCHENNE in omims, "PRAC-DMD-del: Duchenne branch kept")

    print("\n== ClinicalTrials.gov cache (HARD) ==")
    url = "https://clinicaltrials.gov/api/v2/studies?query.term=SPTLC1&pageSize=1"
    http.get(url)
    http._refreshed.clear()                     # a new run: nothing refreshed yet in this run
    http.FORCE_REFRESH.add("https://clinicaltrials.gov/")
    first = http.get(url)
    second = http.get(url)
    http.FORCE_REFRESH.clear()
    hard(not first.from_cache and second.from_cache, "forced refresh refetches once, then the cache serves it")
    hard(http.max_age(url) == 24 * 3600, "ClinicalTrials.gov max age is 1 day")

    print("\n== to review (SOFT; evaluation cases reported only) ==")
    for cid, l in ledgers.items():
        if l.get("branches_dropped") or l["rules_applied"]:
            print(f"  {cid}: branches {[b['diagnosis']['label'] if b['diagnosis'] else b['id'] for b in l['branches']]}")
            for d in l.get("branches_dropped") or []:
                print(f"      dropped: {d['diagnosis']['label']} (score {d['step2_score']})")
            for r in l["rules_applied"]:
                print(f"      rule {r['rule_id']}: {r['statement'][:110]}  promotions {r.get('promotions')}")
    l3 = ledgers.get("AITX-40003")
    if l3:
        print(f"  AITX-40003 branches: {[b['diagnosis']['label'] for b in l3['branches']]}; "
              f"rules applied: {[r['rule_id'] for r in l3['rules_applied']] or 'none'}")
    sp = ROOT / "data" / "rules" / "SPTLC1.json"
    if sp.exists():
        d = json.loads(sp.read_text())
        print(f"  SPTLC1 rules: {[(r['id'], r['applies_when']) for r in d['rules']]}; no-rule note: {d.get('no_rule_reason', '')[:160]}")
    for s in rules["skipped"]:
        print(f"  skipped rule {s['rule_id']}: {s['reasons']}")

    out = ROOT / "out" / "acceptance_step3_0.json"
    out.write_text(json.dumps({"failed": fails, "ledgers": ledgers}, indent=1, ensure_ascii=False))
    print(f"\n{'ALL HARD CHECKS PASSED' if not fails else f'{len(fails)} HARD CHECK(S) FAILED'}  (details: {out})")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
