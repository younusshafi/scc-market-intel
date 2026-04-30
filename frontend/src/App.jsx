import { useState } from 'react'
import { api } from './utils/api'
import { useAPI } from './hooks/useAPI'
import MetricCards from './components/MetricCards'
import TenderTable from './components/TenderTable'
import NewsSection from './components/NewsSection'
import BriefingCard from './components/BriefingCard'
import TrendChart from './components/TrendChart'
import QueryBar from './components/QueryBar'
import CompetitiveBattlefield from './components/CompetitiveBattlefield'
import EarlyWarnings from './components/EarlyWarnings'
import CompetitorTimeline from './components/CompetitorTimeline'
import GalfarProfile from './components/GalfarProfile'
import GeoDistribution from './components/GeoDistribution'
import PTLCContext from './components/PTLCContext'
import RetenderRadar from './components/RetenderRadar'

export default function App() {
  const { data: stats, loading: statsLoading } = useAPI(api.getTenderStats, [])
  const { data: newsStats } = useAPI(api.getNewsStats, [])
  const { data: briefing } = useAPI(api.getLatestBriefing, [])
  const { data: trend } = useAPI(api.getTenderTrend, [])

  return (
    <div className="min-h-screen bg-[#0a0e17]">
      {/* 1. Nav Bar */}
      <nav className="sticky top-0 z-50 bg-[#020617] border-b border-[#334155] px-8 py-3.5 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <svg viewBox="0 0 28 28" fill="none" className="w-7 h-7">
            <rect width="28" height="28" rx="6" fill="#3B82F6" />
            <path d="M7 14h4l3-6 3 10 3-4h4" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <span className="text-lg font-bold text-[#e8ecf4] tracking-tight">Market Intelligence</span>
            <span className="text-[11px] text-[#5a6a85] ml-2 font-normal">Sarooj Construction Company</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-red-500 uppercase tracking-wider">
            <span className="w-[7px] h-[7px] rounded-full bg-red-500 animate-pulse" />
            LIVE
          </span>
          <span className="text-[12px] text-[#5a6a85]">
            Powered by <strong className="text-[#8896b0]">Zavia-ai</strong>
          </span>
          <div className="w-8 h-8 rounded-full bg-[#1E293B] border border-[#334155] flex items-center justify-center text-[11px] font-semibold text-[#8896b0]">
            JF
          </div>
        </div>
      </nav>

      <main className="max-w-[1400px] mx-auto px-8 py-6 space-y-6">
        {/* 2. Executive Briefing + Trend */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          <div className="lg:col-span-3">
            <BriefingCard briefing={briefing?.briefing} />
          </div>
          <div className="lg:col-span-2">
            <TrendChart data={trend} />
          </div>
        </div>

        {/* 3. Metric Cards */}
        <MetricCards stats={stats} newsStats={newsStats} loading={statsLoading} />

        {/* Section divider */}
        <SectionDivider label="Competitive Intelligence" />

        {/* 4. Competitive Battlefield + 5. Early Warnings */}
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
          <div className="xl:col-span-3">
            <CompetitiveBattlefield />
          </div>
          <div className="xl:col-span-1 space-y-5">
            <EarlyWarnings />
          </div>
        </div>

        {/* 6. Competitor Activity Timeline + 7. Galfar Profile */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2">
            <CompetitorTimeline />
          </div>
          <div className="lg:col-span-1">
            <GalfarProfile />
          </div>
        </div>

        {/* Section divider */}
        <SectionDivider label="Market Context" />

        {/* 8. Geographic Distribution + 9. PTLC Pipeline Context */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <GeoDistribution />
          <PTLCContext />
        </div>

        {/* Section divider */}
        <SectionDivider label="Tender Pipeline" />

        {/* NLP Query Bar */}
        <QueryBar />

        {/* 10. SCC-Addressable Tenders Table */}
        <TenderTable />

        {/* 11. Re-Tender Radar */}
        <RetenderRadar />

        {/* Section divider */}
        <SectionDivider label="News Intelligence" />

        {/* 12. News Intelligence */}
        <NewsSection />
      </main>

      {/* 13. Footer */}
      <footer className="border-t border-[#334155] px-8 py-6 text-center text-[11px] text-[#5a6a85] mt-8">
        Data sourced from etendering.tenderboard.gov.om · Oman news RSS · Google News
        <br />
        Powered by <strong className="text-[#8896b0]">Zavia-ai</strong> · Intelligence refresh: daily
      </footer>
    </div>
  )
}


function SectionDivider({ label }) {
  return (
    <div className="flex items-center gap-4 py-2">
      <div className="flex-1 h-px bg-[#1e2a42]" />
      <span className="text-[10px] font-semibold text-[#5a6a85] uppercase tracking-widest">{label}</span>
      <div className="flex-1 h-px bg-[#1e2a42]" />
    </div>
  )
}
