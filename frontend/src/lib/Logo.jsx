/* The Gremlin mark — Nib reduced to a silhouette.
 *
 * Same head and ear paths as public/favicon.svg, so the tab icon and the
 * in-app mark are demonstrably the same object, and the same discipline: one
 * flat fill, no side shading, no pupil highlight, no mauve inner ear. Those
 * are character-illustration details and they turn to mud below about 48px,
 * which is every size this mark is ever drawn at.
 *
 * Two deliberate differences from the favicon. There is no coloured ground —
 * the sidebar supplies its own, and a tile would read as a badge stuck onto
 * the chrome. And the body is a lighter teal here: the favicon's #1F4640 is
 * chosen for contrast against amber, and would nearly vanish against dark
 * chrome, so this uses Nib's own head colour, which holds on both themes.
 */
export default function Logo({ size = 28, className = "", ...rest }) {
  return (
    <svg viewBox="0 0 512 512" width={size} height={size} role="img"
         aria-label="Gremlin" className={className} {...rest}>
      <g transform="translate(4 67.4) scale(2.1)">
        <g fill="#35695F">
          <path d="M64 84 q-34 -30 -44 -68 q34 8 56 36 q10 14 12 30 Z" />
          <path d="M176 84 q34 -30 44 -68 q-34 8 -56 36 q-10 14 -12 30 Z" />
          <path d="M56 96 q0 -58 64 -58 q64 0 64 58 q0 42 -22 56 q-17 11 -42 11
                   q-25 0 -42 -11 q-22 -14 -22 -56 Z" />
        </g>
        <ellipse cx="94" cy="104" rx="18" ry="18.5" fill="#F2B44A" />
        <ellipse cx="146" cy="104" rx="18" ry="18.5" fill="#F2B44A" />
      </g>
    </svg>
  );
}
