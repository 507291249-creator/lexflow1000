import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        line: "#D8DEE6",
        court: "#235F8C",
        mint: "#256B5A",
        "primary-700": "#173F5F",
        "primary-600": "#173F5F",
        "primary-100": "#EAF2F8",
        "success-700": "#174F43",
        "success-600": "#256B5A",
        "success-100": "#E7F2EE",
        "ai-700": "#51446D",
        "ai-600": "#6A5A88",
        "ai-100": "#F1EEF6",
        "ai-border": "#D8D0E3",
        "warning": "#A86618",
        "warning-bg": "#FBF1DF",
        "danger": "#A83C38",
        "danger-bg": "#F8E9E7",
        "inactive": "#66717D"
      }
    }
  },
  plugins: []
};

export default config;
