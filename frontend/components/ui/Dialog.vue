<script setup lang="ts">
import { onMounted, onUnmounted, watch } from "vue";
import { X } from "lucide-vue-next";

interface Props {
  open?: boolean;
  maxWidth?: "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "4xl";
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  maxWidth: "lg",
});

const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
  (e: "close"): void;
}>();

function close() {
  emit("update:open", false);
  emit("close");
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === "Escape" && props.open) {
    close();
  }
}

onMounted(() => {
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", onKeyDown);
  }
});

onUnmounted(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", onKeyDown);
  }
});

watch(
  () => props.open,
  (val) => {
    if (typeof document !== "undefined") {
      if (val) {
        document.body.style.overflow = "hidden";
      } else {
        document.body.style.overflow = "";
      }
    }
  }
);

const maxWidthClasses = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
  "2xl": "max-w-2xl",
  "3xl": "max-w-3xl",
  "4xl": "max-w-4xl",
};
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-900/60 backdrop-blur-sm"
        @click.self="close"
      >
        <div
          :class="[
            'relative w-full rounded-2xl bg-white p-6 shadow-2xl border border-slate-200 max-h-[90vh] overflow-y-auto',
            maxWidthClasses[maxWidth],
          ]"
          role="dialog"
          aria-modal="true"
        >
          <button
            type="button"
            class="absolute right-4 top-4 rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            @click="close"
          >
            <X class="h-4 w-4" />
            <span class="sr-only">Close</span>
          </button>
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
