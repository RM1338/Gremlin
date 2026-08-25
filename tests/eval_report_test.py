"""What a benchmark report may claim from the samples it actually has.

The rules this encodes: a failed seed is never averaged in silently, a single
sample has no spread to report, and a defect's detection rate is per-seed —
"found in 1 of 5" and "found in 5 of 5" must not collapse into the same number
the way a mean bug count does.

Run from the project root:  python -m tests.eval_report_test
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gremlin.eval import Result, _aggregate, _detection_rates, _stats

# --- stats -----------------------------------------------------------------
assert _stats([]) == {"n": 0}
one = _stats([7])
assert one["n"] == 1 and one["mean"] == 7 and one["sd"] == 0.0, one
many = _stats([2, 4, 6])
assert many["mean"] == 4 and many["min"] == 2 and many["max"] == 6, many
assert many["sd"] > 0, "three different samples have spread"

# --- a failed seed is excluded from the mean, not counted as a zero ---------
runs = [
    Result("gremlin-vision", 30, 8, 3, 100.0, seed=0, bug_keys=["overflow", "crash"]),
    Result("gremlin-vision", 30, 6, 1, 90.0, seed=1, bug_keys=["overflow"]),
    Result("gremlin-vision", 30, 0, 0, 0.0, seed=2, error="ModelQuotaError: out"),
]
a = _aggregate(runs)
assert a["completed"] == 2 and a["failed"] == 1
assert a["screens"]["mean"] == 7, a["screens"]        # (8+6)/2, NOT (8+6+0)/3
assert a["screens"]["n"] == 2, "n must report the samples, not the attempts"
# Everything the arm found in any seed, which is more than any single run did.
assert a["bugs_union"] == ["crash", "overflow"], a["bugs_union"]
assert a["bugs"]["mean"] == 2, a["bugs"]

# --- detection rate is per-seed, and that is the point ----------------------
monkey = _aggregate([
    Result("monkey", 30, 3, 1, 40.0, seed=0, bug_keys=["overflow"]),
    Result("monkey", 30, 2, 0, 41.0, seed=1, bug_keys=[]),
    Result("monkey", 30, 0, 0, 0.0, seed=2, error="boom"),
])
rates = _detection_rates({"gremlin-vision": a, "monkey": monkey})
assert set(rates) == {"crash", "overflow"}, rates
# Both arms find the overflow, but not equally often — a mean would hide this.
assert rates["overflow"]["gremlin-vision"] == {"found_in": 2, "of": 2}
assert rates["overflow"]["monkey"] == {"found_in": 1, "of": 2}
# The crash only one arm ever reached: the ablation's whole reason to exist.
assert rates["crash"]["gremlin-vision"]["found_in"] == 1
assert rates["crash"]["monkey"]["found_in"] == 0
# The failed seed must not inflate the denominator into "0 of 3".
assert rates["crash"]["monkey"]["of"] == 2

# --- a run the quota truncated is a failed sample, not a low score -----------
# The explorer ends gracefully on a ModelError, so run_gremlin returns normally
# and the run looks complete. Averaging it in made the vision arm score below
# the no-model arm it is being compared against, purely because Gemini's daily
# free tier ran out partway through the benchmark.
truncated = _aggregate([
    Result("gremlin-vision", 30, 8, 3, 100.0, seed=0, bug_keys=["overflow"]),
    Result("gremlin-vision", 30, 1, 0, 4.0, seed=1,
           error="ended early at step 1: quota exhausted"),
    Result("gremlin-vision", 30, 1, 0, 4.0, seed=2,
           error="ended early at step 1: quota exhausted"),
])
assert truncated["completed"] == 1 and truncated["failed"] == 2
assert truncated["screens"]["mean"] == 8, truncated["screens"]
assert truncated["screens"]["sd"] == 0.0, "one surviving sample has no spread"

print("eval report: OK")
