import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-noto-sans-jp)', 'sans-serif'],
      },
      colors: {
        brand: { DEFAULT: '#1A56DB', light: '#3B82F6', dark: '#1e40af' },
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: 'none',
            color: '#374151',
            a: { color: '#1A56DB', textDecoration: 'none' },
          },
        },
      },
    },
  },
  plugins: [],
}

export default config
