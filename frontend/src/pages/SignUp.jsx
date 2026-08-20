import { useState } from "react";
import Logo from "../lib/Logo.jsx";
import { Link, useNavigate } from "react-router-dom";
import Mascot from "../lib/Mascot.jsx";
import { signUp } from "../lib/auth.js";

export default function SignUp() {
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [err, setErr] = useState({});
  const upd = (k) => (e) => setF({ ...f, [k]: e.target.value });

  function submit(e) {
    e.preventDefault();
    const errs = {};
    if (!f.name.trim()) errs.name = "Tell us your name";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.email)) errs.email = "Enter a valid email";
    if (f.password.length < 6) errs.password = "At least 6 characters";
    setErr(errs);
    if (Object.keys(errs).length) return;
    signUp({ name: f.name.trim(), email: f.email.trim() });
    nav("/app");
  }

  return (
    <div className="auth">
      <aside className="auth-aside">
        <div className="grid" />
        <div className="z"><div className="brand"><Logo size={30} /> Gremlin<span style={{ color: "var(--brand)" }}>.</span></div></div>
        <div className="z">
          <div style={{ width: 96, marginBottom: 20 }}><Mascot size={96} state="success" /></div>
          <blockquote>Let the gremlin loose. It finds the <em>crash before your users do.</em></blockquote>
          <div className="who">10× the screen coverage of a random monkey — with a reproducible trace for every bug.</div>
        </div>
        <div className="z note">Autonomous UI-testing agent</div>
      </aside>

      <main className="auth-main">
        <form className="auth-card" onSubmit={submit} noValidate>
          <h1>Create your account</h1>
          <p className="sub">Start exploring your app in minutes.</p>

          <div className="field">
            <label>Name</label>
            <input value={f.name} onChange={upd("name")} placeholder="Ada Lovelace" autoComplete="name" />
            {err.name && <div className="err">{err.name}</div>}
          </div>
          <div className="field">
            <label>Email</label>
            <input value={f.email} onChange={upd("email")} placeholder="you@company.com" type="email" autoComplete="email" />
            {err.email && <div className="err">{err.email}</div>}
          </div>
          <div className="field">
            <label>Password</label>
            <input value={f.password} onChange={upd("password")} placeholder="••••••••" type="password" autoComplete="new-password" />
            {err.password && <div className="err">{err.password}</div>}
          </div>

          <button className="btn btn-primary btn-block btn-lg" type="submit">Create account</button>
          <div className="auth-alt">Already have an account? <Link to="/signin">Sign in</Link></div>
          <div className="demo-note">Demo account — credentials are stored only in your browser, no server. Swap in Supabase/Firebase Auth for real accounts.</div>
        </form>
      </main>
    </div>
  );
}
