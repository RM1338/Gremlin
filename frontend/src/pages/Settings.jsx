import { useEffect, useState } from "react";
import { Bolt, Check, Wrench, Spark2, Screens, LogOut } from "../lib/icons.jsx";
import { getUser, signIn, initials } from "../lib/auth.js";

/* Settings — the .env file, with the machine's opinion attached.
 *
 * Everything here was already configurable; it just needed a text editor and a
 * restart. The server owns validation, because only the server can answer the
 * question that actually matters: is the agent you just picked installed?
 */

const GROUP_ICON = {
  remediation: <Wrench />, vision: <Spark2 />, app: <Screens />, run: <Bolt />,
};

export default function Settings() {
  const [cfg, setCfg] = useState(null);
  const [draft, setDraft] = useState({});
  const [secretDraft, setSecretDraft] = useState({});   // typed keys, never read back
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);
  const user = getUser();
  const [profile, setProfile] = useState({ name: user?.name || "", email: user?.email || "" });

  useEffect(() => {
    fetch("/api/settings").then((r) => r.json()).then((d) => { setCfg(d); setDraft(d.values); })
      .catch(() => setMsg({ bad: true, text: "Could not reach the runner." }));
  }, []);

  if (!cfg) return <div className="page-body"><p className="note">Loading settings…</p></div>;

  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }));
  const shown = (f) => !f.depends_on || draft[f.depends_on[0]] === f.depends_on[1];
  const dirty = Object.keys(draft).some((k) => draft[k] !== cfg.values[k])
    || Object.values(secretDraft).some(Boolean);

  async function save() {
    setSaving(true); setMsg(null);
    try {
      const body = { ...draft, ...secretDraft };
      const r = await fetch("/api/settings", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "could not save");
      setCfg(d); setDraft(d.values); setSecretDraft({});
      setMsg({ text: "Saved to .env and applied." });
    } catch (e) {
      setMsg({ bad: true, text: e.message });
    } finally { setSaving(false); }
  }

  function saveProfile() {
    if (!profile.email.trim()) return;
    signIn({ name: profile.name.trim(), email: profile.email.trim() });
    setMsg({ text: "Profile updated." });
  }

  return (
    <>
      <div className="page-head tight">
        <h1 className="page-title">Settings</h1>
        <p className="page-desc">
          Read and written straight to <code>{cfg.env_path}</code>. Nothing here leaves this
          machine, and a hand-edited file keeps its comments.
        </p>
      </div>

      <div className="page-body scrolls">
        <div className="set-grid">
          {cfg.groups.map((g) => (
            <section className="card set-card" key={g.key}>
              <div className="set-head">{GROUP_ICON[g.key]}<h3>{g.label}</h3></div>
              <p className="note set-lede">{g.help}</p>

              {g.key === "remediation" && <AgentAvailability caps={cfg.capabilities} />}
              {g.key === "vision" && draft.LLM_PROVIDER === "local" && cfg.capabilities.local && (
                <div className={"set-probe " + (cfg.capabilities.local.ok ? "ok" : "bad")}>
                  {cfg.capabilities.local.ok ? <Check /> : "!"} {cfg.capabilities.local.detail}
                </div>
              )}

              {cfg.fields.filter((f) => f.group === g.key && shown(f)).map((f) => (
                <FieldRow key={f.key} f={f} value={draft[f.key] ?? ""} onChange={set}
                          secretSet={cfg.secrets[f.key]}
                          secretDraft={secretDraft[f.key] ?? ""}
                          onSecret={(v) => setSecretDraft((s) => ({ ...s, [f.key]: v }))} />
              ))}
            </section>
          ))}

          <section className="card set-card">
            <div className="set-head"><span className="avatar">{initials(user)}</span><h3>Profile</h3></div>
            <p className="note set-lede">
              Local to this browser — it names you in the console and on run notifications.
              There is no account and no server-side user.
            </p>
            <label className="set-field">
              <span className="set-label">Display name</span>
              <input className="set-input" value={profile.name}
                     onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
            </label>
            <label className="set-field">
              <span className="set-label">Email</span>
              <input className="set-input" value={profile.email}
                     onChange={(e) => setProfile({ ...profile, email: e.target.value })} />
            </label>
            <button className="btn" style={{ marginTop: 12 }} onClick={saveProfile}>Update profile</button>
          </section>
        </div>
      </div>

      <div className="set-bar">
        {msg && <span className={"set-msg" + (msg.bad ? " bad" : "")}>{msg.text}</span>}
        <span className="set-hint">
          {cfg.fields.some((f) => f.effect === "restart" && draft[f.key] !== cfg.values[f.key])
            ? "One of these needs a console restart to take effect."
            : "Applies to the next run — no restart needed."}
        </span>
        <button className="btn btn-primary" onClick={save} disabled={!dirty || saving}>
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </>
  );
}

/* Which agents are actually installed. A settings page that lets you pick an
   agent you do not have is a settings page that fails inside a run. */
function AgentAvailability({ caps }) {
  const rows = Object.entries(caps.agents || {});
  if (!rows.length) return null;
  return (
    <div className="set-caps">
      {rows.map(([name, ok]) => (
        <span key={name} className={"set-cap " + (ok ? "ok" : "no")}>
          {ok ? <Check /> : <span className="set-x">✕</span>} {name}
        </span>
      ))}
    </div>
  );
}

function FieldRow({ f, value, onChange, secretSet, secretDraft, onSecret }) {
  return (
    <label className="set-field">
      <span className="set-label">
        {f.label}
        {f.effect === "restart" && <span className="set-tag">restart</span>}
      </span>
      {f.kind === "choice" ? (
        <select className="set-input" value={value} onChange={(e) => onChange(f.key, e.target.value)}>
          {f.choices.map((c) => <option key={c} value={c}>{c || "auto-detect"}</option>)}
        </select>
      ) : f.kind === "secret" ? (
        <input className="set-input" type="password" value={secretDraft}
               placeholder={secretSet ? "•••••••• (set — type to replace)" : "not set"}
               onChange={(e) => onSecret(e.target.value)} />
      ) : (
        <input className="set-input" value={value} inputMode={f.kind === "int" ? "numeric" : undefined}
               onChange={(e) => onChange(f.key, e.target.value)} />
      )}
      <span className="set-help">{f.help}</span>
    </label>
  );
}
