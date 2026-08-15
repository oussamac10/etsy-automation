<script setup lang="ts">
import { ref, computed, watch } from "vue";
import {
  Printer,
  CheckCircle2,
  AlertCircle,
  RotateCw,
  Sparkles,
  Download,
  ShieldCheck,
  Check,
  Image as ImageIcon,
  Plus,
  Palette,
  Layers,
} from "lucide-vue-next";
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
import WorkflowCustomMockupModal from "~/components/workflow/WorkflowCustomMockupModal.vue";

interface DesignPrompt {
  id: string;
  exact_slogan: string | null;
}

interface Concept {
  id: string;
  title: string;
  prompts: DesignPrompt[];
}

interface Asset {
  id: string;
  workflow_id: string;
  storage_key: string;
  mime_type: string;
  byte_size: number;
  checksum_sha256: string;
  width: number | null;
  height: number | null;
  has_alpha: boolean | null;
  url: string | null;
}

interface QaReport {
  dimensions_valid: boolean;
  width: number;
  height: number;
  target_width: number;
  target_height: number;
  density_dpi: number;
  target_dpi: number;
  has_alpha: boolean;
  has_transparent_pixels: boolean;
  transparent_background_valid: boolean;
  safe_margins_valid: boolean;
  cropped_edges_detected: boolean;
  color_space: string;
  file_size_bytes: number;
  checksum_sha256: string;
  typography_applied: boolean;
  exact_slogan_recorded: string | null;
  warnings: string[];
  qa_passed: boolean;
}

interface ProductionJob {
  id: string;
  workflow_id: string;
  source_asset_id: string | null;
  output_asset_id: string | null;
  operations: string[];
  status: string;
  idempotency_key: string;
  attempt_count: number;
  qa_report: QaReport;
  qa_passed: boolean | null;
  started_at: string | null;
  completed_at: string | null;
  failure_kind: string | null;
  failure_message: string | null;
  created_at: string;
  master_asset: Asset | null;
  mockup_assets: Asset[];
  mockup_urls: Record<string, string>;
}

interface Workflow {
  id: string;
  state: string;
  version: number;
  intended_product_uses?: string[];
}

interface ColorOption {
  name: string;
  label: string;
  bg: string;
  border: string;
}

const props = defineProps<{
  workflow: Workflow;
  approvedConcept?: Concept;
  latestProductionJob: ProductionJob | null;
  isProductionLoading: boolean;
  productionError: string | null;
}>();

const emit = defineEmits<{
  (e: "triggerProduction", forceNew: boolean): void;
}>();

function normalizeProductKey(raw: string): string {
  const text = raw.toLowerCase().trim();
  if (text.includes("shirt") || text.includes("tee") || text.includes("apparel") || text === "tshirt") return "tshirt";
  if (text.includes("sweat") || text.includes("hoodie") || text.includes("crewneck") || text === "sweatshirt") return "sweatshirt";
  if (text.includes("tote") || text.includes("bag") || text === "tote_bag") return "tote_bag";
  if (text.includes("mug") || text.includes("cup") || text.includes("ceramic") || text === "mug") return "mug";
  return text.replace(/\s+/g, "_");
}

const PRODUCT_COLOR_PALETTES: Record<string, ColorOption[]> = {
  tshirt: [
    { name: "white", label: "White", bg: "#FFFFFF", border: "border-zinc-300" },
    { name: "black", label: "Black", bg: "#18181B", border: "border-zinc-800" },
    { name: "heather_gray", label: "Heather Gray", bg: "#D1D5DB", border: "border-zinc-300" },
    { name: "sand", label: "Sand / Soft Cream", bg: "#E7DECD", border: "border-amber-200" },
  ],
  sweatshirt: [
    { name: "white", label: "White", bg: "#FFFFFF", border: "border-zinc-300" },
    { name: "black", label: "Black", bg: "#18181B", border: "border-zinc-800" },
    { name: "dark_heather", label: "Dark Heather", bg: "#4B5563", border: "border-zinc-600" },
    { name: "sand", label: "Sand", bg: "#D4C8B5", border: "border-amber-200" },
  ],
  mug: [
    { name: "white", label: "White 11oz", bg: "#FFFFFF", border: "border-zinc-300" },
    { name: "black", label: "Black 11oz", bg: "#18181B", border: "border-zinc-800" },
  ],
  tote_bag: [
    { name: "natural", label: "Natural Oyster", bg: "#F5F5DC", border: "border-amber-200" },
    { name: "black", label: "Black", bg: "#18181B", border: "border-zinc-800" },
  ],
};

const availableMockupTabs = computed<string[]>(() => {
  // 1. Strictly restrict to user-selected Intended Physical Products if set
  const intendedRaw = props.workflow?.intended_product_uses ?? [];
  if (intendedRaw.length > 0) {
    const intendedKeys = Array.from(new Set(intendedRaw.map(normalizeProductKey)));
    return intendedKeys;
  }

  // 2. Fallback to generated mockup URLs
  const urls = props.latestProductionJob?.mockup_urls ?? {};
  const keys = Object.keys(urls);
  if (keys.length > 0) {
    const order = ["mug", "tshirt", "sweatshirt", "tote_bag", "tote"];
    return keys.sort((a, b) => {
      const idxA = order.indexOf(a);
      const idxB = order.indexOf(b);
      return (idxA >= 0 ? idxA : 99) - (idxB >= 0 ? idxB : 99);
    });
  }
  return ["mug", "tshirt"];
});

const selectedMockupTab = ref<string>("mug");
const selectedMockupColor = ref<string>("white");
const showCustomMockupModal = ref(false);

const availableColorsForTab = computed<ColorOption[]>(() => {
  const norm = normalizeProductKey(selectedMockupTab.value);
  return PRODUCT_COLOR_PALETTES[norm] || [
    { name: "white", label: "White", bg: "#FFFFFF", border: "border-zinc-300" },
  ];
});

watch(
  availableMockupTabs,
  (tabs) => {
    if (tabs.length > 0 && !tabs.includes(selectedMockupTab.value)) {
      selectedMockupTab.value = tabs[0];
    }
  },
  { immediate: true }
);

watch(selectedMockupTab, (tab) => {
  const norm = normalizeProductKey(tab);
  if (norm === "tote_bag" || norm === "tote") {
    selectedMockupColor.value = "natural";
  } else {
    selectedMockupColor.value = "white";
  }
});

const currentCustomMockupUrl = computed<string | null>(() => {
  const urls = props.latestProductionJob?.mockup_urls ?? {};
  const norm = normalizeProductKey(selectedMockupTab.value);
  const tab = selectedMockupTab.value;
  const customKey = Object.keys(urls).find(
    (k) => k.startsWith(`${norm}:custom_`) || k.startsWith(`${tab}:custom_`)
  );
  return customKey ? urls[customKey] : null;
});

const currentDisplayedMockupUrl = computed<string | null>(() => {
  const urls = props.latestProductionJob?.mockup_urls ?? {};
  const tab = selectedMockupTab.value;
  const norm = normalizeProductKey(tab);
  const color = selectedMockupColor.value;

  if (color === "custom" && currentCustomMockupUrl.value) {
    return currentCustomMockupUrl.value;
  }

  // 1. Color variant (e.g. tshirt:black)
  if (urls[`${norm}:${color}`]) return urls[`${norm}:${color}`];
  if (urls[`${tab}:${color}`]) return urls[`${tab}:${color}`];

  // 2. Base product mockup
  if (urls[tab]) return urls[tab];
  if (urls[norm]) return urls[norm];
  if (tab === "tote_bag" && urls["tote"]) return urls["tote"];
  if (tab === "tote" && urls["tote_bag"]) return urls["tote_bag"];

  // 3. Fallback to custom mockup if present
  if (currentCustomMockupUrl.value) return currentCustomMockupUrl.value;

  return null;
});

function handleCustomMockupCreated(result: { mockup_url: string; product_type: string; template_id?: string }): void {
  if (props.latestProductionJob) {
    const urls = { ...(props.latestProductionJob.mockup_urls || {}) };
    urls[`${result.product_type}:custom_${result.template_id || 'new'}`] = result.mockup_url;
    urls[result.product_type] = result.mockup_url;
    props.latestProductionJob.mockup_urls = urls;
    selectedMockupColor.value = "custom";
  }
}

function getMockupLabel(product: string): string {
  switch (product.toLowerCase()) {
    case "mug":
      return "☕ Ceramic Mug";
    case "tshirt":
      return "👕 T-Shirt";
    case "sweatshirt":
      return "🧥 Sweatshirt";
    case "tote_bag":
    case "tote":
      return "👜 Tote Bag";
    default:
      return `📦 ${product}`;
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Phase 7: PNG Production Pipeline Card -->
    <Card class="shadow-2xs border-zinc-200">
      <CardHeader class="pb-3 border-b border-zinc-100 bg-zinc-50/50">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <Printer class="h-5 w-5 text-indigo-600" />
            <div>
              <CardTitle class="text-base font-bold">Phase 7: Print-Ready PNG Production & Realistic Mockups</CardTitle>
              <CardDescription class="text-xs text-zinc-500">
                Deterministic 4500×5400 px @ 300 DPI master PNG with transparency, safe trim, slogan typography, QA & mockups
              </CardDescription>
            </div>
          </div>
          <Badge
            v-if="latestProductionJob?.status === 'SUCCEEDED'"
            variant="success"
            class="gap-1 px-3 py-1 font-semibold"
          >
            <CheckCircle2 class="h-3.5 w-3.5" />
            <span>Production Complete</span>
          </Badge>
          <Badge
            v-else-if="workflow.state === 'PRODUCTION' || latestProductionJob?.status === 'RUNNING' || latestProductionJob?.status === 'QUEUED'"
            variant="warning"
            class="gap-1 px-3 py-1 font-semibold"
          >
            <RotateCw class="h-3.5 w-3.5 animate-spin" />
            <span>Processing Pipeline...</span>
          </Badge>
          <Badge
            v-else-if="workflow.state === 'PRODUCTION_FAILED' || latestProductionJob?.status === 'FAILED'"
            variant="destructive"
            class="gap-1 px-3 py-1 font-semibold"
          >
            <AlertCircle class="h-3.5 w-3.5" />
            <span>Production Failed</span>
          </Badge>
          <Badge
            v-else
            variant="secondary"
            class="gap-1 px-3 py-1"
          >
            <span>Ready to Produce</span>
          </Badge>
        </div>
      </CardHeader>

      <CardContent class="p-6 space-y-6">
        <!-- 1. Ready State: CTA to trigger production -->
        <div
          v-if="(workflow.state === 'ARTWORK_APPROVED' || workflow.state === 'IDEA_APPROVED') && (!latestProductionJob || latestProductionJob.status === 'FAILED')"
          class="rounded-xl border border-indigo-100 bg-indigo-50/30 p-6 space-y-4"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="space-y-1">
              <h3 class="text-sm font-bold text-zinc-900">Artwork Approved — Ready for Master File Generation</h3>
              <p class="text-xs text-zinc-600">
                The approved artwork will be scaled proportionally to 4500×5400 px with 300 DPI metadata and safe margin padding.
                <span v-if="approvedConcept?.prompts[0]?.exact_slogan" class="block mt-1 font-medium text-indigo-900">
                  Exact slogan <b>"{{ approvedConcept.prompts[0].exact_slogan }}"</b> will be deterministically rendered via SVG typography overlay.
                </span>
              </p>
            </div>
            <div class="flex flex-wrap gap-2 text-[10px] font-mono">
              <Badge variant="outline" class="bg-white">4500×5400 px</Badge>
              <Badge variant="outline" class="bg-white">300 DPI</Badge>
              <Badge variant="outline" class="bg-white">sRGB PNG</Badge>
            </div>
          </div>

          <Alert v-if="productionError" variant="destructive">
            <AlertCircle class="h-4 w-4" />
            <AlertDescription>{{ productionError }}</AlertDescription>
          </Alert>

          <div class="pt-2 flex items-center gap-3">
            <Button
              variant="default"
              size="default"
              class="gap-2 bg-indigo-600 hover:bg-indigo-700 font-bold px-6 shadow-md shadow-indigo-600/20"
              :disabled="isProductionLoading"
              @click="emit('triggerProduction', false)"
            >
              <RotateCw v-if="isProductionLoading" class="h-4 w-4 animate-spin" />
              <Sparkles v-else class="h-4 w-4" />
              <span>{{ isProductionLoading ? 'Queueing Production...' : 'Start PNG Production' }}</span>
            </Button>
          </div>
        </div>

        <!-- 2. In-Flight State: Pipeline Progress -->
        <div
          v-if="(latestProductionJob?.status === 'RUNNING' || latestProductionJob?.status === 'QUEUED') || (workflow.state === 'PRODUCTION' && latestProductionJob?.status !== 'SUCCEEDED' && latestProductionJob?.status !== 'FAILED')"
          class="rounded-xl border border-zinc-200 bg-zinc-50/50 p-6 space-y-5"
        >
          <div class="flex items-center justify-between">
            <div class="space-y-0.5">
              <h4 class="text-sm font-bold text-zinc-900 flex items-center gap-2">
                <RotateCw class="h-4 w-4 text-indigo-600 animate-spin" />
                <span>Processing Deterministic Pipeline</span>
              </h4>
              <p class="text-xs text-zinc-500">Transforming approved source asset into verified master print files and mockups</p>
            </div>
            <span class="text-xs font-mono text-zinc-400">Step 1–7</span>
          </div>

          <!-- 7-Step Indicator -->
          <div class="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2 text-center text-[11px]">
            <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
              <div class="font-bold mb-0.5">1. Inspect</div>
              <div class="text-[10px] text-indigo-700/70">Validate alpha</div>
            </div>
            <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
              <div class="font-bold mb-0.5">2. Trim</div>
              <div class="text-[10px] text-indigo-700/70">Safe 8% margin</div>
            </div>
            <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
              <div class="font-bold mb-0.5">3. Upscale</div>
              <div class="text-[10px] text-indigo-700/70">4500×5400 px</div>
            </div>
            <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
              <div class="font-bold mb-0.5">4. Typography</div>
              <div class="text-[10px] text-indigo-700/70">SVG overlay</div>
            </div>
            <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
              <div class="font-bold mb-0.5">5. QA Report</div>
              <div class="text-[10px] text-indigo-700/70">Verify bounds</div>
            </div>
            <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
              <div class="font-bold mb-0.5">6. Mockups</div>
              <div class="text-[10px] text-indigo-700/70">T-shirt, tote, mug</div>
            </div>
            <div class="p-2.5 rounded-lg border border-indigo-200 bg-indigo-50/50 font-medium text-indigo-900">
              <div class="font-bold mb-0.5">7. Storage</div>
              <div class="text-[10px] text-indigo-700/70">S3 upload</div>
            </div>
          </div>
        </div>

        <!-- 3. Completed State: Master PNG, QA Report, Mockups -->
        <div v-if="latestProductionJob?.status === 'SUCCEEDED'" class="space-y-6">
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <!-- Master PNG Preview & Download (5 cols) -->
            <div class="lg:col-span-5 space-y-4">
              <div class="border border-zinc-200 rounded-xl overflow-hidden bg-white shadow-2xs">
                <div class="aspect-[45/54] relative flex items-center justify-center p-4 bg-[repeating-conic-gradient(#f4f4f5_0%_25%,#ffffff_0%_50%)] bg-[length:16px_16px]">
                  <img
                    v-if="latestProductionJob.master_asset?.url"
                    :src="latestProductionJob.master_asset.url"
                    alt="Master Production PNG"
                    class="object-contain w-full h-full max-h-[360px]"
                  >
                  <div v-else class="text-zinc-400 text-xs">Master Image Loading...</div>
                  <Badge variant="success" class="absolute top-3 left-3 text-[11px] px-2.5 py-0.5 font-bold shadow-xs">
                    Master Print PNG
                  </Badge>
                </div>
                <div class="p-4 border-t border-zinc-100 bg-zinc-50/50 space-y-3">
                  <div class="flex items-center justify-between text-xs text-zinc-600">
                    <span class="font-mono font-bold">{{ latestProductionJob.master_asset?.width ?? 4500 }} × {{ latestProductionJob.master_asset?.height ?? 5400 }} px</span>
                    <Badge variant="outline" class="text-[10px] font-mono bg-white">300 DPI</Badge>
                    <span class="font-mono text-zinc-500">{{ ((latestProductionJob.master_asset?.byte_size ?? 0) / (1024 * 1024)).toFixed(2) }} MB</span>
                  </div>

                  <a
                    v-if="latestProductionJob.master_asset?.url"
                    :href="latestProductionJob.master_asset.url"
                    target="_blank"
                    download="master_print.png"
                    class="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs h-9 transition-colors shadow-2xs"
                  >
                    <Download class="h-4 w-4" />
                    <span>Download Master PNG</span>
                  </a>
                </div>
              </div>
            </div>

            <!-- QA Report & Mockups (7 cols) -->
            <div class="lg:col-span-7 space-y-6">
              <!-- QA Report Card -->
              <div class="border border-zinc-200 rounded-xl p-5 bg-white space-y-4 shadow-2xs">
                <div class="flex items-center justify-between border-b border-zinc-100 pb-3">
                  <div class="flex items-center gap-2">
                    <ShieldCheck class="h-4 w-4 text-emerald-600" />
                    <h4 class="text-sm font-bold text-zinc-900">Automated QA Validation Report</h4>
                  </div>
                  <Badge
                    :variant="latestProductionJob.qa_passed ? 'success' : 'warning'"
                    class="text-[10px] font-bold px-2 py-0.5"
                  >
                    {{ latestProductionJob.qa_passed ? 'QA PASSED' : 'QA WARNINGS' }}
                  </Badge>
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Canvas Dimensions</span>
                    <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                      <Check class="h-3 w-3 text-emerald-600" />
                      {{ latestProductionJob.qa_report?.width ?? 4500 }}×{{ latestProductionJob.qa_report?.height ?? 5400 }}
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Print Density</span>
                    <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                      <Check class="h-3 w-3 text-emerald-600" />
                      {{ latestProductionJob.qa_report?.density_dpi ?? 300 }} DPI
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Background Alpha</span>
                    <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                      <Check class="h-3 w-3 text-emerald-600" />
                      Transparent
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Safe Margins</span>
                    <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                      <Check class="h-3 w-3 text-emerald-600" />
                      Protected (8%)
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Color Space</span>
                    <span class="font-mono font-bold text-zinc-800 flex items-center gap-1">
                      <Check class="h-3 w-3 text-emerald-600" />
                      {{ latestProductionJob.qa_report?.color_space ?? 'sRGB' }}
                    </span>
                  </div>

                  <div class="p-2.5 rounded-lg bg-zinc-50 border border-zinc-100 space-y-1">
                    <span class="text-[10px] text-zinc-400 block font-medium">Slogan Typography</span>
                    <span class="font-bold text-zinc-800 text-[11px] flex items-center gap-1">
                      <Check v-if="latestProductionJob.qa_report?.typography_applied" class="h-3 w-3 text-emerald-600" />
                      <span v-else class="text-zinc-400">—</span>
                      {{ latestProductionJob.qa_report?.typography_applied ? 'Applied' : 'No Slogan' }}
                    </span>
                  </div>
                </div>

                <div
                  v-if="latestProductionJob.qa_report?.warnings && latestProductionJob.qa_report.warnings.length > 0"
                  class="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 space-y-1"
                >
                  <span class="font-bold text-[11px] block">QA Advisory Warnings:</span>
                  <ul class="list-disc list-inside space-y-0.5 text-[11px]">
                    <li v-for="(warn, wIdx) in latestProductionJob.qa_report.warnings" :key="wIdx">{{ warn }}</li>
                  </ul>
                </div>
              </div>

              <!-- Mockup Gallery -->
              <div class="border border-zinc-200 rounded-xl p-5 bg-white space-y-4 shadow-2xs">
                <div class="flex flex-wrap items-center justify-between border-b border-zinc-100 pb-3 gap-2">
                  <div class="flex items-center gap-2">
                    <ImageIcon class="h-4 w-4 text-indigo-600" />
                    <h4 class="text-sm font-bold text-zinc-900">Product Mockup Gallery</h4>
                    <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-600 border border-zinc-200">
                      {{ selectedMockupColor === 'custom' ? 'Custom Photo Engine' : 'Printful Engine' }}
                    </span>
                  </div>

                  <div class="flex flex-wrap items-center gap-2">
                    <!-- Product Tabs -->
                    <div class="flex flex-wrap gap-1">
                      <button
                        v-for="p in availableMockupTabs"
                        :key="p"
                        type="button"
                        class="text-[11px] px-2.5 py-1 rounded-md font-medium transition-all"
                        :class="
                          (selectedMockupTab === p || (p === 'tote_bag' && selectedMockupTab === 'tote'))
                            ? 'bg-zinc-900 text-white shadow-xs'
                            : 'text-zinc-500 hover:text-zinc-900 bg-zinc-100/80 hover:bg-zinc-200'
                        "
                        @click="selectedMockupTab = p"
                      >
                        {{ getMockupLabel(p) }}
                      </button>
                    </div>

                    <!-- Custom Mockup Button -->
                    <button
                      type="button"
                      class="text-[11px] px-2.5 py-1 rounded-md font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 flex items-center gap-1 transition-all shadow-2xs"
                      @click="showCustomMockupModal = true"
                    >
                      <Plus class="h-3 w-3" />
                      <span>Custom Mockup</span>
                    </button>
                  </div>
                </div>

                <!-- Color Swatches & Custom View Bar -->
                <div class="flex flex-wrap items-center justify-between gap-2 px-1">
                  <div class="flex items-center gap-2">
                    <span class="text-[11px] font-semibold text-zinc-500 flex items-center gap-1">
                      <Palette class="h-3 w-3" />
                      <span>Color:</span>
                    </span>
                    <div class="flex items-center gap-1.5">
                      <button
                        v-for="col in availableColorsForTab"
                        :key="col.name"
                        type="button"
                        class="h-6 w-6 rounded-full border flex items-center justify-center transition-all relative cursor-pointer"
                        :class="[
                          col.border,
                          selectedMockupColor === col.name ? 'ring-2 ring-indigo-600 scale-110 shadow-xs' : 'hover:scale-105 opacity-80 hover:opacity-100'
                        ]"
                        :style="{ backgroundColor: col.bg }"
                        :title="col.label"
                        @click="selectedMockupColor = col.name"
                      >
                        <Check v-if="selectedMockupColor === col.name" class="h-3 w-3" :class="col.name === 'white' || col.name === 'natural' ? 'text-zinc-900' : 'text-white'" />
                      </button>
                    </div>
                  </div>

                  <!-- Custom Template Tab indicator if custom mockup exists -->
                  <div v-if="currentCustomMockupUrl" class="flex items-center gap-1">
                    <button
                      type="button"
                      class="text-[11px] px-2.5 py-0.5 rounded-full font-medium transition-all flex items-center gap-1 cursor-pointer"
                      :class="selectedMockupColor === 'custom' ? 'bg-indigo-600 text-white font-bold shadow-xs' : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200'"
                      @click="selectedMockupColor = 'custom'"
                    >
                      <Layers class="h-3 w-3" />
                      <span>Custom Template</span>
                    </button>
                  </div>
                </div>

                <!-- Mockup Display Area -->
                <div class="aspect-square max-h-[280px] mx-auto bg-zinc-50 rounded-lg overflow-hidden border border-zinc-100 flex items-center justify-center p-3 relative">
                  <img
                    v-if="currentDisplayedMockupUrl"
                    :src="currentDisplayedMockupUrl"
                    :alt="selectedMockupTab"
                    class="object-contain w-full h-full max-h-[260px] rounded transition-opacity duration-200"
                  >
                  <div v-else class="text-zinc-400 text-xs">Mockup not available for this selection</div>
                  <a
                    v-if="currentDisplayedMockupUrl"
                    :href="currentDisplayedMockupUrl"
                    target="_blank"
                    :download="`${selectedMockupTab}_${selectedMockupColor}_mockup.jpg`"
                    class="absolute bottom-2 right-2 rounded bg-white/90 hover:bg-white border border-zinc-200 p-1.5 text-zinc-700 shadow-xs text-[10px] font-mono flex items-center gap-1"
                  >
                    <Download class="h-3 w-3" />
                    <span>Save Mockup</span>
                  </a>
                </div>
              </div>
            </div>
          </div>

          <!-- Provenance & Regeneration Footer -->
          <div class="pt-4 border-t border-zinc-100 flex flex-wrap items-center justify-between gap-4 text-xs text-zinc-500">
            <div class="flex items-center gap-4 text-[11px] font-mono">
              <span>Source Asset: <code>{{ latestProductionJob.source_asset_id?.slice(0, 8) }}...</code></span>
              <span>SHA256: <code>{{ latestProductionJob.qa_report?.checksum_sha256?.slice(0, 8) }}...</code></span>
              <span>Pipeline: <code>image-pipeline@0.1.0</code></span>
            </div>

            <Button
              variant="outline"
              size="sm"
              class="text-xs gap-1.5 ml-auto"
              :disabled="isProductionLoading"
              @click="emit('triggerProduction', true)"
            >
              <RotateCw class="h-3.5 w-3.5" :class="{ 'animate-spin': isProductionLoading }" />
              <span>Regenerate Master & Mockups</span>
            </Button>
          </div>
        </div>

        <!-- 4. Failed State -->
        <div v-if="workflow.state === 'PRODUCTION_FAILED' || (latestProductionJob?.status === 'FAILED' && workflow.state !== 'ARTWORK_APPROVED')" class="space-y-4">
          <Alert variant="destructive">
            <AlertCircle class="h-4 w-4" />
            <AlertTitle>PNG Production Failed</AlertTitle>
            <AlertDescription>
              {{ latestProductionJob?.failure_message || 'An error occurred during production file processing.' }}
            </AlertDescription>
          </Alert>

          <Button
            variant="default"
            size="sm"
            class="gap-1.5"
            :disabled="isProductionLoading"
            @click="emit('triggerProduction', true)"
          >
            <RotateCw class="h-3.5 w-3.5" :class="{ 'animate-spin': isProductionLoading }" />
            <span>Retry PNG Production</span>
          </Button>
        </div>
      </CardContent>
    </Card>

    <!-- Custom Mockup Modal -->
    <WorkflowCustomMockupModal
      v-model:open="showCustomMockupModal"
      :workflow-id="workflow.id"
      :product-type="selectedMockupTab"
      :master-image-url="latestProductionJob?.master_asset?.url"
      @mockup-created="handleCustomMockupCreated"
    />
  </div>
</template>
