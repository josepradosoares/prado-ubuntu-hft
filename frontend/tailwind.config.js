/** @type {import('tailwindcss').Config} */
const brandGreen = {
  50: '#f4faee',
  100: '#e4f2d6',
  200: '#c9e5ae',
  300: '#b8da98',
  400: '#97c966',
  500: '#87c245',
  600: '#72a836',
  700: '#5a862a',
  800: '#476922',
  900: '#39551d',
  950: '#1f300e',
}

const brandNeutral = {
  50: '#f8f8f8',
  100: '#f2f2f2',
  200: '#e2e0e1',
  300: '#cbc8c9',
  400: '#9e999b',
  500: '#767072',
  600: '#595355',
  700: '#433e40',
  800: '#332f31',
  900: '#252223',
  950: '#1b191a',
}

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: brandGreen,
        blue: brandGreen,
        sky: brandGreen,
        indigo: brandGreen,
        emerald: {
          50: '#f4faee',
          100: '#e4f2d6',
          200: '#c9e5ae',
          300: '#b8da98',
          400: '#97c966',
          500: '#87c245',
          600: '#6fa435',
          700: '#568128',
          800: '#446521',
          900: '#36511b',
          950: '#1d2d0d',
        },
        slate: brandNeutral,
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
