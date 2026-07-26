export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        amex: {
          burgundy: '#4A0E17',
          burgundyDark: '#360910',
          burgundyLight: '#631522',
          burgundyHover: '#57101C',
          gold: '#D4AF37',
          goldLight: '#F3E5AB'
        },
        background: {
          primary: '#f8fafc',
          secondary: '#ffffff',
          tertiary: '#f1f5f9',
          surface: '#ffffff'
        },
        text: {
          primary: '#0f172a',
          secondary: '#475569',
          tertiary: '#94a3b8',
          inverse: '#ffffff'
        },
        semantic: {
          success: { bg: '#ecfdf5', text: '#047857', border: '#a7f3d0' },
          warning: { bg: '#fffbeb', text: '#b45309', border: '#fde68a' },
          error: { bg: '#fef2f2', text: '#b91c1c', border: '#fca5a5' },
          info: { bg: '#eff6ff', text: '#1d4ed8', border: '#bfdbfe' }
        },
        brand: {
          primary: '#4A0E17',
          secondary: '#631522',
          accent: '#0284c7'
        },
        border: {
          light: '#e2e8f0',
          medium: '#cbd5e1',
          dark: '#94a3b8'
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Consolas', 'monospace']
      },
      boxShadow: {
        'sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'md': '0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -1px rgba(0, 0, 0, 0.04)',
        'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.03)',
        'card': '0 2px 8px rgba(15, 23, 42, 0.06)'
      }
    }
  },
  plugins: []
}
