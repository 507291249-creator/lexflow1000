import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        line: "#d8e0e8",
        court: "#1f587c",
        mint: "#267466"
      }
    }
  },
  plugins: []
};

export default config;
