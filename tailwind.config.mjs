export default {
  content: ["./src/**/*.{astro,html,js,jsx,md,mdx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1d2522",
        paper: "#f7f5ef",
        line: "#d8d5ca",
        civic: {
          green: "#255f4a",
          leaf: "#6c9a7a",
          lake: "#356d8c",
          gold: "#c79238",
          clay: "#a75f45"
        }
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "Segoe UI",
          "Arial",
          "sans-serif"
        ]
      },
      boxShadow: {
        focus: "0 0 0 3px rgba(53, 109, 140, 0.28)"
      }
    }
  },
  plugins: []
};

