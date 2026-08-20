import Mascot from "../lib/Mascot.jsx";

const STATES = [
  ["idle", "Idle — empty states, hero"],
  ["chaos", "Chaos run — exploring"],
  ["explorer", "Explorer — the policy"],
  ["crash", "Crash caught"],
  ["trace", "Trace reveal — detective"],
  ["error", "Error softener"],
  ["success", "Success cheer"],
];

export default function MascotSheet() {
  return (
    <div style={{ background: "#F5F1E8", minHeight: "100vh", padding: 44, color: "#14211E" }}>
      <h1 style={{ font: "800 30px Inter", margin: "0 0 4px" }}>Nib — mascot sheet</h1>
      <p style={{ color: "#6A7A74", margin: "0 0 34px" }}>
        Chaos ↔ detective. Six states mapped to product moments.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 18 }}>
        {STATES.map(([s, label]) => (
          <figure key={s} style={{ margin: 0, textAlign: "center" }}>
            <Mascot size={150} state={s} />
            <figcaption style={{ font: "600 11px ui-monospace", marginTop: 6, color: "#4A5A55" }}>{label}</figcaption>
          </figure>
        ))}
      </div>

      <div style={{ display: "flex", gap: 26, alignItems: "flex-end", marginTop: 48 }}>
        {[120, 80, 56, 40, 32, 24].map((s) => (
          <figure key={s} style={{ margin: 0, textAlign: "center" }}>
            <Mascot size={s} state="idle" />
            <figcaption style={{ font: "500 10px ui-monospace", marginTop: 4 }}>{s}px</figcaption>
          </figure>
        ))}
      </div>

      <div style={{ display: "flex", gap: 34, marginTop: 48, background: "#0E1512",
                    padding: 30, borderRadius: 18, alignItems: "flex-end" }}>
        <Mascot size={140} state="idle" />
        <Mascot size={140} state="chaos" />
        <Mascot size={140} state="trace" />
        <Mascot size={140} state="success" />
      </div>
    </div>
  );
}
