import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Instrument Serif'", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        stage: "#12100f",
        riser: "#1c1917",
        bone: "#ede6da",
        brass: "#c9962e",
      },
      animation: {
        shine: "shine var(--duration) infinite linear",
        "shiny-text": "shiny-text 8s infinite",
        "pulse-ember": "pulse-ember 1.2s ease-in-out infinite",
      },
      keyframes: {
        shine: {
          "0%": { "background-position": "0% 0%" },
          "50%": { "background-position": "100% 100%" },
          to: { "background-position": "0% 0%" },
        },
        "shiny-text": {
          "0%, 90%, 100%": { "background-position": "calc(-100% - var(--shiny-width)) 0" },
          "30%, 60%": { "background-position": "calc(100% + var(--shiny-width)) 0" },
        },
        "pulse-ember": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
