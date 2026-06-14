const API_BASE = "/api"

async function fetchAPI(endpoint, params = {}) {
  const url = new URL(`${API_BASE}${endpoint}`, window.location.origin)
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      url.searchParams.set(k, v)
    }
  })
  const res = await fetch(url)
  return res.json()
}

async function postAPI(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`, { method: "POST" })
  return res.json()
}

export const getPipeline = async () => {
  try {
    const res = await fetch(`${API_BASE}/pipeline/`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export const setPipelineStatus = async (tenderNumber, tenderTitle, entity, status, closingDate = null, notes = null) => {
  try {
    const body = { tender_number: tenderNumber, tender_title: tenderTitle, entity, status }
    if (closingDate) body.closing_date = closingDate
    if (notes) body.notes = notes
    const res = await fetch(`${API_BASE}/pipeline/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export const removePipelineStatus = async (tenderNumber) => {
  try {
    const res = await fetch(`${API_BASE}/pipeline/${encodeURIComponent(tenderNumber)}`, { method: 'DELETE' })
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export const getTenderPipelineStatus = async (tenderNumber) => {
  try {
    const res = await fetch(`${API_BASE}/pipeline/status/${encodeURIComponent(tenderNumber)}`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export const getTenderNewsSignals = async (tenderNumber) => {
  try {
    const res = await fetch(`${API_BASE}/news/tender-links/${encodeURIComponent(tenderNumber)}`)
    if (!res.ok) return null
    return res.json()
  } catch {
    return null
  }
}

export const askNlq = async (question) => {
  try {
    const res = await fetch(`${API_BASE}/nlq/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    })
    if (!res.ok) return { answer: 'Request failed. Please try again.', sql: '', rows: [], tier: 0, caveats: [], error: 'http_error' }
    return res.json()
  } catch {
    return { answer: 'Could not reach the server. Is the backend running?', sql: '', rows: [], tier: 0, caveats: [], error: 'network_error' }
  }
}

export const api = {
  getTenders: (params) => fetchAPI("/tenders/", params),
  getTenderStats: () => fetchAPI("/tenders/stats"),
  getTenderTrend: () => fetchAPI("/tenders/trend"),
  getNews: (params) => fetchAPI("/news/", params),
  getNewsStats: () => fetchAPI("/news/stats"),
  getJvMentions: (params) => fetchAPI("/news/jv-mentions", params),
  getJvStats: () => fetchAPI("/news/jv-stats"),
  getLatestBriefing: () => fetchAPI("/briefings/latest"),
  getBriefingHistory: () => fetchAPI("/briefings/history"),
  generateBriefing: () => postAPI("/briefings/generate"),
  query: (q) => fetchAPI("/query/", { q }),
  getCompetitiveIntel: () => fetchAPI("/competitive-intel/"),
  getLiveTenders: () => fetchAPI("/competitive-intel/"),
  getGeoDistribution: () => fetchAPI("/geo/distribution"),
  getScoredTenders: () => fetchAPI("/tenders/scored"),
  triggerScoring: () => postAPI("/tenders/score"),
  getNewsIntelligence: () => fetchAPI("/news/intelligence"),
  triggerNewsAnalysis: () => postAPI("/news/analyse"),
  getCompetitorProfiles: () => fetchAPI("/competitive-intel/profiles"),
  buildCompetitorProfiles: () => postAPI("/competitive-intel/build-profiles"),
  getGalfarFinancials: () => fetchAPI("/competitive-intel/galfar-financials"),
  getGalfarStructured: () => fetchAPI("/competitive-intel/galfar-structured"),
  scrapeGalfarFinancials: () => postAPI("/competitive-intel/scrape-galfar"),
  getEntityIntel: () => fetchAPI("/entity-intel/"),
  buildEntityIntel: () => postAPI("/entity-intel/build"),
  getNewsTenderLinks: () => fetchAPI("/news/tender-links"),
  linkNewsToTenders: () => postAPI("/news/link-to-tenders"),
  getPriorityActions: () => fetchAPI("/dashboard/priority-actions"),
  getDashboardMetrics: () => fetchAPI("/dashboard/metrics"),
  getYearlyActivity: () => fetchAPI("/awarded/yearly-activity"),
  getAwardedStats: () => fetchAPI("/awarded/stats"),
  getAwardedWinners: () => fetchAPI("/awarded/winners"),
  getAwardedAnalytics: () => fetchAPI("/awarded/analytics"),
  getAwardedInsights: () => fetchAPI("/awarded/insights"),
  getSCCPerformance: () => fetchAPI("/awarded/scc-performance"),
  getCompetitorHistory: (company) => fetchAPI("/awarded/competitor-history", { company }),
  computeAwardedAnalytics: () => postAPI("/awarded/compute"),
  getHealth: () => fetchAPI("/system/health"),
  getScrapeStatus: () => fetchAPI("/system/scrape-status"),
}
