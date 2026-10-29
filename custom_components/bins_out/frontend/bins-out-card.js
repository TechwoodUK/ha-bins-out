/* Bins Out card for Home Assistant: vanilla ES module, no dependencies. */

const DEFAULT_ENTITY = "sensor.bins_out_next_collection";
// Not "collected": switching put-out off after collection time would mark the bin forgotten.
const TOGGLE_STATUSES = new Set(["tomorrow", "today", "out", "forgotten"]);
const HOLD_MS = 500;
const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const WEEKDAY_MON = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTH_FULL_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const SETTINGS_PATH = "/config/integrations/integration/bins_out";

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

function relDaysPage(n) {
  if (n === null || n === undefined) return "";
  if (n === 0) return "today";
  if (n === 1) return "tomorrow";
  if (n < 0) return `${Math.abs(n)}d ago`;
  return `in ${n} days`;
}

function howOftenText(bin) {
  const weeks = bin.interval_weeks ?? bin.repeat_weeks ?? null;
  if (!weeks || weeks <= 0) return "";
  return weeks === 1 ? "every week" : `every ${weeks} weeks`;
}

function joinSpokenNames(list) {
  if (!list || !list.length) return "bin";
  const names = list.map((b) => String(b.spoken_name || b.name || "bin").trim());
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.length} bins`;
}

function fmtShortTime(timeStr, fallback) {
  if (typeof timeStr === "string" && timeStr.length >= 5) {
    return timeStr.slice(0, 5);
  }
  return fallback;
}

function navigateToSettings() {
  history.pushState(null, "", SETTINGS_PATH);
  window.dispatchEvent(new CustomEvent("location-changed"));
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

function pageIconSvg(kind) {
  let paths = "";
  switch (kind) {
    case "moon":
      paths = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>`;
      break;
    case "sunrise":
      paths = `<path d="M17 18a5 5 0 0 0-10 0"/><line x1="12" y1="2" x2="12" y2="9"/><line x1="4.22" y1="10.22" x2="5.64" y2="11.64"/><line x1="1" y1="18" x2="3" y2="18"/><line x1="21" y1="18" x2="23" y2="18"/><line x1="18.36" y1="11.64" x2="19.78" y2="10.22"/><line x1="23" y1="22" x2="1" y2="22"/><polyline points="8 6 12 2 16 6"/>`;
      break;
    case "warning":
      paths = `<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>`;
      break;
    case "tick":
      paths = `<polyline points="20 6 9 17 4 12"/>`;
      break;
    case "undo":
      paths = `<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>`;
      break;
    case "chevronLeft":
      paths = `<polyline points="15 18 9 12 15 6"/>`;
      break;
    case "chevronRight":
      paths = `<polyline points="9 18 15 12 9 6"/>`;
      break;
    case "calendar":
    default:
      paths = `<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>`;
      break;
  }
  return `<svg class="pg-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
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
:host {
  display: block;
  --bins-green: #2e9e44;
  --bins-orange: #f07a1a;
}
ha-card { position: relative; padding: 16px; box-sizing: border-box; }
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
  box-sizing: border-box;
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
.when { display:inline-flex; align-items:center; gap:3px; font-size:.78rem; color: var(--secondary-text-color); flex-wrap:wrap; justify-content:center; }
.freq { font-size:.75rem; color: var(--secondary-text-color); }
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
  min-height: 44px;
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
  color: color-mix(in srgb, var(--error-color, #db4437) 80%, var(--primary-text-color));
  font-weight: 600;
}
.menu-item[disabled] {
  opacity: .4;
  cursor: default;
}

/* card calendar strip */
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
.dots { display:flex; gap:3px; flex-wrap:wrap; justify-content:center; align-items:center; min-height:8px; }
.dot { width:8px; height:8px; border-radius:50%; flex:none; box-shadow: inset 0 0 0 1px rgba(0,0,0,.35); box-sizing:border-box; display:inline-block; }
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

/* ---------- page view ---------- */

.page-root {
  container-type: inline-size;
  container-name: binspage;
  width: 100%;
  box-sizing: border-box;
  font-size: 14px;
  line-height: 1.45;
  color: var(--primary-text-color);
}

.page-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.col-left, .col-right {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.page-root.is-wide .page-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 20px;
  align-items: start;
}
.page-root.is-wide .reminders-footer {
  grid-column: 1 / -1;
}

@container binspage (min-width: 900px) {
  .page-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
    gap: 20px;
    align-items: start;
  }
  .reminders-footer {
    grid-column: 1 / -1;
  }
}

.page-section {
  padding: 20px;
  border-radius: var(--ha-card-border-radius, 12px);
  box-sizing: border-box;
}

.page-root.is-narrow .page-section {
  padding: 16px 14px;
}

.section-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--secondary-text-color);
  margin: 0 0 14px 0;
  letter-spacing: .01em;
}

/* Next up hero */
.hero-card {
  border-top: 4px solid transparent;
  overflow: hidden;
}
.hero-card.accent-amber {
  border-top-color: var(--bins-orange);
  background: color-mix(in srgb, var(--warning-color, #ffa600) 6%, var(--card-background-color, #fff));
}
.hero-card.accent-strong-amber {
  border-top-color: var(--bins-orange);
  background: color-mix(in srgb, var(--warning-color, #ffa600) 11%, var(--card-background-color, #fff));
}
.hero-card.accent-green {
  border-top-color: var(--bins-green);
  background: color-mix(in srgb, var(--bins-green) 7%, var(--card-background-color, #fff));
}
.hero-card.accent-red {
  border-top-color: var(--error-color, #db4437);
  background: color-mix(in srgb, var(--error-color, #db4437) 8%, var(--card-background-color, #fff));
}
.hero-card.accent-neutral {
  border-top-color: color-mix(in srgb, var(--primary-text-color) 16%, transparent);
}

.hero-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 16px;
}

@container binspage (min-width: 520px) {
  .hero-body {
    flex-direction: row;
    text-align: left;
    align-items: center;
    gap: 24px;
  }
}
.page-root.is-medium .hero-body,
.page-root.is-wide .hero-body {
  flex-direction: row;
  text-align: left;
  align-items: center;
  gap: 24px;
}

.hero-bins {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  flex-shrink: 0;
  padding: 4px 6px;
  max-width: 100%;
}
.hero-bin {
  position: relative;
  width: 136px;
  transition: transform .2s ease;
  flex-shrink: 1;
}
.hero-bins.two .hero-bin {
  width: 112px;
}
.hero-bins.overlap .hero-bin {
  width: 96px;
}
.hero-bins.overlap .hero-bin + .hero-bin {
  margin-left: -24px;
}
.page-root.is-narrow .hero-bin {
  width: 124px;
}
.page-root.is-narrow .hero-bins.two .hero-bin {
  width: 102px;
}
.page-root.is-narrow .hero-bins.overlap .hero-bin {
  width: 88px;
}
.hero-bin .badge {
  width: 28px;
  height: 28px;
  font-size: 15px;
  top: -2px;
  right: -2px;
}

.hero-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.hero-headline {
  margin: 0;
  font-size: 26px;
  line-height: 1.2;
  font-weight: 700;
  color: var(--primary-text-color);
  word-break: break-word;
}
.page-root.is-narrow .hero-headline {
  font-size: 23px;
}

.hero-subtitle {
  display: inline-flex;
  align-items: flex-start;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  line-height: 1.45;
  color: var(--secondary-text-color);
}
@container binspage (min-width: 520px) {
  .hero-subtitle { justify-content: flex-start; }
}
.page-root.is-medium .hero-subtitle,
.page-root.is-wide .hero-subtitle {
  justify-content: flex-start;
}

.hero-icon {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--secondary-text-color);
}
.accent-amber .hero-icon,
.accent-strong-amber .hero-icon {
  color: color-mix(in srgb, var(--bins-orange) 80%, var(--primary-text-color));
}
.accent-green .hero-icon {
  color: color-mix(in srgb, var(--bins-green) 80%, var(--primary-text-color));
}
.accent-red .hero-icon {
  color: color-mix(in srgb, var(--error-color, #db4437) 80%, var(--primary-text-color));
}

.hero-actions {
  margin-top: 4px;
  display: flex;
  justify-content: center;
}
@container binspage (min-width: 520px) {
  .hero-actions { justify-content: flex-start; }
}
.page-root.is-medium .hero-actions,
.page-root.is-wide .hero-actions {
  justify-content: flex-start;
}

.hero-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 48px;
  min-width: 48px;
  padding: 10px 22px;
  border-radius: 12px;
  font: inherit;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: transform .15s ease, background .15s ease, box-shadow .15s ease;
  outline: none;
  box-sizing: border-box;
}
.hero-btn.primary {
  background: #237d35;
  border: 2px solid var(--bins-green);
  color: #ffffff;
  box-shadow: 0 2px 6px rgba(46, 158, 68, 0.28);
}
.hero-btn.primary:hover {
  background: #1d6b2d;
  transform: translateY(-1px);
}
.hero-btn.primary:active {
  transform: scale(0.98);
}
.hero-btn.secondary {
  background: color-mix(in srgb, var(--primary-text-color) 7%, transparent);
  border: 1px solid var(--divider-color, rgba(127,127,127,.3));
  color: var(--primary-text-color);
}
.hero-btn.secondary:hover {
  background: color-mix(in srgb, var(--primary-text-color) 12%, transparent);
}
.hero-btn:focus-visible {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--bins-green) 65%, transparent);
}
.hero-btn[disabled] {
  opacity: 0.45;
  cursor: default;
  transform: none;
}

@keyframes heroSuccessBounce {
  0% { transform: scale(1); }
  40% { transform: scale(1.045); }
  100% { transform: scale(1); }
}
.hero-bounce {
  animation: heroSuccessBounce 0.38s ease-out;
}

/* Your bins in page view */
.page-bins {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
}
.page-root.is-narrow .page-bins {
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 10px;
}
.page-bins .bin {
  padding: 14px 10px 12px;
  min-height: 48px;
}
.page-bins .bin:hover {
  transform: translateY(-2px);
}
.page-bins .bin:active {
  transform: scale(.98);
}
.page-bins .s-tomorrow .label,
.page-bins .s-today .label {
  color: color-mix(in srgb, var(--warning-color, #ffa600) 48%, var(--primary-text-color));
}
.page-bins .s-out .label,
.page-bins .s-collected .label {
  color: color-mix(in srgb, var(--success-color, #43a047) 58%, var(--primary-text-color));
}
.page-bins .s-forgotten .label,
.page-bins .cancelled-line {
  color: color-mix(in srgb, var(--error-color, #db4437) 68%, var(--primary-text-color));
}

/* Month calendar */
.cal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.cal-header .section-title {
  margin: 0;
}
.cal-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}
.cal-month-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--primary-text-color);
  margin-right: 4px;
  min-width: 115px;
  text-align: right;
}
.page-root.is-narrow .cal-month-label {
  font-size: 14px;
  min-width: 0;
}
.cal-nav-btn, .cal-today-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  min-height: 44px;
  padding: 0 8px;
  border-radius: 8px;
  border: 1px solid var(--divider-color, rgba(127,127,127,.25));
  background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
  color: var(--primary-text-color);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background .15s ease;
  outline: none;
  box-sizing: border-box;
}
.cal-nav-btn:hover, .cal-today-btn:hover {
  background: color-mix(in srgb, var(--primary-text-color) 10%, transparent);
}
.cal-nav-btn:focus-visible, .cal-today-btn:focus-visible {
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--bins-green) 60%, transparent);
}

.cal-grid-wrap {
  position: relative;
}
.cal-weekdays {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
  margin-bottom: 4px;
  text-align: center;
}
.cal-wd {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: var(--secondary-text-color);
  padding: 4px 0;
}
.cal-month-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
}
.cal-day {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 4px;
  min-height: 46px;
  padding: 6px 2px 5px;
  border-radius: 8px;
  border: 1.5px solid transparent;
  background: transparent;
  color: var(--primary-text-color);
  font: inherit;
  cursor: pointer;
  box-sizing: border-box;
  outline: none;
  user-select: none;
  transition: background .15s ease, border-color .15s ease;
}
.cal-day.empty {
  cursor: default;
  pointer-events: none;
}
.cal-day:not(.empty):hover {
  background: color-mix(in srgb, var(--primary-text-color) 9%, transparent);
}
.cal-day:focus-visible {
  box-shadow: 0 0 0 2.5px var(--bins-green);
  z-index: 2;
}
.cal-day.next-week {
  background: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
  border-color: color-mix(in srgb, var(--primary-text-color) 10%, transparent);
}
.cal-day.has-events {
  background: color-mix(in srgb, var(--primary-text-color) 6%, transparent);
}
.cal-day.next-week.has-events {
  background: color-mix(in srgb, var(--bins-green) 10%, transparent);
}
.cal-day.today {
  border-color: var(--bins-orange);
  background: color-mix(in srgb, var(--bins-orange) 14%, transparent);
}
.cal-day.selected {
  border-color: var(--bins-green);
  background: color-mix(in srgb, var(--bins-green) 16%, transparent);
}
.cal-num {
  font-size: 13px;
  font-weight: 500;
  line-height: 1.1;
  color: var(--primary-text-color);
}
.cal-day.today .cal-num,
.cal-day.next-week .cal-num {
  font-weight: 700;
}
.cal-day .dots {
  gap: 2px;
  min-height: 9px;
}
.cal-day .dot {
  width: 7px;
  height: 7px;
}
.dot-more {
  font-size: 9px;
  font-weight: 700;
  line-height: 1;
  color: var(--secondary-text-color);
}

/* Day popover */
.cal-popover {
  position: absolute;
  z-index: 90;
  box-sizing: border-box;
  background: var(--card-background-color, #fff);
  color: var(--primary-text-color);
  border: 1px solid var(--divider-color, rgba(127,127,127,.35));
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0,0,0,.25);
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.4;
  max-width: calc(100% - 8px);
}
.pop-date {
  font-weight: 600;
  color: var(--primary-text-color);
}
.pop-bin {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* Coming up list */
.coming-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.coming-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 6px;
  padding: 8px 10px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--primary-text-color) 4%, transparent);
  font-size: 14px;
}
.coming-date {
  font-weight: 600;
  color: var(--primary-text-color);
}
.coming-rel {
  color: var(--secondary-text-color);
  font-size: 13px;
}
.coming-dash {
  color: var(--secondary-text-color);
}
.coming-bins {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
}
.coming-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--primary-text-color);
}
.coming-item em {
  font-style: italic;
  color: var(--secondary-text-color);
}

/* Reminders footer */
.reminders-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 4px 8px;
  padding: 6px 12px;
  font-size: 13px;
  color: var(--secondary-text-color);
  text-align: center;
}
.change-link {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  padding: 0 8px;
  border-radius: 6px;
  color: color-mix(in srgb, var(--bins-green) 65%, var(--primary-text-color));
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
  outline: none;
}
.change-link:hover {
  background: color-mix(in srgb, var(--primary-text-color) 6%, transparent);
}
.change-link:focus-visible {
  box-shadow: 0 0 0 2.5px var(--bins-green);
}

/* Empty state */
.page-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 40px 20px;
  gap: 14px;
}
.empty-art {
  width: 112px;
}
.empty-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--primary-text-color);
}
.empty-sub {
  margin: 0;
  font-size: 14px;
  color: var(--secondary-text-color);
  max-width: 360px;
}

@media (prefers-reduced-motion: reduce) {
  .bin, .bin-art, .hero-bin, .hero-btn, .cal-day, .cal-nav-btn, .cal-today-btn, .page-bins .bin {
    transition: none !important;
  }
  .s-tomorrow.due, .s-today, .hero-bounce {
    animation: none !important;
  }
  .page-bins .bin:hover, .hero-btn.primary:hover, .bin:active, .hero-btn.primary:active {
    transform: none !important;
  }
}
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

    // Page view state
    const now = new Date();
    this._calYear = now.getFullYear();
    this._calMonth = now.getMonth();
    this._calCacheKey = null;
    this._calEvents = null;
    this._openCalDate = null;
    this._calPopoverDocHandler = null;
    this._calPopoverKeyHandler = null;
    this._heroBounceUntil = 0;
    this._widthBand = "narrow";
    this._resizeObserver = null;
  }

  static getStubConfig() {
    return { entity: DEFAULT_ENTITY };
  }

  static getConfigElement() {
    return document.createElement("bins-out-card-editor");
  }

  connectedCallback() {
    if (typeof ResizeObserver === "function" && !this._resizeObserver) {
      this._resizeObserver = new ResizeObserver((entries) => {
        const w = entries[0]?.contentRect?.width ?? this.getBoundingClientRect().width;
        this._applyWidthBand(w);
      });
      this._resizeObserver.observe(this);
    }
    this._applyWidthBand(this.getBoundingClientRect().width);
  }

  disconnectedCallback() {
    this._closeMenu();
    this._closeCalPopover();
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
  }

  _applyWidthBand(width) {
    if (!width) return;
    const band = width >= 900 ? "wide" : width >= 700 ? "medium" : "narrow";
    this._widthBand = band;
    const root = this.shadowRoot && this.shadowRoot.querySelector(".page-root");
    if (root) {
      root.classList.toggle("is-narrow", band === "narrow");
      root.classList.toggle("is-medium", band === "medium");
      root.classList.toggle("is-wide", band === "wide");
    }
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Invalid configuration");
    const days = config.days === undefined ? 14 : Number(config.days);
    if (!Number.isFinite(days) || days < 7 || days > 35) throw new Error("days must be between 7 and 35");
    const layout = config.layout || "auto";
    if (!["auto", "row", "list"].includes(layout)) throw new Error('layout must be "auto", "row" or "list"');
    const view = config.view || "card";
    if (!["card", "page"].includes(view)) throw new Error('view must be "card" or "page"');
    if (config.entity !== undefined && typeof config.entity !== "string") throw new Error("entity must be a string");
    this._config = {
      entity: config.entity || DEFAULT_ENTITY,
      title: config.title === undefined ? "Bins" : String(config.title),
      show_calendar: config.show_calendar !== false,
      days: Math.round(days),
      layout,
      view,
    };
    this._lastKey = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    if (this._config && this._config.view === "page") return 10;
    return this._config && this._config.show_calendar ? 5 : 3;
  }

  _render() {
    if (!this._config || !this._hass) return;
    const stateObj = this._hass.states[this._config.entity];
    // Re-render only when the entity changes, or once a day (so "today" moves on).
    const key = stateObj
      ? `${this._config.view}|${stateObj.last_updated}|${isoLocal(new Date())}`
      : `${this._config.view}|missing`;
    if (key === this._lastKey) return;
    this._lastKey = key;

    this._closeMenu();
    this._closeCalPopover();

    if (!stateObj) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style>
        <ha-card><div class="warning">Bins Out entity not found: <code>${esc(this._config.entity)}</code></div></ha-card>`;
      return;
    }

    const a = stateObj.attributes || {};
    const bins = Array.isArray(a.bins) ? a.bins : [];
    this._bins = bins;
    const cfg = this._config;

    if (cfg.view === "page") {
      this._renderPage(stateObj, a, bins);
      return;
    }

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
      ? `<div class="bins ${layoutClass}">${bins.map((b, i) => this._binHtml(b, i, false)).join("")}</div>`
      : `<div class="empty">No bins configured yet.</div>`;

    const cal = cfg.show_calendar && bins.length ? this._calendarHtml(bins, cfg.days) : "";

    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${header}${banner}${binsHtml}${cal}</ha-card>`;
    this._attachBinHandlers();
  }

  /* ---------- page view rendering ---------- */

  _renderPage(stateObj, a, bins) {
    const w = this.getBoundingClientRect().width;
    if (w) {
      this._widthBand = w >= 900 ? "wide" : w >= 700 ? "medium" : "narrow";
    }
    const bandClass = `is-${this._widthBand}`;

    if (!bins.length) {
      const sampleBin = { container: "wheelie_bin", colour_hex: "#2e9e44", status: "upcoming" };
      this.shadowRoot.innerHTML = `<style>${STYLE}</style>
        <div class="page-root ${bandClass}">
          <ha-card class="page-section page-empty">
            <div class="empty-art" role="img" aria-label="Wheelie bin">${binSvg(sampleBin)}</div>
            <h2 class="empty-title">No bins yet</h2>
            <p class="empty-sub">Add your bins in Bins Out settings to see collection days and get reminders.</p>
            <button type="button" class="hero-btn primary" id="setupBinsBtn">Set up your bins</button>
          </ha-card>
        </div>`;
      const setupBtn = this.shadowRoot.getElementById("setupBinsBtn");
      if (setupBtn) {
        setupBtn.addEventListener("click", () => navigateToSettings());
      }
      return;
    }

    if (!this._calMonthChosen) {
      this._calMonthChosen = true;
      const firstDate = bins
        .map((b) => b.next_collection || (b.upcoming || [])[0])
        .filter(Boolean)
        .sort()[0];
      const first = parseLocalDate(firstDate);
      if (first && first.getFullYear() * 12 + first.getMonth() > this._calYear * 12 + this._calMonth) {
        this._calYear = first.getFullYear();
        this._calMonth = first.getMonth();
      }
    }

    this._ensureMonthEvents(stateObj);

    const heroHtml = this._heroSectionHtml(a, bins);
    const yourBinsHtml = `
      <ha-card class="page-section bins-section">
        <div class="section-title">Your bins</div>
        <div class="page-bins">${bins.map((b, i) => this._binHtml(b, i, true)).join("")}</div>
      </ha-card>`;
    const calSectionHtml = this._monthCalendarSectionHtml();
    const comingUpHtml = this._comingUpSectionHtml(bins);
    const remindersHtml = this._remindersFooterHtml(a);

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <div class="page-root ${bandClass}">
        <div class="page-grid">
          <div class="col-left">
            ${heroHtml}
            ${yourBinsHtml}
          </div>
          <div class="col-right">
            ${calSectionHtml}
            ${comingUpHtml}
          </div>
          ${remindersHtml}
        </div>
      </div>`;

    this._attachBinHandlers();
    this._attachPageHandlers();
  }

  _getHeroBins(a, bins) {
    const nextNames = Array.isArray(a.next_bins) ? a.next_bins : [];
    let heroBins = nextNames.map((n) => bins.find((b) => b.name === n)).filter(Boolean);
    if (!heroBins.length && bins.length) {
      const firstWithDays = bins.find((b) => b.days_until !== null && b.days_until !== undefined);
      if (firstWithDays) {
        heroBins = bins.filter((b) => b.days_until === firstWithDays.days_until);
      } else {
        heroBins = [bins[0]];
      }
    }
    return heroBins;
  }

  _heroSectionHtml(a, bins) {
    const heroBins = this._getHeroBins(a, bins);
    this._heroBins = heroBins;

    let headline = "";
    let subtitle = "";
    let accent = "neutral";
    let icon = "calendar";
    let action = null;

    const forgottenBins = heroBins.filter((b) => b.status === "forgotten");
    const todayBins = heroBins.filter((b) => b.status === "today");
    const tomorrowBins = heroBins.filter((b) => b.status === "tomorrow");
    const allOut = heroBins.length > 0 && heroBins.every((b) => b.status === "out");
    const anyCollected = heroBins.some((b) => b.status === "collected");

    if (forgottenBins.length) {
      headline = `Missed: ${joinSpokenNames(forgottenBins)}`;
      subtitle = a.forgotten_message || "";
      accent = "red";
      icon = "warning";
      action = "mark_out";
    } else if (todayBins.length) {
      headline = `Put the ${joinSpokenNames(todayBins)} out now`;
      subtitle = a.morning_message || "";
      accent = "strong-amber";
      icon = "sunrise";
      action = "mark_out";
    } else if (tomorrowBins.length) {
      headline = `Tonight: ${joinSpokenNames(tomorrowBins)} out`;
      subtitle = a.tonight_message || "";
      accent = "amber";
      icon = "moon";
      action = "mark_out";
    } else if (allOut) {
      headline = "All out. Nice one!";
      const nextDt = parseLocalDate(heroBins[0]?.next_collection);
      const rel = relDaysPage(heroBins[0]?.days_until);
      subtitle = nextDt ? `Collection ${fmtDate(nextDt)}${rel ? " · " + rel : ""}` : "";
      accent = "green";
      icon = "tick";
      action = "undo";
    } else if (anyCollected) {
      headline = "Collected: bring it back in";
      subtitle = "";
      accent = "green";
      icon = "tick";
      action = null;
    } else {
      headline = `Next: ${joinSpokenNames(heroBins)}`;
      const nextDt = parseLocalDate(heroBins[0]?.next_collection);
      const rel = inDays(heroBins[0]?.days_until);
      subtitle = nextDt ? `${fmtDate(nextDt)}${rel ? " · " + rel : ""}` : "No upcoming collections";
      accent = "neutral";
      icon = "calendar";
      action = null;
    }

    const binsCountClass = heroBins.length >= 3 ? "overlap" : heroBins.length === 2 ? "two" : "one";
    const picturesHtml = heroBins.map((b) => {
      const picBin = b.status === "upcoming" ? { ...b, status: "tomorrow" } : b;
      const aria = b.spoken_name || b.name;
      return `<div class="hero-bin" role="img" aria-label="${esc(aria)}">${binSvg(picBin)}${badgeFor(b.status)}</div>`;
    }).join("");

    const subtitleHtml = subtitle
      ? `<div class="hero-subtitle" role="${forgottenBins.length ? "alert" : "status"}">
           <span class="hero-icon">${pageIconSvg(icon)}</span>
           <span>${esc(subtitle)}</span>
         </div>`
      : "";

    let actionHtml = "";
    if (action === "mark_out") {
      const targets = heroBins.filter((b) => !b.put_out && b.entities && b.entities.put_out);
      const canAct = targets.length > 0 || heroBins.some((b) => b.entities && b.entities.put_out);
      actionHtml = `
        <div class="hero-actions">
          <button type="button" class="hero-btn primary" id="heroActionBtn" data-action="mark_out" ${canAct ? "" : "disabled"}>
            ${pageIconSvg("tick")}
            <span class="btn-text">Mark as out</span>
          </button>
        </div>`;
    } else if (action === "undo") {
      const canAct = heroBins.some((b) => b.entities && b.entities.put_out);
      actionHtml = `
        <div class="hero-actions">
          <button type="button" class="hero-btn secondary" id="heroActionBtn" data-action="undo" ${canAct ? "" : "disabled"}>
            ${pageIconSvg("undo")}
            <span class="btn-text">Undo</span>
          </button>
        </div>`;
    }

    const bounceClass = Date.now() < this._heroBounceUntil ? "hero-bounce" : "";

    return `
      <ha-card class="page-section hero-card accent-${accent} ${bounceClass}">
        <div class="section-title">Next up</div>
        <div class="hero-body">
          <div class="hero-bins ${binsCountClass}">${picturesHtml}</div>
          <div class="hero-info">
            <h2 class="hero-headline">${esc(headline)}</h2>
            ${subtitleHtml}
            ${actionHtml}
          </div>
        </div>
      </ha-card>`;
  }

  _monthCalendarSectionHtml() {
    const monthLabel = `${MONTH_FULL_NAMES[this._calMonth]} ${this._calYear}`;
    return `
      <ha-card class="page-section cal-section">
        <div class="cal-header">
          <div class="section-title">Calendar</div>
          <div class="cal-nav">
            <span class="cal-month-label" id="calMonthLabel">${esc(monthLabel)}</span>
            <button type="button" class="cal-nav-btn" id="calPrevBtn" aria-label="Previous month">${pageIconSvg("chevronLeft")}</button>
            <button type="button" class="cal-today-btn" id="calTodayBtn">Today</button>
            <button type="button" class="cal-nav-btn" id="calNextBtn" aria-label="Next month">${pageIconSvg("chevronRight")}</button>
          </div>
        </div>
        <div class="cal-grid-wrap" id="calGridWrap">
          ${this._monthCalendarInnerHtml()}
        </div>
      </ha-card>`;
  }

  _buildMonthDateMap() {
    const bins = this._bins || [];
    const byDate = new Map();
    const seenKey = new Set();

    const movedByBin = new Map();
    for (const bin of bins) {
      const m = {};
      for (const [orig, dest] of Object.entries(bin.moved || {})) m[dest] = orig;
      movedByBin.set(bin, m);
    }

    const addEntry = (dateStr, bin, { movedFrom = null, cancelled = false, estimated = false } = {}) => {
      if (!dateStr) return;
      const k = `${dateStr}|${bin.id || bin.name}|${cancelled ? "c" : "a"}`;
      if (seenKey.has(k)) return;
      seenKey.add(k);
      if (!byDate.has(dateStr)) byDate.set(dateStr, []);
      byDate.get(dateStr).push({ bin, movedFrom, cancelled, estimated });
    };

    if (Array.isArray(this._calEvents) && this._calEvents.length > 0) {
      for (const ev of this._calEvents) {
        const rawStart = ev.start?.date || ev.start?.dateTime || ev.start || "";
        const dateStr = String(rawStart).slice(0, 10);
        if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) continue;
        const summary = String(ev.summary || "").trim();
        const isEst = summary.endsWith(" (estimated)");
        const binName = isEst ? summary.slice(0, -12).trim() : summary;
        const bin = bins.find((b) => b.name === binName)
          || bins.find((b) => b.name.toLowerCase() === binName.toLowerCase());
        if (!bin) continue;
        if (Array.isArray(bin.cancelled) && bin.cancelled.includes(dateStr)) continue;
        const movedFrom = movedByBin.get(bin)?.[dateStr] || null;
        addEntry(dateStr, bin, { movedFrom, cancelled: false, estimated: isEst });
      }
    } else {
      // Fallback: build from bins[].upcoming and bins[].estimated
      for (const bin of bins) {
        const movedFromMap = movedByBin.get(bin) || {};
        const estSet = new Set(Array.isArray(bin.estimated) ? bin.estimated : []);
        for (const d of bin.upcoming || []) {
          addEntry(d, bin, {
            movedFrom: movedFromMap[d] || null,
            cancelled: false,
            estimated: estSet.has(d),
          });
        }
      }
    }

    // Cancelled collections are never calendar events: draw from bins[].cancelled
    for (const bin of bins) {
      for (const d of bin.cancelled || []) {
        addEntry(d, bin, { movedFrom: null, cancelled: true, estimated: false });
      }
    }

    // Keep bin order consistent with this._bins
    const binOrder = new Map(bins.map((b, idx) => [b, idx]));
    for (const entries of byDate.values()) {
      entries.sort((a, b) => (binOrder.get(a.bin) ?? 99) - (binOrder.get(b.bin) ?? 99));
    }

    return byDate;
  }

  _monthCalendarInnerHtml() {
    const year = this._calYear;
    const month = this._calMonth;
    const bins = this._bins || [];
    const byDate = this._buildMonthDateMap();
    this._lastMonthByDate = byDate;

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayTime = today.getTime();
    const todayIso = isoLocal(today);

    const firstDay = new Date(year, month, 1);
    const numDays = new Date(year, month + 1, 0).getDate();
    // Monday-first: Monday = 0 ... Sunday = 6
    const startOffset = (firstDay.getDay() + 6) % 7;

    let anyCancelledInMonth = false;
    let anyEstimatedInMonth = false;
    let anyMovedInMonth = false;

    const cells = [];
    for (let i = 0; i < startOffset; i++) {
      cells.push(`<div class="cal-day empty" aria-hidden="true"></div>`);
    }

    for (let d = 1; d <= numDays; d++) {
      const date = new Date(year, month, d);
      const iso = isoLocal(date);
      const diffDays = Math.round((date.getTime() - todayTime) / 86400000);
      const entries = byDate.get(iso) || [];
      const hasMoved = entries.some((e) => e.movedFrom);
      if (hasMoved) anyMovedInMonth = true;
      if (entries.some((e) => e.cancelled)) anyCancelledInMonth = true;
      if (entries.some((e) => e.estimated)) anyEstimatedInMonth = true;

      const labelParts = entries.map((e) => this._entryLabel(e));
      const dayTitle = `${fmtDate(date)}${labelParts.length ? ": " + labelParts.join(", ") : ": no collections"}`;

      const visibleDots = entries.slice(0, 4);
      const extraCount = entries.length > 4 ? entries.length - 4 : 0;

      const dotsHtml = visibleDots.map((e) => this._dotHtml(e)).join("")
        + (extraCount > 0 ? `<span class="dot-more">+${extraCount}</span>` : "");

      const isToday = iso === todayIso;
      const isNextWeek = diffDays >= 1 && diffDays <= 7;
      const isSelected = this._openCalDate === iso;

      cells.push(`
        <button type="button"
                class="cal-day ${isToday ? "today" : ""} ${isNextWeek ? "next-week" : ""} ${entries.length ? "has-events" : ""} ${isSelected ? "selected" : ""}"
                data-date="${iso}"
                aria-label="${esc(dayTitle)}"
                aria-expanded="${isSelected ? "true" : "false"}">
          ${hasMoved ? `<span class="moved" aria-hidden="true"></span>` : ""}
          <span class="cal-num">${d}</span>
          <span class="dots" aria-hidden="true">${dotsHtml}</span>
        </button>`);
    }

    const totalCells = startOffset + numDays;
    const trailing = (7 - (totalCells % 7)) % 7;
    for (let i = 0; i < trailing; i++) {
      cells.push(`<div class="cal-day empty" aria-hidden="true"></div>`);
    }

    const legend = bins.map((b) => {
      const c = safeColour(b.colour_hex);
      return `<span><span class="dot ${toneClass(c)}" style="background:${c}"></span>${esc(b.name)}</span>`;
    }).join("")
      + (anyCancelledInMonth ? `<span><span class="dot cancelled" style="--dot-color:var(--secondary-text-color)"></span>Cancelled</span>` : "")
      + (anyEstimatedInMonth ? `<span><span class="dot estimated" style="--dot-color:var(--secondary-text-color)"></span>Estimated</span>` : "")
      + (anyMovedInMonth ? `<span><span class="moved" style="position:static"></span>Moved date</span>` : "");

    const weekdaysHtml = WEEKDAY_MON.map((w) => `<div class="cal-wd">${w}</div>`).join("");

    return `
      <div class="cal-weekdays" aria-hidden="true">${weekdaysHtml}</div>
      <div class="cal-month-grid">${cells.join("")}</div>
      <div class="legend">${legend}</div>`;
  }

  _dotHtml(e) {
    const c = safeColour(e.bin.colour_hex);
    if (e.cancelled) {
      return `<span class="dot cancelled ${toneClass(c)}" style="--dot-color:${c}"></span>`;
    }
    if (e.estimated) {
      return `<span class="dot estimated ${toneClass(c)}" style="--dot-color:${c}"></span>`;
    }
    return `<span class="dot ${toneClass(c)}" style="background:${c}"></span>`;
  }

  _entryLabel(e) {
    let t = e.bin.name;
    if (e.cancelled) {
      t += " (cancelled)";
    } else if (e.estimated) {
      t += " (estimated)";
    } else if (e.movedFrom) {
      const o = parseLocalDate(e.movedFrom);
      t += ` (moved from ${o ? fmtDate(o) : e.movedFrom})`;
    }
    return t;
  }

  _ensureMonthEvents(stateObj) {
    if (!this._hass || typeof this._hass.callApi !== "function") return;
    const stateUpdated = stateObj ? stateObj.last_updated : "";
    const ym = `${this._calYear}-${String(this._calMonth + 1).padStart(2, "0")}`;
    const cacheKey = `${stateUpdated}|${ym}`;
    if (this._calCacheKey === cacheKey) return;
    this._calCacheKey = cacheKey;
    this._calEvents = null;

    const startIso = `${this._calYear}-${String(this._calMonth + 1).padStart(2, "0")}-01T00:00:00Z`;
    const nextYear = this._calMonth === 11 ? this._calYear + 1 : this._calYear;
    const nextMonth = this._calMonth === 11 ? 0 : this._calMonth + 1;
    const endIso = `${nextYear}-${String(nextMonth + 1).padStart(2, "0")}-01T00:00:00Z`;

    let req;
    try {
      req = this._hass.callApi(
        "GET",
        `calendars/calendar.bins_out_collections?start=${startIso}&end=${endIso}`,
      );
    } catch (_err) {
      return;
    }
    if (!req || typeof req.then !== "function") return;

    req.then(
      (events) => {
        if (this._calCacheKey !== cacheKey) return;
        this._calEvents = Array.isArray(events) ? events : null;
        this._refreshMonthGridDom();
      },
      () => {
        // Fallback silently to bins[].upcoming on failure
        if (this._calCacheKey !== cacheKey) return;
        this._calEvents = null;
      },
    );
  }

  _refreshMonthGridDom() {
    if (!this.shadowRoot) return;
    const labelEl = this.shadowRoot.getElementById("calMonthLabel");
    if (labelEl) {
      labelEl.textContent = `${MONTH_FULL_NAMES[this._calMonth]} ${this._calYear}`;
    }
    const wrap = this.shadowRoot.getElementById("calGridWrap");
    if (!wrap) return;
    const openDate = this._openCalDate;
    this._closeCalPopover();
    wrap.innerHTML = this._monthCalendarInnerHtml();
    this._attachCalendarDayHandlers();
    if (openDate) {
      const btn = wrap.querySelector(`.cal-day[data-date="${openDate}"]`);
      if (btn) this._openCalPopover(openDate, btn);
    }
  }

  _comingUpSectionHtml(bins) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayTime = today.getTime();
    const todayIso = isoLocal(today);

    const byDate = new Map();
    for (const bin of bins) {
      const estSet = new Set(Array.isArray(bin.estimated) ? bin.estimated : []);
      const cancSet = new Set(Array.isArray(bin.cancelled) ? bin.cancelled : []);
      for (const d of bin.upcoming || []) {
        if (d < todayIso || cancSet.has(d)) continue;
        if (!byDate.has(d)) byDate.set(d, []);
        byDate.get(d).push({ bin, estimated: estSet.has(d) });
      }
    }

    const nextDates = Array.from(byDate.keys()).sort().slice(0, 5);

    const rowsHtml = nextDates.length
      ? nextDates.map((d) => {
          const dt = parseLocalDate(d);
          const diff = dt ? Math.round((dt.getTime() - todayTime) / 86400000) : null;
          const rel = relDaysPage(diff);
          const entries = byDate.get(d) || [];
          const binsHtml = entries.map((e, idx) => {
            const c = safeColour(e.bin.colour_hex);
            const dot = e.estimated
              ? `<span class="dot estimated ${toneClass(c)}" style="--dot-color:${c}" aria-hidden="true"></span>`
              : `<span class="dot ${toneClass(c)}" style="background:${c}" aria-hidden="true"></span>`;
            const comma = idx < entries.length - 1 ? "," : "";
            const namePart = e.estimated
              ? `<em>${esc(e.bin.name)} (estimated)${comma}</em>`
              : `<span>${esc(e.bin.name)}${comma}</span>`;
            return `<span class="coming-item">${dot}${namePart}</span>`;
          }).join(" ");
          return `
            <div class="coming-row">
              <span class="coming-date">${esc(dt ? fmtDate(dt) : d)}</span>
              ${rel ? `<span class="coming-rel">· ${esc(rel)}</span>` : ""}
              <span class="coming-dash">—</span>
              <span class="coming-bins">${binsHtml}</span>
            </div>`;
        }).join("")
      : `<div class="empty">No upcoming collections scheduled.</div>`;

    return `
      <ha-card class="page-section coming-section">
        <div class="section-title">Coming up</div>
        <div class="coming-list">${rowsHtml}</div>
      </ha-card>`;
  }

  _remindersFooterHtml(a) {
    const eve = fmtShortTime(a.evening_time, "19:00");
    const morn = fmtShortTime(a.morning_time, "06:30");
    return `
      <div class="reminders-footer">
        <span>Reminders at <strong>${esc(eve)}</strong> the night before and <strong>${esc(morn)}</strong> on the day.</span>
        <a href="${SETTINGS_PATH}" class="change-link" id="changeRemindersLink">Change</a>
      </div>`;
  }

  _attachPageHandlers() {
    const root = this.shadowRoot;
    if (!root) return;

    // Hero primary / undo button
    const heroBtn = root.getElementById("heroActionBtn");
    if (heroBtn) {
      heroBtn.addEventListener("click", () => {
        const action = heroBtn.dataset.action;
        const heroBins = this._heroBins || [];
        this._heroBounceUntil = Date.now() + 700;
        const heroCard = heroBtn.closest(".hero-card");
        if (heroCard) {
          heroCard.classList.remove("hero-bounce");
          void heroCard.offsetWidth;
          heroCard.classList.add("hero-bounce");
        }
        const textEl = heroBtn.querySelector(".btn-text");
        if (action === "mark_out") {
          if (textEl) textEl.textContent = "Marked as out ✓";
          let targets = heroBins.filter((b) => !b.put_out && b.entities && b.entities.put_out);
          if (!targets.length) {
            targets = heroBins.filter((b) => b.entities && b.entities.put_out);
          }
          for (const b of targets) {
            this._hass.callService("switch", "turn_on", { entity_id: b.entities.put_out });
          }
        } else if (action === "undo") {
          if (textEl) textEl.textContent = "Undone";
          const targets = heroBins.filter((b) => b.entities && b.entities.put_out);
          for (const b of targets) {
            this._hass.callService("switch", "turn_off", { entity_id: b.entities.put_out });
          }
        }
      });
    }

    // Calendar month controls
    const prevBtn = root.getElementById("calPrevBtn");
    const nextBtn = root.getElementById("calNextBtn");
    const todayBtn = root.getElementById("calTodayBtn");

    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        this._closeCalPopover();
        if (this._calMonth === 0) {
          this._calMonth = 11;
          this._calYear -= 1;
        } else {
          this._calMonth -= 1;
        }
        const stateObj = this._hass?.states?.[this._config.entity];
        this._ensureMonthEvents(stateObj);
        this._refreshMonthGridDom();
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        this._closeCalPopover();
        if (this._calMonth === 11) {
          this._calMonth = 0;
          this._calYear += 1;
        } else {
          this._calMonth += 1;
        }
        const stateObj = this._hass?.states?.[this._config.entity];
        this._ensureMonthEvents(stateObj);
        this._refreshMonthGridDom();
      });
    }
    if (todayBtn) {
      todayBtn.addEventListener("click", () => {
        this._closeCalPopover();
        const now = new Date();
        this._calYear = now.getFullYear();
        this._calMonth = now.getMonth();
        const stateObj = this._hass?.states?.[this._config.entity];
        this._ensureMonthEvents(stateObj);
        this._refreshMonthGridDom();
      });
    }

    this._attachCalendarDayHandlers();

    // Change reminders link
    const changeLink = root.getElementById("changeRemindersLink");
    if (changeLink) {
      changeLink.addEventListener("click", (ev) => {
        ev.preventDefault();
        navigateToSettings();
      });
    }
  }

  _attachCalendarDayHandlers() {
    const wrap = this.shadowRoot && this.shadowRoot.getElementById("calGridWrap");
    if (!wrap) return;
    wrap.querySelectorAll(".cal-day[data-date]").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const dateStr = btn.dataset.date;
        if (this._openCalDate === dateStr) {
          this._closeCalPopover();
        } else {
          this._openCalPopover(dateStr, btn);
        }
      });
    });
  }

  _closeCalPopover() {
    if (this._calPopoverDocHandler) {
      window.removeEventListener("pointerdown", this._calPopoverDocHandler, true);
      this._calPopoverDocHandler = null;
    }
    if (this._calPopoverKeyHandler) {
      window.removeEventListener("keydown", this._calPopoverKeyHandler, true);
      this._calPopoverKeyHandler = null;
    }
    if (this.shadowRoot) {
      this.shadowRoot.querySelectorAll(".cal-popover").forEach((el) => el.remove());
      this.shadowRoot.querySelectorAll(".cal-day.selected").forEach((el) => {
        el.classList.remove("selected");
        el.setAttribute("aria-expanded", "false");
      });
    }
    this._openCalDate = null;
  }

  _openCalPopover(dateStr, dayBtn) {
    this._closeCalPopover();
    const wrap = this.shadowRoot && this.shadowRoot.getElementById("calGridWrap");
    if (!wrap || !dayBtn) return;

    this._openCalDate = dateStr;
    dayBtn.classList.add("selected");
    dayBtn.setAttribute("aria-expanded", "true");

    const dt = parseLocalDate(dateStr);
    const dateLabel = dt ? fmtDate(dt) : dateStr;
    const entries = (this._lastMonthByDate && this._lastMonthByDate.get(dateStr)) || [];

    const pop = document.createElement("div");
    pop.className = "cal-popover";
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-label", `${dateLabel} collections`);

    if (entries.length) {
      const itemsHtml = entries.map((e) => {
        const dot = this._dotHtml(e);
        return `<span class="pop-bin">${dot}<span>${esc(this._entryLabel(e))}</span></span>`;
      }).join(", ");
      pop.innerHTML = `<span class="pop-date">${esc(dateLabel)}:</span> ${itemsHtml}`;
    } else {
      pop.innerHTML = `<span class="pop-date">${esc(dateLabel)}:</span> No collections`;
    }

    wrap.appendChild(pop);

    // Position popover near dayBtn within wrap
    const wrapRect = wrap.getBoundingClientRect();
    const btnRect = dayBtn.getBoundingClientRect();
    const popWidth = pop.offsetWidth || 200;
    const popHeight = pop.offsetHeight || 42;

    const centerX = btnRect.left - wrapRect.left + btnRect.width / 2;
    let left = centerX - popWidth / 2;
    left = Math.max(4, Math.min(wrapRect.width - popWidth - 4, left));

    let top = btnRect.bottom - wrapRect.top + 6;
    if (top + popHeight > wrapRect.height && btnRect.top - wrapRect.top > popHeight + 8) {
      top = btnRect.top - wrapRect.top - popHeight - 6;
    }

    pop.style.left = `${Math.round(left)}px`;
    pop.style.top = `${Math.round(top)}px`;

    this._calPopoverKeyHandler = (ev) => {
      if (ev.key === "Escape") {
        ev.preventDefault();
        ev.stopPropagation();
        this._closeCalPopover();
        dayBtn.focus();
      }
    };
    window.addEventListener("keydown", this._calPopoverKeyHandler, true);

    this._calPopoverDocHandler = (ev) => {
      const path = ev.composedPath();
      if (!path.includes(pop) && !path.includes(dayBtn)) {
        this._closeCalPopover();
      }
    };
    setTimeout(() => {
      if (this._openCalDate === dateStr) {
        window.addEventListener("pointerdown", this._calPopoverDocHandler, true);
      }
    }, 30);
  }

  /* ---------- bin tile & card strip ---------- */

  _binHtml(bin, idx, isPage = false) {
    const status = bin.status || "none";
    const next = parseLocalDate(bin.next_collection);
    const rel = inDays(bin.days_until);
    const when = next ? (isPage ? fmtDate(next) : `${fmtDate(next)} · ${rel}`) : "";
    const freq = isPage ? howOftenText(bin) : "";
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

    const freqLine = freq ? `<div class="freq">${esc(freq)}</div>` : "";

    const cancelledLine = cancelledText
      ? `<div class="cancelled-line">${esc(cancelledText)}</div>`
      : "";

    const aria = `${bin.name}: ${label}${when ? ", " + when : ""}${freq ? ", " + freq : ""}${cancelledText ? ", " + cancelledText : ""}${bin.source === "calendar" ? ", automatic calendar" : ""}${canToggle ? ". Tap to toggle put out." : ""}. Hold for options.`;

    return `
      <div class="bin s-${esc(status)} ${bin.due ? "due" : ""} ${disabled ? "disabled" : ""}"
           data-idx="${idx}" role="button" tabindex="${disabled ? -1 : 0}"
           aria-label="${esc(aria)}" ${disabled ? 'aria-disabled="true"' : ""}>
        <div class="bin-art">${binSvg(bin)}${badgeFor(status)}</div>
        <div class="text">
          <div class="name">${esc(bin.name)}</div>
          <div class="label">${esc(label)}</div>
          ${dateLine}
          ${freqLine}
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

  _attachBinHandlers() {
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
    if (this.shadowRoot) {
      this.shadowRoot.querySelectorAll(".card-menu, .menu-backdrop").forEach((el) => el.remove());
    }
    this._menuBin = null;
  }

  _openMenu(bin, binEl) {
    this._closeMenu();
    this._menuBin = bin;

    const cardEl = (binEl && binEl.closest("ha-card")) || this.shadowRoot.querySelector("ha-card");
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
    const view = c.view || "card";
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
        <label>View
          <select id="view">
            ${["card", "page"].map((v) => `<option value="${v}" ${v === view ? "selected" : ""}>${v}</option>`).join("")}
          </select>
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
    root.getElementById("view").addEventListener("change", (e) => this._set("view", e.target.value));
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
