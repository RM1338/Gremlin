import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Mascot from "../lib/Mascot.jsx";
import { signIn } from "../lib/auth.js";

export default function SignIn() {
  const nav = useNavigate();
  const [f, setF] = useState({ email: "", password: "" });
  const [err, setErr] = useState({});
  const upd = (k) => (e) => setF({ ...f, [k]: e.target.value });

  function submit(e) {
    e.preventDefault();
    const errs = {};
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email)) errs.email = "Enter a valid email";
    if (!f.password) errs.password = "Enter your password";
    setErr(errs);
    if (Object.keys(errs).length) return;
    signIn({ email: f.email.trim() });
    nav("/app");
  }

  return (
    <div className="auth">
      <aside className="auth-aside">
        <div className="grid" />
        <div className="z"><div className="brand"><Mascot size={34} float={false} /> Gremlin<span style={{ color: "var(--brand)" }}>.</span></div></div>
        <div className="z">
          <div style={{ width: 96, marginBottom: 20 }}><Mascot size={96} /></div>
          <blockquote>Welcome back. Your <em>gremlin missed you.</em></blockquote>
          <div className="who">Pick up where you left off — open the console and start a run.</div>
        </div>
        <div className="z note">Autonomous UI-testing agent</div>
      </aside>

      <main className="auth-main">
        <form className="auth-card" onSubmit={submit} noValidate>
          <h1>Sign in</h1>
          <p className="sub">Welcome back to Gremlin.</p>

          <div className="field">
            <label>Email</label>
            <input value={f.email} onChange={upd("email")} placeholder="you@company.com" type="email" autoComplete="email" />
            {err.email && <div className="err">{err.email}</div>}
          </div>
          <div className="field">
            <label>Password</label>
            <input value={f.password} onChange={upd("password")} placeholder="••••••••" type="password" autoComplete="current-password" />
            {err.password && <div className="err">{err.password}</div>}
          </div>

          <button className="btn btn-primary btn-block btn-lg" type="submit">Sign in</button>
          <div className="auth-alt">New here? <Link to="/signup">Create an account</Link></div>
          <div className="demo-note">Demo sign-in — any valid-looking email works; the session lives only in your browser.</div>
        </form>
      </main>
    </div>
  );
}
