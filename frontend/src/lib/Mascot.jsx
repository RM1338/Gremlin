/* The Gremlin mascot — a mischievous little creature. Blinks and floats on idle. */
export default function Mascot({ size = 200, float = true }) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size} className={float ? "mascot-float" : ""} aria-label="Gremlin mascot" role="img">
      <defs>
        <linearGradient id="g-skin" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#6ff5c4" />
          <stop offset="0.55" stopColor="#35e6a3" />
          <stop offset="1" stopColor="#159066" />
        </linearGradient>
        <linearGradient id="g-ear" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2bbd85" /><stop offset="1" stopColor="#0e6b4b" />
        </linearGradient>
        <radialGradient id="g-glow" cx="50%" cy="42%" r="58%">
          <stop offset="0" stopColor="#35e6a3" stopOpacity="0.34" /><stop offset="1" stopColor="#35e6a3" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="g-cheek" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#0e6b4b" stopOpacity="0.55" /><stop offset="1" stopColor="#0e6b4b" stopOpacity="0" />
        </radialGradient>
      </defs>

      <circle cx="100" cy="102" r="90" fill="url(#g-glow)" />

      {/* spiky top tufts */}
      <path d="M84 40 l6 -22 8 20 Z" fill="url(#g-skin)" />
      <path d="M100 36 l4 -26 8 24 Z" fill="url(#g-skin)" />
      <path d="M116 40 l10 -18 4 22 Z" fill="url(#g-skin)" />

      {/* ears */}
      <path d="M44 78 L10 40 Q46 46 60 82 Z" fill="url(#g-ear)" />
      <path d="M156 78 L190 40 Q154 46 140 82 Z" fill="url(#g-ear)" />
      <path d="M46 74 L24 48 Q48 54 58 76 Z" fill="#08543a" />
      <path d="M154 74 L176 48 Q152 54 142 76 Z" fill="#08543a" />

      {/* head / body */}
      <path d="M50 98 Q50 50 100 50 Q150 50 150 98 L150 126 Q150 176 100 176 Q50 176 50 126 Z" fill="url(#g-skin)" />
      {/* jaw shading + belly */}
      <ellipse cx="100" cy="140" rx="40" ry="34" fill="#0f6a4b" opacity="0.4" />
      <ellipse cx="70" cy="120" rx="22" ry="18" fill="url(#g-cheek)" />
      <ellipse cx="130" cy="120" rx="22" ry="18" fill="url(#g-cheek)" />

      {/* brows — mischief */}
      <path d="M60 82 L92 90" stroke="#05241a" strokeWidth="6" strokeLinecap="round" />
      <path d="M140 82 L108 90" stroke="#05241a" strokeWidth="6" strokeLinecap="round" />

      {/* eyes */}
      <g className="mascot-eye">
        <ellipse cx="78" cy="104" rx="18" ry="19" fill="#05140e" />
        <ellipse cx="122" cy="104" rx="18" ry="19" fill="#05140e" />
        <circle cx="78" cy="105" r="9" fill="#35e6a3" />
        <circle cx="122" cy="105" r="9" fill="#35e6a3" />
        <circle cx="74" cy="100" r="3.4" fill="#eafff6" />
        <circle cx="118" cy="100" r="3.4" fill="#eafff6" />
      </g>

      {/* grin with fangs */}
      <path d="M74 140 Q100 162 126 140" fill="#05140e" stroke="#05140e" strokeWidth="4" strokeLinejoin="round" />
      <path d="M84 145 l6 12 6 -10 Z" fill="#eafff6" />
      <path d="M116 145 l-6 12 -6 -10 Z" fill="#eafff6" />
      <path d="M74 140 Q100 150 126 140" fill="none" stroke="#0e6b4b" strokeWidth="2.5" opacity="0.7" />

      {/* little clawed hands peeking */}
      <path d="M48 150 q-8 4 -6 14 q6 -3 8 -8" fill="url(#g-skin)" />
      <path d="M152 150 q8 4 6 14 q-6 -3 -8 -8" fill="url(#g-skin)" />
    </svg>
  );
}
