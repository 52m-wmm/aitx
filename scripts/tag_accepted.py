"""Tag an accepted version and archive the results it was accepted on.

Usage:
    python3 scripts/tag_accepted.py step3a-accepted -m "Step 3a accepted: ..."
    python3 scripts/tag_accepted.py step3.0-accepted --backfill     # archive only, for an existing tag

Creates the annotated git tag at HEAD (refuses if it exists, unless --backfill), then copies the results under
out/ (step outputs, acceptance and evaluation files; not the derived review snapshots, screenshots or viewer run
logs) to .cache/snapshots/<tag>/out/ (never committed) with manifest.json: tag, code commit, creation time,
sha256 of every file and, per case, of each step output. The review page can compare against these archives.
Always tag accepted versions with this script so every tag has its archive. Pushing stays a separate step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
SNAPSHOTS = ROOT / ".cache" / "snapshots"
SKIP = {"review", "screenshots", "viewer_runs"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def files_to_archive(out: Path = OUT) -> list[Path]:
    return sorted(p for p in out.rglob("*") if p.is_file() and p.relative_to(out).parts[0] not in SKIP)


def archive(tag: str, commit: str, note: str = "", out: Path = OUT, dest_root: Path = SNAPSHOTS) -> Path:
    dest = dest_root / tag
    if dest.exists():
        shutil.rmtree(dest)
    files = {}
    for p in files_to_archive(out):
        rel = p.relative_to(out)
        target = dest / "out" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        files[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    cases: dict[str, dict] = {}
    for rel, h in files.items():
        parts = Path(rel).parts
        if len(parts) == 2 and parts[0].startswith("step") and parts[1].endswith(".json") and parts[1] != "sources_manifest.json":
            cases.setdefault(parts[1][:-5], {})[parts[0]] = h
    manifest = {"tag": tag, "code_commit": commit, "created_at": int(time.time()),
                "created": time.strftime("%Y-%m-%d %H:%M:%S"), "note": note,
                "cases": dict(sorted(cases.items())), "files": files}
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("-m", "--message", default="")
    ap.add_argument("--backfill", action="store_true", help="tag exists already: archive the current out/ for it")
    args = ap.parse_args()
    exists = bool(git("tag", "--list", args.tag))
    if exists and not args.backfill:
        print(f"tag {args.tag} exists; use --backfill to archive results for it")
        return 2
    if not exists and args.backfill:
        print(f"tag {args.tag} does not exist")
        return 2
    head = git("rev-parse", "--short", "HEAD")
    note = ""
    if args.backfill:
        tagged = git("rev-list", "-n", "1", "--abbrev-commit", args.tag)
        note = (f"backfilled {time.strftime('%Y-%m-%d')}: results from out/ as of code {head}, "
                f"not necessarily identical to those at tag time (tag points to {tagged})")
    else:
        if not args.message:
            print("give -m with the acceptance summary")
            return 2
        git("tag", "-a", args.tag, "-m", args.message)
    dest = archive(args.tag, head, note)
    n = len(json.loads((dest / "manifest.json").read_text())["files"])
    print(f"{'archived' if args.backfill else 'tagged and archived'} {args.tag}: {n} files -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
