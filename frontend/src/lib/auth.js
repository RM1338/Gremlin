/* Client-side session for the demo. This is intentionally NOT real auth — there
   is no server, no password storage, no user database. It gates the console and
   personalizes the UI so the app feels like a complete product.

   To make it real later, swap these four functions for Supabase or Firebase Auth
   (both have free tiers) — the components call only signIn/signUp/signOut/getUser. */

const KEY = "gremlin-session";

export function getUser() {
  try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; }
}

export function isAuthed() { return !!getUser(); }

export function signUp({ name, email }) {
  const user = { name: name || email.split("@")[0], email, at: Date.now() };
  localStorage.setItem(KEY, JSON.stringify(user));
  return user;
}

export function signIn({ email, name }) {
  const user = { name: name || email.split("@")[0], email, at: Date.now() };
  localStorage.setItem(KEY, JSON.stringify(user));
  return user;
}

export function signOut() { localStorage.removeItem(KEY); }

export function initials(user) {
  if (!user) return "?";
  const base = user.name || user.email || "?";
  const parts = base.replace(/@.*/, "").split(/[.\s_-]+/).filter(Boolean);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || base[0].toUpperCase();
}
