import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#122033",
          muted: "#3d4f63",
          inverse: "#f6f1e8",
        },
        paper: {
          DEFAULT: "#f7f3ec",
          card: "#fffdf8",
          muted: "#ebe4d8",
        },
        brand: {
          DEFAULT: "#0f6e68",
          dark: "#0b524e",
          light: "#d7efec",
        },
        price: {
          DEFAULT: "#b45309",
          dark: "#9a3412",
        },
        danger: {
          DEFAULT: "#b42318",
          light: "#fee4e2",
        },
        warn: {
          DEFAULT: "#b54708",
          light: "#fef0c7",
        },
        ok: {
          DEFAULT: "#067647",
          light: "#dcfae6",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "ui-serif", "Georgia", "serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(18, 32, 51, 0.06), 0 12px 32px -16px rgba(18, 32, 51, 0.18)",
      },
      maxWidth: {
        page: "72rem",
      },
    },
  },
  plugins: [],
};

export default config;
