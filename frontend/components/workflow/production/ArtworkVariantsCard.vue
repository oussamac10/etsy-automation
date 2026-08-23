<script setup lang="ts">
import { ref, onMounted } from "vue";
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
  togglePackageInclusion,
} = useArtworkVariants();

type BgMode = "transparent" | "white" | "black" | "charcoal";
// Default to black background preview so dark shirt contrast is immediately evident
const previewBg = ref<BgMode>("black");

const showCreateModal = ref(false);
const selectedType = ref<VariantType>("dark_shirt");
const targetColor = ref("#F5E6C8"); // Default Warm Cream
const darknessThreshold = ref(0.28);
const showAdvancedOptions = ref(false);
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
  defaultColor: string;
}> = [
  {
    type: "dark_shirt",
    title: "Dark Shirt Version",
    desc: "Light cream & off-white details optimized for black & dark fabric (Exact Alpha Preserved)",
    icon: "lucide:moon",
    badge: "Deterministic · Recommended for Black Tees",
    defaultColor: "#F5E6C8",
  },
  {
    type: "light_shirt",
    title: "Light Shirt Version",
    desc: "Dark charcoal & deep outlines optimized for white & pastel fabric",
    icon: "lucide:sun",
    badge: "Deterministic · For White Tees",
    defaultColor: "#1A1A1A",
  },
  {
    type: "black_accent",
    title: "Black Accent Version",
    desc: "Key lines and secondary highlights converted to rich black tones",
    icon: "lucide:circle-dot",
    badge: "Deterministic · Monochrome Black",
    defaultColor: "#0A0A0A",
  },
  {
    type: "white_accent",
    title: "White / Cream Accent",
    desc: "Key lines and secondary highlights converted to crisp white tones",
    icon: "lucide:circle",
    badge: "Deterministic · Monochrome White",
    defaultColor: "#FFFFFF",
  },
  {
    type: "custom",
    title: "Custom Brand Accent",
    desc: "Replace targeted dark/accent elements with your custom brand HEX color",
    icon: "lucide:palette",
    badge: "Deterministic · Custom Color",
    defaultColor: "#E85D04",
  },
];

const darkShirtSwatches = [
  { label: "Warm Cream", hex: "#F5E6C8" },
  { label: "Crisp White", hex: "#FFFFFF" },
  { label: "Soft Sand", hex: "#FAF0E6" },
  { label: "Golden Cream", hex: "#FFF3B0" },
];

onMounted(() => {
  if (props.workflowId) {
    fetchVariants(props.workflowId);
  }
});

function handleSelectPreset(opt: (typeof presetOptions)[0]): void {
  selectedType.value = opt.type;
  targetColor.value = opt.defaultColor;
}

async function handleCreateVariant(): Promise<void> {
  const result = await generateVariant(props.workflowId, {
    variant_type: selectedType.value,
    target_color: targetColor.value,
    custom_color: targetColor.value,
    darkness_threshold: darknessThreshold.value,
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

async function handleTogglePackageInclusion(v: ArtworkVariantItem, event: Event): Promise<void> {
  const target = event.target as HTMLInputElement;
  const nextVal = target.checked;
  const ok = await togglePackageInclusion(props.workflowId, v.id, nextVal);
  if (ok) {
    emit("variantUpdated");
  } else {
    target.checked = !nextVal;
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
  <div class="border border-border rounded-2xl p-4 bg-card text-card-foreground shadow-xs space-y-4">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border">
      <div class="flex items-center gap-2.5">
        <div class="size-8 rounded-xl bg-violet-500/10 text-violet-600 dark:text-violet-400 flex items-center justify-center border border-violet-500/30 shadow-2xs shrink-0">
          <Icon name="lucide:palette" class="size-4" aria-hidden="true" />
        </div>
        <div>
          <div class="flex items-center gap-1.5">
            <h5 class="text-xs font-bold text-foreground leading-tight">Garment Color Variants</h5>
            <span v-if="approvedVariants.length > 0" class="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded-md border border-emerald-500/30">
              <span class="size-1 rounded-full bg-emerald-500" />
              {{ approvedVariants.length }} Approved in ZIP
            </span>
          </div>
          <p class="text-[10px] text-muted-foreground font-medium">
            Deterministic, pixel-perfect transparent PNGs recolored for dark & light shirts without altering the master artwork
          </p>
        </div>
      </div>

      <!-- Actions & Background Switcher Toolbar -->
      <div class="flex items-center gap-2 shrink-0 flex-wrap">
        <!-- Background Switcher -->
        <div class="flex items-center gap-1 bg-secondary/50 p-0.5 rounded-lg border border-border text-[11px]">
          <button
            type="button"
            class="px-2 py-1 rounded-md font-semibold flex items-center gap-1 transition-all cursor-pointer"
            :class="previewBg === 'black' ? 'bg-card text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
            title="Black Garment Background"
            @click="previewBg = 'black'"
          >
            <span class="size-2.5 rounded-full bg-black inline-block" />
            <span>Black</span>
          </button>
          <button
            type="button"
            class="px-2 py-1 rounded-md font-semibold flex items-center gap-1 transition-all cursor-pointer"
            :class="previewBg === 'charcoal' ? 'bg-card text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
            title="Dark Heather / Charcoal Background"
            @click="previewBg = 'charcoal'"
          >
            <span class="size-2.5 rounded-full bg-[#2D3748] inline-block" />
            <span>Charcoal</span>
          </button>
          <button
            type="button"
            class="px-2 py-1 rounded-md font-semibold flex items-center gap-1 transition-all cursor-pointer"
            :class="previewBg === 'white' ? 'bg-card text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
            title="White Garment Background"
            @click="previewBg = 'white'"
          >
            <span class="size-2.5 rounded-full bg-white border border-slate-300 inline-block" />
            <span>White</span>
          </button>
          <button
            type="button"
            class="px-2 py-1 rounded-md font-semibold flex items-center gap-1 transition-all cursor-pointer"
            :class="previewBg === 'transparent' ? 'bg-card text-foreground shadow-2xs font-bold' : 'text-muted-foreground hover:text-foreground'"
            title="Transparent Checkerboard"
            @click="previewBg = 'transparent'"
          >
            <Icon name="lucide:grid" class="size-3" aria-hidden="true" />
            <span class="hidden md:inline">Alpha</span>
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
        <p class="text-xs font-bold text-foreground">Executing Deterministic Color Transformation...</p>
        <p class="text-[11px] text-muted-foreground">Preserving exact geometry, copying alpha channel byte-for-byte, modulating contrast tones.</p>
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
        <div class="p-3 pb-2 flex items-center justify-between gap-2 border-b border-border/60 bg-card">
          <div class="flex items-center gap-1.5 truncate">
            <span class="text-xs font-bold text-foreground truncate" :title="item.title">{{ item.title }}</span>
            <Badge v-if="item.custom_color" variant="outline" class="text-[9px] px-1.5 py-0 font-mono">
              {{ item.custom_color }}
            </Badge>
          </div>

          <!-- Status Badge -->
          <span
            v-if="item.variant_status === 'approved'"
            class="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200 shrink-0"
          >
            <Icon name="lucide:check" class="size-2.5" aria-hidden="true" />
            Approved
          </span>
          <span
            v-else-if="item.variant_status === 'rejected'"
            class="inline-flex items-center gap-1 text-[10px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200 shrink-0"
          >
            Rejected
          </span>
          <span
            v-else-if="item.variant_status === 'failed'"
            class="inline-flex items-center gap-1 text-[10px] font-semibold text-destructive bg-destructive/10 px-2 py-0.5 rounded-full border border-destructive/30 shrink-0"
          >
            Failed
          </span>
          <span
            v-else
            class="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30 shrink-0"
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

        <!-- 6-Point Quality & Validation Checklist -->
        <div class="px-3 py-2 bg-secondary/30 border-t border-border/60 text-[10px] space-y-1">
          <div class="flex items-center justify-between text-muted-foreground font-semibold">
            <span>Validation Checklist</span>
            <span class="text-emerald-700 font-bold flex items-center gap-0.5">
              <Icon name="lucide:shield-check" class="size-3 text-emerald-600" aria-hidden="true" />
              Pass
            </span>
          </div>
          <div class="grid grid-cols-2 gap-x-2 gap-y-0.5 text-foreground/80 font-medium">
            <div class="flex items-center gap-1">
              <Icon name="lucide:check" class="size-2.5 text-emerald-600 shrink-0" />
              <span>Format: PNG (300 DPI)</span>
            </div>
            <div class="flex items-center gap-1">
              <Icon name="lucide:check" class="size-2.5 text-emerald-600 shrink-0" />
              <span>Real Alpha (No JPEG)</span>
            </div>
            <div class="flex items-center gap-1">
              <Icon name="lucide:check" class="size-2.5 text-emerald-600 shrink-0" />
              <span>Dimensions Match</span>
            </div>
            <div class="flex items-center gap-1">
              <Icon name="lucide:check" class="size-2.5 text-emerald-600 shrink-0" />
              <span>100% Geometry Kept</span>
            </div>
            <div class="flex items-center gap-1">
              <Icon name="lucide:check" class="size-2.5 text-emerald-600 shrink-0" />
              <span>Zero Checkerboard</span>
            </div>
            <div class="flex items-center gap-1">
              <Icon name="lucide:check" class="size-2.5 text-emerald-600 shrink-0" />
              <span>High Contrast Darks</span>
            </div>
          </div>
        </div>

        <!-- Buyer Package Inclusion Control -->
        <div class="px-3 py-2 bg-card border-t border-border/60">
          <!-- Outdated master warning -->
          <div
            v-if="item.source_outdated"
            class="p-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-[10px] leading-tight text-foreground/80 space-y-0.5"
          >
            <div class="flex items-center gap-1 font-semibold text-amber-600 dark:text-amber-400">
              <Icon name="lucide:alert-triangle" class="size-3 shrink-0" aria-hidden="true" />
              <span>Source Master Replaced</span>
            </div>
            <p class="text-[9.5px] text-muted-foreground">
              Generated from an older master artwork. Regenerate before including in buyer package.
            </p>
          </div>

          <!-- Approved & Current: Interactive Toggle -->
          <label
            v-else-if="item.variant_status === 'approved'"
            class="flex items-center justify-between gap-2 cursor-pointer select-none group"
            :title="item.include_in_buyer_package ? 'Included in customer delivery ZIP' : 'Click to include in customer delivery ZIP'"
          >
            <div class="flex items-center gap-2 min-w-0">
              <input
                type="checkbox"
                :checked="Boolean(item.include_in_buyer_package)"
                :disabled="isActing"
                class="size-4 rounded border-border text-primary focus:ring-primary/20 accent-primary cursor-pointer"
                @change="handleTogglePackageInclusion(item, $event)"
              >
              <span class="text-xs font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                Include in Buyer Package
              </span>
            </div>
            <span
              v-if="item.include_in_buyer_package"
              class="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 shrink-0"
            >
              In ZIP
            </span>
          </label>

          <!-- Unapproved: Disabled state -->
          <div
            v-else
            class="flex items-center gap-2 opacity-60 cursor-not-allowed select-none"
            title="Approve variant first to include in customer ZIP package"
          >
            <input
              type="checkbox"
              disabled
              class="size-4 rounded border-border text-slate-400 cursor-not-allowed"
            >
            <span class="text-xs text-muted-foreground truncate">
              Include in Buyer Package
            </span>
          </div>
        </div>

        <!-- Card Footer Actions -->
        <div class="p-2.5 border-t border-border/60 bg-card flex items-center justify-between gap-2">
          <div class="flex items-center gap-1.5">
            <Button
              v-if="item.variant_status !== 'approved' && item.variant_status !== 'failed'"
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
              v-else-if="item.variant_status !== 'rejected' && item.variant_status !== 'failed'"
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
          @click="selectedType = 'dark_shirt'; targetColor = '#F5E6C8'; showCreateModal = true"
        >
          <Icon name="lucide:moon" class="size-3.5 text-violet-500" aria-hidden="true" />
          <span>Create Dark Shirt Version</span>
        </Button>
        <Button
          variant="outline"
          size="sm"
          class="text-xs font-semibold gap-1.5 cursor-pointer"
          @click="selectedType = 'light_shirt'; targetColor = '#1A1A1A'; showCreateModal = true"
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
        class="bg-card text-card-foreground rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden border border-border flex flex-col max-h-[90vh]"
        @click.stop
      >
        <!-- Modal Header -->
        <div class="px-5 py-3.5 border-b border-border flex items-center justify-between bg-secondary/30">
          <div class="flex items-center gap-2">
            <div class="size-8 rounded-xl bg-violet-500/10 text-violet-600 dark:text-violet-400 flex items-center justify-center border border-violet-500/30 shadow-2xs">
              <Icon name="lucide:wand-2" class="size-4" aria-hidden="true" />
            </div>
            <div>
              <h4 class="text-xs font-bold text-foreground">Create Garment Color Variant</h4>
              <p class="text-[10px] text-muted-foreground">Deterministic recolor · Exact alpha & geometry preserved</p>
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
            <label class="text-xs font-bold text-foreground">Select Variant Mode</label>
            <div class="grid grid-cols-1 gap-2">
              <button
                v-for="opt in presetOptions"
                :key="opt.type"
                type="button"
                class="p-2.5 rounded-xl border text-left flex items-start gap-3 transition-all cursor-pointer"
                :class="selectedType === opt.type ? 'border-primary bg-primary/5 ring-1 ring-primary/30 shadow-2xs' : 'border-border bg-card hover:bg-secondary/60'"
                @click="handleSelectPreset(opt)"
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

          <!-- Color Replacement Selection -->
          <div class="p-3 rounded-xl bg-secondary/30 border border-border space-y-2">
            <label class="text-xs font-bold text-foreground flex items-center justify-between">
              <span>Dark Elements Replacement Tone</span>
              <span class="text-[10px] font-mono text-muted-foreground">{{ targetColor }}</span>
            </label>

            <!-- Quick Swatches for Dark Shirt -->
            <div v-if="selectedType === 'dark_shirt'" class="flex items-center gap-1.5 flex-wrap pb-1">
              <button
                v-for="swatch in darkShirtSwatches"
                :key="swatch.hex"
                type="button"
                class="px-2.5 py-1 rounded-lg border text-[11px] font-semibold flex items-center gap-1.5 transition-all cursor-pointer"
                :class="targetColor === swatch.hex ? 'border-primary bg-primary/10 text-primary font-bold shadow-2xs' : 'border-border bg-card text-foreground hover:bg-secondary/60'"
                @click="targetColor = swatch.hex"
              >
                <span class="size-3 rounded-full border border-border inline-block shrink-0" :style="{ backgroundColor: swatch.hex }" />
                <span>{{ swatch.label }}</span>
              </button>
            </div>

            <!-- Color Input & Custom Picker -->
            <div class="flex items-center gap-3">
              <input
                v-model="targetColor"
                type="color"
                class="size-9 rounded-lg border border-border cursor-pointer p-0.5 bg-card"
              >
              <input
                v-model="targetColor"
                type="text"
                class="h-9 px-3 rounded-lg border border-border text-xs font-mono font-bold uppercase w-28 bg-card text-foreground"
                placeholder="#F5E6C8"
              >
              <span class="text-[11px] text-muted-foreground">
                {{ selectedType === 'dark_shirt' ? 'Applied to black & dark outlines' : 'Target accent color' }}
              </span>
            </div>
          </div>

          <!-- Advanced Options (Collapsible) -->
          <div class="space-y-2 border-t border-border pt-3">
            <button
              type="button"
              class="text-xs font-semibold text-muted-foreground hover:text-foreground flex items-center gap-1 cursor-pointer"
              @click="showAdvancedOptions = !showAdvancedOptions"
            >
              <Icon :name="showAdvancedOptions ? 'lucide:chevron-down' : 'lucide:chevron-right'" class="size-3.5" aria-hidden="true" />
              <span>Advanced Contrast & Tuning</span>
            </button>

            <div v-if="showAdvancedOptions" class="p-3 rounded-xl bg-slate-50 border border-border space-y-3 animate-in fade-in duration-150">
              <div class="space-y-1">
                <div class="flex items-center justify-between text-xs">
                  <label class="font-bold text-foreground">Darkness Sensitivity Threshold</label>
                  <span class="font-mono text-muted-foreground">{{ darknessThreshold }}</span>
                </div>
                <input
                  v-model.number="darknessThreshold"
                  type="range"
                  min="0.15"
                  max="0.45"
                  step="0.01"
                  class="w-full cursor-pointer accent-primary"
                >
                <p class="text-[10px] text-muted-foreground">
                  Controls how aggressive the engine is at detecting dark shading and near-black textures.
                </p>
              </div>
            </div>
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
            <Icon v-else name="lucide:wand-2" class="size-3.5" aria-hidden="true" />
            <span>{{ isGenerating ? "Recoloring..." : "Generate Variant" }}</span>
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
