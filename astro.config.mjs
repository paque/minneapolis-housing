import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import tailwind from "@astrojs/tailwind";

export default defineConfig({
  site: "https://paque.github.io",
  base: "/minneapolis-housing",
  output: "static",
  integrations: [
    react(),
    tailwind({
      applyBaseStyles: false
    })
  ]
});
