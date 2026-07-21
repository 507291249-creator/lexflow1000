import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0F1B2D",
        "ink-subtle": "#2A3A4F",
        line: "#D7DEE6",
        "line-subtle": "#E6EBF1",
        "surface-sunken": "#EEF1F4",
        court: "#1F5A88",
        "court-subtle": "#E8F0F7",
        "court-border": "#BFD3E2",
        mint: "#1F6B5A",
        "mint-subtle": "#E6F1ED",
        "mint-border": "#BFDDD2",
        "primary-700": "#194A6E",
        "primary-600": "#1F5A88",
        "primary-100": "#E8F0F7",
        "success-700": "#174F43",
        "success-600": "#1F6B5A",
        "success-100": "#E6F1ED",
        "ai-700": "#4E426A",
        "ai-600": "#5E5180",
        "ai-100": "#F0EDF6",
        "ai-border": "#D6CFE2",
        "warning": "#9A5E16",
        "warning-bg": "#FBF1DF",
        "warning-border": "#EBD6A8",
        "danger": "#9E3733",
        "danger-bg": "#F7E9E7",
        "danger-border": "#E6C6C3",
        "inactive": "#69737E",
        "inactive-subtle": "#E7EAEE"
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
