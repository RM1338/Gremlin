/* The mascot's state is derived from the agent's lifecycle, never set by hand.
 *
 * Nib's two modes mirror the two halves of the system: the exploration policy
 * actually running, and the oracle having found something. Tying the character
 * to real state is what separates a mascot from a sticker — it should never
 * look busy when nothing is running, or triumphant when a run found nothing.
 */
export function mascotState(st) {
  // A live run has two distinct halves and they deserve two distinct poses.
  // Everything running used to map to "chaos" — Nib swatting bugs — which is a
  // lie for the majority of a run, when nothing has been caught yet. He scouts
  // until the oracle trips, and only then starts swatting.
  if (st.running) return st.live?.bugs?.length ? "chaos" : "explorer";
  // Only a run that finished in THIS session earns a reaction. `st.trace` is
  // whatever `runs/latest` held on disk when the console booted, so keying off
  // it meant Nib looked like he had just caught something every time the page
  // was opened — the idle state was unreachable in practice. `summary` is set
  // by onDone and only by onDone, which is exactly the signal we want.
  if (st.summary) return st.summary.bugs > 0 ? "crash" : "success";
  return "idle";
}

/* One line of copy per state, in the interface's voice. Kept beside the state
 * mapping so the words and the pose can never drift apart. */
export function mascotLine(state, bugs = 0) {
  switch (state) {
    case "explorer": return "Exploring — mapping every screen it can reach.";
    case "chaos":   return `Swatting — ${bugs} caught so far, still exploring.`;
    case "crash":   return `Caught ${bugs} ${bugs === 1 ? "defect" : "defects"}. Every one has a trace.`;
    case "success": return "Run complete. Nothing broke this time.";
    case "trace":   return "Reading the trace that reproduces it.";
    case "box":     return "Boxed up. Nothing recorded yet.";
    case "measure": return "Same budget, three ways. Counting what each one reached.";
    default:        return "Asleep. Pick a target and start a run.";
  }
}
