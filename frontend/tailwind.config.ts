import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        line: "#d8dee8",
        court: "#1f4f75",
        mint: "#2f7d70",
        amber: "#a46318"
      }
    }
  },
  plugins: []
};

export default config;
