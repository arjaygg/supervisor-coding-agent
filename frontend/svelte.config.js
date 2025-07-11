import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/kit/vite";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  // Consult https://kit.svelte.dev/docs/integrations#preprocessors
  // for more information about preprocessors
  preprocess: vitePreprocess(),

  kit: {
    adapter: adapter({
      // Generate static site
      pages: "build",
      assets: "build",
      fallback: "index.html",
      precompress: false,
      strict: false,
    }),
    prerender: {
      handleHttpError: ({ path, referrer, message }) => {
        console.warn(
          `404 ${path}${referrer ? ` (referrer: ${referrer})` : ""}`
        );
      },
    },
    alias: {
      $lib: "./src/lib",
    },
  },
};

export default config;
