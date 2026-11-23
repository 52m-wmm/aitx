"""Step 3a now selects original XML sources; it does not invent legacy Ledger Actions.

Use scripts/run_step3a.py prepare/run. The source-selection result is reviewed in
scripts/build_viewer.py. Conversion to the Step 4 Ledger contract is not implemented.
"""
from aitx.evidence.source_selection import prepare, run


def add_established(led, step1, step2, *, use_cache=True):
    raise RuntimeError('Step 3a now produces source selections via scripts/run_step3a.py. '
                       'Its Action/Ledger adapter is not integrated; full Step 3 cannot run.')
