// Gremlin probe — opt-in error forwarder.
//
// Modern Flutter (Impeller/Vulkan) does NOT reliably forward framework or Dart
// errors to `logcat`: the on-screen red box / overflow banner still shows, but
// the console text Gremlin's oracle greps for never arrives. So an app that
// wants to be tested by Gremlin installs this in main(). It forwards every
// framework + platform error to logcat as a single, stable, greppable line
// (`GREMLIN_BUG ...`) followed by the first app stack frame (`GREMLIN_LOC ...`).
//
// This is the same hook crash-reporting SDKs (Sentry, Crashlytics) install, so
// it composes with them — it only adds a print, it doesn't swallow anything.
//
// Usage:  void main() { installGremlinProbe(); runApp(...); }

import 'package:flutter/foundation.dart';

/// Match a Dart source location like `foo/bar.dart:42` or `bar.dart:42:7`.
final RegExp _dartLoc = RegExp(r'([A-Za-z0-9_./]+\.dart):(\d+)(?::(\d+))?');

/// Install the forwarders. Idempotent enough to call once at the top of main().
void installGremlinProbe() {
  final FlutterExceptionHandler? priorOnError = FlutterError.onError;
  FlutterError.onError = (FlutterErrorDetails details) {
    _emit(details.exceptionAsString(), details.stack);
    priorOnError?.call(details); // preserve default/SDK handling
  };

  final priorPlatformOnError = PlatformDispatcher.instance.onError;
  PlatformDispatcher.instance.onError = (Object error, StackTrace stack) {
    _emit(error.toString(), stack);
    return priorPlatformOnError?.call(error, stack) ?? false;
  };
}

void _emit(String message, StackTrace? stack) {
  // One line: debugPrint throttling can split/drop big multi-line dumps, but a
  // single short print always lands. This is why we don't rely on the default.
  final String first = message.split('\n').first.trim();
  // ignore: avoid_print
  print('GREMLIN_BUG $first');
  final String? loc = _firstAppFrame(stack);
  if (loc != null) {
    // ignore: avoid_print
    print('GREMLIN_LOC $loc');
  }
}

/// The first stack frame that belongs to app code (not the Flutter framework or
/// the Dart SDK), rendered as `file.dart:line:col` for the oracle to extract.
String? _firstAppFrame(StackTrace? stack) {
  if (stack == null) return null;
  for (final String line in stack.toString().split('\n')) {
    if (line.contains('package:flutter/') || line.contains('(dart:')) {
      continue; // framework / SDK frame
    }
    final Match? m = _dartLoc.firstMatch(line);
    if (m != null) return m.group(0);
  }
  return null;
}
