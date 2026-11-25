"""CLI to import an already reviewed Step3a result."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aitx.step3.a.results import archive


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--prepared',type=Path,required=True)
    ap.add_argument('--destination',type=Path,required=True)
    a=ap.parse_args();print(archive(a.source,a.prepared,a.destination))
