/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Noto Sans"', '"Noto Sans Devanagari"', "system-ui", "sans-serif"],
        mono: ['ui-monospace', '"Cascadia Mono"', "Consolas", "monospace"],
      },
      colors: {
        ink: "#1f2937",
        ledger: { 50: "#f7f6f2", 100: "#efede5", 200: "#ddd9c9", 600: "#7a6a3a", 700: "#5f522b", 900: "#2c2614" },
      },
    },
  },
  plugins: [],
};
