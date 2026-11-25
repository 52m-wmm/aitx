"""Prepare/run the source-selection Step 3a backend without running other pipeline steps."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aitx.step3.a import source_selection as S, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare', help='Offline only; preserve XML and plan calls')
    prepare.add_argument('--cases', type=Path, required=True)
    prepare.add_argument('--case-id', required=True)
    prepare.add_argument('--xml', type=Path, required=True)
    prepare.add_argument('--management-id')
    prepare.add_argument('--threshold', type=int, default=8000)
    prepare.add_argument('--output', type=Path, help='Default: a new timestamped batch in runs/step3a/<case-id>')
    run = sub.add_parser('run', help='Paid execution; explicit approved budget required; no retry')
    run.add_argument('--output', type=Path, help='Default: the explicitly selected batch for --case-id')
    run.add_argument('--case-id', help='Case whose standard output directory should be used')
    run.add_argument('--resume', action='store_true', help='Recover saved answers and run only unstarted blocks')
    recovery = sub.add_parser('recover', help='Offline: rebuild selections from saved responses, no model calls')
    recovery.add_argument('--output', type=Path)
    recovery.add_argument('--case-id')
    run.add_argument('--concurrency', type=int, choices=range(1, 5), default=4)
    run.add_argument('--max-cost-usd', type=float, required=True)
    selection = sub.add_parser('select', help='Select the default CLI batch; the viewer always shows the latest batch')
    selection.add_argument('--case-id', required=True)
    selection.add_argument('--batch', required=True)
    args = parser.parse_args()
    if args.command == 'select':
        print(results.select(ROOT, args.case_id, args.batch))
        return
    if args.output is None:
        if not args.case_id:
            parser.error('run requires --case-id or an explicit --output')
        if args.command == 'prepare':
            if Path(args.case_id).name != args.case_id or args.case_id in ('.', '..'):
                parser.error('Invalid case ID')
            batch = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            args.output = ROOT / 'runs' / 'step3a' / args.case_id / batch
        else:
            args.output = results.current_folder(ROOT, args.case_id)
            if args.output is None:
                parser.error('No displayed batch selected; use select or --output')
    if args.command == 'prepare':
        cases = json.loads(args.cases.read_text())
        if isinstance(cases, dict):
            cases = [cases]
        matches = [c for c in cases if c['id'] == args.case_id]
        if len(matches) != 1:
            raise ValueError('Expected exactly one matching case')
        result = S.prepare(matches[0], args.xml, args.output, threshold=args.threshold,
                           management_id=args.management_id)
    elif args.command == 'recover':
        result = S.recover(args.output)
    else:
        result = S.run(args.output, max_cost_usd=args.max_cost_usd, concurrency=args.concurrency, resume=args.resume)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
