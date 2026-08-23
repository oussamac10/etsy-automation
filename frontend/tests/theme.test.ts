import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { useTheme, THEME_STORAGE_KEY } from "~/composables/useTheme";
import ThemeToggle from "~/components/ThemeToggle.vue";

describe("useTheme composable", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    vi.restoreAllMocks();
  });

  it("sets dark theme and adds .dark class to documentElement", () => {
    const { theme, isDark, setTheme } = useTheme();

    setTheme("dark");

    expect(theme.value).toBe("dark");
    expect(isDark.value).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("sets light theme and removes .dark class from documentElement", () => {
    const { theme, isDark, setTheme } = useTheme();

    setTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    setTheme("light");
    expect(theme.value).toBe("light");
    expect(isDark.value).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("toggles between dark and light themes correctly", () => {
    const { isDark, setTheme, toggleTheme } = useTheme();

    setTheme("light");
    expect(isDark.value).toBe(false);

    toggleTheme();
    expect(isDark.value).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    toggleTheme();
    expect(isDark.value).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("initializes theme preference from localStorage if present", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");

    const { theme, isDark, initTheme } = useTheme();
    initTheme();

    expect(theme.value).toBe("dark");
    expect(isDark.value).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});

describe("ThemeToggle component", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("renders accessible button and toggles theme on click", async () => {
    const { setTheme } = useTheme();
    setTheme("light");

    const wrapper = mount(ThemeToggle, {
      global: {
        stubs: {
          Icon: {
            template: '<span class="icon-stub" :data-icon="$attrs.name"></span>',
          },
        },
      },
    });

    const button = wrapper.find('[data-testid="theme-toggle-btn"]');
    expect(button.exists()).toBe(true);
    expect(button.attributes("aria-label")).toBe("Switch to dark theme");

    await button.trigger("click");

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(button.attributes("aria-label")).toBe("Switch to light theme");
  });
});
