/* The Gremlin mark — the mascot reduced to a dot composition.
 *
 * A character cannot be a logo: at 20px in a sidebar Nib's face turns to mush.
 * So the mark keeps only what identifies the creature — two ears above a round
 * head mass, and a pair of amber eyes — built from circles and squares that
 * stay crisp at any size. Same geometry as public/favicon.svg, so the tab icon
 * and the in-app mark are demonstrably the same object.
 */
export default function Logo({ size = 28, className = "", ...rest }) {
  return (
    <svg viewBox="0 0 512 512" width={size} height={size} role="img"
         aria-label="Gremlin" className={className} {...rest}>
      <rect x="146" y="112" width="78" height="78" rx="8" fill="var(--mark-ear, #24504A)" />
      <rect x="288" y="112" width="78" height="78" rx="8" fill="var(--mark-ear, #24504A)" />
      <g fill="var(--mark-head, #35695F)">
        <circle cx="196" cy="236" r="44" /><circle cx="316" cy="236" r="44" />
        <circle cx="150" cy="308" r="44" /><circle cx="362" cy="308" r="44" />
        <circle cx="198" cy="378" r="44" /><circle cx="314" cy="378" r="44" />
        <circle cx="256" cy="424" r="44" />
      </g>
      <rect x="212" y="264" width="88" height="88" rx="10" fill="var(--mark-face, #2A554D)" />
      <circle cx="228" cy="296" r="21" fill="var(--mark-eye, #F5B23C)" />
      <circle cx="284" cy="296" r="21" fill="var(--mark-eye, #F5B23C)" />
    </svg>
  );
}
