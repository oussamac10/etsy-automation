import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "../stores/auth";

// Mock Nuxt globals
vi.stubGlobal("useRuntimeConfig", () => ({
  public: {
    apiBase: "http://localhost:8000",
  },
}));

vi.stubGlobal("useRequestHeaders", () => ({}));

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.restoreAllMocks();
  });

  it("starts uninitialized and loading=false", () => {
    const store = useAuthStore();
    expect(store.user).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.loading).toBe(false);
  });

  it("checkAuth success sets user and initialized", async () => {
    const mockUser = { id: "123", email: "owner@example.com", is_active: true };
    const fetchMock = vi.fn().mockResolvedValue(mockUser);
    vi.stubGlobal("$fetch", fetchMock);

    const store = useAuthStore();
    await store.checkAuth();

    expect(store.user).toEqual(mockUser);
    expect(store.initialized).toBe(true);
    expect(store.isAuthenticated).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/me",
      expect.any(Object)
    );
  });

  it("checkAuth failure sets user=null and initialized=true", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("401 Unauthorized"));
    vi.stubGlobal("$fetch", fetchMock);

    const store = useAuthStore();
    await store.checkAuth();

    expect(store.user).toBeNull();
    expect(store.initialized).toBe(true);
    expect(store.isAuthenticated).toBe(false);
  });

  it("login success sets user", async () => {
    const mockUser = { id: "123", email: "owner@example.com", is_active: true };
    const fetchMock = vi.fn().mockResolvedValue({ user: mockUser });
    vi.stubGlobal("$fetch", fetchMock);

    const store = useAuthStore();
    await store.login("owner@example.com", "password");

    expect(store.user).toEqual(mockUser);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/login",
      expect.objectContaining({
        method: "POST",
        body: { email: "owner@example.com", password: "password" },
      })
    );
  });

  it("logout clears user and resets initialized", async () => {
    const fetchMock = vi.fn().mockResolvedValue({});
    vi.stubGlobal("$fetch", fetchMock);

    const store = useAuthStore();
    store.user = { id: "123", email: "owner@example.com", is_active: true };
    store.initialized = true;

    await store.logout();

    expect(store.user).toBeNull();
    expect(store.initialized).toBe(false);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/logout",
      expect.any(Object)
    );
  });
});
