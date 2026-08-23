import { ref, computed, nextTick } from "vue";

export type ThemePreference = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "marketplace_studio_theme";

// Module-level reactive singleton state shared across components
const preference = ref<ThemePreference>("system");
const isDark = ref(false);
const isInitialized = ref(false);

/**
 * Temporarily disables all individual CSS transitions across all DOM elements
 * during theme switching so every component updates simultaneously with zero delay/stagger.
 */
function disableTransitions(): () => void {
  if (typeof document === "undefined") return () => {};
  const css = document.createElement("style");
  css.appendChild(
    document.createTextNode(
      "*,*::before,*::after{-webkit-transition:none!important;-moz-transition:none!important;-o-transition:none!important;-ms-transition:none!important;transition:none!important}"
    )
  );
  document.head.appendChild(css);

  return () => {
    // Force DOM reflow to flush calculated styles
    (() => window.getComputedStyle(document.body))();
    // Re-enable transitions on the next animation frame
    requestAnimationFrame(() => {
      if (css.parentNode) {
        document.head.removeChild(css);
      }
    });
  };
}

export function useTheme() {
  function getSystemPreference(): boolean {
    if (typeof window === "undefined") return false;
    return Boolean(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  async function applyTheme(themeVal: ThemePreference, withTransition = true) {
    if (typeof document === "undefined") return;

    let darkActive = false;
    if (themeVal === "dark") {
      darkActive = true;
    } else if (themeVal === "light") {
      darkActive = false;
    } else {
      darkActive = getSystemPreference();
    }

    const updateDOM = () => {
      isDark.value = darkActive;
      if (darkActive) {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    };

    if (!withTransition || !isInitialized.value) {
      updateDOM();
      return;
    }

    // Modern View Transitions API with smooth full-viewport cross-fade
    const doc = document as Document & {
      startViewTransition?: (cb: () => Promise<void> | void) => { ready: Promise<void>; finished: Promise<void> };
    };

    if (typeof doc.startViewTransition === "function") {
      const enableTransitions = disableTransitions();
      try {
        const transition = doc.startViewTransition(async () => {
          updateDOM();
          await nextTick();
        });
        await transition.ready;
      } finally {
        enableTransitions();
      }
      return;
    }

    // Fallback: disable individual element transitions so all components change at the exact same millisecond
    const enableTransitions = disableTransitions();
    updateDOM();
    await nextTick();
    enableTransitions();
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
    applyTheme(newTheme, true);
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
    applyTheme(savedTheme, false);

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
