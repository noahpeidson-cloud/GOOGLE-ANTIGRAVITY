/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ops: {
          bg: '#0a0d14',
          surface: '#111726',
          card: '#161f33',
          cardHover: '#1c2842',
          border: '#1e293b',
          borderLight: '#334155',
          accent: '#38bdf8',
          accentHover: '#0ea5e9',
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
          muted: '#94a3b8'
        }
      }
    },
  },
  plugins: [],
}
