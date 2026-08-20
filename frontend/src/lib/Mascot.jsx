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
  idle:    { face: "curious", far: "rest",  near: "rest",  glow: false },
  chaos:   { face: "swat",    far: "swing", near: "swat",  glow: false, bugs: true },
  crash:   { face: "gotcha",  far: "hip",   near: "point", glow: false },
  trace:   { face: "focused", far: "hold",  near: "card",  glow: false, visor: true },
  error:   { face: "sorry",   far: "shrug", near: "shrug", glow: false },
  success: { face: "cheer",   far: "hip",   near: "fist",  glow: true, sparkle: true },
  // the policy half, drawn as what it actually is: someone scouting unmapped
  // ground. Hand up against the light, map in the other, hat on.
  explorer: { face: "scout",  far: "carry", near: "glass", glow: false, hat: true, map: true, pack: true },
};

export default function Mascot({
  size = 200,
  state = "idle",
  float = false,
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
      className={`nib nib-${state} ${float ? "nib-float" : ""} ${className}`}
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
          0%   { transform: translate(0,0)        rotate(0deg) }
          25%  { transform: translate(2.5px,-4px) rotate(-1.6deg) }
          50%  { transform: translate(0,-6px)     rotate(0deg) }
          75%  { transform: translate(-2.5px,-4px) rotate(1.6deg) }
          100% { transform: translate(0,0)        rotate(0deg) }
        }
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
        @keyframes nib-floaty  { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-8px)} }
        .nib-spark path { animation: nib-pop 1.5s ease-in-out infinite; transform-origin:50% 50%; }
        .nib-float { animation: nib-floaty 4.4s ease-in-out infinite; }
        @media (prefers-reduced-motion: reduce) { .nib, .nib * { animation: none !important; } }
      `}</style>

      <ellipse cx="120" cy="272" rx="58" ry="9" fill="#12211E" opacity="0.16" />

      <g className="nib-body">
        {/* tail — rooted in the lower back and drawn behind everything, which is
            what the old floating wing shape never was. Spade tip: gremlin, not bat. */}
        <g className="nib-tail">
          <path d="M148 214 q44 10 52 -30" fill="none" stroke="#24504A" strokeWidth="14" strokeLinecap="round" />
          {/* the spade's base straddles the end of the curve — a tip that only
              meets it at one point reads as a rhombus floating beside the hip */}
          <path d="M200 152 q16 16 15 29 q-9 -6 -15 5 q-6 -11 -15 -5 q-1 -13 15 -29 Z" fill="#24504A" />
        </g>

        {/* legs: short and thick, three claws each */}
        {[86, 128].map((x) => (
          <g key={x}>
            <rect x={x} y="206" width="27" height="40" rx="13" fill="#2A554D" />
            <path d={`M${x - 5} 244 q18 -8 37 0 q0 9 -8 10 l-21 0 q-8 -1 -8 -10 Z`} fill="#20443E" />
            {[6, 15, 24].map((o) => (
              <path key={o} d={`M${x + o - 3} 254 l3 6 3 -6 Z`} fill="#173430" />
            ))}
          </g>
        ))}

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
        <Arm pose={s.far} side="far" />

        {/* the trace card goes over the far arm so the near hand overlaps it */}
        {s.near === "card" && <TraceCard />}

        <Arm pose={s.near} side="near" glow={s.glow} animate={s.near} />
        {s.near === "glass" && <Binoculars />}
        {s.sparkle && <Sparkles />}

        {/* head — nearly half the figure */}
        <g className="nib-head">
          <EarL /><EarR />
          <path d="M56 96 q0 -58 64 -58 q64 0 64 58 q0 42 -22 56 q-17 11 -42 11
                   q-25 0 -42 -11 q-22 -14 -22 -56 Z" fill="#35695F" />
          {/* cool shadow down one side, warm rim on the other */}
          <path d="M56 96 q0 42 22 56 q8 5 18 8 q-30 -30 -24 -80 q-16 6 -16 16 Z"
                fill="#20443E" opacity="0.55" />
          <Face face={s.face} visor={s.visor} />
          {s.hat && <Hat />}
        </g>

        {s.bugs && bugs && <Swarm />}
      </g>
    </svg>
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
  glass: { d: "M154 164 q40 -8 44 -38",   w: [198, 126], a: -18 },
  swat:  { d: "M154 164 q40 -4 46 -32",  w: [200, 132], a: -34 },
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

/* Binoculars, just lowered rather than up at the eyes — raised to the face they
   hide the one part of the drawing that carries the character. */
function Binoculars() {
  return (
    <g transform="rotate(-18 198 126)">
      {/* leather rather than dark teal: against the body they were a silhouette */}
      <rect x="182" y="112" width="14" height="26" rx="6" fill="#6E5B44" />
      <rect x="199" y="112" width="14" height="26" rx="6" fill="#6E5B44" />
      <rect x="194" y="118" width="7" height="9" rx="2" fill="#8E7757" />
      <circle cx="189" cy="115" r="4.6" fill="#EFE6D2" />
      <circle cx="206" cy="115" r="4.6" fill="#EFE6D2" />
      <rect x="181" y="130" width="33" height="5" rx="2.5" fill="#4E3F30" />
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

function Face({ face, visor }) {
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
