/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', '"Noto Sans"', '"Noto Sans Devanagari"', "system-ui", "sans-serif"],
        display: ['"Source Serif 4"', '"Noto Serif Devanagari"', "Georgia", "serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", '"Cascadia Mono"', "Consolas", "monospace"],
      },
      colors: {
        ink: "#1f2937",
        ledger: {
          50: "#faf9f5",
          100: "#efede5",
          200: "#ddd9c9",
          600: "#7a6a3a",
          700: "#5f522b",
          800: "#3d3420",
          900: "#2c2614",
        },
        hero: "#211d14",
        accent: "#e8921a",
      },
    },
  },
  plugins: [],
};
