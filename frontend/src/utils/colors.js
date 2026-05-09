/**
 * Canonical competitor colour map — single source of truth.
 * Tailwind bg/text/border classes + hex for Recharts + 2-letter abbreviation.
 * Import getCompetitorColor() wherever competitor colours are needed.
 */
export const COMPETITOR_COLORS = {
  'Galfar':           { bg: 'bg-red-500/20',    text: 'text-red-400',    border: 'border-red-500/30',    hex: '#DC2626', abbr: 'GL' },
  'Strabag':          { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/30', hex: '#EA580C', abbr: 'ST' },
  'Al Tasnim':        { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30', hex: '#CA8A04', abbr: 'AT' },
  'L&T':              { bg: 'bg-violet-500/20', text: 'text-violet-400', border: 'border-violet-500/30', hex: '#7C3AED', abbr: 'LT' },
  'Larsen & Toubro':  { bg: 'bg-violet-500/20', text: 'text-violet-400', border: 'border-violet-500/30', hex: '#7C3AED', abbr: 'LT' },
  'Towell':           { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/30', hex: '#9333EA', abbr: 'TW' },
  'Hassan Allam':     { bg: 'bg-green-500/20',  text: 'text-green-400',  border: 'border-green-500/30',  hex: '#16A34A', abbr: 'HA' },
  'Arab Contractors': { bg: 'bg-cyan-500/20',   text: 'text-cyan-400',   border: 'border-cyan-500/30',   hex: '#0891B2', abbr: 'AC' },
  'Ozkar':            { bg: 'bg-pink-500/20',   text: 'text-pink-400',   border: 'border-pink-500/30',   hex: '#DB2777', abbr: 'OZ' },
  'Sarooj':           { bg: 'bg-blue-600/20',   text: 'text-blue-400',   border: 'border-blue-600/30',   hex: '#2563EB', abbr: 'SC' },
}

const FALLBACK_COLOR = {
  bg: 'bg-slate-500/20', text: 'text-slate-400', border: 'border-slate-500/30', hex: '#6B7280', abbr: '??',
}

/**
 * Looks up a competitor by partial name match. Returns full colour object.
 * For unknown competitors, abbr is the first 2 uppercase letters.
 */
export function getCompetitorColor(name) {
  if (!name) return FALLBACK_COLOR
  const key = Object.keys(COMPETITOR_COLORS).find(
    k => name.toLowerCase().includes(k.toLowerCase())
  )
  if (key) return COMPETITOR_COLORS[key]
  return { ...FALLBACK_COLOR, abbr: name.substring(0, 2).toUpperCase() }
}

/** Hex-only lookup — for Recharts fill/stroke props. */
export function getCompetitorHex(name) {
  return getCompetitorColor(name).hex
}
