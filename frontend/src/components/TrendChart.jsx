import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'

export default function TrendChart({ data }) {
  return (
    <div className="bg-surface border border-slate-700/50 rounded-xl p-6">
      <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
        Tender Volume Trend
      </h3>

      {data && data.length > 0 ? (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} barGap={2}>
            <XAxis
              dataKey="month"
              tick={{ fill: '#94A3B8', fontSize: 11 }}
              axisLine={{ stroke: '#334155' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#94A3B8', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: '#1E293B',
                border: '1px solid #334155',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              labelStyle={{ color: '#94A3B8' }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', color: '#94A3B8' }}
            />
            <Bar dataKey="total" name="All Tenders" fill="#334155" radius={[3, 3, 0, 0]} />
            <Bar dataKey="scc" name="SCC-Relevant" fill="#3B82F6" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-sm text-slate-500 italic">No trend data available yet.</p>
      )}
    </div>
  )
}
