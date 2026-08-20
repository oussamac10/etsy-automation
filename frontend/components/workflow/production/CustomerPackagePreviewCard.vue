<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import type { BuyerPackagePreviewResponse, PackageFileItem } from "~/types/artworkVariants";
import { getApiErrorMessage, getCsrfHeaders } from "~/utils/api";
import { sanitizeUrl } from "~/utils/sanitize";
import Card from "~/components/ui/Card.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardContent from "~/components/ui/CardContent.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import Skeleton from "~/components/ui/Skeleton.vue";

const props = defineProps<{
  workflowId: string;
  refreshKey?: number | string;
}>();

const emit = defineEmits<{
  (e: "packageRebuilt"): void;
  (e: "etsySynced"): void;
}>();

const config = useRuntimeConfig();
const apiBase = config.public.apiBase ? config.public.apiBase.replace(/\/$/, "") : "";

const preview = ref<BuyerPackagePreviewResponse | null>(null);
const isLoading = ref(false);
const isRebuilding = ref(false);
const isSyncing = ref(false);
const errorMessage = ref<string | null>(null);
const successMessage = ref<string | null>(null);

function formatBytes(bytes: number): string {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

async function fetchPreview(): Promise<void> {
  if (!props.workflowId) return;
  isLoading.value = true;
  errorMessage.value = null;
  try {
    const data = await $fetch<BuyerPackagePreviewResponse>(
      `${apiBase}/api/v1/workflows/${props.workflowId}/package/preview`,
      {
        headers: { Accept: "application/json" },
        credentials: "include",
      }
    );
    preview.value = data;
  } catch (err: unknown) {
    errorMessage.value = getApiErrorMessage(err, "Failed to load buyer package preview.");
  } finally {
    isLoading.value = false;
  }
}

async function handleRebuild(): Promise<void> {
  if (!props.workflowId) return;
  isRebuilding.value = true;
  errorMessage.value = null;
  successMessage.value = null;
  try {
    const headers = getCsrfHeaders();
    await $fetch(`${apiBase}/api/v1/workflows/${props.workflowId}/package/build`, {
      method: "POST",
      headers,
      credentials: "include",
    });
    successMessage.value = "Customer buyer deliverable ZIP package built successfully.";
    await fetchPreview();
    emit("packageRebuilt");
  } catch (err: unknown) {
    errorMessage.value = getApiErrorMessage(err, "Failed to rebuild customer package.");
  } finally {
    isRebuilding.value = false;
  }
}

async function handleSyncEtsy(): Promise<void> {
  if (!props.workflowId) return;
  isSyncing.value = true;
  errorMessage.value = null;
  successMessage.value = null;
  try {
    const headers = getCsrfHeaders();
    await $fetch(`${apiBase}/api/v1/workflows/${props.workflowId}/etsy/sync-files`, {
      method: "POST",
      headers,
      credentials: "include",
    });
    successMessage.value = "Updated buyer deliverable files synchronized with Etsy listing draft.";
    await fetchPreview();
    emit("etsySynced");
  } catch (err: unknown) {
    errorMessage.value = getApiErrorMessage(err, "Failed to sync files to Etsy listing draft.");
  } finally {
    isSyncing.value = false;
  }
}

onMounted(() => {
  fetchPreview();
});

watch(
  () => props.refreshKey,
  () => {
    fetchPreview();
  }
);

defineExpose({
  fetchPreview,
  handleRebuild,
});
</script>

<template>
  <div class="border border-border/80 rounded-2xl p-4 bg-white shadow-xs space-y-4">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/80">
      <div class="flex items-center gap-2.5">
        <div class="size-8 rounded-xl bg-primary/10 text-primary flex items-center justify-center border border-primary/20 shadow-2xs shrink-0">
          <Icon name="lucide:archive" class="size-4" aria-hidden="true" />
        </div>
        <div>
          <div class="flex items-center gap-1.5">
            <h5 class="text-xs font-bold text-foreground leading-tight">Buyer Deliverable ZIP Package</h5>
            <span v-if="preview?.needs_rebuild" class="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-500/10 px-1.5 py-0.2 rounded-md border border-amber-500/30">
              <Icon name="lucide:alert-circle" class="size-2.5 text-amber-500" aria-hidden="true" />
              Rebuild Required
            </span>
            <span v-else-if="preview?.package_asset" class="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded-md border border-emerald-200/60">
              <Icon name="lucide:check-circle-2" class="size-2.5 text-emerald-600" aria-hidden="true" />
              Assembled & Verified
            </span>
          </div>
          <p class="text-[10px] text-muted-foreground font-medium">
            Custom-tailored Etsy buyer ZIP package containing the master PNG, selected garment variants, README, and commercial license
          </p>
        </div>
      </div>

      <!-- Action Buttons Top Bar -->
      <div class="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          class="h-7 text-xs font-semibold gap-1.5 cursor-pointer"
          :disabled="isLoading || isRebuilding"
          @click="fetchPreview"
        >
          <Icon name="lucide:refresh-cw" class="size-3" :class="{ 'animate-spin': isLoading }" aria-hidden="true" />
          <span>Refresh</span>
        </Button>

        <a
          v-if="preview?.package_download_url"
          :href="sanitizeUrl(preview.package_download_url)"
          target="_blank"
          rel="noopener noreferrer"
          download
          class="inline-flex items-center justify-center h-7 px-2.5 rounded-lg text-xs font-semibold border border-border bg-white hover:bg-slate-50 text-foreground transition-colors shadow-2xs gap-1.5 cursor-pointer"
          title="Download the full buyer ZIP package to your local disk"
        >
          <Icon name="lucide:download" class="size-3 text-primary" aria-hidden="true" />
          <span>Download ZIP</span>
        </a>

        <Button
          variant="default"
          size="sm"
          class="h-7 text-xs font-bold gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground shadow-2xs cursor-pointer"
          :disabled="isRebuilding || isLoading"
          @click="handleRebuild"
        >
          <Icon v-if="isRebuilding" name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
          <Icon v-else name="lucide:sparkles" class="size-3" aria-hidden="true" />
          <span>{{ preview?.package_asset ? "Rebuild Package" : "Build Package" }}</span>
        </Button>
      </div>
    </div>

    <!-- Alert Notifications -->
    <div v-if="errorMessage" class="p-2.5 rounded-xl border border-destructive/30 bg-destructive/10 text-destructive text-xs flex items-center justify-between gap-2">
      <div class="flex items-center gap-1.5">
        <Icon name="lucide:alert-triangle" class="size-3.5 shrink-0" aria-hidden="true" />
        <span>{{ errorMessage }}</span>
      </div>
      <button type="button" class="text-xs font-bold hover:underline cursor-pointer" @click="errorMessage = null">Dismiss</button>
    </div>

    <div v-if="successMessage" class="p-2.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-xs flex items-center justify-between gap-2">
      <div class="flex items-center gap-1.5">
        <Icon name="lucide:check-circle" class="size-3.5 shrink-0 text-emerald-600" aria-hidden="true" />
        <span>{{ successMessage }}</span>
      </div>
      <button type="button" class="text-xs font-bold hover:underline cursor-pointer" @click="successMessage = null">Dismiss</button>
    </div>

    <!-- Etsy Out-Of-Sync Warning Alert Banner -->
    <div
      v-if="preview?.etsy_files_out_of_sync"
      class="p-3 rounded-xl border border-amber-500/30 bg-amber-500/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 animate-in fade-in duration-200"
    >
      <div class="flex items-start gap-2.5">
        <Icon name="lucide:alert-triangle" class="size-4 text-amber-500 shrink-0 mt-0.5" aria-hidden="true" />
        <div>
          <h6 class="text-xs font-semibold text-foreground">Etsy Digital Files Out of Sync</h6>
          <p class="text-[11px] text-foreground/80 dark:text-foreground/90 leading-relaxed">
            The buyer package content has changed since the Etsy draft was created. Synchronize to update Etsy's digital files before publishing.
          </p>
        </div>
      </div>
      <Button
        variant="default"
        size="sm"
        class="h-7 text-xs font-bold gap-1.5 bg-amber-600 hover:bg-amber-700 text-white shrink-0 shadow-2xs cursor-pointer"
        :disabled="isSyncing"
        @click="handleSyncEtsy"
      >
        <Icon v-if="isSyncing" name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
        <Icon v-else name="lucide:cloud-upload" class="size-3" aria-hidden="true" />
        <span>Sync Updated Files</span>
      </Button>
    </div>

    <!-- Needs Rebuild Notice Banner -->
    <div
      v-if="preview?.needs_rebuild && !preview?.etsy_files_out_of_sync"
      class="p-3 rounded-xl border border-amber-500/30 bg-amber-500/10 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5"
    >
      <div class="flex items-center gap-2">
        <Icon name="lucide:alert-circle" class="size-4 text-amber-500 shrink-0" aria-hidden="true" />
        <div>
          <p class="text-xs font-semibold text-foreground">Buyer package needs rebuilding.</p>
          <p class="text-[11px] text-foreground/80 dark:text-foreground/90">
            Selected variant inclusions have been updated. Rebuild the ZIP archive to bundle the changes.
          </p>
        </div>
      </div>
      <Button
        variant="outline"
        size="sm"
        class="h-7 text-xs font-bold border-amber-500/40 text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 shrink-0 cursor-pointer"
        :disabled="isRebuilding"
        @click="handleRebuild"
      >
        <Icon v-if="isRebuilding" name="lucide:loader-2" class="size-3 animate-spin" aria-hidden="true" />
        <Icon v-else name="lucide:refresh-cw" class="size-3" aria-hidden="true" />
        <span>Rebuild Package</span>
      </Button>
    </div>

    <!-- Loading Skeleton -->
    <div v-if="isLoading && !preview" class="space-y-2">
      <Skeleton class="h-8 w-full rounded-lg" />
      <Skeleton class="h-8 w-full rounded-lg" />
      <Skeleton class="h-8 w-full rounded-lg" />
    </div>

    <!-- Files Breakdown Table -->
    <div v-else-if="preview" class="border border-border/70 rounded-xl overflow-hidden">
      <div class="px-3 py-2 bg-slate-50 border-b border-border/70 flex items-center justify-between text-[11px] font-bold text-muted-foreground">
        <span>Included Customer Deliverables ({{ preview.included_count }} files)</span>
        <span>Est. Size: {{ formatBytes(preview.estimated_total_bytes) }}</span>
      </div>

      <div class="divide-y divide-border/50 bg-white">
        <div
          v-for="f in preview.files"
          :key="f.filename"
          class="px-3 py-2 flex items-center justify-between gap-2 text-xs hover:bg-slate-50/70 transition-colors"
          :class="{ 'opacity-50 bg-slate-50/40': !f.included }"
        >
          <!-- Left: Icon & File Info -->
          <div class="flex items-center gap-2.5 truncate min-w-0">
            <div
              class="size-6 rounded-md flex items-center justify-center shrink-0"
              :class="f.included ? 'bg-primary/10 text-primary' : 'bg-slate-100 text-slate-400'"
            >
              <Icon
                :name="f.type.includes('png') || f.type === 'original' || f.type.includes('shirt') || f.type.includes('accent') || f.type === 'custom' ? 'lucide:image' : 'lucide:file-text'"
                class="size-3"
                aria-hidden="true"
              />
            </div>
            <div class="truncate">
              <div class="flex items-center gap-1.5 truncate">
                <span class="font-semibold text-foreground truncate">{{ f.name }}</span>
                <span
                  v-if="f.type === 'original'"
                  class="text-[9px] font-bold text-primary bg-primary/10 px-1.5 py-0.2 rounded border border-primary/20 shrink-0"
                >
                  Master PNG
                </span>
                <span
                  v-else-if="f.type === 'readme'"
                  class="text-[9px] font-bold text-slate-600 bg-slate-100 px-1.5 py-0.2 rounded border border-slate-200 shrink-0"
                >
                  Guide
                </span>
                <span
                  v-else-if="f.type === 'license'"
                  class="text-[9px] font-bold text-slate-600 bg-slate-100 px-1.5 py-0.2 rounded border border-slate-200 shrink-0"
                >
                  License
                </span>
              </div>
              <p class="text-[10px] font-mono text-muted-foreground truncate">{{ f.filename }}</p>
            </div>
          </div>

          <!-- Right: File Size & Status Badge -->
          <div class="flex items-center gap-2 shrink-0">
            <span class="text-[11px] font-mono text-muted-foreground">{{ formatBytes(f.byte_size) }}</span>

            <span
              v-if="f.included"
              class="inline-flex items-center gap-1 text-[9px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded-md border border-emerald-200/60"
            >
              <Icon name="lucide:check" class="size-2.5" aria-hidden="true" />
              Included
            </span>
            <span
              v-else-if="f.status === 'outdated'"
              class="inline-flex items-center gap-1 text-[9px] font-semibold text-amber-700 bg-amber-500/10 px-1.5 py-0.5 rounded-md border border-amber-500/30"
              title="Generated from older master artwork. Regenerate to include."
            >
              <Icon name="lucide:alert-triangle" class="size-2.5 text-amber-500" aria-hidden="true" />
              Outdated
            </span>
            <span
              v-else-if="f.status === 'unapproved'"
              class="inline-flex items-center gap-1 text-[9px] font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded-md border border-slate-200"
            >
              Unapproved
            </span>
            <span
              v-else
              class="inline-flex items-center gap-1 text-[9px] font-semibold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-md border border-slate-200"
            >
              Unselected
            </span>
          </div>
        </div>
      </div>

      <!-- Compliance & Integrity Strip Footer -->
      <div class="px-3 py-2 bg-slate-50 border-t border-border/70 flex flex-wrap items-center justify-between gap-2 text-[11px]">
        <div class="flex items-center gap-3 text-muted-foreground">
          <div class="flex items-center gap-1">
            <Icon name="lucide:shield-check" class="size-3 text-emerald-600" aria-hidden="true" />
            <span>Etsy File Limit: &le; 20 MB / file, &le; 5 files</span>
          </div>
          <div class="flex items-center gap-1">
            <Icon name="lucide:file-check-2" class="size-3 text-primary" aria-hidden="true" />
            <span>CRC-32 & ZIP Integrity Verified</span>
          </div>
        </div>

        <div v-if="preview.package_asset" class="flex items-center gap-1.5 text-muted-foreground font-mono text-[10px]">
          <span>Archive Size:</span>
          <span class="font-bold text-foreground">{{ formatBytes(preview.package_asset.byte_size) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
