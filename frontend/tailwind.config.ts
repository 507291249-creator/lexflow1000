import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0C1A2B",
        "ink-subtle": "#26384F",
        line: "#D5DEE9",
        "line-subtle": "#E8EDF3",
        "surface-sunken": "#EEF2F6",
        navy: "#0E1F33",
        "navy-700": "#15293F",
        "navy-600": "#1E3650",
        court: "#1A5A9C",
        "court-subtle": "#E7F0FA",
        "court-border": "#BDD5EA",
        mint: "#137A69",
        "mint-subtle": "#E3F2EF",
        "mint-border": "#B4DCD2",
        "primary-700": "#164A80",
        "primary-600": "#1A5A9C",
        "primary-100": "#E7F0FA",
        "success-700": "#0F5A4C",
        "success-600": "#137A69",
        "success-100": "#E3F2EF",
        "ai-700": "#4A3F73",
        "ai-600": "#5C4F8C",
        "ai-100": "#EFEDF7",
        "ai-border": "#D3CCE3",
        "warning": "#955A14",
        "warning-bg": "#FBF1DE",
        "warning-border": "#EBD5A6",
        "danger": "#A03631",
        "danger-bg": "#F7E9E7",
        "danger-border": "#E6C6C3",
        "inactive": "#6B7682",
        "inactive-subtle": "#E8EBEF"
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
