/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        space: {
          950: '#030712',
          900: '#050b14',
          850: '#07101e',
          800: '#0a1526',
          750: '#0d1c33',
          700: '#112240',
        },
        cyan: {
          glow: '#00f0ff',
          neon: '#00e5ff',
          electric: '#22d3ee',
          dim: '#0891b2',
        },
        gold: {
          accent: '#fbbf24',
          glow: '#f59e0b',
          amber: '#d97706',
        },
        alert: {
          normal: '#10b981',
          review: '#38bdf8',
          attention: '#f59e0b',
          critical: '#ef4444',
          insufficient: '#94a3b8',
        }
      },
      fontFamily: {
        mono: ['"DM Mono"', '"JetBrains Mono"', 'monospace'],
        display: ['"Rajdhani"', '"Space Grotesk"', 'sans-serif'],
        sans: ['"Inter"', 'sans-serif'],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px -3px rgba(0, 240, 255, 0.35)',
        'glow-gold': '0 0 20px -3px rgba(251, 191, 36, 0.3)',
        'glow-alert': '0 0 25px -2px rgba(245, 158, 11, 0.4)',
        'panel': '0 8px 32px 0 rgba(0, 0, 0, 0.55)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scanline': 'scan 6s linear infinite',
      },
      keyframes: {
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(1000%)' },
        }
      }
    },
  },
  plugins: [],
}
