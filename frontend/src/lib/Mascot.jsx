/* Nib — the Gremlin mascot.
 *
 * Two modes, because the product has two halves and they are genuinely
 * different jobs:
 *
 *   chaos     — the exploration policy. Playful, reckless, jabbing at controls
 *               to see what gives. Wide eyes, toothy grin, claws out.
 *   detective — the oracle and the reporter. Visor down, focused, holding the
 *               repro trace it just proved.
 *
 * That split is not decoration: it is the oracle/policy boundary the whole
 * architecture rests on, drawn as a character. The model decides where to go;
 * the log decides what is broken.
 *
 * Construction follows mascot practice rather than icon practice — the head is
 * nearly half the total height, the body is small and CHUNKY (never spindly),
 * and the limbs are thick enough to survive being scaled down. Three colours
 * carry it: a deep teal-green body, one neon accent for the active state, and
 * amber eyes. That restraint is what keeps it legible at 32px.
 */

// Each state gets BOTH arms posed. Reusing one pose for several states was what
// made crash, chaos and success read as the same drawing.
const STATES = {
  // idle is the cold-start state, so it is the one a first-time visitor meets.
  // Nothing is running, so Nib is not "standing by" — he is asleep in a chair.
  idle:    { face: "asleep",  far: "sleep", near: "sleep", glow: false, chair: true, sit: true },
  chaos:   { face: "swat",    far: "swing", near: "swat",  glow: false, bugs: true },
  crash:   { face: "gotcha",  far: "hip",   near: "point", glow: false },
  trace:   { face: "focused", far: "hold",  near: "card",  glow: false, visor: true },
  error:   { face: "sorry",   far: "shrug", near: "shrug", glow: false },
  success: { face: "cheer",   far: "hip",   near: "fist",  glow: true, sparkle: true },
  // the policy half, drawn as what it actually is: someone scouting unmapped
  // ground. Hand up against the light, map in the other, hat on.
  // Both hands are on the binoculars, so this pose cannot also hold the map —
  // the pack stays because it is worn rather than held.
  explorer: { face: "scout",  far: "glassUp", near: "glassUp", glow: false, hat: true, pack: true, glassUp: true },
  // nothing has happened yet, so Nib is not idle-with-a-caption: he is stowed,
  // peering over the rim of the box he ships in. Paws on the edge, mouth open,
  // waiting to be let out.
  box:     { face: "curious", far: "rim",   near: "rim",   glow: false, box: true },
  // The benchmark. Nib is not the one being tested — he is the one running the
  // trial: same budget, same cold start, three arms, and a clipboard that says
  // what each one reached. A mascot straining under a weight said the page was
  // about his effort; it is about a controlled comparison.
  measure: { face: "focused", far: "fist",  near: "card",  glow: false,
             clipboard: true, stopwatch: true, einstein: true },
};

export default function Mascot({
  size = 200,
  state = "idle",
  bugs = true,
  className = "",
  ...rest
}) {
  const s = STATES[state] || STATES.idle;
  return (
    <svg
      viewBox="0 0 240 286"
      width={size}
      height={size * 1.19}
      className={`nib nib-${state} ${className}`}
      role="img"
      aria-label={`Gremlin mascot, ${state}`}
      {...rest}
    >
      <style>{`
        /* fill-box ONLY on the elements whose keyframes use percentage origins.
           As a bare descendant selector it also re-based every plain transform
           attribute in the drawing, which is what detached the mitts from the
           wrists and threw the tip off the tail. (No backticks in here: this
           block is a template literal.) */
        .nib-body, .nib-chest, .nib-head, .nib-lids,
        .nib-earL, .nib-earR, .nib-tail, .nib-jab,
        .nib-swat, .nib-wing,
        .nib-spark path { transform-box: fill-box; }

        /* Natural idle motion is never one axis. The body travels a shallow
           figure-of-eight — up, across, down, back — while squashing on the low
           beat and stretching at the top. The head runs the SAME cycle a beat
           late, which is follow-through: the bit that stops it looking rigid. */
        .nib-body  { animation: nib-idle 4.2s ease-in-out infinite; transform-origin:50% 100%; }
        .nib-chest { animation: nib-squash 4.2s ease-in-out infinite; transform-origin:50% 100%; }
        .nib-head  { animation: nib-follow 4.2s ease-in-out infinite; animation-delay:-.28s; transform-origin:50% 100%; }
        .nib-lids  { animation: nib-blink 5.6s infinite; transform-origin:50% 50%; }
        .nib-earL  { animation: nib-earL 4.2s ease-in-out infinite; animation-delay:-.42s; transform-origin:90% 95%; }
        .nib-earR  { animation: nib-earR 4.2s ease-in-out infinite; animation-delay:-.42s; transform-origin:10% 95%; }
        .nib-tail  { animation: nib-tail 3.2s ease-in-out infinite; transform-origin:0% 100%; }

        .nib-jab   { animation: nib-jab 0.9s ease-in-out infinite; transform-origin:50% 0%; }
        .nib-scan  { animation: nib-scan 2.4s ease-in-out infinite; }

        /* chaos is Nib fighting off actual bugs, so the energy belongs to the
           bugs and the swatting arm — not to the body. Winding the whole figure
           up made it look deranged rather than busy. */
        .nib-chaos .nib-body,
        .nib-chaos .nib-chest,
        .nib-chaos .nib-head { animation-duration: 2.1s; }
        .nib-chaos .nib-tail { animation-duration: 0.9s; }
        .nib-chaos .nib-earL,
        .nib-chaos .nib-earR { animation-duration: 1.1s; }
        .nib-swat { animation: nib-swat 0.62s ease-in-out infinite; transform-origin:50% 0%; }

        /* Each bug flies its own wandering loop; the durations are deliberately
           not multiples of each other so the swarm never syncs up. */
        .nib-bug  { animation: nib-fly 3s ease-in-out infinite; }
        .nib-wing { animation: nib-buzz 0.11s linear infinite; transform-origin:100% 60%; }

        @keyframes nib-idle {
          0%   { transform: translate(0,0)      rotate(0deg) }
          25%  { transform: translate(2.5px,0)  rotate(-1.6deg) }
          50%  { transform: translate(0,0)      rotate(0deg) }
          75%  { transform: translate(-2.5px,0) rotate(1.6deg) }
          100% { transform: translate(0,0)      rotate(0deg) }
        }
        /* Asleep in a chair: no sway at all, just breathing, and the head
           nods over. The .nib-idle selector here is the STATE class, not the
           keyframe of the same name — the two-class selector wins.
           (No backticks in this block: it is a template literal.) */
        .nib-idle .nib-body { animation: nib-breathe 5.4s ease-in-out infinite; }
        .nib-idle .nib-head { animation: nib-doze 5.4s ease-in-out infinite; }
        .nib-idle .nib-earL, .nib-idle .nib-earR { animation-duration: 6.5s; }
        .nib-idle .nib-lids { animation: none; }
        @keyframes nib-breathe {
          0%,100% { transform: scale(1, 1) }
          50%     { transform: scale(1.012, 0.988) }
        }
        @keyframes nib-doze {
          0%,100% { transform: rotate(-7deg) translateY(0) }
          50%     { transform: rotate(-9deg) translateY(2px) }
        }
        @keyframes nib-zzz {
          0%   { transform: translate(0,0) scale(.75); opacity: 0 }
          20%  { opacity: 1 }
          70%  { opacity: .85 }
          100% { transform: translate(9px,-26px) scale(1.1); opacity: 0 }
        }
        .nib-zzz text { animation: nib-zzz 3.4s ease-out infinite; }
        @keyframes nib-squash {
          0%,100% { transform: scale(1.035, 0.965) }
          50%     { transform: scale(0.975, 1.03) }
        }
        @keyframes nib-follow {
          0%   { transform: rotate(0deg) translateY(0) }
          25%  { transform: rotate(-3deg) translateY(-1px) }
          50%  { transform: rotate(0deg) translateY(-2px) }
          75%  { transform: rotate(3deg) translateY(-1px) }
          100% { transform: rotate(0deg) translateY(0) }
        }
        @keyframes nib-swat {
          0%,100% { transform: rotate(0deg) }
          35%     { transform: rotate(24deg) translate(-2px,6px) }
          60%     { transform: rotate(-6deg) }
        }
        @keyframes nib-fly {
          0%   { transform: translate(0,0)         rotate(0deg) }
          18%  { transform: translate(15px,-13px)  rotate(14deg) }
          36%  { transform: translate(-9px,-25px)  rotate(-16deg) }
          55%  { transform: translate(-24px,-8px)  rotate(9deg) }
          74%  { transform: translate(-6px,12px)   rotate(-11deg) }
          88%  { transform: translate(11px,5px)    rotate(6deg) }
          100% { transform: translate(0,0)         rotate(0deg) }
        }
        @keyframes nib-buzz { 0%,100%{transform:scaleY(1)} 50%{transform:scaleY(0.25)} }
        @keyframes nib-tail { 0%,100%{transform:rotate(-7deg)} 50%{transform:rotate(11deg)} }
        @keyframes nib-earL { 0%,100%{transform:rotate(0)} 30%{transform:rotate(-6deg)} 70%{transform:rotate(3deg)} }
        @keyframes nib-earR { 0%,100%{transform:rotate(0)} 30%{transform:rotate(6deg)} 70%{transform:rotate(-3deg)} }
        @keyframes nib-blink   { 0%,93%,100%{transform:scaleY(1)} 96%{transform:scaleY(0.08)} }
        @keyframes nib-jab     { 0%,100%{transform:translate(0,0) rotate(0)} 50%{transform:translate(4px,8px) rotate(9deg)} }
        @keyframes nib-scan    { 0%,100%{opacity:.55} 50%{opacity:1} }
        @keyframes nib-pop     { 0%,100%{transform:scale(.5);opacity:0} 45%{transform:scale(1);opacity:.95} }
        .nib-spark path { animation: nib-pop 1.5s ease-in-out infinite; transform-origin:50% 50%; }

        /* The stopwatch runs in steps rather than a smooth sweep — a mechanical
           tick reads as timing something, a glide reads as decoration. */
        .nib-tick { animation: nib-tick 3s steps(12) infinite; transform-origin: 44px 132px; }
        @keyframes nib-tick { to { transform: rotate(360deg) } }

        @media (prefers-reduced-motion: reduce) { .nib, .nib * { animation: none !important; } }
      `}</style>

      {/* Contact shadow. It used to sit at cy=272 while the lowest claw was at
          y=260 — a 12px gap under every pose, which is most of why the figure
          read as hovering. It now overlaps the thing casting it. */}
      <ellipse cx="120" cy={s.box ? 266 : s.sit ? 274 : 258}
               rx={s.box ? 94 : s.sit ? 88 : 58} ry="9"
               fill="#12211E" opacity="0.16" />

      {s.chair && <ChairBack />}
      {s.box && <BoxBack />}

      <g className="nib-body">
        {/* tail — rooted in the lower back and drawn behind everything, which is
            what the old floating wing shape never was. Spade tip: gremlin, not bat. */}
        <g className="nib-tail" style={s.box ? { display: "none" } : undefined}>
          <path d="M148 214 q44 10 52 -30" fill="none" stroke="#24504A" strokeWidth="14" strokeLinecap="round" />
          {/* the spade's base straddles the end of the curve — a tip that only
              meets it at one point reads as a rhombus floating beside the hip */}
          <path d="M200 152 q16 16 15 29 q-9 -6 -15 5 q-6 -11 -15 -5 q-1 -13 15 -29 Z" fill="#24504A" />
        </g>

        {!s.sit && !s.box && <Legs />}

        {s.pack && <Pack />}

        {/* torso: small and CHUNKY — never spindly */}
        <path d="M84 158 q36 -13 72 0 q9 33 2 58 q-38 15 -76 0 q-7 -25 2 -58 Z"
              fill="#2F6055" />
        <path d="M84 158 q-9 33 -2 58 q11 4 18 5 q-15 -31 -6 -63 Z"
              fill="#20443E" opacity="0.6" />
        <ellipse cx="120" cy="194" rx="24" ry="23" fill="#4E8E7B" />
        {s.pack && <PackStrap />}

        {/* the map goes under the far arm, so the hand reads as holding it */}
        {s.map && <MapScroll />}
        {!s.glassUp && !s.box && <Arm pose={s.far} side="far" />}
        {/* after the far arm, so the closed fist reads as gripping it */}
        {s.stopwatch && <Stopwatch />}

        {/* the trace card goes over the far arm so the near hand overlaps it */}
        {s.near === "card" && !s.clipboard && <TraceCard />}
        {s.clipboard && <Clipboard />}

        {!s.glassUp && !s.box && <Arm pose={s.near} side="near" glow={s.glow} animate={s.near} />}
        {s.sparkle && <Sparkles />}

        {/* head — nearly half the figure */}
        <g className="nib-head">
          {/* Behind the head path on purpose: only what escapes the skull's
              silhouette shows, which is what makes it a halo of hair rather
              than a wig sitting on top of him. The ears then land in front. */}
          {s.einstein && <Frizz />}
          <EarL /><EarR />
          <path d="M56 96 q0 -58 64 -58 q64 0 64 58 q0 42 -22 56 q-17 11 -42 11
                   q-25 0 -42 -11 q-22 -14 -22 -56 Z" fill="#35695F" />
          {/* cool shadow down one side, warm rim on the other */}
          <path d="M56 96 q0 42 22 56 q8 5 18 8 q-30 -30 -24 -80 q-16 6 -16 16 Z"
                fill="#20443E" opacity="0.55" />
          <Face face={s.face} visor={s.visor} hidden={s.glassUp} />
          {s.hat && <Hat />}
          {s.einstein && <><Specs /><Tache /></>}
        </g>
        {/* Binoculars go up at the face, and the arms that hold them are drawn
            last so both paws close over the barrels. The lenses show Nib's eyes
            through the glass, which is how the pose keeps the character the
            older lowered-binoculars version was protecting. */}
        {s.glassUp && (
          <>
            <Binoculars />
            <Arm pose="glassUp" side="far" />
            <Arm pose="glassUp" side="near" />
          </>
        )}

        {s.chair && <ChairFront />}
        {/* after the seat, so the shins hang over its front edge */}
        {s.sit && <Legs sit />}
        {s.chair && <Zzz />}

        {s.bugs && bugs && <Swarm />}
      </g>

      {/* The near wall hides everything below the rim; the paws go on top of it
          so they read as gripping the edge rather than painted on the card. */}
      {s.box && (
        <>
          <BoxFront />
          <Arm pose="rim" side="far" />
          <Arm pose="rim" side="near" />
        </>
      )}
    </svg>
  );
}

/* A shipping box, in two halves so Nib can sit between them: the far wall and
   its folded-open flaps behind him, the near wall in front. Cardboard is three
   values — lit face, fold shadow, interior — and nothing else, which is what
   keeps it from competing with the character. */
function BoxBack() {
  return (
    <g>
      {/* interior of the far wall, in shadow: this is what makes the head read
          as INSIDE the box rather than standing behind it */}
      <path d="M44 198 L196 198 L188 166 L52 166 Z" fill="#7A5E40" />
      {/* The two back flaps, folded open. They hinge on the box's top corners
          and are drawn long enough to pass BEHIND the near wall — a flap that
          starts where the wall starts reads as a plank propped against it. */}
      <path d="M40 190 L10 148 L44 138 L74 180 Z" fill="#B8905F" />
      <path d="M200 190 L230 148 L196 138 L166 180 Z" fill="#B8905F" />
      <path d="M40 190 L10 148 L44 138 Z" fill="#9A7648" opacity="0.4" />
      <path d="M200 190 L230 148 L196 138 Z" fill="#9A7648" opacity="0.4" />
    </g>
  );
}

function BoxFront() {
  return (
    <g>
      {/* the cut edge of the card, catching the light along the near rim */}
      <path d="M36 192 L204 192 L196 180 L44 180 Z" fill="#DFBB8B" />
      <path d="M36 192 L204 192 L198 266 L42 266 Z" fill="#C79E6F" />
      {/* the corner fold: one plane turned away from the light */}
      <path d="M36 192 L70 192 L72 266 L42 266 Z" fill="#A9814F" opacity="0.35" />
      {/* tape seam down the middle */}
      <path d="M112 192 L130 192 L128 266 L114 266 Z" fill="#E0C49B" opacity="0.5" />
    </g>
  );
}

/* Legs. The only thing sitting changes is where they start and how long they
   are: the shins drop from under the seat rail and the feet dangle, which is
   what sitting on a chair actually looks like from the front. */
function Legs({ sit }) {
  // Standing: one straight shin from hip to claw.
  //
  // Sitting is not the same shape shortened, which is why the earlier attempts
  // read as a post driven through the bench. In a true front view the thigh is
  // hidden — it lies on the seat, behind the seat's front face — so drawing one
  // is not the fix either. What sells it is the JOINT: a knee resting on top of
  // the seat's front edge, with the shin hanging off it. Give the knee a little
  // more width than the shin and the leg reads as bent even though the thigh
  // itself is never drawn.
  if (sit) {
    return (
      <>
        {[94, 146].map((cx) => {
          const fx = cx - 13.5;
          return (
            <g key={cx}>
              {/* knee straddles the seat's top edge (y=212); any higher and it
                  overlaps the belly and reads as a blob rather than a joint */}
              <circle cx={cx} cy="222" r="17" fill="#2A554D" />
              <rect x={cx - 12.5} y="218" width="25" height="34" rx="12.5" fill="#2A554D" />
              <path d={`M${fx - 5} 248 q18 -8 37 0 q0 9 -8 10 l-21 0 q-8 -1 -8 -10 Z`} fill="#20443E" />
              {[6, 15, 24].map((o) => (
                <path key={o} d={`M${fx + o - 3} 258 l3 6 3 -6 Z`} fill="#173430" />
              ))}
            </g>
          );
        })}
      </>
    );
  }
  return (
    <>
      {[86, 128].map((x) => (
        <g key={x}>
          <rect x={x} y="206" width="27" height="40" rx="13" fill="#2A554D" />
          <path d={`M${x - 5} 244 q18 -8 37 0 q0 9 -8 10 l-21 0 q-8 -1 -8 -10 Z`} fill="#20443E" />
          {[6, 15, 24].map((o) => (
            <path key={o} d={`M${x + o - 3} 254 l3 6 3 -6 Z`} fill="#173430" />
          ))}
        </g>
      ))}
    </>
  );
}

/* The chair, in two halves. The back and rear legs go behind Nib; the seat rail
   and front legs go in front of him. Drawing all of it behind would leave him
   sitting on top of a chair rather than in it. */
function ChairBack() {
  // The posts have to sit outside x 56..184 — that is the head's own span, and
  // anything inside it is simply painted over, which is what made the first
  // version look like a stool with two stubs.
  return (
    <g>
      <rect x="36" y="116" width="15" height="126" rx="6" fill="#6E5B44" />
      <rect x="189" y="116" width="15" height="126" rx="6" fill="#6E5B44" />
      <rect x="36" y="120" width="168" height="17" rx="8" fill="#8E7757" />
      <rect x="36" y="152" width="168" height="17" rx="8" fill="#8E7757" />
      <rect x="36" y="184" width="168" height="17" rx="8" fill="#8E7757" />
      <rect x="52" y="234" width="12" height="40" rx="5" fill="#5C4B39" />
      <rect x="176" y="234" width="12" height="40" rx="5" fill="#5C4B39" />
    </g>
  );
}
function ChairFront() {
  return (
    <g>
      <rect x="28" y="212" width="184" height="20" rx="9" fill="#A88F6E" />
      <rect x="28" y="225" width="184" height="8" rx="4" fill="#6E5B44" opacity=".7" />
      <rect x="32" y="230" width="15" height="44" rx="7" fill="#8E7757" />
      <rect x="193" y="230" width="15" height="44" rx="7" fill="#8E7757" />
    </g>
  );
}

/* Sleep marks. Three, staggered, drifting up and out. */
function Zzz() {
  return (
    <g className="nib-zzz" fill="#4E8E7B" fontFamily="Inter, system-ui, sans-serif" fontWeight="800">
      {[[188, 142, 13, 0], [202, 120, 16, 1.1], [216, 96, 19, 2.2]].map(([x, y, sz, d]) => (
        <text key={x} x={x} y={y} fontSize={sz} opacity="0"
              style={{ animationDelay: `${d}s` }}>z</text>
      ))}
    </g>
  );
}

// The literal bugs. Making them physical is the whole joke of the product: the
// agent is not "thinking about quality", it is knocking defects out of the air.
function Swarm() {
  // x, y, scale, seconds, delay — staggered so they never move as one block
  const BUGS = [[210, 108, 1, 3.0, 0], [148, 30, 0.78, 3.7, -1.1], [50, 140, 0.9, 2.4, -0.6]];
  return (
    <g>
      {BUGS.map(([x, y, k, dur, delay]) => (
        <g key={`${x}-${y}`} transform={`translate(${x} ${y}) scale(${k})`}>
          <g className="nib-bug" style={{ animationDuration: `${dur}s`, animationDelay: `${delay}s` }}>
            <Bug />
          </g>
        </g>
      ))}
    </g>
  );
}

export function Bug() {
  return (
    <g>
      {/* Warm, not neon green: the defect is the thing Nib is against, and the
          console already speaks that language (the red bar on the trace card).
          A green bug on a green gremlin also simply disappears. */}
      <circle cx="0" cy="0" r="12.5" fill="#F2B44A" opacity="0.22" />
      <ellipse className="nib-wing" cx="-2" cy="-5.5" rx="6.5" ry="3.6" fill="#FDF1D8" opacity="0.85" />
      <ellipse className="nib-wing" cx="4" cy="-6" rx="5.5" ry="3.2" fill="#FDF1D8" opacity="0.65" />
      <ellipse cx="0" cy="0" rx="7.5" ry="5.4" fill="#E0574B" />
      <path d="M-7 0 q7 -3 14 0" fill="none" stroke="#4A1A14" strokeWidth="1.3" opacity="0.6" />
      <circle cx="7.5" cy="-0.5" r="3.8" fill="#4A1A14" />
      <path d="M9 -4 l4.5 -4.5 M11 -1.5 l5.5 -1.5" fill="none" stroke="#4A1A14" strokeWidth="1.4" strokeLinecap="round" />
      <path d="M-4 5 l-2 4 M2 5.4 l1 4.5" fill="none" stroke="#4A1A14" strokeWidth="1.3" strokeLinecap="round" />
    </g>
  );
}

function EarL() {
  return (
    <g className="nib-earL">
      <path d="M64 84 q-34 -30 -44 -68 q34 8 56 36 q10 14 12 30 Z" fill="#2A554D" />
      <path d="M64 78 q-25 -23 -33 -50 q24 8 39 26 q8 11 10 22 Z" fill="#B87A72" opacity="0.8" />
    </g>
  );
}
function EarR() {
  return (
    <g className="nib-earR">
      <path d="M176 84 q34 -30 44 -68 q-34 8 -56 36 q-10 14 -12 30 Z" fill="#2A554D" />
      <path d="M176 78 q25 -23 33 -50 q-24 8 -39 26 q-8 11 -10 22 Z" fill="#B87A72" opacity="0.8" />
    </g>
  );
}

// Poses are written for the RIGHT arm (shoulder at 156,168) and mirrored for
// the left. Each is a single stroked path from shoulder to wrist plus a mitt
// placed exactly on the wrist point, so the limb reads as one continuous piece
// rather than a sleeve with a hand parked next to it.
const ARM = {
  rest:  { d: "M154 164 q22 26 15 48",   w: [170, 217], a: 2 },
  swing: { d: "M154 164 q34 16 33 44",   w: [188, 211], a: 16 },
  jab:   { d: "M154 164 q38 12 44 32",   w: [199, 199], a: 30 },
  point: { d: "M154 164 q40 4 56 -18",   w: [212, 145], a: -46 },
  card:  { d: "M154 164 q14 18 -2 34",   w: [152, 201], a: -6 },
  hold:  { d: "M154 164 q20 20 8 34",    w: [163, 201], a: -4 },
  shrug: { d: "M154 164 q30 8 38 -4",    w: [192, 156], a: 196 },
  fist:  { d: "M154 164 q36 -6 42 -32",  w: [196, 130], a: -14 },
  hip:   { d: "M154 164 q30 16 18 32",   w: [172, 197], a: 22 },
  carry: { d: "M154 164 q34 12 26 40",    w: [180, 204], a: 12 },
  // both arms reach up to grip the barrels at eye level
  // elbow bulges outward, forearm comes back in to the barrel — held, not glued
  glassUp:{ d: "M154 164 q32 -12 24 -36",  w: [178, 128], a: -20 },
  // asleep: hangs slack, wrist turned out
  sleep: { d: "M154 164 q18 20 8 38",     w: [162, 206], a: 8 },
  swat:  { d: "M154 164 q40 -4 46 -32",  w: [200, 132], a: -34 },
  // hooked over the box rim: elbow out, forearm dropping onto the edge
  rim:   { d: "M154 164 q30 6 26 18",    w: [180, 182], a: 12 },
};

// `transform-box: fill-box` re-bases an element's transform on its own bounding
// box, so a mirroring transform attribute lands somewhere unpredictable — that
// is what detached the ear earlier and what hid the far arm entirely. Mirroring
// the path data instead has no such interaction.
function mirrorPath(d) {
  const m = d.match(/^M([\d.-]+) ([\d.-]+) q([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+)$/);
  if (!m) return d;
  const n = m.slice(1).map(Number);
  return `M${240 - n[0]} ${n[1]} q${-n[2]} ${n[3]} ${-n[4]} ${n[5]}`;
}

function Arm({ pose, side, glow, animate }) {
  const cls = animate === "jab" ? "nib-jab" : animate === "swat" ? "nib-swat" : "";
  const p = ARM[pose] || ARM.rest;
  const far = side === "far";
  const d = far ? mirrorPath(p.d) : p.d;
  const wx = far ? 240 - p.w[0] : p.w[0];
  const wy = p.w[1];
  const ang = far ? -p.a : p.a;
  const claw = far ? -1 : 1;
  return (
    <g className={cls}>
      <path d={d} stroke="#2A554D" strokeWidth="21" strokeLinecap="round" fill="none" />
      <path d={d} stroke="#3E7A6B" strokeWidth="13" strokeLinecap="round" fill="none" opacity="0.5" />
      <g transform={`translate(${wx} ${wy}) rotate(${ang})`}>
        {glow && <circle cx="0" cy="0" r="19" fill="#46E08B" opacity="0.22" />}
        {pose === "fist" ? (
          <circle cx="0" cy="0" r="14" fill="#3E7A6B" />
        ) : (
          <>
            <ellipse cx="0" cy="0" rx="14.5" ry="13" fill="#3E7A6B" />
            {/* rounded finger stubs rather than spikes — friendlier, still a paw */}
            {[-8.5, 0, 8.5].map((o, i) => (
              <circle key={i} cx={o * claw} cy="10" r="4.6" fill="#357062" />
            ))}
          </>
        )}
      </g>
    </g>
  );
}

/* The bench, seen from above: a pad running away from the viewer with a wider
   head rest at the top. Drawn behind everything, so Nib lies ON it. */
/* The Einstein kit, for the benchmark. Three props over the face Nib already
   has — no redrawn head, no new camera. Overlapping circles rather than one
   hand-cut outline: a fluffy silhouette is exactly what circles are good at,
   and it cannot go wrong the way a bespoke path can. */
function Frizz() {
  // Spaced closer than 2r, so every circle overlaps its neighbours and the row
  // fuses into one mass. Spread them out and you get polka dots, and a lighter
  // highlight inside each one makes that worse by giving every dot a centre.
  const tufts = [
    [50, 92, 19], [50, 68, 19], [62, 46, 20], [84, 30, 20], [110, 22, 21],
    [138, 22, 21], [164, 32, 20], [184, 50, 19], [194, 72, 18], [194, 94, 18],
  ];
  return (
    <g>
      {/* A shade darker than the page it sits on. At #E4E0D8 the halo washed
          out against a near-white console and read as a smudge. */}
      {tufts.map(([cx, cy, r]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} fill="#D6D0C4" />
      ))}
      {/* one broad highlight across the whole mass, not one per tuft */}
      {tufts.slice(2, 7).map(([cx, cy, r]) => (
        <circle key={`h${cx}`} cx={cx - 2} cy={cy - 5} r={r * 0.82} fill="#EAE5DA" />
      ))}
    </g>
  );
}

/* Round wire spectacles, sized to sit outside Nib's eyes (r18 at 94 and 146)
   rather than on top of them — the amber iris is half his recognition and the
   lenses have to stay clear enough to show it. */
function Specs() {
  return (
    <g fill="none" stroke="#3A424D" strokeWidth="3.6" strokeLinecap="round">
      {[94, 146].map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy="104" r="23" fill="#DCE6EC" fillOpacity="0.22" />
          <circle cx={cx} cy="104" r="23" />
        </g>
      ))}
      <path d="M117 100 q3 -4 6 0" />
      {/* temples, running back to where the ears meet the skull */}
      <path d="M71 100 q-9 -5 -15 -2" />
      <path d="M169 100 q9 -5 15 -2" />
    </g>
  );
}

/* The moustache. Bushy, drooping past the corners of the mouth, and drawn over
   it — a professor's moustache hides the mouth, that is the whole shape. */
function Tache() {
  return (
    <g>
      <path d="M120 124 q-14 -7 -27 1 q-9 6 -6 13 q4 7 14 4 q12 -4 19 -11
               q7 7 19 11 q10 3 14 -4 q3 -7 -6 -13 q-13 -8 -27 -1 Z"
            fill="#DDD8CC" />
      <path d="M120 124 q-14 -7 -27 1 q-6 4 -6 9 q10 -8 22 -6 q7 1 11 -4 Z"
            fill="#F4F1EB" opacity="0.75" />
      <path d="M93 138 q9 3 16 -3 M147 138 q-9 3 -16 -3"
            fill="none" stroke="#C9C4BA" strokeWidth="2.2" strokeLinecap="round" />
    </g>
  );
}

/* A pith helmet: brim, dome, band. Drawn over the face so it reads as worn, and
   kept narrow enough that the ears still come out from under the brim. */
function Hat() {
  return (
    <g>
      <path d="M68 68 q5 -56 52 -56 q47 0 52 56 Z" fill="#C6AF90" />
      <path d="M68 68 q5 -56 52 -56 q-17 15 -22 56 Z" fill="#A88F6E" opacity="0.55" />
      <path d="M70 57 q50 13 100 0 l0 11 q-50 13 -100 0 Z" fill="#35695F" />
      <ellipse cx="120" cy="70" rx="76" ry="16" fill="#C6AF90" />
      <path d="M44 70 q76 21 152 0 q-76 11 -152 0 Z" fill="#A88F6E" opacity="0.5" />
    </g>
  );
}

/* Binoculars raised to the eyes and held in both paws.

   The previous version kept them lowered at the hip, on the reasoning that
   raising them hides the face. That is true of opaque binoculars — the fix is
   not to lower them but to make the lenses read as glass, with Nib's own eyes
   visible through them. The character survives and the pose finally shows him
   doing the thing the explorer state is named for. */
function Binoculars() {
  return (
    <g>
      <rect x="66" y="84" width="44" height="54" rx="18" fill="#6E5B44" />
      <rect x="130" y="84" width="44" height="54" rx="18" fill="#6E5B44" />
      <rect x="74" y="90" width="11" height="44" rx="5.5" fill="#8E7757" opacity=".5" />
      <rect x="138" y="90" width="11" height="44" rx="5.5" fill="#8E7757" opacity=".5" />
      {/* bridge + focus wheel */}
      <rect x="104" y="96" width="32" height="18" rx="7" fill="#8E7757" />
      <rect x="113" y="88" width="14" height="36" rx="6" fill="#5C4B39" />
      {/* Tinted glass, not a window. Showing Nib's eyes through the lenses put
          two staring circles at the front of the drawing and read as unsettling
          rather than as looking; coated optics reflect the sky instead. */}
      {[88, 152].map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy="108" r="19" fill="#4E3F30" />
          <circle cx={cx} cy="108" r="14.5" fill="#1F3B36" />
          <circle cx={cx} cy="108" r="14.5" fill="none" stroke="#5E8A7E" strokeWidth="1.6" opacity=".5" />
          <ellipse cx={cx - 3.5} cy="103" rx="9" ry="4.2" fill="#CFE3DA" opacity=".30"
                   transform={`rotate(-38 ${cx - 3.5} 103)`} />
          <ellipse cx={cx + 4} cy="114" rx="5" ry="2.4" fill="#CFE3DA" opacity=".16"
                   transform={`rotate(-38 ${cx + 4} 114)`} />
          <circle cx={cx - 7.5} cy="100.5" r="2.4" fill="#F7F3E8" opacity=".6" />
        </g>
      ))}
    </g>
  );
}

/* The pack: this half of the agent is the one that goes out and stays out. */
function Pack() {
  // The torso runs to x=158, so a pack that stops there is a pack you cannot
  // see. It has to clear the body's edge to read at all.
  return (
    <g>
      <rect x="140" y="152" width="56" height="62" rx="17" fill="#A88F6E" />
      <rect x="162" y="168" width="30" height="24" rx="8" fill="#8E7757" />
      <rect x="170" y="196" width="18" height="6" rx="3" fill="#6E5B44" />
      <rect x="150" y="142" width="16" height="18" rx="7" fill="#6E5B44" />
    </g>
  );
}

/* Drawn over the torso, which is the only thing that makes the pack read as
   worn rather than as something parked behind him. */
function PackStrap() {
  return (
    <g>
      <path d="M150 157 q-24 24 -50 52" fill="none" stroke="#6E5B44" strokeWidth="9" strokeLinecap="round" />
      <rect x="118" y="182" width="13" height="14" rx="3" fill="#8E7757" transform="rotate(-44 124 189)" />
    </g>
  );
}

/* The map is the point of the pose: this half of the agent is the one deciding
   where to go, and it is doing it from something it drew itself. */
function MapScroll() {
  return (
    <g transform="rotate(7 92 200)">
      <rect x="66" y="186" width="52" height="30" rx="4" fill="#EFE6D2" stroke="#20443E" strokeWidth="2.5" />
      <path d="M74 208 q10 -14 20 -6 q8 6 16 -6" fill="none" stroke="#9BB0A9" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M100 194 l4 4 -4 4 -4 -4 Z" fill="#E0574B" />
      <rect x="60" y="184" width="9" height="34" rx="4.5" fill="#A88F6E" />
      <rect x="115" y="184" width="9" height="34" rx="4.5" fill="#A88F6E" />
    </g>
  );
}

function Sparkles() {
  return (
    <g className="nib-spark">
      {/* clear of the head and ears, which are drawn on top of these */}
      {[[34, 132, 8], [208, 126, 7], [120, 18, 6], [46, 198, 5]].map(([x, y, r], i) => (
        <path key={i} transform={`translate(${x} ${y})`} fill="#46E08B" opacity="0.9"
              style={{ animationDelay: `${i * 0.22}s` }}
              d={`M0 ${-r} Q${r * 0.28} ${-r * 0.28} ${r} 0 Q${r * 0.28} ${r * 0.28} 0 ${r}
                  Q${-r * 0.28} ${r * 0.28} ${-r} 0 Q${-r * 0.28} ${-r * 0.28} 0 ${-r} Z`} />
      ))}
    </g>
  );
}

/* The invigilator's clipboard: three rows, because the benchmark has three
   arms, and the ticks land in reading order. Same paper stock as the trace
   card — it is the same evidence, counted rather than replayed. */
function Clipboard() {
  return (
    <g transform="rotate(7 140 198)">
      <rect x="104" y="166" width="74" height="64" rx="6" fill="#F3EFE4" stroke="#20443E" strokeWidth="2.5" />
      <rect x="128" y="160" width="26" height="10" rx="3" fill="#8A94A3" stroke="#20443E" strokeWidth="2" />
      {[184, 199, 214].map((y, i) => (
        <g key={y}>
          <rect x="112" y={y - 6} width="12" height="12" rx="3" fill="none" stroke="#9BB0A9" strokeWidth="2" />
          <rect x="130" y={y - 3} width={40 - i * 11} height="6" rx="3" fill="#9BB0A9" />
          {i < 2 && (
            <path d={`M114 ${y} l3.5 4 6-8`} fill="none" stroke="#2F6055"
                  strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
          )}
        </g>
      ))}
    </g>
  );
}

/* A stopwatch in the raised fist. Equal action budget is the whole premise of
   the comparison, so the thing he holds up is the budget. */
function Stopwatch() {
  return (
    <g>
      <rect x="41" y="110" width="7" height="9" rx="2.5" fill="#2E343D" />
      <circle cx="44" cy="132" r="16" fill="#2E343D" />
      <circle cx="44" cy="132" r="12" fill="#F3EFE4" />
      <g className="nib-tick">
        <path d="M44 132 L44 123" stroke="#E0574B" strokeWidth="2.6" strokeLinecap="round" />
      </g>
      <circle cx="44" cy="132" r="1.9" fill="#20443E" />
    </g>
  );
}

function TraceCard() {
  // The actual product output: the reproduction trace. This is the honest prop —
  // Gremlin does not catch bugs in a net, it proves a path that reproduces one.
  return (
    <g transform="rotate(-6 120 196)">
      <rect x="82" y="160" width="76" height="58" rx="6" fill="#F3EFE4" stroke="#20443E" strokeWidth="2.5" />
      <rect x="90" y="169" width="34" height="5" rx="2.5" fill="#E0574B" />
      {[181, 191, 201].map((y, i) => (
        <g key={y}>
          <circle cx="93" cy={y} r="2.6" fill="#35695F" />
          <rect x="100" y={y - 2.5} width={44 - i * 9} height="5" rx="2.5" fill="#9BB0A9" />
        </g>
      ))}
    </g>
  );
}

function Face({ face, visor, hidden }) {
  // The binocular pose covers the eyes with its own lenses; drawing Nib's
  // underneath just puts two sets of eyes in the same place.
  if (hidden) return <Mouth face={face} />;
  if (visor) {
    return (
      <g>
        {/* visor down: the detective half. One glowing band reads instantly. */}
        <path d="M62 94 q58 -16 116 0 l0 26 q-58 14 -116 0 Z" fill="#16302C" />
        <path d="M70 100 q50 -11 100 0 l0 14 q-50 10 -100 0 Z" fill="#46E08B" opacity="0.9"
              className="nib-scan" />
        <path d="M62 94 q58 -16 116 0" fill="none" stroke="#20443E" strokeWidth="4" />
        <Mouth face="focused" />
      </g>
    );
  }
  if (face === "asleep") {
    return (
      <g>
        {/* closed lids curve down, and sit a little lower than open eyes do */}
        <path d="M78 106 q17 15 34 0" fill="none" stroke="#1B3B36" strokeWidth="7" strokeLinecap="round" />
        <path d="M128 106 q17 15 34 0" fill="none" stroke="#1B3B36" strokeWidth="7" strokeLinecap="round" />
        <Mouth face="asleep" />
      </g>
    );
  }
  if (face === "cheer") {
    return (
      <g>
        <path d="M76 104 q18 -20 36 0" fill="none" stroke="#1B3B36" strokeWidth="7" strokeLinecap="round" />
        <path d="M128 104 q18 -20 36 0" fill="none" stroke="#1B3B36" strokeWidth="7" strokeLinecap="round" />
        <Mouth face="cheer" />
      </g>
    );
  }
  return (
    <g>
      {/* Soft arced brows. The angular downward slash read as a threat; a raised
          arc reads as curiosity, which is the character we actually want. */}
      {face === "sorry" ? (
        <>
          <path d="M72 78 q18 8 32 2" fill="none" stroke="#2E5049" strokeWidth="6" strokeLinecap="round" />
          <path d="M168 78 q-18 8 -32 2" fill="none" stroke="#2E5049" strokeWidth="6" strokeLinecap="round" />
        </>
      ) : face === "swat" ? (
        <>
          {/* driven down toward the nose: concentration, not rage */}
          <path d="M72 70 q18 2 32 8" fill="none" stroke="#2E5049" strokeWidth="6.5" strokeLinecap="round" />
          <path d="M168 70 q-18 2 -32 8" fill="none" stroke="#2E5049" strokeWidth="6.5" strokeLinecap="round" />
        </>
      ) : (
        <>
          <path d="M72 76 q17 -9 33 -1" fill="none" stroke="#2E5049" strokeWidth="6" strokeLinecap="round" />
          <path d="M168 76 q-17 -9 -33 -1" fill="none" stroke="#2E5049" strokeWidth="6" strokeLinecap="round" />
        </>
      )}

      <g className="nib-lids">

        {face === "scout" ? (
          // both eyes off to the horizon, which is what makes it read as looking
          // for something rather than looking at you
          <><Eye cx={94} r={18} px={101} py={103} /><Eye cx={146} r={18} px={153} py={103} /></>
        ) : face === "swat" ? (
          // both pupils tracking the same bug — that is what makes it look like
          // it is fighting something rather than hallucinating something
          <><Eye cx={94} r={19} px={101} py={100} /><Eye cx={146} r={19} px={153} py={100} /></>
        ) : (
          <><Eye cx={94} r={18} px={94} /><Eye cx={146} r={18} px={146} /></>
        )}
        {face === "gotcha" && (
          <>
            {/* the lid has to clear the top of the eye (cy 104 - ry 18.5 = 85.5).
                At -14 it stopped at y=90 and left a crescent of white above it; much
                taller than this and it starts eating the brows. */}
            <path d="M74 104 q20 -14 40 -2 l0 -22 -40 0 Z" fill="#35695F" />
            <path d="M126 104 q20 -14 40 -2 l0 -22 -40 0 Z" fill="#35695F" />
          </>
        )}
      </g>
      <Mouth face={face} />
    </g>
  );
}

function Eye({ cx, r, px, py = 106 }) {
  return (
    <g>
      <ellipse cx={cx} cy="104" rx={r} ry={r * 1.03} fill="#F3EFE4" />
      <circle cx={px} cy={py} r={r * 0.54} fill="#F2B44A" />
      <circle cx={px} cy={py} r={r * 0.28} fill="#2A2114" />
      <circle cx={cx - 4} cy="99" r={r * 0.19} fill="#fff" />
    </g>
  );
}

function Mouth({ face }) {
  // One mouth per face. Sharing a smile across curious/swat/gotcha/cheer was
  // why idle, chaos, crash and success all read as the same happy drawing.
  switch (face) {
    case "sorry":
      return <path d="M104 143 q16 -11 32 0" fill="none" stroke="#14100A" strokeWidth="5" strokeLinecap="round" />;

    case "focused":
      // flat and unreadable — it is working, not feeling
      return <path d="M106 138 q14 2 28 0" fill="none" stroke="#14100A" strokeWidth="5" strokeLinecap="round" />;

    case "scout":
      // a short, confident line — pleased to be somewhere new, not grinning
      return <path d="M104 134 q15 9 29 -4" fill="none" stroke="#2E2018" strokeWidth="5" strokeLinecap="round" />;

    case "curious":
      // small open "o". Interested, not pleased. Nothing has happened yet.
      return <ellipse cx="120" cy="137" rx="7.5" ry="6.5" fill="#2E2018" />;

    case "asleep":
      // slack and slightly open — a mouth doing nothing, not a smile
      return <ellipse cx="118" cy="139" rx="6" ry="7.5" fill="#2E2018" opacity=".9" />;

    case "swat":
      // jaw set, teeth bared on one side. The fangs hang off the lip line — as
      // free-floating triangles under it they read as crumbs, not teeth.
      return (
        <g>
          <path d="M100 130 q19 10 38 -6 q-4 16 -19 16 q-16 0 -19 -10 Z" fill="#25150F" />
          <path d="M107 133 l4 11 5 -10 Z" fill="#F7F3E8" />
          <path d="M126 130 l4 11 5 -11 Z" fill="#F7F3E8" />
        </g>
      );

    case "gotcha":
      // caught you: asymmetric smirk, one fang tucked under the raised corner
      return (
        <g>
          <path d="M102 141 q18 5 34 -13" fill="none" stroke="#2E2018" strokeWidth="5.5" strokeLinecap="round" />
          <path d="M122 134 l4.5 11 4.5 -10 Z" fill="#F7F3E8" />
        </g>
      );

    default:
      // cheer: symmetric open smile, no fangs — relief, not mischief
      return <path d="M100 130 q20 22 40 0 q-20 8 -40 0 Z" fill="#2E2018" />;
  }
}
