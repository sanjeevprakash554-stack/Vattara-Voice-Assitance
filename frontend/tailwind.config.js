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
        charcoal: {
          DEFAULT: 'rgb(var(--color-charcoal-rgb, 23 24 22) / <alpha-value>)',
          50: 'rgb(var(--color-charcoal-rgb, 23 24 22) / 0.1)',
          100: 'rgb(var(--color-charcoal-rgb, 23 24 22) / 0.2)',
          200: 'rgb(var(--color-charcoal-rgb, 23 24 22) / 0.4)',
          300: 'rgb(var(--color-charcoal-rgb, 23 24 22) / 0.6)',
          400: 'rgb(var(--color-charcoal-rgb, 23 24 22) / 0.8)',
          500: 'rgb(var(--color-charcoal-rgb, 23 24 22) / 1)',
        },
        graphite: 'rgb(var(--color-graphite-rgb, 36 38 34) / <alpha-value>)',
        warmblack: 'rgb(var(--color-warmblack-rgb, 16 17 15) / <alpha-value>)',
        burnt: {
          DEFAULT: 'rgb(var(--color-burnt-rgb, 228 119 69) / <alpha-value>)',
          light: 'rgb(var(--color-burnt-rgb, 228 119 69) / 0.8)',
          dark: 'rgb(var(--color-burnt-rgb, 228 119 69) / 0.9)',
        },
        amber: {
          DEFAULT: 'rgb(var(--color-amber-rgb, 240 173 87) / <alpha-value>)',
          light: 'rgb(var(--color-amber-rgb, 240 173 87) / 0.8)',
          dark: 'rgb(var(--color-amber-rgb, 240 173 87) / 0.9)',
        },
        lavender: {
          DEFAULT: 'rgb(var(--color-lavender-rgb, 167 139 250) / <alpha-value>)',
          light: 'rgb(var(--color-lavender-rgb, 167 139 250) / 0.8)',
          dark: 'rgb(var(--color-lavender-rgb, 167 139 250) / 0.9)',
        },
        ivory: 'rgb(var(--color-ivory-rgb, 242 238 230) / <alpha-value>)',
        mutedgrey: 'rgb(var(--color-mutedgrey-rgb, 170 169 159) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'float': 'float 6s ease-in-out infinite',
        'wave': 'wave 1.5s ease-in-out infinite',
        'glow': 'glow 3s ease-in-out infinite alternate',
        'spin-slow': 'spin 20s linear infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        wave: {
          '0%, 100%': { height: '8px' },
          '50%': { height: '32px' },
        },
        glow: {
          '0%': { filter: 'drop-shadow(0 0 15px rgba(var(--color-burnt-rgb, 228 119 69), 0.3))' },
          '100%': { filter: 'drop-shadow(0 0 30px rgba(var(--color-amber-rgb, 240 173 87), 0.6))' },
        },
      },
    },
  },
  plugins: [],
}
