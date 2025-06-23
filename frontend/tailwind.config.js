/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{html,js,svelte,ts}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          900: "#1e3a8a",
        },
        gray: {
          850: "#1a202c", // Custom gray-850 between 800 (#1f2937) and 900 (#111827)
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
