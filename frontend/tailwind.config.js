/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#F7F4EF',
          100: '#EDE6DB',
          200: '#D9CFC0',
          300: '#C4B5A0',
          400: '#A89888',
          500: '#8B7355',
          600: '#6F5C45',
          700: '#5A4A38',
          800: '#45382B',
          900: '#352C22',
        },
        accent: {
          400: '#9CAF88',
          500: '#7A9168',
          600: '#5F7550',
        },
        wine: {
          400: '#C49A8A',
          500: '#A67B6B',
          600: '#8B6356',
        },
        vip: {
          300: '#E8D4A8',
          400: '#D4B896',
          500: '#C4A574',
          600: '#A68B5C',
          700: '#8B7355',
        },
        paper: '#FAF8F5',
        surface: '#F5F1EB',
        ink: '#2C2825',
        muted: '#5C5348',
      },
      fontFamily: {
        sans: [
          'system-ui',
          '-apple-system',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'sans-serif',
        ],
        serif: [
          '"Noto Serif SC"',
          '"Songti SC"',
          '"STSong"',
          'Georgia',
          'serif',
        ],
      },
      boxShadow: {
        soft: '0 4px 24px -10px rgba(44, 40, 37, 0.08)',
        hover: '0 12px 40px -14px rgba(107, 92, 69, 0.18)',
        vip: '0 10px 36px -12px rgba(196, 165, 116, 0.35)',
        inner: 'inset 0 1px 0 rgba(255,255,255,0.6)',
      },
      backgroundImage: {
        'hero-grad':
          'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(232, 223, 208, 0.9), transparent 70%), radial-gradient(ellipse 60% 40% at 100% 0%, rgba(156, 175, 136, 0.12), transparent 50%), linear-gradient(180deg, #FAF8F5 0%, #F5F1EB 55%, #FAF8F5 100%)',
        'cta-grad':
          'linear-gradient(135deg, #6F5C45 0%, #8B7355 50%, #7A9168 100%)',
        'summary-grad':
          'linear-gradient(135deg, #5A4A38 0%, #7A9168 100%)',
        'vip-grad':
          'linear-gradient(135deg, #E8D4A8 0%, #C4A574 50%, #A68B5C 100%)',
        'text-grad':
          'linear-gradient(135deg, #5A4A38 0%, #7A9168 100%)',
        'paper-texture':
          'url("data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23C9B99A\' fill-opacity=\'0.06\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")',
      },
      borderRadius: {
        '4xl': '2rem',
      },
    },
  },
  plugins: [],
}
