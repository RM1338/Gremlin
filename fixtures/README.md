# The fixtures moved out

`gremlin_bench` (Flutter) and `gremlin_bench_rn` (React Native) are now their
own repositories, one per fixture:

| Fixture | Repository | Toolkit |
|---|---|---|
| GremlinBench | `~/Projects/gremlin-bench-flutter` | Flutter |
| GremlinBench RN | `~/Projects/gremlin-bench-rn` | React Native |

**Not tidiness — Tier 2 requires it.** The fixer cuts a scratch branch, commits
one fix, and reverts with `git checkout .` when a gate fails, all against the
repository that *encloses* the app. While the fixtures lived here that was
Gremlin's own tree, so a failed gate could have discarded uncommitted work in
this repo; the dirty-tree refusal was the only thing preventing it.

For the same reason they are one repo **each**, not one shared `fixtures` repo.
A shared tree would mean editing the Flutter bench dirties the React Native
bench, and neither could be fixed while the other had changes.

## Running against them

They sit under `GREMLIN_PROJECTS_ROOT` (default `~/Projects`), so the console's
target picker lists them with no extra configuration:

```
python run.py --project ~/Projects/gremlin-bench-flutter --policy coverage
python -m gremlin.eval --project ~/Projects/gremlin-bench-flutter --actions 30
```

A future Kotlin/Android-native fixture belongs in `~/Projects/gremlin-bench-kotlin`,
on the same terms.
