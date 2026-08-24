import tailwindcss from "@tailwindcss/vite";

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: false },

  modules: ["@pinia/nuxt", "@nuxt/icon"],

  icon: {
    mode: "svg",
    clientBundle: {
      scan: true,
      sizeLimitKb: 256,
    },
  },

  css: ["~/assets/css/main.css"],

  vite: {
    plugins: [tailwindcss()],
    server: {
      watch: {
        usePolling: true,
      },
    },
  },

  typescript: {
    strict: true,
    typeCheck: false, // `pnpm typecheck` runs vue-tsc explicitly.
  },

  runtimeConfig: {
    public: {
      // Overridden by NUXT_PUBLIC_API_BASE. Never place a secret in `public`.
      apiBase: "http://localhost:8000",
    },
  },

  nitro: {
    // The container health check hits /api/_health on the Nuxt server itself.
    preset: "node-server",
  },

  app: {
    head: {
      title: "NovaCraftPixel — AI-Powered Etsy Product Studio",
      htmlAttrs: { lang: "en" },
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        {
          name: "description",
          content:
            "Autonomous research-to-draft digital Etsy product studio with complete creative control at every milestone.",
        },
      ],
      link: [
        { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" },
      ],
      script: [
        {
          innerHTML: `(function(){try{var t=localStorage.getItem('marketplace_studio_theme')||'system';var d=t==='dark'||(t==='system'&&window.matchMedia('(prefers-color-scheme:dark)').matches);if(d){document.documentElement.classList.add('dark');}else{document.documentElement.classList.remove('dark');}}catch(e){}})();`,
          type: "text/javascript",
          tagPosition: "head",
        },
      ],
    },
  },
});
