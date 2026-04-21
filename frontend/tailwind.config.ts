import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "hsl(var(--brand-50))",
          100: "hsl(var(--brand-100))",
          500: "hsl(var(--brand-500))",
          600: "hsl(var(--brand-600))",
          700: "hsl(var(--brand-700))",
        },

        "nav-bg": "hsl(var(--nav-bg))",
        "nav-bg-hover": "hsl(var(--nav-bg-hover))",
        "nav-fg": "hsl(var(--nav-fg))",
        "nav-fg-muted": "hsl(var(--nav-fg-muted))",
        "nav-active-bg": "hsl(var(--nav-active-bg))",
        "nav-divider": "hsl(var(--nav-divider))",

        "page-bg": "hsl(var(--page-bg))",
        surface: "hsl(var(--surface))",
        "surface-alt": "hsl(var(--surface-alt))",

        "text-primary": "hsl(var(--text-primary))",
        "text-secondary": "hsl(var(--text-secondary))",
        "text-tertiary": "hsl(var(--text-tertiary))",

        "border-default": "hsl(var(--border-default))",
        "border-strong": "hsl(var(--border-strong))",
        divider: "hsl(var(--divider))",

        "status-green": "hsl(var(--status-green))",
        "status-green-bg": "hsl(var(--status-green-bg))",
        "status-red": "hsl(var(--status-red))",
        "status-red-bg": "hsl(var(--status-red-bg))",
        "status-amber": "hsl(var(--status-amber))",
        "status-amber-bg": "hsl(var(--status-amber-bg))",

        // shadcn/ui compat
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      fontFamily: {
        sans: [
          '"Noto Sans JP"',
          '"Hiragino Kaku Gothic ProN"',
          '"Hiragino Sans"',
          '"Yu Gothic UI"',
          "Meiryo",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [animate],
} satisfies Config;
