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

interface ManifestFile {
  type: string;
  asset_id?: string | null;
  filename: string;
  byte_size?: number;
}

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

const manifest = computed(() => {
  return (props.packageAsset?.provenance as Record<string, any>)?.manifest || null;
});

const manifestFiles = computed<ManifestFile[]>(() => {
  if (manifest.value && Array.isArray(manifest.value.files) && manifest.value.files.length > 0) {
    return manifest.value.files;
  }
  return [];
});

const includedVariantFiles = computed<ManifestFile[]>(() => {
  return manifestFiles.value.filter(
    (f) => f.type !== 'original' && f.type !== 'pdf' && f.type !== 'readme' && f.type !== 'license'
  );
});

function getVariantTitle(type: string): string {
  if (type === 'dark_shirt') return 'Dark Shirt Variant PNG';
  if (type === 'light_shirt') return 'Light Shirt Variant PNG';
  if (type.startsWith('accent_') || type === 'custom') return 'Color Accent Variant PNG';
  return `${type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())} PNG`;
}

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
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:package-check" class="size-4 text-primary" aria-hidden="true" />
          <span>Buyer Delivery Package</span>
          <Badge v-if="packageAsset" variant="success" class="text-[10px] font-mono font-medium">
            <span class="size-1.5 rounded-full bg-emerald-500 mr-1 animate-pulse" aria-hidden="true" />
            Ready
          </Badge>
        </CardTitle>
        <CardDescription class="text-xs">
          Digital deliverables packaged for Etsy buyer download.
        </CardDescription>
      </div>

      <div class="flex items-center gap-2 self-start sm:self-auto shrink-0">
        <a
          v-if="downloadUrl"
          :href="sanitizeUrl(downloadUrl)"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted text-foreground transition-colors cursor-pointer"
        >
          <Icon name="lucide:download" class="size-3.5 text-primary" aria-hidden="true" />
          <span>Download ZIP</span>
        </a>

        <Button
          type="button"
          variant="outline"
          size="sm"
          class="h-8 gap-1.5 text-xs font-medium cursor-pointer"
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
        <!-- Master Artwork PNG -->
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

        <!-- Dynamically Included Artwork Variants -->
        <div
          v-for="variant in includedVariantFiles"
          :key="variant.filename"
          class="p-2.5 rounded-lg bg-muted/40 border border-border/70 flex items-center justify-between"
        >
          <div class="flex items-center gap-2.5">
            <Icon name="lucide:image" class="size-4 text-primary shrink-0" aria-hidden="true" />
            <div>
              <div class="flex items-center gap-1.5">
                <p class="font-semibold text-foreground">{{ getVariantTitle(variant.type) }}</p>
                <Badge variant="outline" class="text-[9px] px-1.5 py-0 font-mono text-primary border-primary/30 bg-primary/5">
                  Variant Included
                </Badge>
              </div>
              <p class="text-[11px] font-mono text-muted-foreground">{{ variant.filename }} • Transparent (300 DPI)</p>
            </div>
          </div>
          <Icon name="lucide:check" class="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
        </div>

        <!-- Print-Ready Vector PDF (if present) -->
        <div v-if="manifest?.has_pdf !== false" class="p-2.5 rounded-lg bg-muted/40 border border-border/70 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <Icon name="lucide:file-text" class="size-4 text-primary shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold text-foreground">Print-Ready Vector PDF</p>
              <p class="text-[11px] text-muted-foreground">15 × 18 in • Vector artwork PDF file</p>
            </div>
          </div>
          <Icon name="lucide:check" class="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
        </div>

        <!-- Commercial License -->
        <div class="p-2.5 rounded-lg bg-muted/40 border border-border/70 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <Icon name="lucide:shield-check" class="size-4 text-primary shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold text-foreground">Commercial License</p>
              <p class="text-[11px] text-muted-foreground">Unlimited POD &amp; physical commercial rights included</p>
            </div>
          </div>
          <Icon name="lucide:check" class="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
        </div>

        <!-- Sizing & Print Guide -->
        <div class="p-2.5 rounded-lg bg-muted/40 border border-border/70 flex items-center justify-between">
          <div class="flex items-center gap-2.5">
            <Icon name="lucide:book-open" class="size-4 text-primary shrink-0" aria-hidden="true" />
            <div>
              <p class="font-semibold text-foreground">Sizing &amp; Print Guide</p>
              <p class="text-[11px] text-muted-foreground">
                Comprehensive heat press, garment color usage &amp; sublimation instructions
              </p>
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
    </CardContent>
  </Card>
</template>

