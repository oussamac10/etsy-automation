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
      title: "Marketplace Studio",
      htmlAttrs: { lang: "en" },
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        {
          name: "description",
          content:
            "Autonomous research-to-draft digital product studio with complete creative control at every milestone.",
        },
      ],
      link: [
        {
          rel: "icon",
          type: "image/svg+xml",
          href: "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiIgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiBmaWxsPSJub25lIj48ZGVmcz48bGluZWFyR3JhZGllbnQgaWQ9InN0dWRpby1ncmFkIiB4MT0iMiIgeTE9IjIiIHgyPSIzMCIgeTI9IjMwIiBncmFkaWVudFVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHN0b3Agb2Zmc2V0PSIwJSIgc3RvcC1jb2xvcj0iIzNCODJGNiIvPjxzdG9wIG9mZnNldD0iNTAlIiBzdG9wLWNvbG9yPSIjMjU2M0VCIi8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjMUQ0RUQ4Ii8+PC9saW5lYXJHcmFkaWVudD48bGluZWFyR3JhZGllbnQgaWQ9InNwYXJrbGUtZ3JhZCIgeDE9IjIwIiB5MT0iNCIgeDI9IjI4IiB5Mj0iMTIiIGdyYWRpZW50VW5pdHM9InVzZXJTcGFjZU9uVXNlIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjRkRFMDQ3Ii8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjRjU5RTBCIi8+PC9saW5lYXJHcmFkaWVudD48ZmlsdGVyIGlkPSJzaGFkb3ciIHg9IjAiIHk9IjAiIHdpZHRoPSIzMiIgaGVpZ2h0PSIzMiIgZmlsdGVydW5pdHM9InVzZXJTcGFjZU9uVXNlIj48ZmVEcm9wU2hhZG93IGR4PSIwIiBkeT0iMSIgc3RkRGV2aWF0aW9uPSIxIiBmbG9vZC1jb2xvcj0iIzBGMTcyQSIgZmxvb2Qtb3BhY2l0eT0iMC4xOCIvPjwvZmlsdGVyPjwvZGVmcz48cmVjdCB4PSIyIiB5PSIyIiB3aWR0aD0iMjgiIGhlaWdodD0iMjgiIHJ4PSI3IiBmaWxsPSJ1cmwoI3N0dWRpby1ncmFkKSIgZmlsdGVyPSJ1cmwoI3NoYWRvdykiLz48cmVjdCB4PSIyLjUiIHk9IjIuNSIgd2lkdGg9IjI3IiBoZWlnaHQ9IjI3IiByeD0iNi41IiBzdHJva2U9IiM2MEE1RkEiIHN0cm9rZS1vcGFjaXR5PSIwLjQiIHN0cm9rZS13aWR0aD0iMSIvPjxwYXRoIGQ9Ik03IDExLjVMOSA4aDE0bDIgMy41djEuNWMwIDEuMS0uOSAyLTIgMnMtMi0uOS0yLTJjMCAxLjEtLjkgMi0yIDJzLTItLjktMi0yYzAgMS4xLS45IDItMiAycy0yLS45LTItMmMwIDEuMS0uOSAyLTIgMnMtMi0uOS0yLTJ2LTEuNXoiIGZpbGw9IiNGRkZGRkYiIGZpbGwtb3BhY2l0eT0iMC45NSIvPjxwYXRoIGQ9Ik04IDE1djhjMCAuNTUuNDUgMSAxIDFoMTRjLjU1IDAgMS0uNDUgMS0xdi04IiBzdHJva2U9IiNGRkZGRkYiIHN0cm9rZS13aWR0aD0iMS43NSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PHBhdGggZD0iTTEzIDI0di01YzAtLjU1LjQ1LTEgMS0xaDRjLjU1IDAgMSAuNDUgMSAxdjUiIGZpbGw9IiNEQkVBRkUiIGZpbGwtb3BhY2l0eT0iMC4zIiBzdHJva2U9IiNGRkZGRkYiIHN0cm9rZS13aWR0aD0iMS41IiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48cGF0aCBkPSJNMjQgNC41TDI0LjggNi44TDI3IDcuNUwyNC44IDguMkwyNCAxMC41TDIzLjIgOC4yTDIxIDcuNUwyMy4yIDYuOEwyNCA0LjVaIiBmaWxsPSJ1cmwoI3NwYXJrbGUtZ3JhZCkiLz48L3N2Zz4=",
        },
        { rel: "alternate icon", type: "image/x-icon", href: "/favicon.ico" },
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
