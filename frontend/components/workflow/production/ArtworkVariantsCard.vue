<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import type { ArtworkVariantItem, VariantType } from "~/types/artworkVariants";
import { useArtworkVariants } from "~/composables/useArtworkVariants";
import { sanitizeUrl } from "~/utils/sanitize";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import Skeleton from "~/components/ui/Skeleton.vue";
import DeleteConfirmModal from "~/components/ui/DeleteConfirmModal.vue";

const props = defineProps<{
  workflowId: string;
  masterImageUrl?: string | null;
}>();

const emit = defineEmits<{
  (e: "variantUpdated"): void;
}>();

const {
  variants,
  approvedVariants,
  isFetching,
  isGenerating,
  isActing,
  actionError,
  fetchVariants,
  generateVariant,
  approveVariant,
  rejectVariant,
  deleteVariant,
} = useArtworkVariants();

type BgMode = "transparent" | "white" | "black" | "charcoal";
const previewBg = ref<BgMode>("transparent");

const showCreateModal = ref(false);
const selectedType = ref<VariantType>("dark_shirt");
const customColor = ref("#E85D04");
const customInstructions = ref("");

const zoomedImageUrl = ref<string | null>(null);
const zoomedTitle = ref<string>("");

const variantToDelete = ref<ArtworkVariantItem | null>(null);
const isDeleting = ref(false);
const deleteError = ref<string | null>(null);

const presetOptions: Array<{
  type: VariantType;
  title: string;
  desc: string;
  icon: string;
  badge: string;
}> = [
  {
    type: "dark_shirt",
    title: "Dark Shirt Version",
    desc: "Light cream & off-white details optimized for black & dark garments",
    icon: "lucide:moon",
    badge: "Recommended for Black Tees",
  },
  {
    type: "light_shirt",
    title: "Light Shirt Version",
    desc: "Dark charcoal & deep outlines optimized for white & pastel garments",
    icon: "lucide:sun",
    badge: "Recommended for White Tees",
  },
  {
    type: "black_accent",
    title: "Black Accent Version",
    desc: "Key lines and secondary highlights converted to rich black tones",
    icon: "lucide:circle-dot",
    badge: "Monochrome Black",
  },
  {
    type: "white_accent",
    title: "White / Cream Accent",
    desc: "Key lines and secondary highlights converted to crisp white tones",
    icon: "lucide:circle",
    badge: "Monochrome White",
  },
  {
    type: "custom",
    title: "Custom Brand Accent",
    desc: "Replace targeted accent elements with your custom brand HEX color",
    icon: "lucide:palette",
    badge: "Custom Color",
  },
];

onMounted(() => {
  if (props.workflowId) {
    fetchVariants(props.workflowId);
  }
});

async function handleCreateVariant(): Promise<void> {
  const result = await generateVariant(props.workflowId, {
    variant_type: selectedType.value,
    custom_color: selectedType.value === "custom" ? customColor.value : undefined,
    custom_instructions: customInstructions.value.trim() || undefined,
  });

  if (result) {
    showCreateModal.value = false;
    customInstructions.value = "";
    emit("variantUpdated");
  }
}

async function handleApprove(v: ArtworkVariantItem): Promise<void> {
  const ok = await approveVariant(props.workflowId, v.id);
  if (ok) {
    emit("variantUpdated");
  }
}

async function handleReject(v: ArtworkVariantItem): Promise<void> {
  const ok = await rejectVariant(props.workflowId, v.id);
  if (ok) {
    emit("variantUpdated");
  }
}

function openDeleteModal(v: ArtworkVariantItem): void {
  variantToDelete.value = v;
  deleteError.value = null;
}

async function confirmDelete(): Promise<void> {
  if (!variantToDelete.value) return;
  isDeleting.value = true;
  deleteError.value = null;
  const ok = await deleteVariant(props.workflowId, variantToDelete.value.id);
  if (ok) {
    variantToDelete.value = null;
    emit("variantUpdated");
  } else {
    deleteError.value = actionError.value || "Failed to delete variant.";
  }
  isDeleting.value = false;
}

function getBgClass(bg: BgMode): string {
  if (bg === "white") return "bg-white";
  if (bg === "black") return "bg-[#121212]";
  if (bg === "charcoal") return "bg-[#2D3748]";
  return "bg-[linear-gradient(45deg,#F1F5F9_25%,transparent_25%),linear-gradient(-45deg,#F1F5F9_25%,transparent_25%),linear-gradient(45deg,transparent_75%,#F1F5F9_75%),linear-gradient(-45deg,transparent_75%,#F1F5F9_75%)] bg-[size:14px_14px] bg-[position:0_0,0_7px,7px_-7px,-7px_0px]";
}
</script>

<template>
  <div class="border border-border/80 rounded-2xl p-4 bg-white shadow-xs space-y-4">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/80">
      <div class="flex items-center gap-2.5">
        <div class="size-8 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center border border-violet-200/80 shadow-2xs shrink-0">
          <Icon name="lucide:palette" class="size-4" aria-hidden="true" />
        </div>
        <div>
          <div class="flex items-center gap-1.5">
            <h5 class="text-xs font-bold text-foreground leading-tight">Garment Color Variants</h5>
            <span v-if="approvedVariants.length > 0" class="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded-md border border-emerald-200/60">
              <span class="size-1 rounded-full bg-emerald-500" />
              {{ approvedVariants.length }} Approved in ZIP
            </span>
          </div>
          <p class="text-[10px] text-muted-foreground font-medium">
            High-contrast transparent PNGs optimized for dark & light shirts without altering the master
          </p>
        </div>
      </div>

      <!-- Actions & Background Switcher Toolbar -->
      <div class="flex items-center gap-2 shrink-0 flex-wrap">
        <!-- Background Switcher -->
        <div class="flex items-center gap-1 bg-secondary/50 p-0.5 rounded-lg border border-border/80 text-[11px]">
          <button
            type="button"
            class="px-2 py-1 rounded-md font-semibold flex items-center gap-1 transition-all cursor-pointer"
            :class="previewBg === 'transparent' ? 'bg-white text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
            title="Transparent Checkerboard"
            @click="previewBg = 'transparent'"
          >
            <Icon name="lucide:grid" class="size-3" aria-hidden="true" />
            <span class="hidden md:inline">Alpha</span>
          </button>
          <button
            type="button"
            class="px-2 py-1 rounded-md font-semibold flex items-center gap-1 transition-all cursor-pointer"
            :class="previewBg === 'white' ? 'bg-white text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
            title="White Garment Background"
            @click="previewBg = 'white'"
          >
            <span class="size-2.5 rounded-full bg-white border border-slate-300 inline-block" />
            <span class="hidden md:inline">White</span>
          </button>
          <button
            type="button"
            class="px-2 py-1 rounded-md font-semibold flex items-center gap-1 transition-all cursor-pointer"
            :class="previewBg === 'black' ? 'bg-white text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
            title="Black Garment Background"
            @click="previewBg = 'black'"
          >
            <span class="size-2.5 rounded-full bg-black inline-block" />
            <span class="hidden md:inline">Black</span>
          </button>
          <button
            type="button"
            class="px-2 py-1 rounded-md font-semibold flex items-center gap-1 transition-all cursor-pointer"
            :class="previewBg === 'charcoal' ? 'bg-white text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
            title="Dark Heather / Charcoal Background"
            @click="previewBg = 'charcoal'"
          >
            <span class="size-2.5 rounded-full bg-[#2D3748] inline-block" />
            <span class="hidden md:inline">Charcoal</span>
          </button>
        </div>

        <!-- Add Variant Trigger Button -->
        <Button
          variant="default"
          size="sm"
          class="text-xs font-bold gap-1.5 shadow-2xs cursor-pointer inline-flex items-center"
          :disabled="isGenerating"
          @click="showCreateModal = true"
        >
          <Icon name="lucide:plus" class="size-3.5" aria-hidden="true" />
          <span>New Color Variant</span>
        </Button>
      </div>
    </div>

    <!-- Error Alert -->
    <Alert v-if="actionError" variant="destructive" class="py-2.5">
      <Icon name="lucide:circle-alert" class="size-4" aria-hidden="true" />
      <div>
        <AlertTitle class="text-xs font-bold">Variant Operation Error</AlertTitle>
        <AlertDescription class="text-xs">{{ actionError }}</AlertDescription>
      </div>
    </Alert>

    <!-- Generating Progress Banner -->
    <div v-if="isGenerating" class="p-4 rounded-xl border border-primary/20 bg-primary/5 flex items-center gap-3 animate-in fade-in duration-200">
      <Icon name="lucide:loader-2" class="size-5 animate-spin text-primary shrink-0" aria-hidden="true" />
      <div>
        <p class="text-xs font-bold text-foreground">Generating Color-Safe Artwork Variant...</p>
        <p class="text-[11px] text-muted-foreground">Extracting high-contrast tones, preserving alpha transparency & details.</p>
      </div>
    </div>

    <!-- Variants Grid -->
    <div v-if="variants.length > 0" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <div
        v-for="item in variants"
        :key="item.id"
        class="border border-border/80 rounded-xl overflow-hidden bg-slate-50/50 hover:shadow-xs transition-all flex flex-col justify-between"
      >
        <!-- Card Top Bar -->
        <div class="p-3 pb-2 flex items-center justify-between gap-2 border-b border-border/60 bg-white">
          <div class="flex items-center gap-1.5 truncate">
            <span class="text-xs font-bold text-foreground truncate">{{ item.title }}</span>
            <Badge v-if="item.custom_color" variant="outline" class="text-[9px] px-1.5 py-0 font-mono">
              {{ item.custom_color }}
            </Badge>
          </div>

          <!-- Status Badge -->
          <span
            v-if="item.variant_status === 'approved'"
            class="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200"
          >
            <Icon name="lucide:check" class="size-2.5" aria-hidden="true" />
            Approved
          </span>
          <span
            v-else-if="item.variant_status === 'rejected'"
            class="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200"
          >
            Rejected
          </span>
          <span
            v-else
            class="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30"
          >
            Ready for Review
          </span>
        </div>

        <!-- Image Preview Frame with Interactive Background -->
        <div
          class="relative group w-full h-[200px] overflow-hidden flex items-center justify-center p-3 transition-colors duration-200"
          :class="getBgClass(previewBg)"
        >
          <img
            v-if="item.url"
            :src="item.url"
            :alt="item.title"
            class="object-contain max-h-[170px] w-full transition-transform duration-200 group-hover:scale-105"
          >
          <div v-else class="flex flex-col items-center justify-center gap-2 text-muted-foreground">
            <Icon name="lucide:image" class="size-8 animate-pulse text-slate-300" />
            <span class="text-[11px]">Loading variant preview...</span>
          </div>

          <!-- Hover Overlay -->
          <div
            v-if="item.url"
            class="absolute inset-0 bg-black/40 backdrop-blur-2xs opacity-0 group-hover:opacity-100 transition-opacity duration-150 flex items-center justify-center gap-2"
          >
            <button
              type="button"
              class="h-7 px-2.5 rounded-md bg-white/95 hover:bg-white text-slate-900 text-[11px] font-semibold shadow-xs flex items-center gap-1 cursor-pointer"
              title="Inspect Zoom"
              @click="zoomedImageUrl = item.url; zoomedTitle = item.title"
            >
              <Icon name="lucide:zoom-in" class="size-3" aria-hidden="true" />
              <span>Zoom</span>
            </button>
            <a
              :href="sanitizeUrl(item.url)"
              target="_blank"
              rel="noopener noreferrer"
              :download="`${item.title.toLowerCase().replace(/\\s+/g, '_')}_300dpi.png`"
              class="h-7 w-7 rounded-md bg-white/95 hover:bg-white text-slate-900 flex items-center justify-center shadow-xs cursor-pointer"
              title="Download Variant PNG"
            >
              <Icon name="lucide:download" class="size-3" aria-hidden="true" />
            </a>
          </div>
        </div>

        <!-- Card Footer Actions -->
        <div class="p-2.5 border-t border-border/60 bg-white flex items-center justify-between gap-2">
          <div class="flex items-center gap-1.5">
            <Button
              v-if="item.variant_status !== 'approved'"
              variant="default"
              size="sm"
              class="h-7 text-[11px] font-bold px-2.5 gap-1 bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer"
              :disabled="isActing"
              @click="handleApprove(item)"
            >
              <Icon name="lucide:check" class="size-3" aria-hidden="true" />
              <span>Approve</span>
            </Button>
            <Button
              v-if="item.variant_status === 'approved'"
              variant="outline"
              size="sm"
              class="h-7 text-[11px] px-2 text-muted-foreground hover:text-foreground cursor-pointer"
              :disabled="isActing"
              @click="handleReject(item)"
            >
              Reject
            </Button>
            <Button
              v-else-if="item.variant_status !== 'rejected'"
              variant="outline"
              size="sm"
              class="h-7 text-[11px] px-2 text-muted-foreground hover:text-foreground cursor-pointer"
              :disabled="isActing"
              @click="handleReject(item)"
            >
              Reject
            </Button>
          </div>

          <button
            type="button"
            class="h-7 w-7 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 flex items-center justify-center transition-colors cursor-pointer"
            title="Delete Variant"
            :disabled="isActing"
            @click="openDeleteModal(item)"
          >
            <Icon name="lucide:trash-2" class="size-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="!isFetching"
      class="py-8 px-4 text-center rounded-xl border border-dashed border-border bg-secondary/15 space-y-3"
    >
      <div class="size-10 rounded-2xl bg-secondary text-primary border border-border/80 flex items-center justify-center mx-auto shadow-2xs">
        <Icon name="lucide:palette" class="size-5" aria-hidden="true" />
      </div>
      <div class="max-w-md mx-auto">
        <p class="text-xs font-bold text-foreground">No garment color variants generated yet</p>
        <p class="text-[11px] text-muted-foreground mt-0.5">
          Generate an alternate Dark Shirt or Light Shirt version to prevent dark lines disappearing on black garments.
        </p>
      </div>
      <div class="flex items-center justify-center gap-2 pt-1 flex-wrap">
        <Button
          variant="outline"
          size="sm"
          class="text-xs font-semibold gap-1.5 cursor-pointer"
          @click="selectedType = 'dark_shirt'; showCreateModal = true"
        >
          <Icon name="lucide:moon" class="size-3.5 text-violet-500" aria-hidden="true" />
          <span>Create Dark Shirt Version</span>
        </Button>
        <Button
          variant="outline"
          size="sm"
          class="text-xs font-semibold gap-1.5 cursor-pointer"
          @click="selectedType = 'light_shirt'; showCreateModal = true"
        >
          <Icon name="lucide:sun" class="size-3.5 text-amber-500" aria-hidden="true" />
          <span>Create Light Shirt Version</span>
        </Button>
      </div>
    </div>

    <!-- Loading Skeleton -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <Skeleton class="h-[260px] rounded-xl" />
      <Skeleton class="h-[260px] rounded-xl" />
    </div>

    <!-- Create Variant Modal Dialog -->
    <div
      v-if="showCreateModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-150"
      @click="showCreateModal = false"
    >
      <div
        class="bg-white rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden border border-border flex flex-col max-h-[90vh]"
        @click.stop
      >
        <!-- Modal Header -->
        <div class="px-5 py-3.5 border-b border-border flex items-center justify-between bg-secondary/30">
          <div class="flex items-center gap-2">
            <div class="size-8 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center border border-violet-200/80 shadow-2xs">
              <Icon name="lucide:wand-2" class="size-4" aria-hidden="true" />
            </div>
            <div>
              <h4 class="text-xs font-bold text-foreground">Create Garment Color Variant</h4>
              <p class="text-[10px] text-muted-foreground">Derived from approved master PNG without mutating original</p>
            </div>
          </div>
          <button
            type="button"
            class="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center justify-center transition-colors cursor-pointer"
            @click="showCreateModal = false"
          >
            <Icon name="lucide:x" class="size-3.5" aria-hidden="true" />
          </button>
        </div>

        <!-- Modal Body -->
        <div class="p-5 overflow-y-auto space-y-4">
          <!-- Presets Grid -->
          <div class="space-y-2">
            <label class="text-xs font-bold text-foreground">Select Variant Type</label>
            <div class="grid grid-cols-1 gap-2">
              <button
                v-for="opt in presetOptions"
                :key="opt.type"
                type="button"
                class="p-2.5 rounded-xl border text-left flex items-start gap-3 transition-all cursor-pointer"
                :class="selectedType === opt.type ? 'border-primary bg-primary/5 ring-1 ring-primary/30 shadow-2xs' : 'border-border bg-white hover:bg-slate-50'"
                @click="selectedType = opt.type"
              >
                <div
                  class="size-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                  :class="selectedType === opt.type ? 'bg-primary text-white' : 'bg-secondary text-muted-foreground'"
                >
                  <Icon :name="opt.icon" class="size-3.5" aria-hidden="true" />
                </div>
                <div class="flex-1 truncate">
                  <div class="flex items-center justify-between gap-1">
                    <span class="text-xs font-bold text-foreground">{{ opt.title }}</span>
                    <span class="text-[9px] font-semibold px-1.5 py-0.2 rounded-md bg-secondary text-secondary-foreground border border-border">
                      {{ opt.badge }}
                    </span>
                  </div>
                  <p class="text-[11px] text-muted-foreground leading-tight mt-0.5">{{ opt.desc }}</p>
                </div>
              </button>
            </div>
          </div>

          <!-- Custom Color Picker if Custom selected -->
          <div v-if="selectedType === 'custom'" class="p-3 rounded-xl bg-secondary/30 border border-border space-y-2">
            <label class="text-xs font-bold text-foreground flex items-center gap-1.5">
              <span>Target Brand Accent Color</span>
            </label>
            <div class="flex items-center gap-3">
              <input
                v-model="customColor"
                type="color"
                class="size-9 rounded-lg border border-border cursor-pointer p-0.5 bg-white"
              >
              <input
                v-model="customColor"
                type="text"
                class="h-9 px-3 rounded-lg border border-border text-xs font-mono font-bold uppercase w-28 bg-white"
                placeholder="#E85D04"
              >
              <div class="flex items-center gap-1">
                <button
                  v-for="hex in ['#E85D04', '#F4A261', '#2A9D8F', '#E76F51', '#457B9D']"
                  :key="hex"
                  type="button"
                  class="size-6 rounded-md border border-border/80 cursor-pointer shadow-2xs hover:scale-110 transition-transform"
                  :style="{ backgroundColor: hex }"
                  @click="customColor = hex"
                />
              </div>
            </div>
          </div>

          <!-- Special Directive (Optional) -->
          <div class="space-y-1.5">
            <label class="text-xs font-bold text-foreground">Special Refinement Instructions (Optional)</label>
            <input
              v-model="customInstructions"
              type="text"
              class="h-9 px-3 rounded-lg border border-border text-xs w-full bg-white placeholder:text-muted-foreground focus:outline-hidden focus:ring-1 focus:ring-primary"
              placeholder="e.g. Ensure delicate inner flower line details remain crisp white"
            >
          </div>
        </div>

        <!-- Modal Footer -->
        <div class="px-5 py-3 border-t border-border flex items-center justify-between bg-secondary/20">
          <Button
            variant="outline"
            size="sm"
            class="text-xs cursor-pointer"
            :disabled="isGenerating"
            @click="showCreateModal = false"
          >
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="text-xs font-bold gap-1.5 shadow-2xs cursor-pointer inline-flex items-center"
            :disabled="isGenerating"
            @click="handleCreateVariant"
          >
            <Icon v-if="isGenerating" name="lucide:loader-2" class="size-3.5 animate-spin" aria-hidden="true" />
            <Icon v-else name="lucide:sparkles" class="size-3.5" aria-hidden="true" />
            <span>{{ isGenerating ? "Generating..." : "Generate Variant" }}</span>
          </Button>
        </div>
      </div>
    </div>

    <!-- Zoom Inspection Modal -->
    <div
      v-if="zoomedImageUrl"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xs animate-in fade-in duration-150"
      @click="zoomedImageUrl = null"
    >
      <div class="relative max-w-4xl max-h-[90vh] bg-slate-950 rounded-2xl overflow-hidden shadow-2xl p-3 border border-slate-800 flex flex-col" @click.stop>
        <div class="flex items-center justify-between pb-2 mb-2 border-b border-slate-800 px-2 text-slate-200">
          <span class="text-xs font-bold text-white">{{ zoomedTitle }} Inspection</span>
          <button
            type="button"
            class="h-7 w-7 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center justify-center transition-colors cursor-pointer"
            @click="zoomedImageUrl = null"
          >
            <Icon name="lucide:x" class="size-4" aria-hidden="true" />
          </button>
        </div>
        <div
          class="overflow-auto max-h-[75vh] flex items-center justify-center rounded-xl p-4 transition-colors"
          :class="getBgClass(previewBg)"
        >
          <img :src="zoomedImageUrl" :alt="zoomedTitle" class="max-h-[70vh] object-contain drop-shadow-2xl">
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Dialog -->
    <DeleteConfirmModal
      :open="Boolean(variantToDelete)"
      title="Delete Garment Variant?"
      description="Permanently delete this color-safe variant graphic from your workflow."
      :item-name="variantToDelete?.title || 'Color Variant'"
      item-category="Artwork Color Variant"
      :image-url="variantToDelete?.url || null"
      :is-deleting="isDeleting"
      :error="deleteError"
      confirm-text="Delete Variant"
      @close="variantToDelete = null"
      @confirm="confirmDelete"
    />
  </div>
</template>
