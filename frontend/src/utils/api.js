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
