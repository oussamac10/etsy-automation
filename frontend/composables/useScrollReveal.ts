import { ref, onMounted, onUnmounted } from "vue";

export interface ScrollRevealOptions {
  threshold?: number;
  rootMargin?: string;
  once?: boolean;
}

/**
 * Clean, lightweight scroll reveal composable using IntersectionObserver.
 * Fully SSR-safe and automatically honors `prefers-reduced-motion`.
 */
export function useScrollReveal(options: ScrollRevealOptions = {}) {
  const { threshold = 0.15, rootMargin = "0px 0px -40px 0px", once = true } = options;

  const targetRef = ref<HTMLElement | null>(null);
  const isVisible = ref(false);
  const prefersReducedMotion = ref(false);

  let observer: IntersectionObserver | null = null;

  onMounted(() => {
    if (typeof window === "undefined") return;

    // Check user accessibility preference for reduced motion
    const motionQuery = typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;
    prefersReducedMotion.value = motionQuery?.matches ?? false;

    const handleMotionChange = (e: MediaQueryListEvent) => {
      prefersReducedMotion.value = e.matches;
      if (e.matches) {
        isVisible.value = true;
      }
    };

    if (motionQuery?.addEventListener) {
      motionQuery.addEventListener("change", handleMotionChange);
    }

    // If user prefers reduced motion or no IntersectionObserver, display immediately
    if (prefersReducedMotion.value || !("IntersectionObserver" in window)) {
      isVisible.value = true;
      return;
    }

    observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry && entry.isIntersecting) {
          isVisible.value = true;
          if (once && observer && targetRef.value) {
            observer.unobserve(targetRef.value);
            observer.disconnect();
          }
        } else if (!once) {
          isVisible.value = false;
        }
      },
      { threshold, rootMargin }
    );

    if (targetRef.value) {
      observer.observe(targetRef.value);
    }
  });

  onUnmounted(() => {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
  });

  return {
    targetRef,
    isVisible,
    prefersReducedMotion,
  };
}
