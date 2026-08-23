import { ref, computed } from "vue";

export type ThemePreference = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "marketplace_studio_theme";

// Module-level reactive singleton state shared across components
const preference = ref<ThemePreference>("system");
const isDark = ref(false);
const isInitialized = ref(false);

export function useTheme() {
  function getSystemPreference(): boolean {
    if (typeof window === "undefined") return false;
    return Boolean(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  function applyTheme(themeVal: ThemePreference) {
    if (typeof document === "undefined") return;

    let darkActive = false;
    if (themeVal === "dark") {
      darkActive = true;
    } else if (themeVal === "light") {
      darkActive = false;
    } else {
      darkActive = getSystemPreference();
    }

    isDark.value = darkActive;
    if (darkActive) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }

  function setTheme(newTheme: ThemePreference) {
    preference.value = newTheme;
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(THEME_STORAGE_KEY, newTheme);
      } catch {
        // Ignore local storage quota/security restrictions
      }
    }
    applyTheme(newTheme);
  }

  function toggleTheme() {
    if (isDark.value) {
      setTheme("light");
    } else {
      setTheme("dark");
    }
  }

  function initTheme() {
    if (typeof window === "undefined") return;

    let savedTheme: ThemePreference = "system";
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY) as ThemePreference | null;
      if (stored && (stored === "light" || stored === "dark" || stored === "system")) {
        savedTheme = stored;
      }
    } catch {
      // Ignore
    }

    preference.value = savedTheme;
    applyTheme(savedTheme);

    if (!isInitialized.value) {
      isInitialized.value = true;
      if (window.matchMedia) {
        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const handler = (e: MediaQueryListEvent) => {
          if (preference.value === "system") {
            isDark.value = e.matches;
            if (e.matches) {
              document.documentElement.classList.add("dark");
            } else {
              document.documentElement.classList.remove("dark");
            }
          }
        };
        if (mediaQuery.addEventListener) {
          mediaQuery.addEventListener("change", handler);
        } else if ((mediaQuery as unknown as { addListener?: (cb: (e: MediaQueryListEvent) => void) => void }).addListener) {
          (mediaQuery as unknown as { addListener: (cb: (e: MediaQueryListEvent) => void) => void }).addListener(handler);
        }
      }
    }
  }

  return {
    theme: computed(() => preference.value),
    isDark: computed(() => isDark.value),
    setTheme,
    toggleTheme,
    initTheme,
  };
}
