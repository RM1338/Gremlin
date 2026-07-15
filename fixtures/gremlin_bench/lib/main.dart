// GremlinBench — a deliberately broken Flutter app.
//
// Its only purpose is to be a lab rat for the Gremlin UI-testing agent: every
// button leads to a screen with one isolated, planted defect that maps to a
// signal Gremlin's oracle matches on `logcat`. Nothing here is meant to work.
//
// One bug per screen, so a run can assert "Gremlin caught exactly these".

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import 'gremlin_probe.dart';

void main() {
  // Force the semantics tree on so `uiautomator dump` is deterministic even on
  // a device with no accessibility service running (see Gremlin grounding note).
  WidgetsFlutterBinding.ensureInitialized();
  SemanticsBinding.instance.ensureSemantics();

  // Opt into Gremlin: forward framework/Dart errors to logcat as greppable
  // lines. Required because modern Flutter doesn't reliably log them itself.
  installGremlinProbe();

  runApp(const BenchApp());
}

class BenchApp extends StatelessWidget {
  const BenchApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GremlinBench',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: Colors.teal, useMaterial3: true),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  void _go(BuildContext context, Widget page) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    // Each tile is labelled so it shows up as a content-desc in the a11y tree.
    final items = <(String, Widget)>[
      ('Overflow bug', const OverflowPage()),
      ('Crash on tap bug', const CrashPage()),
      ('Bad build bug', const BadBuildPage()),
      ('Clean screen', const CleanPage()),
    ];
    return Scaffold(
      appBar: AppBar(title: const Text('GremlinBench')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Text(
              'Each button opens a screen with one planted defect.',
              style: TextStyle(fontSize: 16),
            ),
          ),
          for (final (label, page) in items)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Semantics(
                button: true,
                label: label,
                child: ElevatedButton(
                  onPressed: () => _go(context, page),
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size.fromHeight(56),
                  ),
                  child: Text(label),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// PLANTED BUG 1 — layout overflow.
/// A Row of fixed-width boxes far wider than any phone screen, with no Expanded
/// or Flexible, so RenderFlex prints "A RenderFlex overflowed by N pixels".
class OverflowPage extends StatelessWidget {
  const OverflowPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Overflow')),
      body: Center(
        child: Row(
          children: [
            for (final c in [Colors.red, Colors.green, Colors.blue])
              Container(width: 250, height: 120, color: c),
          ],
        ),
      ),
    );
  }
}

/// PLANTED BUG 2 — uncaught exception on interaction.
/// Tapping the button throws, producing an unhandled Dart error + stack trace.
class CrashPage extends StatelessWidget {
  const CrashPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Crash on tap')),
      body: Center(
        child: Semantics(
          button: true,
          label: 'Trigger crash',
          child: ElevatedButton(
            onPressed: () {
              throw StateError('planted crash: button tapped');
            },
            child: const Text('Trigger crash'),
          ),
        ),
      ),
    );
  }
}

/// PLANTED BUG 3 — exception thrown during build().
/// Opening this screen throws while building, so Flutter logs a render/build
/// error and paints the red error box.
class BadBuildPage extends StatelessWidget {
  const BadBuildPage({super.key});

  @override
  Widget build(BuildContext context) {
    throw StateError('planted build error: BadBuildPage failed to build');
  }
}

/// A clean screen so exploration has somewhere safe to go (no signal here).
class CleanPage extends StatelessWidget {
  const CleanPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Clean screen')),
      body: const Center(
        child: Text('Nothing is broken here.', style: TextStyle(fontSize: 18)),
      ),
    );
  }
}
