import { useState, useRef } from 'react'
import { api } from './utils/api'
import { useAPI } from './hooks/useAPI'
import TabNavigation from './components/TabNavigation'
import MetricCards from './components/MetricCards'
import TenderTable from './components/TenderTable'
import BriefingCard from './components/BriefingCard'
import TrendChart from './components/TrendChart'
import CompetitiveBattlefield from './components/CompetitiveBattlefield'
import PriorityActions from './components/PriorityActions'
import GalfarProfile from './components/GalfarProfile'
import ScoredTenders from './components/ScoredTenders'
import NewsIntelligence from './components/NewsIntelligence'
import CompetitorProfiles from './components/CompetitorProfiles'
import EntityIntelligence from './components/EntityIntelligence'
import AwardedIntelligence from './components/AwardedIntelligence'
import MarketContext from './components/MarketContext'

export default function App() {
  const { data: stats } = useAPI(api.getTenderStats, [])
  const { data: briefing, refetch: refetchBriefing } = useAPI(api.getLatestBriefing, [])
  const { data: trend } = useAPI(api.getTenderTrend, [])
  const { data: compIntel } = useAPI(api.getCompetitiveIntel, [])
  const { data: scoredData } = useAPI(api.getScoredTenders, [])
  const { data: newsIntel } = useAPI(api.getNewsIntelligence, [])
  const { data: profiles } = useAPI(api.getCompetitorProfiles, [])

  const [activeTab, setActiveTab] = useState('command-centre')
  const contentRef = useRef(null)

  function handleTabChange(tabId) {
    setActiveTab(tabId)
    contentRef.current?.scrollTo({ top: 0, behavior: 'smooth' })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Notification dots
  const notifications = {}
  if (compIntel?.live_competitive?.length > 0) {
    notifications['competitive-intel'] = true
  }
  const highPriorityNews = (newsIntel?.articles || []).filter(a => a.priority?.toLowerCase() === 'high')
  if (highPriorityNews.length > 0) {
    notifications['market-news'] = true
  }

  // Tab summary data
  const tabSummaries = {
    'competitive-intel': [
      `${compIntel?.live_competitive?.length || '—'} live competitive`,
      `${compIntel?.head_to_head?.length || '—'} head-to-head`,
      `${compIntel?.activity_summary?.length || '—'} tracked competitors`,
    ].join(' · '),
    'opportunities': [
      `${scoredData?.total || '—'} scored`,
      `${(scoredData?.tenders || []).filter(t => t.score >= 70).length || '—'} recommended`,
    ].join(' · '),
    'market-news': [
      `${newsIntel?.total || '—'} articles`,
      `${highPriorityNews.length || '—'} high priority`,
    ].join(' · '),
    'profiles': [
      `${profiles?.profiles?.length || '—'} competitor profiles`,
    ].join(' · '),
  }

  return (
    <div className="min-h-screen bg-[#0F172A]">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-[#020617] border-b border-[#1e2a42] px-8 py-3 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <svg viewBox="0 0 28 28" fill="none" className="w-7 h-7">
            <rect width="28" height="28" rx="6" fill="#3B82F6" />
            <path d="M7 14h4l3-6 3 10 3-4h4" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <span className="text-lg font-bold text-[#e8ecf4] tracking-tight">Market Intelligence</span>
            <span className="text-xs text-[#5a6a85] ml-2">Sarooj Construction Company</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="inline-flex items-center gap-1.5 text-[10px] font-bold text-red-500 uppercase tracking-wider">
            <span className="w-[6px] h-[6px] rounded-full bg-red-500 animate-pulse" />
            LIVE
          </span>
          <span className="text-[10px] text-[#5a6a85]">
            Powered by <strong className="text-[#8896b0]">Zavia-ai</strong>
          </span>
          <div className="w-7 h-7 rounded-full bg-[#1e2a42] border border-[#334155] flex items-center justify-center text-[10px] font-semibold text-[#8896b0]">
            JF
          </div>
        </div>
      </nav>

      {/* Tab Navigation */}
      <TabNavigation activeTab={activeTab} onTabChange={handleTabChange} notifications={notifications} />

      {/* Tab Summary Bar */}
      {activeTab !== 'command-centre' && tabSummaries[activeTab] && (
        <div className="bg-[#0a0e17] border-b border-[#1e2a42] px-8 py-1.5">
          <div className="max-w-[1400px] mx-auto">
            <p className="text-xs text-[#5a6a85] font-mono">{tabSummaries[activeTab]}</p>
          </div>
        </div>
      )}

      {/* Content */}
      <main ref={contentRef} className="max-w-[1400px] mx-auto px-8 py-5 space-y-5">

        {/* TAB 1: Command Centre */}
        {activeTab === 'command-centre' && (
          <>
            <BriefingCard briefing={briefing?.briefing} onRefresh={refetchBriefing} />
            <MetricCards />
            <PriorityActions />
            <TrendChart data={trend} />
          </>
        )}

        {/* TAB 2: Competitive Intel */}
        {activeTab === 'competitive-intel' && (
          <>
            <CompetitiveBattlefield />
            <CompetitorProfiles />
          </>
        )}

        {/* TAB 3: Opportunities */}
        {activeTab === 'opportunities' && (
          <>
            <ScoredTenders />
            <div className="mt-6">
              <TenderTable sccOnly={true} />
            </div>
          </>
        )}

        {/* TAB 4: Market & News */}
        {activeTab === 'market-news' && (
          <>
            <NewsIntelligence />
            <EntityIntelligence />
            <AwardedIntelligence />
            <MarketContext stats={stats} />
          </>
        )}

        {/* TAB 5: Profiles */}
        {activeTab === 'profiles' && (
          <>
            <GalfarProfile />
            <CompetitorProfiles />
          </>
        )}

      </main>

      {/* Footer */}
      <footer className="border-t border-[#1e2a42] px-8 py-5 text-center text-[10px] text-[#5a6a85] mt-6">
        Data sourced from etendering.tenderboard.gov.om &middot; Oman news RSS &middot; Google News
        <br />
        Powered by <strong className="text-[#8896b0]">Zavia-ai</strong> &middot; Intelligence refresh: daily
      </footer>
    </div>
  )
}
