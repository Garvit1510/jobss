module.exports = {
  content: ["./src/**/*.{js,jsx}", "./public/index.html"],
  theme: {
    extend: {
      colors: {
        ink: "#111111",
        paper: "#FDFBF4",
        offwhite: "#F4F1E8",
        brand: { yellow: "#FFE14D", blue: "#4D6FFF", green: "#22C55E", red: "#FF5A4D", purple: "#C4B5FD" },
      },
      fontFamily: {
        display: ['"Space Grotesk"', "sans-serif"],
        sans: ["Inter", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      boxShadow: {
        brutalsm: "3px 3px 0 #111",
        brutal: "6px 6px 0 #111",
        brutallg: "10px 10px 0 #111",
      },
      borderWidth: { 3: "3px" },
      keyframes: {
        marquee: { "0%": { transform: "translateX(0)" }, "100%": { transform: "translateX(-50%)" } },
        shimmer: { "0%": { backgroundPosition: "-400px 0" }, "100%": { backgroundPosition: "400px 0" } },
      },
      animation: { marquee: "marquee 30s linear infinite", shimmer: "shimmer 1.4s linear infinite" },
    },
  },
  plugins: [],
};
