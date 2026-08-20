/* The mascot's state is derived from the agent's lifecycle, never set by hand.
 *
 * Nib's two modes mirror the two halves of the system: chaos is the exploration
 * policy actually running, detective is the oracle having found something and
 * the trace being available to read. Tying the character to real state is what
 * separates a mascot from a sticker — it should never look busy when nothing is
 * running, or triumphant when a run found nothing.
 */
export function mascotState(st) {
  if (st.running) return "chaos";
  const bugs = (st.trace?.bugs?.length ?? 0) || (st.live?.bugs?.length ?? 0);
  if (st.done || st.trace) return bugs > 0 ? "crash" : "success";
  return "idle";
}

/* One line of copy per state, in the interface's voice. Kept beside the state
 * mapping so the words and the pose can never drift apart. */
export function mascotLine(state, bugs = 0) {
  switch (state) {
    case "chaos":   return "Exploring — tapping everything it hasn't tried yet.";
    case "crash":   return `Caught ${bugs} ${bugs === 1 ? "defect" : "defects"}. Every one has a trace.`;
    case "success": return "Run complete. Nothing broke this time.";
    case "trace":   return "Reading the trace that reproduces it.";
    default:        return "Idle. Pick a target and start a run.";
  }
}
