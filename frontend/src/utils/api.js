const API_BASE = 'http://localhost:8000/api'

async function fetchAPI(endpoint, params = {}) {
  const url = new URL(`${API_BASE}${endpoint}`, window.location.origin)
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') {
      url.searchParams.set(k, v)
    }
  })

  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function postAPI(endpoint) {
  const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const api = {
  // Tenders
  getTenders: (params) => fetchAPI('/tenders/', params),
  getTenderStats: () => fetchAPI('/tenders/stats'),
  getTenderTrend: () => fetchAPI('/tenders/trend'),

  // News
  getNews: (params) => fetchAPI('/news/', params),
  getNewsStats: () => fetchAPI('/news/stats'),
  getJvMentions: (params) => fetchAPI('/news/jv-mentions', params),
  getJvStats: () => fetchAPI('/news/jv-stats'),

  // Briefings
  getLatestBriefing: () => fetchAPI('/briefings/latest'),
  getBriefingHistory: () => fetchAPI('/briefings/history'),

  // Query
  query: (q) => fetchAPI('/query/', { q }),

  // Competitive Intelligence
  getCompetitiveIntel: () => fetchAPI('/competitive-intel/'),

  // Geography
  getGeoDistribution: () => fetchAPI('/geo/distribution'),

  // AI Scoring
  getScoredTenders: () => fetchAPI('/tenders/scored'),
  triggerScoring: () => postAPI('/tenders/score'),

  // AI News Intelligence
  getNewsIntelligence: () => fetchAPI('/news/intelligence'),
  triggerNewsAnalysis: () => postAPI('/news/analyse'),

  // Competitor Profiles
  getCompetitorProfiles: () => fetchAPI('/competitive-intel/profiles'),
  buildCompetitorProfiles: () => postAPI('/competitive-intel/build-profiles'),

  // Galfar MSX Financials
  getGalfarFinancials: () => fetchAPI('/competitive-intel/galfar-financials'),
  scrapeGalfarFinancials: () => postAPI('/competitive-intel/scrape-galfar'),

  // Entity Intelligence
  getEntityIntel: () => fetchAPI('/entity-intel/'),
  buildEntityIntel: () => postAPI('/entity-intel/build'),

  // News-Tender Links
  getNewsTenderLinks: () => fetchAPI('/news/tender-links'),
  linkNewsToTenders: () => postAPI('/news/link-to-tenders'),

  // Dashboard
  getPriorityActions: () => fetchAPI('/dashboard/priority-actions'),
  getDashboardMetrics: () => fetchAPI('/dashboard/metrics'),

  // Awarded
  getAwardedStats: () => fetchAPI('/awarded/stats'),
  getAwardedWinners: () => fetchAPI('/awarded/winners'),
  getAwardedAnalytics: () => fetchAPI('/awarded/analytics'),
  getAwardedInsights: () => fetchAPI('/awarded/insights'),
  getSCCPerformance: () => fetchAPI('/awarded/scc-performance'),
  getCompetitorHistory: (company) => fetchAPI('/awarded/competitor-history', { company }),
  computeAwardedAnalytics: () => postAPI('/awarded/compute'),

  // System
  getHealth: () => fetchAPI('/system/health'),
  getScrapeStatus: () => fetchAPI('/system/scrape-status'),
}
