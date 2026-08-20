/* Inline SVG icons. Stroke icons inherit currentColor. */
const s = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" };

export const Stop = (p) => (<svg viewBox="0 0 24 24" fill="currentColor" {...p}><rect x="6" y="6" width="12" height="12" rx="2.5" /></svg>);
export const Bolt = (p) => (<svg viewBox="0 0 24 24" fill="currentColor" {...p}><path d="M13 2L4 14h6l-1 8 9-12h-6z" /></svg>);
export const Home = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M3 12l9-9 9 9M5 10v10h14V10" /></svg>);
export const Live = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><circle cx="12" cy="12" r="3" /><path d="M5 12a7 7 0 0114 0M2 12a10 10 0 0120 0" /></svg>);
export const List = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M8 6h13M8 12h13M8 18h13" /><circle cx="3" cy="6" r="1.2" /><circle cx="3" cy="12" r="1.2" /><circle cx="3" cy="18" r="1.2" /></svg>);
export const Bug = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><rect x="7" y="7" width="10" height="11" rx="5" /><path d="M7 11H3M21 11h-4M6 15H3M21 15h-3M12 7V4M12 18v3" /></svg>);
export const Bars = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg>);
export const Screens = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><rect x="3" y="4" width="18" height="14" rx="2" /><path d="M8 20h8" /></svg>);
export const Steps = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M4 18h4v-6H4zM10 18h4V6h-4zM16 18h4v-9h-4z" /></svg>);
export const Check = (p) => (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M20 6L9 17l-5-5" /></svg>);
export const Chevron = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M9 6l6 6-6 6" /></svg>);
export const LogOut = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" /></svg>);
export const Eye = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>);
export const Brain = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M9 3a3 3 0 00-3 3 3 3 0 00-2 5 3 3 0 001 5 3 3 0 005 2V3zM15 3a3 3 0 013 3 3 3 0 012 5 3 3 0 01-1 5 3 3 0 01-5 2V3z" /></svg>);
export const Clock = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>);
export const Route = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><circle cx="6" cy="19" r="2" /><circle cx="18" cy="5" r="2" /><path d="M6 17V9a4 4 0 014-4h4M18 7v8a4 4 0 01-4 4h-4" /></svg>);
export const Book = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM19 3v18" /></svg>);
export const Copy = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15V5a2 2 0 012-2h8" /></svg>);
export const Doc = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9z" /><path d="M14 3v6h6M8 13h8M8 17h6" /></svg>);
export const Wrench = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M15 4a5 5 0 00-6.5 6.5L3 16v5h5l5.5-5.5A5 5 0 0015 4z" /><circle cx="16.5" cy="7.5" r=".6" fill="currentColor" /></svg>);
export const Spark2 = (p) => (<svg viewBox="0 0 24 24" fill="currentColor" {...p}><path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z" /></svg>);
export const X = (p) => (<svg viewBox="0 0 24 24" {...s} {...p}><path d="M6 6l12 12M18 6L6 18" /></svg>);
