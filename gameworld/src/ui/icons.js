// Ability icons, as inline SVG.
//
// Inline rather than image files: they're a few hundred bytes each, they need no network
// request and no loading state, and the colours live in the same place as everything else
// they have to read against. A slot must be identifiable by SHAPE at a glance — colour is
// doing enough work already telling you ready from cooling.

export const ICONS = {
  // Heal — a white cross.
  plus: `<svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M9.6 2.6h4.8v7h7v4.8h-7v7H9.6v-7h-7V9.6h7z"
      fill="#ffffff" stroke="#cfe3ff" stroke-width="0.8" stroke-linejoin="round"/></svg>`,

  // Firebomb — a light brown octagon.
  octagon: `<svg viewBox="0 0 24 24" aria-hidden="true">
    <polygon points="8.2,2 15.8,2 22,8.2 22,15.8 15.8,22 8.2,22 2,15.8 2,8.2"
      fill="#c49a6c" stroke="#7d5c3a" stroke-width="1.6" stroke-linejoin="round"/></svg>`,

  // Ring of Fire — a bright red-orange disc with a hotter core.
  burst: `<svg viewBox="0 0 24 24" aria-hidden="true">
    <circle cx="12" cy="12" r="10" fill="#ff5a1e" stroke="#ffb066" stroke-width="1.4"/>
    <circle cx="12" cy="12" r="4.6" fill="#ffd08a" opacity="0.9"/></svg>`,

  // Dash Strike — a blood-red arrow, angled 45° up. Rotated about the icon's centre
  // (negative is anticlockwise in SVG, where y grows downward), so it reads as lunging
  // forward-and-up rather than sliding sideways.
  arrow: `<svg viewBox="0 0 24 24" aria-hidden="true">
    <g transform="rotate(-45 12 12)">
      <path d="M2 9.2h12V4l8 8-8 8v-5.2H2z"
        fill="#a11212" stroke="#e04a4a" stroke-width="1.3" stroke-linejoin="round"/>
    </g></svg>`,

  // Potion — a flask.
  flask: `<svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M9.5 2h5v2h-1v5.2l5 8.4A2.6 2.6 0 0 1 16.2 22H7.8a2.6 2.6 0 0 1-2.3-4.4l5-8.4V4h-1z"
      fill="#e0568a" stroke="#ffd0e0" stroke-width="1.1" stroke-linejoin="round"/></svg>`,
};
