import { LayoutDashboard, Swords, Target, Newspaper, UserSearch } from 'lucide-react'

const TABS = [
  { id: 'command-centre', label: 'Command Centre', icon: LayoutDashboard },
  { id: 'competitive-intel', label: 'Competitive Intel', icon: Swords },
  { id: 'opportunities', label: 'Opportunities', icon: Target },
  { id: 'market-news', label: 'Market & News', icon: Newspaper },
  { id: 'profiles', label: 'Profiles', icon: UserSearch },
]

export default function TabNavigation({ activeTab, onTabChange, notifications = {} }) {
  return (
    <div className="sticky top-[57px] z-40 bg-[#0f1525] border-b border-[#1e2a42]">
      <div className="max-w-[1400px] mx-auto px-8">
        <div className="flex gap-1 overflow-x-auto scrollbar-hide" style={{ scrollbarWidth: 'none' }}>
          {TABS.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            const hasNotification = notifications[tab.id]

            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`relative flex items-center gap-2 px-4 py-3 text-[13px] font-medium uppercase tracking-[0.05em] whitespace-nowrap transition-colors duration-150 border-b-2 ${
                  isActive
                    ? 'text-[#e8ecf4] border-[#3b82f6]'
                    : 'text-[#5a6a85] border-transparent hover:text-[#8896b0]'
                }`}
              >
                <Icon size={16} />
                {tab.label}
                {hasNotification && (
                  <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-red-500" />
                )}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
