<script setup lang="ts">
import { computed, ref } from 'vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Badge from '~/components/ui/Badge.vue';
import type { Asset } from '~/types/workflow';
import { sanitizeUrl } from '~/utils/sanitize';

const props = defineProps<{
  packageAsset?: Asset | null;
  downloadUrl?: string | null;
  version: number;
  isBuilding?: boolean;
}>();

const emit = defineEmits<{
  (e: 'build-package'): void;
}>();

const copied = ref(false);

const byteSize = computed(() => {
  if (!props.packageAsset?.byte_size) return null;
  const bytes = props.packageAsset.byte_size;
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
});

const checksum = computed(() => props.packageAsset?.checksum_sha256 || null);

async function copyChecksum() {
  if (!checksum.value) return;
  try {
    await navigator.clipboard.writeText(checksum.value);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch {
    // clipboard copy failed
  }
}
</script>

<template>
  <Card class="border-border shadow-xs overflow-hidden">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div class="space-y-1">
        <div class="flex items-center gap-2 flex-wrap">
          <CardTitle class="text-base font-semibold flex items-center gap-2">
            <Icon name="lucide:package-check" class="size-4.5 text-primary" aria-hidden="true" />
            <span>Customer ZIP Download Package</span>
          </CardTitle>
          <Badge v-if="packageAsset" variant="success" class="text-[10px] font-mono font-bold">
            {{ byteSize }}
          </Badge>
          <Badge v-else variant="outline" class="text-[10px] font-medium text-muted-foreground">
            Ready on Approval
          </Badge>
        </div>
        <CardDescription class="text-xs">
          Complete digital delivery ZIP archive packaged for direct Etsy buyer upload.
        </CardDescription>
      </div>

      <div class="flex items-center gap-2 self-start sm:self-auto shrink-0">
        <button
          v-if="!packageAsset"
          type="button"
          :disabled="isBuilding"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary-hover transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
          @click="emit('build-package')"
        >
          <Icon :name="isBuilding ? 'lucide:loader-circle' : 'lucide:box'" :class="['size-3.5', isBuilding ? 'animate-spin' : '']" aria-hidden="true" />
          <span>{{ isBuilding ? 'Compiling ZIP...' : 'Build Package' }}</span>
        </button>

        <template v-else>
          <button
            type="button"
            :disabled="isBuilding"
            title="Rebuild ZIP package"
            class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer disabled:opacity-50"
            @click="emit('build-package')"
          >
            <Icon :name="isBuilding ? 'lucide:loader-circle' : 'lucide:refresh-cw'" :class="['size-3.5', isBuilding ? 'animate-spin' : '']" aria-hidden="true" />
            <span class="hidden sm:inline">{{ isBuilding ? 'Rebuilding...' : 'Rebuild' }}</span>
          </button>

          <a
            v-if="downloadUrl"
            :href="sanitizeUrl(downloadUrl)"
            target="_blank"
            rel="noopener noreferrer"
            download="customer_print_package.zip"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 transition-colors shadow-2xs cursor-pointer"
          >
            <Icon name="lucide:download" class="size-3.5" aria-hidden="true" />
            <span>Download ZIP</span>
          </a>
        </template>
      </div>
    </CardHeader>

    <CardContent class="space-y-3.5 pt-0">
      <!-- Archive Manifest Grid -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
        <!-- Master PNG Item -->
        <div class="p-3 bg-slate-50/90 border border-slate-200/90 rounded-xl flex items-center gap-3 transition-all hover:bg-white hover:shadow-2xs">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 shrink-0 border border-indigo-100/80">
            <Icon name="lucide:file-image" class="size-5" aria-hidden="true" />
          </div>
          <div class="space-y-0.5 min-w-0 flex-1">
            <div class="flex items-center justify-between gap-1">
              <p class="font-semibold text-slate-900 truncate text-xs">master.png</p>
              <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-indigo-50 text-indigo-700 font-bold">PNG</span>
            </div>
            <p class="text-[10px] text-slate-500 truncate">4500×5400 px • 300 DPI • Transparent</p>
          </div>
        </div>

        <!-- Print-Ready PDF Item -->
        <div class="p-3 bg-slate-50/90 border border-slate-200/90 rounded-xl flex items-center gap-3 transition-all hover:bg-white hover:shadow-2xs">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-red-50 text-red-600 shrink-0 border border-red-100/80">
            <Icon name="lucide:file-text" class="size-5" aria-hidden="true" />
          </div>
          <div class="space-y-0.5 min-w-0 flex-1">
            <div class="flex items-center justify-between gap-1">
              <p class="font-semibold text-slate-900 truncate text-xs">print-ready.pdf</p>
              <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-red-50 text-red-700 font-bold">PDF</span>
            </div>
            <p class="text-[10px] text-slate-500 truncate">Vector-compatible layout • 300 DPI</p>
          </div>
        </div>

        <!-- Product Mockups Item -->
        <div class="p-3 bg-slate-50/90 border border-slate-200/90 rounded-xl flex items-center gap-3 transition-all hover:bg-white hover:shadow-2xs">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 shrink-0 border border-emerald-100/80">
            <Icon name="lucide:layers" class="size-5" aria-hidden="true" />
          </div>
          <div class="space-y-0.5 min-w-0 flex-1">
            <div class="flex items-center justify-between gap-1">
              <p class="font-semibold text-slate-900 truncate text-xs">Product Mockups</p>
              <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-50 text-emerald-700 font-bold">WEBP/JPG</span>
            </div>
            <p class="text-[10px] text-slate-500 truncate">Realistic blank template previews</p>
          </div>
        </div>

        <!-- License & Instructions Item -->
        <div class="p-3 bg-slate-50/90 border border-slate-200/90 rounded-xl flex items-center gap-3 transition-all hover:bg-white hover:shadow-2xs">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600 shrink-0 border border-amber-100/80">
            <Icon name="lucide:scroll-text" class="size-5" aria-hidden="true" />
          </div>
          <div class="space-y-0.5 min-w-0 flex-1">
            <div class="flex items-center justify-between gap-1">
              <p class="font-semibold text-slate-900 truncate text-xs">LICENSE & GUIDE</p>
              <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-50 text-amber-700 font-bold">TXT/PDF</span>
            </div>
            <p class="text-[10px] text-slate-500 truncate">Commercial license terms & buyer guide</p>
          </div>
        </div>
      </div>

      <!-- SHA-256 Checksum -->
      <div v-if="checksum" class="flex items-center justify-between p-2.5 bg-slate-100/80 border border-slate-200 rounded-lg text-[11px] font-mono text-slate-700">
        <div class="flex items-center gap-1.5 truncate mr-2">
          <Icon name="lucide:fingerprint" class="size-3.5 text-slate-400 shrink-0" aria-hidden="true" />
          <span class="text-slate-500 select-none text-[10px] font-sans font-semibold">SHA-256:</span>
          <span class="truncate text-[10px]">{{ checksum }}</span>
        </div>
        <button
          type="button"
          class="text-primary hover:text-primary-hover font-sans text-[10px] font-semibold shrink-0 cursor-pointer flex items-center gap-1 focus-visible:outline-none"
          @click="copyChecksum"
        >
          <Icon :name="copied ? 'lucide:check' : 'lucide:copy'" class="size-3" aria-hidden="true" />
          <span>{{ copied ? 'Copied' : 'Copy' }}</span>
        </button>
      </div>
    </CardContent>
  </Card>
</template>
