import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#09090b", 900: "#0c0c0f", 850: "#111115", 800: "#16161b", 700: "#1d1d24", 600: "#272730", 500: "#3a3a46" },
        fog: { DEFAULT: "#e7e7ea", 300: "#b9b9c3", 400: "#8e8e9b", 500: "#6b6b78" },
        ember: { DEFAULT: "#f5a524", 400: "#f7b84d", 600: "#d98b0e", glow: "rgba(245,165,36,0.18)" },
        cyan: { DEFAULT: "#5ac8fa" },
        ok: "#3ecf8e", warn: "#f5c524", bad: "#ff5c5c",
      },
      fontFamily: { sans: ["'Inter Variable'", "ui-sans-serif", "system-ui"], mono: ["'JetBrains Mono Variable'", "ui-monospace"] },
      boxShadow: { panel: "0 1px 0 rgba(255,255,255,0.04) inset, 0 20px 40px -20px rgba(0,0,0,0.6)", glow: "0 0 0 1px rgba(245,165,36,0.35), 0 8px 30px -8px rgba(245,165,36,0.35)" },
      keyframes: { shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } } },
      animation: { shimmer: "shimmer 2.2s linear infinite" },
    },
  },
  plugins: [],
} satisfies Config;
