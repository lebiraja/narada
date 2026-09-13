import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { mono: ["ui-monospace", "SFMono-Regular", "monospace"] },
      colors: {
        ink: "#0a0a0b",
        bone: "#e8e4dc",
        ember: "#ff4d1c",
      },
    },
  },
  plugins: [],
};

export default config;
