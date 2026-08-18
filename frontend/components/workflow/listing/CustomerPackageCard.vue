<script setup lang="ts">
import { computed, ref } from 'vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Badge from '~/components/ui/Badge.vue';
import type { Asset } from '~/types/workflow';

const props = defineProps<{
  packageAsset?: Asset | null;
  downloadUrl?: string | null;
  version: number;
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
  <Card class="border-border shadow-xs">
    <CardHeader class="flex flex-row items-center justify-between pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2">
          <Icon name="lucide:package-check" class="size-4 text-primary" aria-hidden="true" />
          <span>Customer ZIP Download Package</span>
          <Badge v-if="packageAsset" variant="success" class="text-[10px] font-mono">
            {{ byteSize }}
          </Badge>
          <Badge v-else variant="outline" class="text-[10px]">
            Ready on Approval
          </Badge>
        </CardTitle>
        <CardDescription class="text-xs">
          Complete digital delivery ZIP archive packaged for direct Etsy upload.
        </CardDescription>
      </div>

      <a
        v-if="downloadUrl"
        :href="downloadUrl"
        download
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 text-white hover:bg-slate-800 transition-colors shadow-2xs"
      >
        <Icon name="lucide:download" class="size-3.5" aria-hidden="true" />
        <span>Download ZIP</span>
      </a>
    </CardHeader>

    <CardContent class="space-y-3 pt-0">
      <!-- Archive Manifest Grid -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
        <div class="p-2.5 bg-slate-50 border border-slate-200/80 rounded-lg flex items-center gap-2.5">
          <Icon name="lucide:file-image" class="size-5 text-indigo-600 shrink-0" aria-hidden="true" />
          <div class="space-y-0.5 min-w-0">
            <p class="font-semibold text-slate-900 truncate">master.png</p>
            <p class="text-[10px] text-slate-500">4500x5400 px, 300 DPI, sRGB, Transparent</p>
          </div>
        </div>

        <div class="p-2.5 bg-slate-50 border border-slate-200/80 rounded-lg flex items-center gap-2.5">
          <Icon name="lucide:file-text" class="size-5 text-red-600 shrink-0" aria-hidden="true" />
          <div class="space-y-0.5 min-w-0">
            <p class="font-semibold text-slate-900 truncate">print-ready.pdf</p>
            <p class="text-[10px] text-slate-500">High-res 300 DPI vector-compatible layout</p>
          </div>
        </div>

        <div class="p-2.5 bg-slate-50 border border-slate-200/80 rounded-lg flex items-center gap-2.5">
          <Icon name="lucide:layers" class="size-5 text-emerald-600 shrink-0" aria-hidden="true" />
          <div class="space-y-0.5 min-w-0">
            <p class="font-semibold text-slate-900 truncate">Product Mockups</p>
            <p class="text-[10px] text-slate-500">Realistic blank template previews</p>
          </div>
        </div>

        <div class="p-2.5 bg-slate-50 border border-slate-200/80 rounded-lg flex items-center gap-2.5">
          <Icon name="lucide:scroll-text" class="size-5 text-amber-600 shrink-0" aria-hidden="true" />
          <div class="space-y-0.5 min-w-0">
            <p class="font-semibold text-slate-900 truncate">LICENSE & INSTRUCTIONS</p>
            <p class="text-[10px] text-slate-500">Commercial usage & customer setup guide</p>
          </div>
        </div>
      </div>

      <!-- SHA-256 Checksum -->
      <div v-if="checksum" class="flex items-center justify-between p-2 bg-slate-100/70 border border-slate-200 rounded-md text-[11px] font-mono text-slate-700">
        <div class="flex items-center gap-1.5 truncate mr-2">
          <Icon name="lucide:fingerprint" class="size-3.5 text-slate-500 shrink-0" aria-hidden="true" />
          <span class="text-slate-500 select-none">SHA256:</span>
          <span class="truncate">{{ checksum }}</span>
        </div>
        <button
          type="button"
          class="text-primary hover:text-primary/80 font-sans text-[10px] font-semibold shrink-0 cursor-pointer flex items-center gap-1 focus-visible:outline-none"
          @click="copyChecksum"
        >
          <Icon :name="copied ? 'lucide:check' : 'lucide:copy'" class="size-3" aria-hidden="true" />
          <span>{{ copied ? 'Copied' : 'Copy' }}</span>
        </button>
      </div>
    </CardContent>
  </Card>
</template>
