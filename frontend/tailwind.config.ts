import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#E8EEF7",
        "ink-subtle": "#B3C0D2",
        line: "#283A52",
        "line-subtle": "#1F3050",
        "surface-sunken": "#111E30",
        court: "#6CA4E0",
        "court-strong": "#2F6FB3",
        "court-hover": "#3B7DC9",
        "court-subtle": "#15324A",
        "court-border": "#2B4D72",
        mint: "#3DBFA0",
        "mint-subtle": "#0F2E27",
        "mint-border": "#1E4A3F",
        "primary-700": "#2F6FB3",
        "primary-600": "#3B7DC9",
        "primary-100": "#15324A",
        "success-700": "#2A9D7E",
        "success-600": "#3DBFA0",
        "success-100": "#0F2E27",
        "ai-700": "#6B5BA0",
        "ai-600": "#A99BD9",
        "ai-100": "#221D38",
        "ai-border": "#3D3460",
        "warning": "#E0A24A",
        "warning-bg": "#332614",
        "warning-border": "#5C4220",
        "danger": "#E06560",
        "danger-bg": "#331816",
        "danger-border": "#5C2A26",
        "inactive": "#7A8A9E",
        "inactive-subtle": "#1F2A38"
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
