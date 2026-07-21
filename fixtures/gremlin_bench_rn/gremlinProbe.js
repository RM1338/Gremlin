/**
 * Gremlin probe — opt-in error forwarding for React Native apps under test.
 *
 * Gremlin detects bugs by matching `adb logcat`, which only works if the failure
 * actually reaches the log. React Native is inconsistent here: LogBox intercepts
 * errors in development, a production bundle strips React's warnings entirely,
 * and what console.* forwards to the native log has changed across versions.
 *
 * So rather than depend on the framework's default logging, an app under test
 * can import this file once and forward its own failures under a marker Gremlin
 * matches exactly (`GREMLIN_BUG`). This is the same opt-in contract the Flutter
 * side uses via gremlin_probe.dart.
 *
 * Import it as the very first line of index.js, before anything else can throw:
 *
 *     import './gremlinProbe';
 *
 * It is deliberately dependency-free and side-effect-only.
 */

const MARKER = 'GREMLIN_BUG';

/* Keep the originals — the probe must observe, never swallow. An error that
   stops reaching the real console would be a bug the developer can't see. */
const originalError = console.error;
const originalWarn = console.warn;

function emit(kind, parts) {
  const body = parts
    .map((p) => {
      if (p instanceof Error) {
        return `${p.message}\n${p.stack || ''}`;
      }
      if (typeof p === 'object' && p !== null) {
        try {
          return JSON.stringify(p);
        } catch {
          return String(p);
        }
      }
      return String(p);
    })
    .join(' ');
  // One marker per line: the oracle scans logcat line by line, and a stack that
  // arrives as a single blob would hide its own source location.
  for (const line of `${MARKER} [${kind}] ${body}`.split('\n')) {
    if (line.trim()) {
      originalError.call(console, line);
    }
  }
}

/* Uncaught JS errors. ErrorUtils is React Native's global error hook; it fires
   for anything that escapes a component, including render-time throws. */
if (typeof global !== 'undefined' && global.ErrorUtils) {
  const previous = global.ErrorUtils.getGlobalHandler
    ? global.ErrorUtils.getGlobalHandler()
    : null;
  global.ErrorUtils.setGlobalHandler((error, isFatal) => {
    emit(isFatal ? 'fatal' : 'error', [error]);
    // Hand back to whatever was installed before, so the red screen and the
    // app's own crash reporting still behave normally.
    if (previous) {
      previous(error, isFatal);
    }
  });
}

/* React's correctness warnings (a missing `key`, a bad hook call, a setState on
   an unmounted component) arrive as console.error/warn, not as thrown errors.
   They are real defects — a missing key silently corrupts list state on reorder
   — so they are forwarded too. */
console.error = function (...args) {
  emit('console.error', args);
  originalError.apply(console, args);
};

console.warn = function (...args) {
  emit('console.warn', args);
  originalWarn.apply(console, args);
};

/* Promise rejections nobody handled. RN's default is version-dependent and
   often silent, which is exactly the class of defect worth catching. */
if (typeof global !== 'undefined' && typeof global.HermesInternal !== 'undefined') {
  const tracking = global.HermesInternal?.enablePromiseRejectionTracker;
  if (typeof tracking === 'function') {
    tracking({
      allRejections: true,
      onUnhandled: (id, rejection) => {
        emit('unhandled-rejection', [
          'Possible Unhandled Promise Rejection',
          rejection,
        ]);
      },
    });
  }
}
