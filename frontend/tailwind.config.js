export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: {
          primary: '#ffffff',
          secondary: '#f8fafc',
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
          success: { bg: '#dcfce7', text: '#166534', border: '#86efac' },
          warning: { bg: '#fef9c3', text: '#854d0e', border: '#fde047' },
          error: { bg: '#fee2e2', text: '#991b1b', border: '#fca5a5' },
          info: { bg: '#dbeafe', text: '#1e40af', border: '#93c5fd' }
        },
        brand: {
          primary: '#1e40af',
          secondary: '#3b82f6',
          accent: '#0ea5e9'
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
      spacing: {
        '1': '0.25rem', '2': '0.5rem', '3': '0.75rem', '4': '1rem',
        '6': '1.5rem', '8': '2rem', '12': '3rem'
      },
      borderRadius: {
        'sm': '0.25rem', 'md': '0.375rem', 'lg': '0.5rem', 'xl': '0.75rem', 'full': '9999px'
      },
      boxShadow: {
        'sm': '0 1px 2px rgba(0, 0, 0, 0.05)',
        'md': '0 4px 6px rgba(0, 0, 0, 0.1)',
        'lg': '0 10px 15px rgba(0, 0, 0, 0.1)',
        'xl': '0 20px 25px rgba(0, 0, 0, 0.15)'
      },
      transitionDuration: {
        'fast': '150ms',
        'normal': '250ms',
        'slow': '350ms'
      }
    }
  },
  plugins: []
}
