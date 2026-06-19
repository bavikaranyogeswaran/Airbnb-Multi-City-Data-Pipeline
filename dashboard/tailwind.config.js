/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          red:   '#FF5A5F',
          teal:  '#00A699',
          dark:  '#484848',
          gray:  '#767676',
          light: '#F7F7F7',
        },
      },
    },
  },
  plugins: [],
};
