/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        app: {
          bg: "rgb(var(--app-bg) / <alpha-value>)",
          surface: "rgb(var(--app-surface) / <alpha-value>)",
          border: "rgb(var(--app-border) / <alpha-value>)",
          text: {
            primary: "rgb(var(--app-text-primary) / <alpha-value>)",
            secondary: "rgb(var(--app-text-secondary) / <alpha-value>)",
          },
          accent: {
            DEFAULT: "rgb(var(--app-accent) / <alpha-value>)",
            hover: "rgb(var(--app-accent-hover) / <alpha-value>)",
            light: "rgb(var(--app-accent-light) / <alpha-value>)",
          },
          success: "#16A34A",
          warning: "#D97706",
          error: "#DC2626",
        }
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
      },
      borderRadius: {
        lg: "8px",
      },
      spacing: {
        '4': '4px',
        '8': '8px',
        '12': '12px',
        '16': '16px',
        '24': '24px',
        '32': '32px',
      }
    },
  },
  plugins: [],
}
