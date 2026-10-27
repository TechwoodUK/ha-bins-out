/* Bins Out card for Home Assistant: vanilla ES module, no dependencies. */

const DEFAULT_ENTITY = "sensor.bins_out_next_collection";
// Not "collected": switching put-out off after collection time would mark the bin forgotten.
const TOGGLE_STATUSES = new Set(["tomorrow", "today", "out", "forgotten"]);
const HOLD_MS = 500;
const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/* ---------- helpers ---------- */

function parseLocalDate(str) {
  if (!str || typeof str !== "string") return null;
  const [y, m, d] = str.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function isoLocal(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function fmtDate(date) {
  return `${DAY_NAMES[date.getDay()]} ${date.getDate()} ${MONTH_NAMES[date.getMonth()]}`;
}

function inDays(n) {
  if (n === null || n === undefined) return "";
  if (n === 0) return "today";
  if (n === 1) return "in 1 day";
  return `in ${n} days`;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function safeColour(hex) {
  return /^#[0-9a-f]{3,8}$/i.test(hex || "") ? hex : "#888888";
}

function luminance(hex) {
  let h = safeColour(hex).slice(1);
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

// Light fills (white, yellow) need a dark outline on light themes.
function isLightColour(hex) {
  return luminance(hex) > 0.7;
}

// Dark fills (black, brown, purple, dark blue) need a theme-coloured outline on dark themes.
function isDarkColour(hex) {
  return luminance(hex) < 0.3;
}

// CSS class for a bin's tone, used by the SVG and the calendar/legend dots.
function toneClass(hex) {
  if (isLightColour(hex)) return "light";
  if (isDarkColour(hex)) return "dark";
  return "";
}

function statusLabel(bin) {
  switch (bin.status) {
    case "upcoming": return inDays(bin.days_until) || "Upcoming";
    case "tomorrow": return "Tonight";
    case "today": return "Put out NOW";
    case "out": return "Out ✓";
    case "collected": return "Collected, bring it in";
    case "forgotten": return "Missed!";
    default: return "No collections";
  }
}

function binSvg(bin) {
  const container = bin.container || "wheelie_bin";
  const fill = bin.status === "none" ? "#9e9e9e" : safeColour(bin.colour_hex);
  const light = isLightColour(fill);
  const dark = isDarkColour(fill);
  const stroke = light ? "#333" : "rgba(0,0,0,0.35)";
  const lid = light ? "#d0d0d0" : "rgba(0,0,0,0.25)";
  const svgClass = `bin-svg ${dark ? "darkfill" : ""}`;

  let inner = "";

  switch (container) {
    case "food_caddy":
      inner = `
    <!-- Food caddy handle -->
    <path class="hl" d="M11 42 C11 15, 53 15, 53 42" fill="none" stroke="${stroke}" stroke-width="3" stroke-linecap="round"/>
    <path d="M12 42 C12 17, 52 17, 52 42" fill="none" stroke="${light ? "#777" : "#333"}" stroke-width="1.5" stroke-linecap="round"/>
    <path d="M25 18 H39" stroke="${lid}" stroke-width="4.5" stroke-linecap="round"/>
    <circle cx="10.5" cy="42" r="3" fill="#2b2b2b" stroke="${stroke}" stroke-width="1"/>
    <circle cx="53.5" cy="42" r="3" fill="#2b2b2b" stroke="${stroke}" stroke-width="1"/>
    <!-- Body -->
    <path class="ol" d="M10 41 H54 L50 68 Q50 71 47 71 H17 Q14 71 14 68 Z" fill="${fill}" stroke="${stroke}" stroke-width="1.5" stroke-linejoin="round"/>
    <rect x="18" y="47" width="28" height="18" rx="3" fill="rgba(0,0,0,0.06)"/>
    <line x1="32" y1="48" x2="32" y2="64" stroke="rgba(0,0,0,0.12)" stroke-width="1.5" stroke-linecap="round"/>
    <!-- Locking lid & catch -->
    <rect class="ol" x="8" y="35" width="48" height="7" rx="3" fill="${fill}" stroke="${stroke}" stroke-width="1.5"/>
    <rect x="9" y="36" width="46" height="3" rx="1.5" fill="${lid}"/>
    <rect class="ol" x="27" y="38" width="10" height="9" rx="2" fill="${lid}" stroke="${stroke}" stroke-width="1.2"/>
    <rect x="29" y="42" width="6" height="3" rx="1" fill="rgba(0,0,0,0.3)"/>`;
      break;

    case "box":
      inner = `
    <!-- Contents over rim -->
    <ellipse cx="32" cy="44" rx="26" ry="4" fill="rgba(0,0,0,0.3)"/>
    <path d="M16 45 L16 34 Q16 31 19 29 L19 23 H23 L23 29 Q26 31 26 34 L26 45 Z" fill="#2e7d32"/>
    <path d="M18 32 L18 42" stroke="rgba(255,255,255,0.4)" stroke-width="1" stroke-linecap="round"/>
    <rect x="18" y="21.5" width="6" height="2.5" rx="0.5" fill="#d4af37"/>
    <rect x="29" y="31" width="11" height="14" rx="1.5" fill="#cfd8dc" stroke="#90a4ae" stroke-width="0.8" transform="rotate(5 34 38)"/>
    <ellipse cx="35" cy="31" rx="5" ry="1.5" fill="#eceff1" stroke="#90a4ae" stroke-width="0.6"/>
    <circle cx="35" cy="31" r="0.8" fill="#546e7a"/>
    <rect x="43" y="36" width="11" height="9" rx="1" fill="#ffa726" stroke="#fb8c00" stroke-width="0.8"/>
    <line x1="43" y1="39" x2="54" y2="39" stroke="rgba(0,0,0,0.2)" stroke-width="0.8"/>
    <!-- Box Body -->
    <path class="ol" d="M6 46 H58 L52 71 H12 Z" fill="${fill}" stroke="${stroke}" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M12 47 L16 69 M52 47 L48 69" stroke="rgba(0,0,0,0.18)" stroke-width="1.5" stroke-linecap="round"/>
    <!-- Rim lip -->
    <rect class="ol" x="4" y="43" width="56" height="5" rx="1.5" fill="${fill}" stroke="${stroke}" stroke-width="1.5"/>
    <rect x="5" y="46.5" width="54" height="1.5" fill="${lid}"/>
    <!-- Hand-hold slots -->
    <rect x="9" y="52" width="7" height="4.5" rx="2.2" fill="rgba(0,0,0,0.38)" stroke="${stroke}" stroke-width="0.8"/>
    <rect x="48" y="52" width="7" height="4.5" rx="2.2" fill="rgba(0,0,0,0.38)" stroke="${stroke}" stroke-width="0.8"/>
    <rect x="21" y="52" width="22" height="13" rx="1.5" fill="rgba(0,0,0,0.06)"/>
    <path d="M26 58 H38" stroke="rgba(0,0,0,0.15)" stroke-width="1.5" stroke-linecap="round"/>`;
      break;

    case "bag":
      inner = `
    <!-- Webbing handles -->
    <path class="hl" d="M19 33 C19 17, 27 17, 27 33" fill="none" stroke="${light ? "#444" : "#222"}" stroke-width="2.6" stroke-linecap="round"/>
    <path class="hl" d="M37 33 C37 17, 45 17, 45 33" fill="none" stroke="${light ? "#444" : "#222"}" stroke-width="2.6" stroke-linecap="round"/>
    <path d="M20 33 C20 18.5, 26 18.5, 26 33" fill="none" stroke="${lid}" stroke-width="1" stroke-linecap="round"/>
    <path d="M38 33 C38 18.5, 44 18.5, 44 33" fill="none" stroke="${lid}" stroke-width="1" stroke-linecap="round"/>
    <!-- Slumped bag body -->
    <path class="ol" d="M14 33 C11 44 8 58 11 69 C12 71 16 72 21 72 H43 C48 72 52 71 53 69 C56 58 53 44 50 33 C45 31 19 31 14 33 Z" fill="${fill}" stroke="${stroke}" stroke-width="1.5" stroke-linejoin="round"/>
    <!-- Webbing straps down front -->
    <path d="M22 36 V68 M42 36 V68" stroke="${lid}" stroke-width="2.5" stroke-linecap="square"/>
    <path d="M22 36 V68 M42 36 V68" stroke="rgba(255,255,255,0.3)" stroke-width="0.8" stroke-dasharray="2 2"/>
    <!-- Slump folds -->
    <path d="M14 55 Q32 62 50 54" fill="none" stroke="rgba(0,0,0,0.16)" stroke-width="1.8" stroke-linecap="round"/>
    <path d="M17 63 Q32 68 47 62" fill="none" stroke="rgba(0,0,0,0.13)" stroke-width="1.8" stroke-linecap="round"/>
    <!-- Top gathered hem & Velcro flap -->
    <path class="ol" d="M13 32 Q32 35 51 32 L50 36 Q32 39 14 36 Z" fill="${lid}" stroke="${stroke}" stroke-width="1"/>
    <rect class="ol" x="27" y="33" width="10" height="7" rx="1.5" fill="${fill}" stroke="${stroke}" stroke-width="1"/>
    <rect x="29" y="37" width="6" height="2" rx="0.5" fill="${lid}"/>`;
      break;

    case "wheelie_bin":
    default:
      inner = `
    <!-- Rear handlebar & hinges -->
    <rect x="13" y="7" width="38" height="4" rx="2" fill="${lid}" stroke="${stroke}" stroke-width="1.2"/>
    <rect x="16" y="9" width="5" height="5" rx="1" fill="${lid}"/>
    <rect x="43" y="9" width="5" height="5" rx="1" fill="${lid}"/>
    <!-- Wheels at back bottom -->
    <circle cx="15" cy="69" r="6.5" fill="#262626" stroke="#111" stroke-width="1.2"/>
    <circle cx="15" cy="69" r="2.5" fill="#757575"/>
    <circle cx="49" cy="69" r="6.5" fill="#262626" stroke="#111" stroke-width="1.2"/>
    <circle cx="49" cy="69" r="2.5" fill="#757575"/>
    <rect x="22" y="66" width="20" height="3" rx="1" fill="${lid}"/>
    <!-- Main bin body -->
    <path class="ol" d="M10 18 H54 L48 68 H16 Z" fill="${fill}" stroke="${stroke}" stroke-width="1.5" stroke-linejoin="round"/>
    <!-- Moulded vertical panels -->
    <path d="M21 25 L23 61 M32 25 V61 M43 25 L41 61" stroke="rgba(0,0,0,0.18)" stroke-width="2.5" stroke-linecap="round"/>
    <rect x="24" y="27" width="7" height="32" rx="1" fill="rgba(0,0,0,0.06)"/>
    <rect x="33" y="27" width="7" height="32" rx="1" fill="rgba(0,0,0,0.06)"/>
    <!-- Collar -->
    <path class="ol" d="M8 15 H56 L54 19 H10 Z" fill="${fill}" stroke="${stroke}" stroke-width="1.5"/>
    <!-- Flat lid overhanging at front with lip -->
    <rect class="ol" x="6" y="10" width="52" height="7" rx="2.5" fill="${fill}" stroke="${stroke}" stroke-width="1.5"/>
    <rect x="7" y="11" width="50" height="3" rx="1.5" fill="${lid}"/>
    <path class="ol" d="M24 17 H40 L38 20 H26 Z" fill="${fill}" stroke="${stroke}" stroke-width="1.2"/>`;
      break;
  }

  return `
  <svg viewBox="0 0 64 80" class="${svgClass}" aria-hidden="true">${inner}
  </svg>`;
}

function badgeFor(status) {
  switch (status) {
    case "out":
    case "collected":
      return `<span class="badge ok" aria-hidden="true">✓</span>`;
    case "forgotten":
      return `<span class="badge err" aria-hidden="true">!</span>`;
    case "today":
    case "tomorrow":
      return `<span class="badge warn" aria-hidden="true">●</span>`;
    default:
      return "";
  }
}

function syncIconSvg() {
  return `<span class="source-icon" title="Dates from council calendar" aria-label="Dates from council calendar">
    <svg viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M13.5 6.5A5.5 5.5 0 0 0 3.2 4.8M2.5 3v2.5h2.5"/>
      <path d="M2.5 9.5a5.5 5.5 0 0 0 10.3 1.7M13.5 13v-2.5h-2.5"/>
    </svg>
  </span>`;
}

function getRecentCancelled(bin, today) {
  if (!Array.isArray(bin.cancelled) || !bin.cancelled.length) return null;
  const todayTime = today.getTime();
  const matches = [];
  for (const d of bin.cancelled) {
    const dt = parseLocalDate(d);
    if (!dt) continue;
    const diff = Math.round((dt.getTime() - todayTime) / 86400000);
    if (diff >= -7 && diff <= 14) {
      matches.push({ dateStr: d, dt, diff });
    }
  }
  if (!matches.length) return null;
  // Pick closest to today; if distance is tied, prefer future
  matches.sort((a, b) => {
    const diffA = Math.abs(a.diff);
    const diffB = Math.abs(b.diff);
    if (diffA !== diffB) return diffA - diffB;
    return b.diff - a.diff;
  });
  return matches[0];
}

/* ---------- styles ---------- */

const STYLE = `
:host { display: block; }
ha-card { position: relative; padding: 16px; }
.header { display:flex; align-items:baseline; justify-content:space-between; gap:8px; margin-bottom:12px; }
.title { font-size: 1.25rem; font-weight: 500; color: var(--primary-text-color); }
.summary { font-size: .85rem; color: var(--secondary-text-color); }

.banner {
  display:flex; gap:10px; align-items:flex-start;
  padding:10px 12px; margin-bottom:12px; border-radius:10px;
  font-size:.9rem; line-height:1.35; color: var(--primary-text-color);
  background: color-mix(in srgb, var(--warning-color, #ffa600) 16%, transparent);
  border-left: 4px solid var(--warning-color, #ffa600);
}
.banner.err {
  background: color-mix(in srgb, var(--error-color, #db4437) 16%, transparent);
  border-left-color: var(--error-color, #db4437);
}
.banner .icon { font-size: 1.1rem; line-height: 1.2; }

.bins { display:grid; gap:12px; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }
.bins.row { grid-auto-flow: column; grid-auto-columns: minmax(110px, 1fr); grid-template-columns: none; overflow-x:auto; }
.bins.list { grid-template-columns: 1fr; }

.bin {
  --ring: transparent;
  position:relative; display:flex; flex-direction:column; align-items:center; text-align:center;
  gap:4px; padding:12px 8px 10px; border-radius:14px; cursor:pointer;
  background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
  border: 2px solid var(--ring);
  transition: transform .15s ease, box-shadow .2s ease, background .2s ease;
  user-select:none; -webkit-user-select:none; -webkit-tap-highlight-color: transparent;
  outline: none;
}
.bin:hover { background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); }
.bin:active { transform: scale(.97); }
.bin:focus-visible { box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary-color, #03a9f4) 60%, transparent); }
.bin.disabled { cursor: default; }

.bins.list .bin { flex-direction:row; text-align:left; gap:14px; padding:10px 12px; }
.bins.list .bin .text { flex:1; align-items:flex-start; }
.bins.list .bin-art { width:52px; }

.bin-art { position:relative; width:72px; transition: filter .3s ease, opacity .3s ease; }
.bin-svg { width:100%; height:auto; display:block; filter: drop-shadow(0 2px 3px rgba(0,0,0,.25)); }
.bin-svg.darkfill .ol { stroke: color-mix(in srgb, var(--primary-text-color, #000) 55%, transparent); stroke-width: 2; }
/* Handles stand out from the background in light and dark themes alike. */
.bin-svg .hl { stroke: color-mix(in srgb, var(--primary-text-color, #000) 70%, transparent); }
.text { display:flex; flex-direction:column; align-items:center; gap:2px; min-width:0; }
.name { font-weight:600; color: var(--primary-text-color); font-size: .98rem; }
.label { font-size:.85rem; font-weight:600; color: var(--secondary-text-color); }
.when { display:inline-flex; align-items:center; gap:3px; font-size:.78rem; color: var(--secondary-text-color); }
.cancelled-line { font-size:.74rem; color: var(--error-color, #db4437); font-weight: 500; }
.source-icon { display:inline-flex; align-items:center; opacity:.75; color: var(--secondary-text-color); vertical-align:middle; }

.badge {
  position:absolute; top:-4px; right:-6px; width:22px; height:22px; border-radius:50%;
  display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:700; color:#fff;
  box-shadow: 0 1px 3px rgba(0,0,0,.35);
}
.badge.ok { background: var(--success-color, #43a047); }
.badge.err { background: var(--error-color, #db4437); }
.badge.warn { background: var(--warning-color, #ffa600); font-size: 9px; }

/* statuses */
/* Not due soon: keep the true colour, just slightly lighter; plain border and quieter label. */
.s-upcoming .bin-art { opacity:.7; }
.s-upcoming .label { font-size:.8rem; font-weight:500; }
.s-none .bin-art { opacity:.35; filter: grayscale(1); }
.s-tomorrow { --ring: var(--warning-color, #ffa600); }
.s-tomorrow .label, .s-today .label { color: var(--warning-color, #ffa600); }
.s-tomorrow.due { animation: glow 2.4s ease-in-out infinite; }
.s-today { --ring: var(--warning-color, #ffa600); animation: glowStrong 1.2s ease-in-out infinite; }
.s-out .label, .s-collected .label { color: var(--success-color, #43a047); }
.s-collected { --ring: color-mix(in srgb, var(--success-color, #43a047) 60%, transparent); }
.s-forgotten { --ring: var(--error-color, #db4437); background: color-mix(in srgb, var(--error-color, #db4437) 10%, transparent); }
.s-forgotten .label { color: var(--error-color, #db4437); }

@keyframes glow {
  0%,100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--warning-color, #ffa600) 0%, transparent); }
  50% { box-shadow: 0 0 14px 2px color-mix(in srgb, var(--warning-color, #ffa600) 45%, transparent); }
}
@keyframes glowStrong {
  0%,100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--warning-color, #ffa600) 20%, transparent); }
  50% { box-shadow: 0 0 20px 5px color-mix(in srgb, var(--warning-color, #ffa600) 70%, transparent); }
}
@media (prefers-reduced-motion: reduce) {
  .bin, .bin-art { transition: none; }
  .s-tomorrow.due, .s-today { animation: none; }
}

/* in-card menu */
.menu-backdrop {
  position: absolute;
  inset: 0;
  z-index: 95;
  background: rgba(0,0,0,0.06);
  border-radius: var(--ha-card-border-radius, 12px);
}
.card-menu {
  position: absolute;
  z-index: 100;
  box-sizing: border-box;
  background: var(--card-background-color, #fff);
  color: var(--primary-text-color, #212121);
  border: 1px solid var(--divider-color, rgba(127,127,127,.3));
  border-radius: 10px;
  box-shadow: 0 4px 18px rgba(0,0,0,.28);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.menu-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 8px 12px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--primary-text-color);
  font: inherit;
  font-size: .84rem;
  text-align: left;
  cursor: pointer;
  transition: background .15s ease, color .15s ease;
  outline: none;
  box-sizing: border-box;
}
.menu-item:hover, .menu-item:focus-visible {
  background: color-mix(in srgb, var(--primary-text-color) 10%, transparent);
}
.menu-item.danger-confirm {
  background: color-mix(in srgb, var(--error-color, #db4437) 16%, transparent);
  color: var(--error-color, #db4437);
  font-weight: 600;
}
.menu-item[disabled] {
  opacity: .4;
  cursor: default;
}

/* calendar */
.cal { margin-top:16px; padding-top:12px; border-top:1px solid var(--divider-color, rgba(127,127,127,.25)); }
.cal-strip { display:grid; grid-template-columns: repeat(7, 1fr); gap:4px; }
.day {
  position:relative; display:flex; flex-direction:column; align-items:center; gap:3px;
  padding:5px 0 6px; border-radius:8px; min-height:44px;
  color: var(--secondary-text-color); font-size:.72rem;
}
.day .dn { font-size:.62rem; text-transform:uppercase; letter-spacing:.04em; opacity:.8; }
.day .dd { font-size:.85rem; font-weight:600; color: var(--primary-text-color); }
.day.today { background: color-mix(in srgb, var(--primary-color, #03a9f4) 18%, transparent); }
.day.today .dd { color: var(--primary-color, #03a9f4); }
.day.has { background: color-mix(in srgb, var(--primary-text-color) 5%, transparent); }
.day.today.has { background: color-mix(in srgb, var(--primary-color, #03a9f4) 18%, transparent); }
.dots { display:flex; gap:3px; flex-wrap:wrap; justify-content:center; min-height:8px; }
.dot { width:8px; height:8px; border-radius:50%; flex:none; box-shadow: inset 0 0 0 1px rgba(0,0,0,.35); box-sizing:border-box; }
.dot.light { box-shadow: inset 0 0 0 1.5px #333; }
.dot.dark { box-shadow: 0 0 0 1.5px color-mix(in srgb, var(--primary-text-color, #000) 55%, transparent); }
.dot.cancelled {
  background: transparent !important;
  box-shadow: none !important;
  border: 1.5px solid var(--dot-color, #888) !important;
  position: relative;
}
.dot.cancelled::after {
  content: "";
  position: absolute;
  top: 50%;
  left: -2px;
  right: -2px;
  height: 1.5px;
  background: var(--dot-color, #888);
  transform: rotate(-45deg);
}
.dot.cancelled.light {
  border-color: #333 !important;
}
.dot.cancelled.light::after {
  background: #333 !important;
}
.dot.cancelled.dark {
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--primary-text-color, #000) 55%, transparent) !important;
}
/* Estimated: the council hasn't published this date yet. Faded fill, dashed ring. */
.dot.estimated {
  background: color-mix(in srgb, var(--dot-color, #888) 30%, transparent) !important;
  box-shadow: none !important;
  border: 1.5px dashed var(--dot-color, #888);
}
.dot.estimated.light { border-color: #333; }
.dot.estimated.dark { border-color: color-mix(in srgb, var(--primary-text-color, #000) 60%, var(--dot-color)); }
.moved { position:absolute; top:3px; right:4px; width:6px; height:6px; border-radius:50%; background: var(--warning-color, #ffa600); }
.legend { display:flex; flex-wrap:wrap; gap:6px 14px; margin-top:10px; font-size:.75rem; color: var(--secondary-text-color); }
.legend span { display:inline-flex; align-items:center; gap:5px; }

.empty { padding:8px 0; color: var(--secondary-text-color); }
.warning { padding:16px; color: var(--error-color, #db4437); }
`;

/* ---------- card ---------- */

class BinsOutCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._lastKey = null;
    this._bins = [];
    this._menuBin = null;
    this._confirmTimer = null;
    this._docPointerHandler = null;
    this._menuKeyHandler = null;
  }

  static getStubConfig() {
    return { entity: DEFAULT_ENTITY };
  }

  static getConfigElement() {
    return document.createElement("bins-out-card-editor");
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Invalid configuration");
    const days = config.days === undefined ? 14 : Number(config.days);
    if (!Number.isFinite(days) || days < 7 || days > 35) throw new Error("days must be between 7 and 35");
    const layout = config.layout || "auto";
    if (!["auto", "row", "list"].includes(layout)) throw new Error('layout must be "auto", "row" or "list"');
    if (config.entity !== undefined && typeof config.entity !== "string") throw new Error("entity must be a string");
    this._config = {
      entity: config.entity || DEFAULT_ENTITY,
      title: config.title === undefined ? "Bins" : String(config.title),
      show_calendar: config.show_calendar !== false,
      days: Math.round(days),
      layout,
    };
    this._lastKey = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return this._config && this._config.show_calendar ? 5 : 3;
  }

  disconnectedCallback() {
    this._closeMenu();
  }

  _render() {
    if (!this._config || !this._hass) return;
    const stateObj = this._hass.states[this._config.entity];
    // Re-render only when the entity changes, or once a day (so "today" moves on).
    const key = stateObj
      ? `${stateObj.last_updated}|${isoLocal(new Date())}`
      : "missing";
    if (key === this._lastKey) return;
    this._lastKey = key;

    this._closeMenu();

    if (!stateObj) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style>
        <ha-card><div class="warning">Bins Out entity not found: <code>${esc(this._config.entity)}</code></div></ha-card>`;
      return;
    }

    const a = stateObj.attributes || {};
    const bins = Array.isArray(a.bins) ? a.bins : [];
    this._bins = bins;
    const cfg = this._config;

    let banner = "";
    if (a.forgotten_message) banner = `<div class="banner err" role="alert"><span class="icon">⚠️</span><span>${esc(a.forgotten_message)}</span></div>`;
    else if (a.morning_message) banner = `<div class="banner" role="status"><span class="icon">🌅</span><span>${esc(a.morning_message)}</span></div>`;
    else if (a.tonight_message) banner = `<div class="banner" role="status"><span class="icon">🌙</span><span>${esc(a.tonight_message)}</span></div>`;

    const days = Number(stateObj.state);
    const nextBins = Array.isArray(a.next_bins) ? a.next_bins : [];
    const summary = nextBins.length && Number.isFinite(days)
      ? `${esc(nextBins.join(" & "))} ${esc(inDays(days))}`
      : "";

    const header = cfg.title
      ? `<div class="header"><div class="title">${esc(cfg.title)}</div><div class="summary">${summary}</div></div>`
      : "";

    const layoutClass = cfg.layout === "auto" ? "" : cfg.layout;
    const binsHtml = bins.length
      ? `<div class="bins ${layoutClass}">${bins.map((b, i) => this._binHtml(b, i)).join("")}</div>`
      : `<div class="empty">No bins configured yet.</div>`;

    const cal = cfg.show_calendar && bins.length ? this._calendarHtml(bins, cfg.days) : "";

    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${header}${banner}${binsHtml}${cal}</ha-card>`;
    this._attachHandlers();
  }

  _binHtml(bin, idx) {
    const status = bin.status || "none";
    const next = parseLocalDate(bin.next_collection);
    const when = next ? `${fmtDate(next)} · ${inDays(bin.days_until)}` : "";
    const ents = bin.entities || {};
    const canToggle = TOGGLE_STATUSES.has(status) && !!ents.put_out;
    const canInfo = !!ents.status;
    const disabled = !canToggle && !canInfo;
    const label = statusLabel(bin);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const recentCancelled = getRecentCancelled(bin, today);
    const cancelledText = recentCancelled ? `${fmtDate(recentCancelled.dt)} cancelled` : "";
    const sync = bin.source === "calendar" ? syncIconSvg() : "";

    let dateLine = "";
    if (when) {
      dateLine = `<div class="when">${esc(when)}${sync}</div>`;
    } else if (sync) {
      dateLine = `<div class="when">${sync}</div>`;
    }

    const cancelledLine = cancelledText
      ? `<div class="cancelled-line">${esc(cancelledText)}</div>`
      : "";

    const aria = `${bin.name}: ${label}${when ? ", " + when : ""}${cancelledText ? ", " + cancelledText : ""}${bin.source === "calendar" ? ", automatic calendar" : ""}${canToggle ? ". Tap to toggle put out." : ""}. Hold for options.`;

    return `
      <div class="bin s-${esc(status)} ${bin.due ? "due" : ""} ${disabled ? "disabled" : ""}"
           data-idx="${idx}" role="button" tabindex="${disabled ? -1 : 0}"
           aria-label="${esc(aria)}" ${disabled ? 'aria-disabled="true"' : ""}>
        <div class="bin-art">${binSvg(bin)}${badgeFor(status)}</div>
        <div class="text">
          <div class="name">${esc(bin.name)}</div>
          <div class="label">${esc(label)}</div>
          ${dateLine}
          ${cancelledLine}
        </div>
      </div>`;
  }

  _calendarHtml(bins, numDays) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const byDate = new Map();
    for (const bin of bins) {
      const movedFrom = {};
      for (const [orig, dest] of Object.entries(bin.moved || {})) movedFrom[dest] = orig;
      const estimated = new Set(Array.isArray(bin.estimated) ? bin.estimated : []);
      for (const d of bin.upcoming || []) {
        if (!byDate.has(d)) byDate.set(d, []);
        byDate.get(d).push({
          bin, movedFrom: movedFrom[d] || null, cancelled: false, estimated: estimated.has(d),
        });
      }
      for (const d of bin.cancelled || []) {
        if (!byDate.has(d)) byDate.set(d, []);
        byDate.get(d).push({ bin, movedFrom: null, cancelled: true });
      }
    }
    let anyCancelledInStrip = false;
    let anyEstimatedInStrip = false;
    const cells = [];
    for (let i = 0; i < numDays; i++) {
      const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() + i);
      const iso = isoLocal(date);
      const entries = byDate.get(iso) || [];
      const moved = entries.filter((e) => e.movedFrom);
      if (entries.some((e) => e.cancelled)) anyCancelledInStrip = true;
      if (entries.some((e) => e.estimated)) anyEstimatedInStrip = true;
      const titleParts = entries.map((e) => {
        let t = e.bin.name;
        if (e.cancelled) {
          t += " (cancelled)";
        } else if (e.estimated) {
          t += " (estimated: the council hasn't confirmed this date yet)";
        } else if (e.movedFrom) {
          const o = parseLocalDate(e.movedFrom);
          t += ` (moved from ${o ? fmtDate(o) : e.movedFrom})`;
        }
        return t;
      });
      const title = `${fmtDate(date)}${titleParts.length ? ": " + titleParts.join(", ") : ""}`;
      cells.push(`
        <div class="day ${i === 0 ? "today" : ""} ${entries.length ? "has" : ""}" title="${esc(title)}">
          ${moved.length ? `<span class="moved"></span>` : ""}
          <span class="dn">${DAY_NAMES[date.getDay()]}</span>
          <span class="dd">${date.getDate()}</span>
          <span class="dots">${entries.map((e) => {
            const c = safeColour(e.bin.colour_hex);
            if (e.cancelled) {
              return `<span class="dot cancelled ${toneClass(c)}" style="--dot-color:${c}"></span>`;
            }
            if (e.estimated) {
              return `<span class="dot estimated ${toneClass(c)}" style="--dot-color:${c}"></span>`;
            }
            return `<span class="dot ${toneClass(c)}" style="background:${c}"></span>`;
          }).join("")}</span>
        </div>`);
    }
    const anyMoved = bins.some((b) => b.moved && Object.keys(b.moved).length);
    const legend = bins.map((b) => {
      const c = safeColour(b.colour_hex);
      return `<span><span class="dot ${toneClass(c)}" style="background:${c}"></span>${esc(b.name)}</span>`;
    }).join("")
      + (anyCancelledInStrip ? `<span><span class="dot cancelled" style="--dot-color:var(--secondary-text-color)"></span>Cancelled</span>` : "")
      + (anyEstimatedInStrip ? `<span><span class="dot estimated" style="--dot-color:var(--secondary-text-color)"></span>Estimated</span>` : "")
      + (anyMoved ? `<span><span class="moved" style="position:static"></span>Moved date</span>` : "");
    return `<div class="cal"><div class="cal-strip">${cells.join("")}</div><div class="legend">${legend}</div></div>`;
  }

  _attachHandlers() {
    this.shadowRoot.querySelectorAll(".bin").forEach((el) => {
      const bin = this._bins[Number(el.dataset.idx)];
      if (!bin) return;
      let timer = null;
      let held = false;
      const clear = () => { if (timer) { clearTimeout(timer); timer = null; } };
      el.addEventListener("pointerdown", (ev) => {
        if (ev.button !== undefined && ev.button !== 0) return;
        held = false;
        clear();
        timer = setTimeout(() => {
          held = true;
          timer = null;
          this._openMenu(bin, el);
        }, HOLD_MS);
      });
      el.addEventListener("pointerup", clear);
      el.addEventListener("pointerleave", clear);
      el.addEventListener("pointercancel", clear);
      el.addEventListener("contextmenu", (ev) => {
        ev.preventDefault();
        clear();
        held = true;
        this._openMenu(bin, el);
      });
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        if (held) { held = false; return; }
        this._tap(bin);
      });
      el.addEventListener("keydown", (ev) => {
        if (ev.key === "ContextMenu" || (ev.shiftKey && ev.key === "F10")) {
          ev.preventDefault();
          this._openMenu(bin, el);
        } else if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          this._tap(bin);
        }
      });
    });
  }

  _closeMenu() {
    if (this._confirmTimer) {
      clearTimeout(this._confirmTimer);
      this._confirmTimer = null;
    }
    if (this._docPointerHandler) {
      window.removeEventListener("pointerdown", this._docPointerHandler, true);
      this._docPointerHandler = null;
    }
    if (this._menuKeyHandler) {
      window.removeEventListener("keydown", this._menuKeyHandler, true);
      this._menuKeyHandler = null;
    }
    const cardEl = this.shadowRoot && this.shadowRoot.querySelector("ha-card");
    if (cardEl) {
      cardEl.querySelectorAll(".card-menu, .menu-backdrop").forEach((el) => el.remove());
    }
    this._menuBin = null;
  }

  _openMenu(bin, binEl) {
    this._closeMenu();
    this._menuBin = bin;

    const cardEl = this.shadowRoot.querySelector("ha-card");
    if (!cardEl) return;

    // Backdrop
    const backdrop = document.createElement("div");
    backdrop.className = "menu-backdrop";
    backdrop.addEventListener("click", (e) => {
      e.stopPropagation();
      this._closeMenu();
    });
    cardEl.appendChild(backdrop);

    // Menu container
    const menuEl = document.createElement("div");
    menuEl.className = "card-menu";
    menuEl.setAttribute("role", "menu");
    menuEl.setAttribute("aria-label", `${bin.name} options`);

    const todayIso = isoLocal(new Date());

    // 1. Cancel next collection (Tue 27 Oct)
    if (bin.next_collection) {
      const nextDate = parseLocalDate(bin.next_collection);
      const dateLabel = nextDate ? fmtDate(nextDate) : bin.next_collection;
      const origText = `Cancel next collection (${dateLabel})`;

      const cancelBtn = document.createElement("button");
      cancelBtn.className = "menu-item";
      cancelBtn.setAttribute("role", "menuitem");
      cancelBtn.textContent = origText;

      let confirming = false;
      cancelBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (!confirming) {
          confirming = true;
          cancelBtn.textContent = "Tap again to confirm";
          cancelBtn.classList.add("danger-confirm");
          this._confirmTimer = setTimeout(() => {
            confirming = false;
            cancelBtn.textContent = origText;
            cancelBtn.classList.remove("danger-confirm");
            this._confirmTimer = null;
          }, 4000);
        } else {
          if (this._confirmTimer) {
            clearTimeout(this._confirmTimer);
            this._confirmTimer = null;
          }
          this._hass.callService("bins_out", "cancel_collection", {
            bin: bin.id,
            date: bin.next_collection,
          });
          this._closeMenu();
        }
      });
      menuEl.appendChild(cancelBtn);
    }

    // 2. Restore entries (one per date in cancelled that is today or later, max 3, soonest first)
    const restoreDates = (bin.cancelled || [])
      .filter((d) => d >= todayIso)
      .sort()
      .slice(0, 3);

    for (const d of restoreDates) {
      const dObj = parseLocalDate(d);
      const dLabel = dObj ? fmtDate(dObj) : d;
      const restoreBtn = document.createElement("button");
      restoreBtn.className = "menu-item";
      restoreBtn.setAttribute("role", "menuitem");
      restoreBtn.textContent = `Restore ${dLabel}`;
      restoreBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._hass.callService("bins_out", "restore_collection", {
          bin: bin.id,
          date: d,
        });
        this._closeMenu();
      });
      menuEl.appendChild(restoreBtn);
    }

    // 3. Details
    const detailsBtn = document.createElement("button");
    detailsBtn.className = "menu-item";
    detailsBtn.setAttribute("role", "menuitem");
    detailsBtn.textContent = "Details";
    const statusEnt = bin.entities && bin.entities.status;
    if (!statusEnt) {
      detailsBtn.disabled = true;
    } else {
      detailsBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._moreInfo(bin);
        this._closeMenu();
      });
    }
    menuEl.appendChild(detailsBtn);

    cardEl.appendChild(menuEl);

    // Position menu relative to cardEl
    const cardRect = cardEl.getBoundingClientRect();
    const binRect = binEl.getBoundingClientRect();

    const menuWidth = Math.min(260, cardRect.width - 24);
    menuEl.style.width = `${Math.round(menuWidth)}px`;

    const binCenterX = binRect.left - cardRect.left + (binRect.width / 2);
    let left = binCenterX - (menuWidth / 2);
    left = Math.max(12, Math.min(cardRect.width - menuWidth - 12, left));

    let top = binRect.bottom - cardRect.top + 6;
    const menuHeight = menuEl.offsetHeight || 140;
    if (top + menuHeight > cardRect.height && binRect.top - cardRect.top > menuHeight + 10) {
      top = binRect.top - cardRect.top - menuHeight - 6;
    }

    menuEl.style.left = `${Math.round(left)}px`;
    menuEl.style.top = `${Math.round(top)}px`;

    // Keyboard navigation & outside pointerdown
    const focusable = Array.from(menuEl.querySelectorAll(".menu-item:not([disabled])"));
    if (focusable.length) focusable[0].focus();

    this._menuKeyHandler = (ev) => {
      if (ev.key === "Escape") {
        ev.preventDefault();
        ev.stopPropagation();
        this._closeMenu();
        binEl.focus();
        return;
      }
      const activeEl = menuEl.querySelector(":focus");
      const idx = focusable.indexOf(activeEl);
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        const nextIdx = (idx + 1) % focusable.length;
        focusable[nextIdx].focus();
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        const prevIdx = (idx - 1 + focusable.length) % focusable.length;
        focusable[prevIdx].focus();
      } else if (ev.key === "Home") {
        ev.preventDefault();
        focusable[0]?.focus();
      } else if (ev.key === "End") {
        ev.preventDefault();
        focusable[focusable.length - 1]?.focus();
      }
    };
    window.addEventListener("keydown", this._menuKeyHandler, true);

    this._docPointerHandler = (ev) => {
      const path = ev.composedPath();
      if (!path.includes(menuEl)) {
        this._closeMenu();
      }
    };
    setTimeout(() => {
      if (this._menuBin) {
        window.addEventListener("pointerdown", this._docPointerHandler, true);
      }
    }, 50);
  }

  _tap(bin) {
    const ents = bin.entities || {};
    if (TOGGLE_STATUSES.has(bin.status) && ents.put_out) {
      this._hass.callService("switch", "toggle", { entity_id: ents.put_out });
    } else {
      this._moreInfo(bin);
    }
  }

  _moreInfo(bin) {
    const id = bin.entities && bin.entities.status;
    if (!id) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", {
      detail: { entityId: id }, bubbles: true, composed: true,
    }));
  }
}

/* ---------- editor ---------- */

class BinsOutCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    const c = this._config || {};
    const title = c.title === undefined ? "Bins" : c.title;
    const days = c.days === undefined ? 14 : c.days;
    const layout = c.layout || "auto";
    this.shadowRoot.innerHTML = `
      <style>
        .form { display:grid; gap:14px; padding:4px 0; }
        label { display:flex; flex-direction:column; gap:4px; font-size:.9rem; color: var(--primary-text-color); }
        label.row { flex-direction:row; align-items:center; gap:10px; }
        input[type=text], input[type=number], select {
          padding:8px 10px; border-radius:6px; font: inherit;
          border:1px solid var(--divider-color, #ccc);
          background: var(--card-background-color, #fff); color: var(--primary-text-color);
        }
        .hint { font-size:.75rem; color: var(--secondary-text-color); }
      </style>
      <div class="form">
        <label>Entity
          <input type="text" id="entity" value="${esc(c.entity || DEFAULT_ENTITY)}">
        </label>
        <label>Title
          <input type="text" id="title" value="${esc(title)}">
          <span class="hint">Leave empty to hide the header.</span>
        </label>
        <label class="row"><input type="checkbox" id="show_calendar" ${c.show_calendar === false ? "" : "checked"}> Show calendar</label>
        <label>Calendar days (7–35)
          <input type="number" id="days" min="7" max="35" value="${esc(days)}">
        </label>
        <label>Layout
          <select id="layout">
            ${["auto", "row", "list"].map((l) => `<option value="${l}" ${l === layout ? "selected" : ""}>${l}</option>`).join("")}
          </select>
        </label>
      </div>`;
    const root = this.shadowRoot;
    root.getElementById("entity").addEventListener("change", (e) => this._set("entity", e.target.value.trim()));
    root.getElementById("title").addEventListener("change", (e) => this._set("title", e.target.value));
    root.getElementById("show_calendar").addEventListener("change", (e) => this._set("show_calendar", e.target.checked));
    root.getElementById("days").addEventListener("change", (e) => {
      const v = Math.min(35, Math.max(7, Number(e.target.value) || 14));
      e.target.value = v;
      this._set("days", v);
    });
    root.getElementById("layout").addEventListener("change", (e) => this._set("layout", e.target.value));
  }

  _set(key, value) {
    this._config = { ...this._config, [key]: value };
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: this._config }, bubbles: true, composed: true,
    }));
  }
}

/* ---------- registration ---------- */

// HA 2026.10 can swap window.customElements for a new registry while it boots. If this module ran
// before the swap, our definitions would be stranded in the old registry ("Configuration error").
// So register in whatever registry is current, and again whenever it changes. Each registry gets a
// fresh subclass, because one constructor can't be defined in two registries.
function register() {
  const reg = window.customElements;
  if (!reg) return;
  if (!reg.get("bins-out-card")) reg.define("bins-out-card", class extends BinsOutCard {});
  if (!reg.get("bins-out-card-editor")) reg.define("bins-out-card-editor", class extends BinsOutCardEditor {});
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === "bins-out-card")) {
    window.customCards.push({
      type: "bins-out-card",
      name: "Bins Out",
      description: "Shows when each bin needs to go out.",
      preview: true,
    });
  }
}

// Cheap and idempotent: only defines what's missing in the current registry, so it also covers
// the registry object being swapped (old definitions don't carry over).
function checkRegistry() {
  register();
}

checkRegistry();
const registryTimer = setInterval(checkRegistry, 250);
setTimeout(() => clearInterval(registryTimer), 30000);
window.addEventListener("load", checkRegistry);
// Exposed for demo.html's "Simulate registry swap" test.
window.__binsOutCheckRegistry = checkRegistry;
