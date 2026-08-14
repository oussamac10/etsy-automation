<script setup lang="ts">
/* global $fetch */
import { ref, onMounted, onUnmounted } from "vue";
import { useWorkflowStore } from "~/stores/workflow";

interface Workflow {
  id: string;
  name: string;
  idea_mode: string;
  target_marketplace: string;
  target_country: string;
  output_language: string;
  target_buyer: string | null;
  intended_product_uses: string[];
  state: string;
  version: number;
  created_at: string;
  updated_at: string;
}

const config = useRuntimeConfig();
const apiBase = config.public.apiBase;
const store = useWorkflowStore();

const workflows = ref<Workflow[]>([]);
const isListLoading = ref(true);
const listError = ref<string | null>(null);

// Form state
const showCreateForm = ref(false);
const ideaMode = ref<"market-led" | "user-idea" | "hybrid">("market-led");
const workflowName = ref("");
const targetCountry = ref("US");
const outputLanguage = ref("en");
const targetMarketplace = ref("etsy");
const targetBuyer = ref("");
const intendedProductUses = ref("");
const isCreating = ref(false);
const creationError = ref<string | null>(null);

// Original Idea fields (for user-idea/hybrid modes)
const originalText = ref("");
const slogan = ref("");
const desiredStyle = ref("");
const audience = ref("");
const occasion = ref("");
const season = ref("");

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(";").shift() ?? null;
  return null;
}

async function loadWorkflows(): Promise<void> {
  isListLoading.value = true;
  listError.value = null;
  try {
    const data = await $fetch<{ items: Workflow[] }>(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows`,
      { credentials: "include" }
    );
    workflows.value = data.items;
  } catch (err) {
    listError.value = "Failed to load workflows. Please ensure you are logged in.";
  } finally {
    isListLoading.value = false;
  }
}

async function handleCreateWorkflow(): Promise<void> {
  isCreating.value = true;
  creationError.value = null;

  try {
    const csrf = getCookie("etsy_csrf");
    const headers: Record<string, string> = {};
    if (csrf) {
      headers["x-csrf-token"] = csrf;
    }

    // Step 1: Create the workflow
    const payload = {
      idea_mode: ideaMode.value,
      name: workflowName.value.trim(),
      target_country: targetCountry.value.trim(),
      output_language: outputLanguage.value.trim(),
      target_marketplace: targetMarketplace.value.trim(),
      target_buyer: targetBuyer.value.trim() || null,
      intended_product_uses: intendedProductUses.value
        .split(",")
        .map((u) => u.trim())
        .filter((u) => u.length > 0),
    };

    const newWorkflow = await $fetch<Workflow>(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows`,
      {
        method: "POST",
        headers,
        body: payload,
        credentials: "include",
      }
    );

    // Step 2: If user-idea or hybrid, submit original idea
    if (ideaMode.value !== "market-led") {
      const ideaPayload = {
        original_text: originalText.value.trim(),
        slogan: slogan.value.trim() || null,
        desired_style: desiredStyle.value.trim() || null,
        audience: audience.value.trim() || null,
        occasion: occasion.value.trim() || null,
        season: season.value.trim() || null,
        product_uses: intendedProductUses.value
          .split(",")
          .map((u) => u.trim())
          .filter((u) => u.length > 0),
      };

      await $fetch(
        `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${newWorkflow.id}/ideas`,
        {
          method: "POST",
          headers,
          body: ideaPayload,
          credentials: "include",
        }
      );
    }

    // Step 3: Trigger the background research run automatically!
    await $fetch(
      `${apiBase.replace(/\/$/, "")}/api/v1/workflows/${newWorkflow.id}/research`,
      {
        method: "POST",
        headers,
        credentials: "include",
      }
    );

    // Reset form and reload
    showCreateForm.value = false;
    workflowName.value = "";
    targetBuyer.value = "";
    intendedProductUses.value = "";
    originalText.value = "";
    slogan.value = "";
    desiredStyle.value = "";
    audience.value = "";
    occasion.value = "";
    season.value = "";

    await loadWorkflows();
  } catch (err: any) {
    creationError.value = err.data?.detail || "Failed to create workflow.";
  } finally {
    isCreating.value = false;
  }
}

let pollInterval: any = null;

onMounted(() => {
  loadWorkflows();
  // Poll every 5 seconds to dynamically update campaign states
  pollInterval = setInterval(loadWorkflows, 5000);
});

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval);
  }
});
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <NavBar />

    <main id="main" class="mx-auto max-w-6xl px-6 py-12">
      <!-- Premium Design Header -->
      <header class="mb-12 flex flex-col md:flex-row md:items-center md:justify-between gap-6 border-b border-slate-200 pb-8">
        <div>
          <h1 class="text-4xl font-extrabold tracking-tight text-slate-900 bg-gradient-to-r from-indigo-600 to-sky-500 bg-clip-text text-transparent">
            Etsy PNG Automation
          </h1>
          <p class="mt-3 max-w-2xl text-slate-600">
            Generate and list optimized digital art designs. Select target audiences, research search queries, synthesise ideas, and approve assets with complete manual verification controls.
          </p>
        </div>
        <div>
          <button
            v-if="!showCreateForm"
            type="button"
            class="inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-indigo-600 to-sky-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-100 hover:shadow-indigo-200 hover:from-indigo-700 hover:to-sky-600 transition-all duration-200 transform hover:-translate-y-0.5 focus:ring-2 focus:ring-indigo-500"
            @click="showCreateForm = true"
          >
            Create New Campaign
          </button>
          <button
            v-else
            type="button"
            class="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-all duration-200 focus:ring-2 focus:ring-slate-500"
            @click="showCreateForm = false"
          >
            Cancel Creation
          </button>
        </div>
      </header>

      <!-- New Workflow Form with selection cards -->
      <section v-if="showCreateForm" class="mb-12 rounded-2xl border border-slate-200 bg-white p-8 shadow-xl animate-fade-in">
        <h2 class="text-2xl font-bold text-slate-800 mb-6">Start a New Design Campaign</h2>

        <div v-if="creationError" class="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
          {{ creationError }}
        </div>

        <form @submit.prevent="handleCreateWorkflow" class="space-y-8">
          <!-- Step 1: Mode Selection Cards -->
          <div>
            <label class="block text-sm font-semibold text-slate-700 mb-3">Choose Design Input Mode</label>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <!-- Mode 1: Market Led -->
              <div
                class="relative rounded-2xl border-2 p-5 cursor-pointer transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                :class="ideaMode === 'market-led' ? 'border-indigo-600 bg-indigo-50/50 shadow-md' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'"
                @click="ideaMode = 'market-led'"
              >
                <div class="flex items-center justify-between mb-2">
                  <span class="text-md font-bold text-slate-800">Discover Ideas</span>
                  <span v-if="ideaMode === 'market-led'" class="h-5 w-5 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs">✓</span>
                </div>
                <p class="text-xs text-slate-500">
                  Fully automated market trend discovery. The AI searches seasonal demand and devises three unique concepts from search queries.
                </p>
                <span class="inline-block mt-3 text-xs font-semibold px-2 py-0.5 rounded bg-indigo-100 text-indigo-800">market-led</span>
              </div>

              <!-- Mode 2: User Idea -->
              <div
                class="relative rounded-2xl border-2 p-5 cursor-pointer transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                :class="ideaMode === 'user-idea' ? 'border-indigo-600 bg-indigo-50/50 shadow-md' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'"
                @click="ideaMode = 'user-idea'"
              >
                <div class="flex items-center justify-between mb-2">
                  <span class="text-md font-bold text-slate-800">Use My Idea</span>
                  <span v-if="ideaMode === 'user-idea'" class="h-5 w-5 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs">✓</span>
                </div>
                <p class="text-xs text-slate-500">
                  Supply your own direct theme/concept. The engine optimizes your concept, queries related keywords, and outputs a ready-to-test brief.
                </p>
                <span class="inline-block mt-3 text-xs font-semibold px-2 py-0.5 rounded bg-indigo-100 text-indigo-800">user-idea</span>
              </div>

              <!-- Mode 3: Hybrid -->
              <div
                class="relative rounded-2xl border-2 p-5 cursor-pointer transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                :class="ideaMode === 'hybrid' ? 'border-indigo-600 bg-indigo-50/50 shadow-md' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'"
                @click="ideaMode = 'hybrid'"
              >
                <div class="flex items-center justify-between mb-2">
                  <span class="text-md font-bold text-slate-800">Hybrid Approach</span>
                  <span v-if="ideaMode === 'hybrid'" class="h-5 w-5 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs">✓</span>
                </div>
                <p class="text-xs text-slate-500">
                  Blend user direction with market signals. The engine maps your brief against general trends to produce derived variations.
                </p>
                <span class="inline-block mt-3 text-xs font-semibold px-2 py-0.5 rounded bg-indigo-100 text-indigo-800">hybrid</span>
              </div>
            </div>
          </div>

          <!-- Step 2: Campaign Settings -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label for="campaign-name" class="block text-sm font-semibold text-slate-700">Campaign Name</label>
              <input
                id="campaign-name"
                v-model="workflowName"
                type="text"
                required
                placeholder="e.g. Autumn Mugs 2026"
                class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
              />
            </div>
            <div>
              <label for="target-country" class="block text-sm font-semibold text-slate-700">Target Marketplace Country</label>
              <select
                id="target-country"
                v-model="targetCountry"
                class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
              >
                <option value="US">United States (US)</option>
                <option value="CA">Canada (CA)</option>
                <option value="GB">United Kingdom (GB)</option>
                <option value="AU">Australia (AU)</option>
              </select>
            </div>
          </div>

          <!-- Optional Targeting Filters -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <label for="output-language" class="block text-sm font-semibold text-slate-700">Output Language</label>
              <input
                id="output-language"
                v-model="outputLanguage"
                type="text"
                required
                class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
              />
            </div>
            <div>
              <label for="target-buyer" class="block text-sm font-semibold text-slate-700">Target Buyer Persona (Optional)</label>
              <input
                id="target-buyer"
                v-model="targetBuyer"
                type="text"
                placeholder="e.g. coffee lovers, teachers"
                class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
              />
            </div>
            <div>
              <label for="product-uses" class="block text-sm font-semibold text-slate-700">Intended Physical Products</label>
              <input
                id="product-uses"
                v-model="intendedProductUses"
                type="text"
                placeholder="e.g. mug, tumbler, tshirt"
                class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
              />
              <span class="text-xs text-slate-400">Comma-separated list.</span>
            </div>
          </div>

          <!-- Step 3: Wording / Brief inputs (for user-idea/hybrid modes) -->
          <div v-if="ideaMode !== 'market-led'" class="border-t border-slate-200 pt-6 space-y-6">
            <h3 class="text-lg font-bold text-slate-800">Your Design Idea Details</h3>
            
            <div>
              <label for="original-text" class="block text-sm font-semibold text-slate-700">Idea Brief / Prompt Wording</label>
              <textarea
                id="original-text"
                v-model="originalText"
                required
                rows="3"
                placeholder="Detail the subject, elements, colors, and layout you want (minimum 3 characters)"
                class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
              ></textarea>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label for="desired-style" class="block text-sm font-semibold text-slate-700">Desired Style (Optional)</label>
                <input
                  id="desired-style"
                  v-model="desiredStyle"
                  type="text"
                  placeholder="e.g. watercolor, retro vector, minimalist pencil line art"
                  class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                />
              </div>
              <div>
                <label for="slogan" class="block text-sm font-semibold text-slate-700">Exact Slogan / Typography Text (Optional)</label>
                <input
                  id="slogan"
                  v-model="slogan"
                  type="text"
                  placeholder="e.g. BUT FIRST COFFEE"
                  class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                />
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label for="audience" class="block text-sm font-semibold text-slate-700">Audience (Optional)</label>
                <input
                  id="audience"
                  v-model="audience"
                  type="text"
                  placeholder="e.g. dog moms"
                  class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                />
              </div>
              <div>
                <label for="occasion" class="block text-sm font-semibold text-slate-700">Occasion (Optional)</label>
                <input
                  id="occasion"
                  v-model="occasion"
                  type="text"
                  placeholder="e.g. Mother's Day"
                  class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                />
              </div>
              <div>
                <label for="season" class="block text-sm font-semibold text-slate-700">Season (Optional)</label>
                <input
                  id="season"
                  v-model="season"
                  type="text"
                  placeholder="e.g. Fall / Halloween"
                  class="mt-1 block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm"
                />
              </div>
            </div>
          </div>

          <div class="flex justify-end pt-4">
            <button
              type="submit"
              :disabled="isCreating"
              class="inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-indigo-600 to-sky-500 px-6 py-3 text-sm font-bold text-white shadow-lg hover:from-indigo-700 hover:to-sky-600 transition-all duration-200 focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {{ isCreating ? 'Submitting & Researching...' : 'Launch Campaign' }}
            </button>
          </div>
        </form>
      </section>

      <!-- Active Workflows List -->
      <section class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 class="text-2xl font-bold text-slate-800 mb-6">Your Design Workflows</h2>

        <div v-if="isListLoading" class="flex flex-col items-center justify-center py-12 text-slate-500 animate-pulse">
          <p>Loading your campaigns...</p>
        </div>

        <div v-else-if="listError" class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <p>{{ listError }}</p>
        </div>

        <div v-else-if="workflows.length === 0" class="text-center py-16">
          <div class="mx-auto h-12 w-12 text-slate-300 mb-4 font-bold text-3xl">🎨</div>
          <h3 class="text-lg font-semibold text-slate-700 mb-1">No Active Campaigns</h3>
          <p class="text-slate-500 text-sm mb-6 max-w-sm mx-auto">
            Get started by creating your first product design workflow using one of the research modes.
          </p>
          <button
            type="button"
            class="inline-flex items-center justify-center rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-indigo-700"
            @click="showCreateForm = true"
          >
            Create Your First Campaign
          </button>
        </div>

        <div v-else class="overflow-hidden rounded-xl border border-slate-100">
          <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead class="bg-slate-50 text-xs font-semibold text-slate-700 uppercase">
              <tr>
                <th scope="col" class="px-6 py-4">Campaign Name</th>
                <th scope="col" class="px-6 py-4">Input Mode</th>
                <th scope="col" class="px-6 py-4">Country & Lang</th>
                <th scope="col" class="px-6 py-4">State</th>
                <th scope="col" class="px-6 py-4">Created At</th>
                <th scope="col" class="relative px-6 py-4"><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 bg-white text-slate-600">
              <tr
                v-for="wf in workflows"
                :key="wf.id"
                class="hover:bg-slate-50 transition-colors duration-150"
              >
                <td class="whitespace-nowrap px-6 py-4 font-semibold text-slate-900">
                  <NuxtLink :to="`/workflow/${wf.id}`" class="hover:text-indigo-600 underline decoration-indigo-200">
                    {{ wf.name }}
                  </NuxtLink>
                </td>
                <td class="whitespace-nowrap px-6 py-4">
                  <span class="inline-flex items-center rounded-md bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 border border-indigo-100">
                    {{ wf.idea_mode }}
                  </span>
                </td>
                <td class="whitespace-nowrap px-6 py-4 font-mono text-xs">
                  {{ wf.target_country }} ({{ wf.output_language }})
                </td>
                <td class="whitespace-nowrap px-6 py-4">
                  <span
                    class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border"
                    :class="{
                      'bg-slate-100 text-slate-800 border-slate-200': wf.state === 'DRAFT',
                      'bg-amber-100 text-amber-800 border-amber-200 animate-pulse': wf.state === 'RESEARCH_QUEUED' || wf.state === 'RESEARCHING',
                      'bg-blue-100 text-blue-800 border-blue-200': wf.state === 'IDEA_REVIEW',
                      'bg-green-100 text-green-800 border-green-200': wf.state.endsWith('_APPROVED') || wf.state === 'ETSY_DRAFT_CREATED',
                      'bg-red-100 text-red-800 border-red-200': wf.state.endsWith('_FAILED')
                    }"
                  >
                    {{ wf.state }}
                  </span>
                </td>
                <td class="whitespace-nowrap px-6 py-4 text-xs">
                  {{ new Date(wf.created_at).toLocaleString() }}
                </td>
                <td class="whitespace-nowrap px-6 py-4 text-right text-sm">
                  <NuxtLink
                    :to="`/workflow/${wf.id}`"
                    class="font-semibold text-indigo-600 hover:text-indigo-900 focus:outline-none focus:underline"
                  >
                    Open Dashboard →
                  </NuxtLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in {
  animation: fadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
</style>
