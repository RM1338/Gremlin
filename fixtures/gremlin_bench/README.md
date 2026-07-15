# GremlinBench — a deliberately broken Flutter app

This is a fixture, not a real app. Its only purpose is to be a lab rat for
[Gremlin](../../README.md): every button opens a screen with one isolated,
planted defect that maps to a signal Gremlin's oracle matches on `logcat`.
Nothing here is meant to work.

| Screen | Planted defect | Oracle signal |
|---|---|---|
| Overflow bug | a `Row` of fixed-width boxes wider than the screen | `renderflex-overflow` |
| Crash on tap bug | an `onPressed` that throws | `dart-exception` |
| Bad build bug | a widget that throws in `build()` | `dart-exception` / render error |
| Clean screen | nothing — a safe place for exploration to go | (none) |

`lib/gremlin_probe.dart` is the opt-in error forwarder described in the main
README; `main()` installs it so framework/Dart errors reach `logcat` on modern
(Impeller) devices. Copy that one file into any app you want Gremlin to test.

## Run it

```bash
flutter build apk --debug
adb install -r build/app/outputs/flutter-apk/app-debug.apk
# then point Gremlin at it:
python run.py --project fixtures/gremlin_bench --steps 30
```

Because each control is a real, if intentional, bug, this doubles as a
regression fixture for Gremlin itself: a healthy Gremlin catches every planted
signal, and the Tier-2 autofix can turn the overflow green end to end.
