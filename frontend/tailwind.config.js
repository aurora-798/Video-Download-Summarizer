/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#2F73FF',
          600: '#1e5fe6',
          700: '#1a4fc4',
          800: '#1a3fa1',
          900: '#1a3074',
        },
        accent: {
          400: '#22d3ee',
          500: '#00B4D8',
          600: '#0095b8',
        },
        vip: {
          300: '#fde68a',
          400: '#fcd34d',
          500: '#FFB020',
          600: '#d97706',
          700: '#b45309',
        },
        surface: '#F7F8FB',
        ink: '#0f172a',
      },
      fontFamily: {
        sans: [
          'system-ui',
          '-apple-system',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'Helvetica Neue',
          'sans-serif',
        ],
      },
      boxShadow: {
        soft: '0 4px 24px -8px rgba(15, 23, 42, 0.10)',
        hover: '0 12px 40px -12px rgba(47, 115, 255, 0.35)',
        vip: '0 10px 36px -12px rgba(255, 176, 32, 0.55)',
      },
      backgroundImage: {
        'hero-grad':
          'radial-gradient(1200px 600px at 20% -10%, rgba(96,165,250,0.25), transparent 60%), radial-gradient(900px 500px at 80% 0%, rgba(34,211,238,0.20), transparent 60%), linear-gradient(180deg, #f0f7ff 0%, #ffffff 100%)',
        'cta-grad':
          'linear-gradient(135deg, #2F73FF 0%, #00B4D8 100%)',
        'vip-grad':
          'linear-gradient(135deg, #FFD56B 0%, #FFB020 50%, #ff8a00 100%)',
        'text-grad':
          'linear-gradient(135deg, #2F73FF 0%, #00B4D8 100%)',
      },
      keyframes: {
        floaty: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        floaty: 'floaty 6s ease-in-out infinite',
        shimmer: 'shimmer 3s linear infinite',
      },
    },
  },
  plugins: [],
}
