/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#1E293B',
        'surface-hover': '#253348',
        'border-subtle': '#1e2a42',
        competitor: {
          sarooj: '#f59e0b',
          galfar: '#ef4444',
          strabag: '#3b82f6',
          altasnim: '#8b5cf6',
          lt: '#06b6d4',
          towell: '#10b981',
          hassanallam: '#ec4899',
          arabcontractors: '#f97316',
          ozkar: '#64748b',
        },
      },
      fontFamily: {
        sans: ['DM Sans', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        card: '12px',
      },
      maxWidth: {
        dashboard: '1400px',
      },
    },
  },
  plugins: [],
}
