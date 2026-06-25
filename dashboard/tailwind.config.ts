import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#141412",
        paper: "#f7f5ef",
        line: "#ded8ca",
        accent: "#2f6f63"
      },
      fontFamily: {
        sans: ["Geist", "Satoshi", "Avenir Next", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "Liberation Mono", "monospace"]
      }
    }
  },
  plugins: []
} satisfies Config;
