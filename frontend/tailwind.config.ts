import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0F1E2E",
        "ink-subtle": "#334155",
        line: "#E2E8F0",
        "line-subtle": "#EDF1F6",
        "surface-sunken": "#EEF2F7",
        court: "#1E5FB0",
        "court-subtle": "#EAF2FB",
        "court-border": "#C3D8EE",
        mint: "#0E7C6A",
        "mint-subtle": "#E2F3EF",
        "mint-border": "#B3DDD2",
        "primary-700": "#194F94",
        "primary-600": "#1E5FB0",
        "primary-100": "#EAF2FB",
        "success-700": "#0B5E50",
        "success-600": "#0E7C6A",
        "success-100": "#E2F3EF",
        "ai-700": "#4A3F73",
        "ai-600": "#6B5BB1",
        "ai-100": "#F0EDF8",
        "ai-border": "#D4CCE7",
        "warning": "#955A14",
        "warning-bg": "#FBF1DE",
        "warning-border": "#EBD5A6",
        "danger": "#A02F2A",
        "danger-bg": "#F8E8E6",
        "danger-border": "#E4C5C1",
        "inactive": "#64748B",
        "inactive-subtle": "#E8EDF3"
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
