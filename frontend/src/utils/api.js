const API_BASE = 'https://scc-intel-api.onrender.com/api'

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

export const api = {
  // Tenders
  getTenders: (params) => fetchAPI('/tenders/', params),
  getTenderStats: () => fetchAPI('/tenders/stats'),
  getTenderTrend: () => fetchAPI('/tenders/trend'),

  // News
  getNews: (params) => fetchAPI('/news/', params),
  getNewsStats: () => fetchAPI('/news/stats'),

  // Briefings
  getLatestBriefing: () => fetchAPI('/briefings/latest'),
  getBriefingHistory: () => fetchAPI('/briefings/history'),

  // Query
  query: (q) => fetchAPI('/query/', { q }),

  // Competitive Intelligence
  getCompetitiveIntel: () => fetchAPI('/competitive-intel/'),

  // Geography
  getGeoDistribution: () => fetchAPI('/geo/distribution'),

  // System
  getHealth: () => fetchAPI('/system/health'),
  getScrapeStatus: () => fetchAPI('/system/scrape-status'),
}
