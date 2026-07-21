import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        "ink-subtle": "#374151",
        line: "#D8DEE6",
        "line-subtle": "#E5E7EB",
        court: "#235F8C",
        "court-subtle": "#EAF2F8",
        mint: "#256B5A",
        "mint-subtle": "#E7F2EE",
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
        "inactive": "#66717D",
        "inactive-subtle": "#E5E7EB"
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
          "Apple Color Emoji",
          "Segoe UI Emoji",
          "Segoe UI Symbol",
          "Noto Color Emoji"
        ]
      },
      fontSize: {
        xs: ["11px", { lineHeight: "14px" }],
        sm: ["12px", { lineHeight: "15px" }],
        base: ["14px", { lineHeight: "18px" }],
        md: ["15px", { lineHeight: "20px" }],
        lg: ["16px", { lineHeight: "22px" }],
        xl: ["18px", { lineHeight: "25px" }],
        "2xl": ["20px", { lineHeight: "28px" }],
        "3xl": ["24px", { lineHeight: "32px" }]
      },
      spacing: {
        "1": "4px",
        "2": "8px",
        "3": "12px",
        "4": "16px",
        "5": "20px",
        "6": "24px",
        "8": "32px"
      },
      boxShadow: {
        "card-sm": "0 1px 2px rgba(0, 0, 0, 0.04)",
        "card": "0 1px 3px rgba(0, 0, 0, 0.06)",
        "card-lg": "0 2px 8px rgba(0, 0, 0, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
