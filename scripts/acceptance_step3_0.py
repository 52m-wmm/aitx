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
import re
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


# PubMed now answers every automated client with a cookie / proof-of-work check page (HTTP 203, seen 2026-11-04);
# the check is never bypassed: a PubMed link is confirmed through NCBI's official E-utilities (esummary) instead.
# Reports keep the pubmed.ncbi.nlm.nih.gov address; every other site must still answer HTTP 200.
PUBMED = re.compile(r"^https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?$")
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id={pmid}"


def check_url(url: str) -> str:
    """The URL actually requested to confirm `url`: the E-utilities record for a PubMed article, else the URL itself."""
    m = PUBMED.match(url or "")
    return ESUMMARY.format(pmid=m.group(1)) if m else url


def pubmed_record_ok(body: str, pmid: str) -> bool:
    """esummary JSON names the PMID with no error (an unknown PMID comes back with an "error" field)."""
    try:
        rec = json.loads(body).get("result", {}).get(pmid) or {}
    except (ValueError, AttributeError):
        return False
    return bool(rec) and "error" not in rec and str(rec.get("uid")) == pmid


def url_ok(url: str) -> bool:
    m = PUBMED.match(url or "")
    if m:
        body = _fetch(check_url(url))
        return body is not None and pubmed_record_ok(body, m.group(1))
    return _fetch(url) is not None


def _fetch(url: str) -> str | None:
    """Body of an HTTP 200 answer, else None (paced per host, retried on 429/5xx and network errors)."""
    req = urllib.request.Request(url, headers={"User-Agent": http.USER_AGENT})
    host = urllib.parse.urlparse(url).netloc
    for attempt in range(4):                       # many links in a row get rate-limited: pace, back off, retry
        wait = _last_hit.get(host, 0) + HOST_INTERVAL_S - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_hit[host] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace") if r.status == 200 else None
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503):
                return None
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(3 * (attempt + 1))
    return None


LINK_CHECK = "distinct source links resolve"
OUT = ROOT / "out" / "acceptance_step3_0.json"


def background_urls(ledgers: dict) -> list[str]:
    items = [e for l in ledgers.values() for e in l["evidence"] if e["section"] == "background"]
    return sorted({(e.get("source") or {}).get("url") for e in items} - {None})


def links_only() -> int:
    """Recheck the link HARD item on the saved ledgers; the other results of that run are kept as they were."""
    saved = json.loads(OUT.read_text())
    urls = background_urls(saved["ledgers"])
    bad = [u for u in urls if not url_ok(u)]
    what = f"{len(urls)} {LINK_CHECK}" + (f" -> {bad[:6]}" if bad else "")
    print(f"  [{'PASS' if not bad else 'FAIL'}] {what}  (PubMed via E-utilities esummary)")
    saved["failed"] = [f for f in saved["failed"] if LINK_CHECK not in f] + ([what] if bad else [])
    saved["links_rechecked_at"] = int(time.time())
    OUT.write_text(json.dumps(saved, indent=1, ensure_ascii=False))
    failed = saved["failed"]
    print("\nALL HARD CHECKS PASSED" if not failed else f"\n{len(failed)} HARD CHECK(S) FAILED: {failed}")
    return 1 if saved["failed"] else 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--offpeak-only", action="store_true",
                    help="exit without LLM calls during the provider's peak-price hours (config/llm_peak_hours.json)")
    ap.add_argument("--links-only", action="store_true",
                    help="recheck only the source links of the ledgers saved by the last full run (no LLM)")
    args = ap.parse_args()
    if args.links_only:
        return links_only()
    if args.offpeak_only:
        from aitx import peak
        peak.guard()
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
    urls = background_urls(ledgers)
    bad_urls = [u for u in urls if not url_ok(u)]
    hard(not bad_urls, f"{len(urls)} {LINK_CHECK}" + (f" -> {bad_urls[:6]}" if bad_urls else ""))

    print("\n== rules (HARD) ==")
    rules = load_rules()
    hard(bool(rules["loaded"]), f"{len(rules['loaded'])} rule(s) loaded with re-verified quotes; "
                                f"{len(rules['skipped'])} skipped")
    files = {r["id"]: r for f in (ROOT / "data" / "rules").glob("*.json") for r in json.loads(f.read_text())["rules"]}
    for rid in ("NF1-1", "CFTR-1"):          # reverse test: rules the reviewer vetoed must fail the support check
        sc = (files.get(rid) or {}).get("support_check") or {}
        hard(sc.get("overall") in ("partially_supported", "not_supported"),
             f"support check stops {rid} on its own -> {sc.get('overall')}")
    import eval_support_check as ESC
    ESC.collect()
    reg = ESC.evaluate(json.loads(ESC.SET.read_text())["cases"])
    hard(not ESC.leaks(json.loads(ESC.SET.read_text())["cases"]), "regression cases do not appear in the check prompt")
    hard(not reg["false_pass"], f"support check regression set ({reg['n']} reviewed rules, {reg['prompt_version']}): "
                                f"accuracy {reg['accuracy']}, false passes {reg['false_pass']}, false blocks {reg['false_block']}")
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

    out = OUT
    out.write_text(json.dumps({"failed": fails, "ledgers": ledgers}, indent=1, ensure_ascii=False))
    print(f"\n{'ALL HARD CHECKS PASSED' if not fails else f'{len(fails)} HARD CHECK(S) FAILED'}  (details: {out})")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
