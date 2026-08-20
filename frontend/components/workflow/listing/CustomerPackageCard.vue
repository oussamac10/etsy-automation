<script setup lang="ts">
import { computed, ref } from 'vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
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
  <Card class="border-border bg-card shadow-xs overflow-hidden" data-testid="customer-package-card">
    <CardHeader class="p-4 sm:p-5 pb-3">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
            <Icon name="lucide:package-check" class="size-4" aria-hidden="true" />
          </div>
          <div class="min-w-0">
            <CardTitle class="text-sm font-semibold tracking-tight flex items-center gap-2">
              <span>Buyer Delivery Package</span>
              <Badge v-if="packageAsset" variant="outline" class="text-[10px] font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20">
                Ready
              </Badge>
            </CardTitle>
            <CardDescription class="text-xs text-muted-foreground truncate">
              Digital deliverables packaged for Etsy buyer download.
            </CardDescription>
          </div>
        </div>

        <Button
          type="button"
          variant="outline"
          size="sm"
          class="h-8 gap-1.5 text-xs font-medium shrink-0 cursor-pointer"
          :disabled="isBuilding"
          @click="emit('build-package')"
        >
          <Icon v-if="isBuilding" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:refresh-cw" class="size-3.5 text-primary" aria-hidden="true" />
          <span>{{ isBuilding ? 'Building...' : packageAsset ? 'Rebuild' : 'Build Package' }}</span>
        </Button>
      </div>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-3 text-xs">
      <!-- Deliverables Clean Vertical List -->
      <div class="space-y-2">
        <div class="p-2.5 rounded-lg bg-muted/40 border border-border/70 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <Icon name="lucide:file-image" class="size-4 text-primary shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold text-foreground">Master Artwork PNG</p>
              <p class="text-[11px] text-muted-foreground">4500 × 5400 px • Transparent background (300 DPI)</p>
            </div>
          </div>
          <Icon name="lucide:check" class="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
        </div>

        <div class="p-2.5 rounded-lg bg-muted/40 border border-border/70 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <Icon name="lucide:file-text" class="size-4 text-primary shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold text-foreground">Print-Ready Vector PDF</p>
              <p class="text-[11px] text-muted-foreground">15 × 18 in • Vector artwork PDF file</p>
            </div>
          </div>
          <Icon name="lucide:check" class="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
        </div>

        <div class="p-2.5 rounded-lg bg-muted/40 border border-border/70 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <Icon name="lucide:shield-check" class="size-4 text-primary shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold text-foreground">Commercial License</p>
              <p class="text-[11px] text-muted-foreground">Unlimited POD & physical commercial rights included</p>
            </div>
          </div>
          <Icon name="lucide:check" class="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
        </div>

        <div class="p-2.5 rounded-lg bg-muted/40 border border-border/70 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <Icon name="lucide:book-open" class="size-4 text-primary shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold text-foreground">Sizing &amp; Print Guide</p>
              <p class="text-[11px] text-muted-foreground">Comprehensive heat press &amp; sublimation instructions</p>
            </div>
          </div>
          <Icon name="lucide:check" class="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
        </div>
      </div>

      <!-- Etsy File Usage Stats -->
      <div class="pt-2 border-t border-border/50 flex items-center justify-between text-muted-foreground">
        <span class="flex items-center gap-1.5">
          <Icon name="lucide:hard-drive" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Etsy Delivery Usage: <strong class="text-foreground font-semibold">1 / 5 file slots</strong> used</span>
        </span>
        <span v-if="byteSize" class="font-mono text-[11px] font-semibold text-foreground">{{ byteSize }}</span>
      </div>

      <!-- Download Link Button -->
      <div v-if="downloadUrl" class="pt-1">
        <a
          :href="sanitizeUrl(downloadUrl)"
          target="_blank"
          rel="noopener noreferrer"
          class="w-full inline-flex items-center justify-center gap-1.5 h-8 px-3 rounded-md text-xs font-semibold bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
        >
          <Icon name="lucide:download" class="size-3.5" aria-hidden="true" />
          <span>Download Package ZIP</span>
        </a>
      </div>
    </CardContent>
  </Card>
</template>
