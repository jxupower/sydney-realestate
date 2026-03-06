import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Design system tokens (from UIUX sample)
        sidebar: {
          bg: "#1E1B4B",
          text: "#C7D2FE",
          active: "#818CF8",
        },
        accent: {
          DEFAULT: "#4F46E5",
          light: "#818CF8",
        },
        underval: {
          green: "#10B981",
          yellow: "#F59E0B",
          red: "#EF4444",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
