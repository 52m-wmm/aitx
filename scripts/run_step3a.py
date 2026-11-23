"""Prepare/run the source-selection Step 3a backend without running other pipeline steps."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aitx.evidence import source_selection as S


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare', help='Offline only; preserve XML and plan calls')
    prepare.add_argument('--cases', type=Path, required=True)
    prepare.add_argument('--case-id', required=True)
    prepare.add_argument('--xml', type=Path, required=True)
    prepare.add_argument('--management-id')
    prepare.add_argument('--threshold', type=int, default=8000)
    prepare.add_argument('--output', type=Path, required=True)
    run = sub.add_parser('run', help='Paid execution; explicit approved budget required; no retry')
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--max-cost-usd', type=float, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        cases = json.loads(args.cases.read_text())
        if isinstance(cases, dict):
            cases = [cases]
        matches = [c for c in cases if c['id'] == args.case_id]
        if len(matches) != 1:
            raise ValueError('Expected exactly one matching case')
        result = S.prepare(matches[0], args.xml, args.output, threshold=args.threshold,
                           management_id=args.management_id)
    else:
        result = S.run(args.output, max_cost_usd=args.max_cost_usd)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
