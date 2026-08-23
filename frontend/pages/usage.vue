<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import NavBar from "~/components/NavBar.vue";
import Alert from "~/components/ui/Alert.vue";
import AlertDescription from "~/components/ui/AlertDescription.vue";
import AlertTitle from "~/components/ui/AlertTitle.vue";
import Badge from "~/components/ui/Badge.vue";
import Button from "~/components/ui/Button.vue";
import Card from "~/components/ui/Card.vue";
import CardContent from "~/components/ui/CardContent.vue";
import CardDescription from "~/components/ui/CardDescription.vue";
import CardHeader from "~/components/ui/CardHeader.vue";
import CardTitle from "~/components/ui/CardTitle.vue";
import Dialog from "~/components/ui/Dialog.vue";
import DialogDescription from "~/components/ui/DialogDescription.vue";
import DialogFooter from "~/components/ui/DialogFooter.vue";
import DialogHeader from "~/components/ui/DialogHeader.vue";
import DialogTitle from "~/components/ui/DialogTitle.vue";
import Input from "~/components/ui/Input.vue";
import Label from "~/components/ui/Label.vue";
import Pagination from "~/components/ui/Pagination.vue";
import Progress from "~/components/ui/Progress.vue";
import Skeleton from "~/components/ui/Skeleton.vue";
import { useAuthStore } from "~/stores/auth";
import { getApiErrorMessage, getCsrfHeaders } from "~/utils/api";

interface ProviderBreakdown {
  provider: string;
  cost_decimal: string | number;
  tokens: number;
  percentage: number;
}

interface OperationBreakdown {
  operation: string;
  cost_decimal: string | number;
  calls: number;
  percentage: number;
}

interface UsageSummary {
  currency: string;
  today_spent: string | number;
  daily_budget: string | number;
  daily_usage_pct: number;
  month_spent: string | number;
  monthly_budget: string | number;
  monthly_usage_pct: number;
  total_spent: string | number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_images: number;
  total_calls: number;
  is_paused: boolean;
  notify_on_budget_warning: boolean;
  by_provider: ProviderBreakdown[];
  by_operation: OperationBreakdown[];
  updated_at: string;
}

interface LedgerItem {
  id: string;
  workflow_id: string;
  workflow_name: string;
  created_at: string;
  provider: string;
  service: string;
  operation: string;
  input_units: number;
  output_units: number;
  unit_kind: string;
  currency: string;
  estimated_cost: string | number;
  actual_cost: string | number | null;
  effective_cost: string | number;
  status: string;
}

const auth = useAuthStore();
const config = useRuntimeConfig();
const router = useRouter();

const summary = ref<UsageSummary | null>(null);
const ledgerItems = ref<LedgerItem[]>([]);
const isLoading = ref(true);
const isLedgerLoading = ref(false);
const error = ref<string | null>(null);

// Filters
const selectedProviderFilter = ref<string>("all");
const searchQuery = ref<string>("");

// Budget Modal
const isBudgetModalOpen = ref(false);
const editDailyBudget = ref<number>(2.0);
const editMonthlyBudget = ref<number>(30.0);
const editNotifyWarning = ref<boolean>(true);
const editIsPaused = ref<boolean>(false);
const isSavingBudget = ref(false);
const budgetSaveError = ref<string | null>(null);

function formatCurrency(amount: string | number | null | undefined, currency = "USD"): string {
  if (amount === null || amount === undefined) return "$0.00";
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(isNaN(num) ? 0 : num);
}

function formatTokens(count: number | null | undefined): string {
  if (!count) return "0";
  return new Intl.NumberFormat("en-US").format(count);
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return dateStr;
  }
}

function getProviderIcon(provider: string): string {
  const p = provider.toLowerCase();
  if (p.includes("gemini")) return "lucide:sparkles";
  if (p.includes("recraft")) return "lucide:palette";
  if (p.includes("tavily")) return "lucide:search";
  if (p.includes("printful")) return "lucide:shirt";
  return "lucide:cpu";
}

function getOperationBadge(op: string): { label: string; variant: "default" | "secondary" | "outline" | "destructive" } {
  const o = op.toLowerCase();
  if (o.includes("image")) return { label: "Artwork Gen", variant: "default" };
  if (o.includes("synthesis") || o.includes("text")) return { label: "LLM Reasoning", variant: "secondary" };
  if (o.includes("search")) return { label: "Market Intel", variant: "outline" };
  if (o.includes("mockup")) return { label: "Mockup Engine", variant: "outline" };
  return { label: op.replace(/_/g, " "), variant: "secondary" };
}

async function loadSummary() {
  error.value = null;
  try {
    const apiBase = (config.public.apiBase as string) || "";
    const data = await $fetch<UsageSummary>(`${apiBase.replace(/\/$/, "")}/api/v1/usage/summary`, {
      credentials: "include",
    });
    summary.value = data;
    editDailyBudget.value = parseFloat(String(data.daily_budget));
    editMonthlyBudget.value = parseFloat(String(data.monthly_budget));
    editNotifyWarning.value = data.notify_on_budget_warning;
    editIsPaused.value = data.is_paused;
  } catch (err: unknown) {
    if (typeof err === "object" && err !== null && "statusCode" in err && (err as { statusCode: number }).statusCode === 401) {
      router.push("/login");
      return;
    }
    error.value = getApiErrorMessage(err, "Failed to load usage summary.");
  }
}

async function loadLedger() {
  isLedgerLoading.value = true;
  try {
    const apiBase = (config.public.apiBase as string) || "";
    const provParam = selectedProviderFilter.value !== "all" ? `&provider=${selectedProviderFilter.value}` : "";
    const data = await $fetch<{ items: LedgerItem[] }>(
      `${apiBase.replace(/\/$/, "")}/api/v1/usage/ledger?limit=100${provParam}`,
      {
        credentials: "include",
      }
    );
    ledgerItems.value = data.items;
  } catch (err: unknown) {
    console.error("Failed to load usage ledger:", err);
  } finally {
    isLedgerLoading.value = false;
  }
}

async function refreshAll() {
  isLoading.value = true;
  await Promise.all([loadSummary(), loadLedger()]);
  isLoading.value = false;
}

function openBudgetModal() {
  if (summary.value) {
    editDailyBudget.value = parseFloat(String(summary.value.daily_budget));
    editMonthlyBudget.value = parseFloat(String(summary.value.monthly_budget));
    editNotifyWarning.value = summary.value.notify_on_budget_warning;
    editIsPaused.value = summary.value.is_paused;
  }
  budgetSaveError.value = null;
  isBudgetModalOpen.value = true;
}

async function saveBudgetLimits() {
  if (editDailyBudget.value > editMonthlyBudget.value) {
    budgetSaveError.value = "Daily budget cannot exceed the monthly budget.";
    return;
  }
  isSavingBudget.value = true;
  budgetSaveError.value = null;
  try {
    const apiBase = (config.public.apiBase as string) || "";
    const updated = await $fetch<UsageSummary>(`${apiBase.replace(/\/$/, "")}/api/v1/usage/budget`, {
      method: "POST",
      headers: getCsrfHeaders(),
      body: {
        daily_budget: editDailyBudget.value,
        monthly_budget: editMonthlyBudget.value,
        notify_on_budget_warning: editNotifyWarning.value,
        is_paused: editIsPaused.value,
      },
      credentials: "include",
    });
    summary.value = updated;
    isBudgetModalOpen.value = false;
  } catch (err: unknown) {
    budgetSaveError.value = getApiErrorMessage(err, "Failed to update budget settings.");
  } finally {
    isSavingBudget.value = false;
  }
}


const filteredLedger = computed(() => {
  let list = ledgerItems.value;
  if (selectedProviderFilter.value !== "all") {
    list = list.filter((i) => i.provider.toLowerCase() === selectedProviderFilter.value.toLowerCase());
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase().trim();
    list = list.filter(
      (i) =>
        i.workflow_name.toLowerCase().includes(q) ||
        i.service.toLowerCase().includes(q) ||
        i.operation.toLowerCase().includes(q)
    );
  }
  return list;
});

// Pagination state (Max 20 per page)
const currentPage = ref(1);
const pageSize = 20;
const totalFilteredLedger = computed(() => filteredLedger.value.length);
const paginatedLedger = computed(() => {
  const start = (currentPage.value - 1) * pageSize;
  return filteredLedger.value.slice(start, start + pageSize);
});

watch([selectedProviderFilter, searchQuery], () => {
  currentPage.value = 1;
});

onMounted(async () => {
  await auth.checkAuth();
  if (!auth.isAuthenticated) {
    router.push("/login");
    return;
  }
  await refreshAll();
});
</script>

<template>
  <div class="min-h-screen bg-background pb-16">
    <NavBar />

    <main id="main" class="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-10 space-y-8">
      <!-- Page Hero Header -->
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border pb-6">
        <div class="space-y-1">
          <div class="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-primary">
            <Icon name="lucide:coins" class="size-4" aria-hidden="true" />
            <span>Financial & Token Governance</span>
          </div>
          <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
            Token Usage & Cost Controls
          </h1>
          <p class="text-sm text-muted-foreground max-w-2xl">
            Live multi-provider accounting for Gemini, Recraft, and Tavily. Enforce strict daily and monthly budget ceilings.
          </p>
        </div>

        <div class="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            class="gap-1.5 cursor-pointer text-xs font-semibold"
            :disabled="isLoading"
            @click="refreshAll"
          >
            <Icon
              name="lucide:refresh-cw"
              class="size-3.5"
              :class="{ 'animate-spin': isLoading }"
              aria-hidden="true"
            />
            <span>Refresh Ledger</span>
          </Button>

          <Button
            variant="default"
            size="sm"
            data-testid="edit-budgets-btn"
            class="gap-1.5 font-semibold cursor-pointer shadow-2xs text-xs"
            @click="openBudgetModal"
          >
            <Icon name="lucide:sliders" class="size-3.5" aria-hidden="true" />
            <span>Configure Budgets</span>
          </Button>
        </div>
      </div>

      <!-- Emergency Pause Warning Banner if active -->
      <Alert
        v-if="summary?.is_paused"
        variant="destructive"
        class="bg-rose-50 border-rose-200 text-rose-900 shadow-2xs"
      >
        <Icon name="lucide:alert-triangle" class="size-5 text-rose-600" aria-hidden="true" />
        <div class="ml-2">
          <AlertTitle class="font-bold text-sm text-rose-900">Automation Engine Is Paused</AlertTitle>
          <AlertDescription class="text-xs text-rose-700 mt-0.5">
            Background API calls and new research/artwork generations are suspended. You can resume processing anytime from the budget settings modal.
          </AlertDescription>
        </div>
      </Alert>

      <!-- Main Budget Progress & Status Banners -->
      <div v-if="!isLoading && summary" class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Daily Budget Card -->
        <Card class="p-5 border shadow-2xs relative overflow-hidden">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="size-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-200">
                <Icon name="lucide:sun" class="size-4" aria-hidden="true" />
              </div>
              <div>
                <h3 class="text-xs font-bold text-foreground uppercase tracking-wider">Today's Spend Limit</h3>
                <p class="text-xs text-muted-foreground">Rolling 24-hour ceiling</p>
              </div>
            </div>
            <Badge
              :variant="summary.daily_usage_pct >= 90 ? 'destructive' : summary.daily_usage_pct >= 70 ? 'secondary' : 'default'"
              class="font-mono text-xs px-2 py-0.5"
            >
              {{ summary.daily_usage_pct }}% Used
            </Badge>
          </div>

          <div class="mt-4 space-y-2">
            <div class="flex items-baseline justify-between">
              <span class="text-2xl font-extrabold text-foreground font-mono" data-testid="today-spent">
                {{ formatCurrency(summary.today_spent, summary.currency) }}
              </span>
              <span class="text-xs font-medium text-muted-foreground font-mono">
                Cap: {{ formatCurrency(summary.daily_budget, summary.currency) }}
              </span>
            </div>
            <Progress
              :model-value="Math.min(100, summary.daily_usage_pct)"
              class="h-2.5 bg-secondary"
            />
          </div>
        </Card>

        <!-- Monthly Budget Card -->
        <Card class="p-5 border shadow-2xs relative overflow-hidden">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="size-8 rounded-lg bg-blue-50 text-primary flex items-center justify-center border border-blue-200">
                <Icon name="lucide:calendar-days" class="size-4" aria-hidden="true" />
              </div>
              <div>
                <h3 class="text-xs font-bold text-foreground uppercase tracking-wider">Current Month Spend</h3>
                <p class="text-xs text-muted-foreground">Cumulative monthly cap</p>
              </div>
            </div>
            <Badge
              :variant="summary.monthly_usage_pct >= 90 ? 'destructive' : summary.monthly_usage_pct >= 70 ? 'secondary' : 'default'"
              class="font-mono text-xs px-2 py-0.5"
            >
              {{ summary.monthly_usage_pct }}% Used
            </Badge>
          </div>

          <div class="mt-4 space-y-2">
            <div class="flex items-baseline justify-between">
              <span class="text-2xl font-extrabold text-foreground font-mono" data-testid="month-spent">
                {{ formatCurrency(summary.month_spent, summary.currency) }}
              </span>
              <span class="text-xs font-medium text-muted-foreground font-mono">
                Cap: {{ formatCurrency(summary.monthly_budget, summary.currency) }}
              </span>
            </div>
            <Progress
              :model-value="Math.min(100, summary.monthly_usage_pct)"
              class="h-2.5 bg-secondary"
            />
          </div>
        </Card>
      </div>

      <!-- Top KPI Stats Cards -->
      <div v-if="!isLoading && summary" class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Total Cost Card -->
        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between text-muted-foreground">
            <span class="text-xs font-semibold uppercase tracking-wide">Lifetime Spend</span>
            <Icon name="lucide:wallet" class="size-4" aria-hidden="true" />
          </div>
          <p class="text-2xl font-extrabold text-foreground mt-2 font-mono">
            {{ formatCurrency(summary.total_spent, summary.currency) }}
          </p>
          <span class="text-[11px] text-muted-foreground">Across all completed workflows</span>
        </Card>

        <!-- Total Tokens Card -->
        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between text-muted-foreground">
            <span class="text-xs font-semibold uppercase tracking-wide">Total LLM Tokens</span>
            <Icon name="lucide:cpu" class="size-4" aria-hidden="true" />
          </div>
          <p class="text-2xl font-extrabold text-foreground mt-2 font-mono" data-testid="total-tokens">
            {{ formatTokens(summary.total_tokens) }}
          </p>
          <span class="text-[11px] text-muted-foreground">
            {{ formatTokens(summary.total_input_tokens) }} in / {{ formatTokens(summary.total_output_tokens) }} out
          </span>
        </Card>

        <!-- Generated Artwork Images -->
        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between text-muted-foreground">
            <span class="text-xs font-semibold uppercase tracking-wide">Artworks Generated</span>
            <Icon name="lucide:palette" class="size-4" aria-hidden="true" />
          </div>
          <p class="text-2xl font-extrabold text-foreground mt-2 font-mono">
            {{ summary.total_images }}
          </p>
          <span class="text-[11px] text-muted-foreground">Recraft V3 raster & vector files</span>
        </Card>

        <!-- Total API Operations -->
        <Card class="p-4 shadow-2xs hover:shadow-xs transition-shadow">
          <div class="flex items-center justify-between text-muted-foreground">
            <span class="text-xs font-semibold uppercase tracking-wide">API Dispatches</span>
            <Icon name="lucide:activity" class="size-4" aria-hidden="true" />
          </div>
          <p class="text-2xl font-extrabold text-foreground mt-2 font-mono">
            {{ summary.total_calls }}
          </p>
          <span class="text-[11px] text-emerald-600 font-medium">100% Ledger Reconciled</span>
        </Card>
      </div>

      <!-- Loading Skeletons -->
      <div v-if="isLoading" class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Skeleton class="h-36 rounded-xl" />
        <Skeleton class="h-36 rounded-xl" />
      </div>

      <!-- Provider & Operation Breakdown Section -->
      <div v-if="!isLoading && summary" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Spend by Provider -->
        <Card class="shadow-2xs">
          <CardHeader class="pb-3 border-b border-border/80">
            <div class="flex items-center justify-between">
              <div>
                <CardTitle class="text-sm font-bold flex items-center gap-2">
                  <Icon name="lucide:boxes" class="size-4 text-primary" aria-hidden="true" />
                  <span>Cost & Units by Provider</span>
                </CardTitle>
                <CardDescription class="text-xs">Distribution across AI & external services</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent class="p-4 space-y-4">
            <div v-if="summary.by_provider.length === 0" class="text-center py-6 text-xs text-muted-foreground">
              No provider calls recorded yet.
            </div>
            <div
              v-for="prov in summary.by_provider"
              :key="prov.provider"
              class="space-y-1.5"
            >
              <div class="flex items-center justify-between text-xs">
                <span class="font-semibold text-foreground flex items-center gap-1.5 capitalize">
                  <Icon :name="getProviderIcon(prov.provider)" class="size-3.5 text-primary" aria-hidden="true" />
                  {{ prov.provider }}
                </span>
                <div class="flex items-center gap-2">
                  <span v-if="prov.tokens > 0" class="text-muted-foreground font-mono text-[11px]">
                    {{ formatTokens(prov.tokens) }} toks
                  </span>
                  <span class="font-mono font-bold text-foreground">
                    {{ formatCurrency(prov.cost_decimal, summary.currency) }}
                  </span>
                  <span class="text-muted-foreground text-[11px] w-10 text-right">
                    ({{ prov.percentage }}%)
                  </span>
                </div>
              </div>
              <Progress :model-value="prov.percentage" class="h-1.5 bg-secondary" />
            </div>
          </CardContent>
        </Card>

        <!-- Spend by Operation Stage -->
        <Card class="shadow-2xs">
          <CardHeader class="pb-3 border-b border-border/80">
            <div class="flex items-center justify-between">
              <div>
                <CardTitle class="text-sm font-bold flex items-center gap-2">
                  <Icon name="lucide:workflow" class="size-4 text-primary" aria-hidden="true" />
                  <span>Spend by Pipeline Stage</span>
                </CardTitle>
                <CardDescription class="text-xs">Cost allocation across workflow stages</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent class="p-4 space-y-4">
            <div v-if="summary.by_operation.length === 0" class="text-center py-6 text-xs text-muted-foreground">
              No operation spend recorded yet.
            </div>
            <div
              v-for="op in summary.by_operation"
              :key="op.operation"
              class="space-y-1.5"
            >
              <div class="flex items-center justify-between text-xs">
                <span class="font-semibold text-foreground flex items-center gap-1.5">
                  <Badge variant="outline" class="text-[10px] px-1.5 py-0">
                    {{ op.operation.replace(/_/g, " ") }}
                  </Badge>
                </span>
                <div class="flex items-center gap-2">
                  <span class="text-muted-foreground font-mono text-[11px]">
                    {{ op.calls }} calls
                  </span>
                  <span class="font-mono font-bold text-foreground">
                    {{ formatCurrency(op.cost_decimal, summary.currency) }}
                  </span>
                  <span class="text-muted-foreground text-[11px] w-10 text-right">
                    ({{ op.percentage }}%)
                  </span>
                </div>
              </div>
              <Progress :model-value="op.percentage" class="h-1.5 bg-secondary" />
            </div>
          </CardContent>
        </Card>
      </div>

      <!-- Live Provider Usage Ledger Table Section -->
      <Card class="shadow-2xs overflow-hidden">
        <CardHeader class="p-4 sm:p-5 border-b border-border/80 bg-secondary/20">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <CardTitle class="text-base font-bold flex items-center gap-2">
                <Icon name="lucide:receipt" class="size-4 text-primary" aria-hidden="true" />
                <span>Provider Execution Ledger</span>
              </CardTitle>
              <CardDescription class="text-xs">
                Granular record of token counts, model calls, and reconciled micro-costs.
              </CardDescription>
            </div>

            <!-- Filters & Search -->
            <div class="flex flex-wrap items-center gap-2">
              <div class="relative w-44 sm:w-56">
                <Icon name="lucide:search" class="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" aria-hidden="true" />
                <Input
                  v-model="searchQuery"
                  placeholder="Search workflow or model..."
                  class="h-8 pl-8 text-xs bg-white"
                />
              </div>

              <select
                v-model="selectedProviderFilter"
                class="h-8 rounded-md border border-input bg-white px-2.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring cursor-pointer"
                @change="loadLedger"
              >
                <option value="all">All Providers</option>
                <option value="gemini">Gemini</option>
                <option value="recraft">Recraft</option>
                <option value="tavily">Tavily</option>
                <option value="fake">Local Development</option>
              </select>
            </div>
          </div>
        </CardHeader>

        <CardContent class="p-0">
          <!-- Table -->
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-secondary/40 border-b border-border text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                <tr>
                  <th scope="col" class="py-3 px-4">Date & Time</th>
                  <th scope="col" class="py-3 px-4">Workflow</th>
                  <th scope="col" class="py-3 px-4">Provider / Model</th>
                  <th scope="col" class="py-3 px-4">Operation</th>
                  <th scope="col" class="py-3 px-4">Tokens / Units</th>
                  <th scope="col" class="py-3 px-4 text-right">Cost</th>
                  <th scope="col" class="py-3 px-4 text-center">Status</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border/60">
                <tr v-if="isLedgerLoading">
                  <td colspan="7" class="py-8 text-center text-xs text-muted-foreground">
                    <div class="flex items-center justify-center gap-2">
                      <Icon name="lucide:loader-circle" class="size-4 animate-spin text-primary" aria-hidden="true" />
                      <span>Loading ledger records...</span>
                    </div>
                  </td>
                </tr>

                <tr v-else-if="filteredLedger.length === 0">
                  <td colspan="7" class="py-10 text-center text-xs text-muted-foreground">
                    <div class="flex flex-col items-center gap-1.5">
                      <Icon name="lucide:receipt-text" class="size-8 text-muted-foreground/50" aria-hidden="true" />
                      <span class="font-medium text-foreground">No ledger entries found</span>
                      <span class="text-[11px]">When AI research or artwork operations execute, their token logs appear here.</span>
                    </div>
                  </td>
                </tr>

                <tr
                  v-for="item in paginatedLedger"
                  v-else
                  :key="item.id"
                  class="hover:bg-secondary/30 transition-colors"
                >
                  <td class="py-3 px-4 font-mono text-[11px] text-muted-foreground whitespace-nowrap">
                    {{ formatDate(item.created_at) }}
                  </td>
                  <td class="py-3 px-4 font-medium text-foreground whitespace-nowrap max-w-[160px] truncate">
                    <NuxtLink
                      :to="`/workflow/${item.workflow_id}`"
                      class="hover:underline hover:text-primary transition-colors flex items-center gap-1"
                    >
                      <span>{{ item.workflow_name || 'Workflow' }}</span>
                      <Icon name="lucide:external-link" class="size-3 text-muted-foreground" aria-hidden="true" />
                    </NuxtLink>
                  </td>
                  <td class="py-3 px-4 whitespace-nowrap">
                    <div class="flex items-center gap-1.5 font-medium capitalize">
                      <Icon :name="getProviderIcon(item.provider)" class="size-3.5 text-primary" aria-hidden="true" />
                      <span>{{ item.provider }}</span>
                      <span class="text-muted-foreground font-mono text-[10px]">({{ item.service }})</span>
                    </div>
                  </td>
                  <td class="py-3 px-4 whitespace-nowrap">
                    <Badge :variant="getOperationBadge(item.operation).variant" class="text-[10px] font-semibold px-2 py-0.5">
                      {{ getOperationBadge(item.operation).label }}
                    </Badge>
                  </td>
                  <td class="py-3 px-4 font-mono text-[11px] text-muted-foreground whitespace-nowrap">
                    <span v-if="item.unit_kind === 'tokens'">
                      {{ formatTokens(item.input_units) }} in / {{ formatTokens(item.output_units) }} out
                    </span>
                    <span v-else>
                      {{ item.output_units || item.input_units || 1 }} {{ item.unit_kind }}
                    </span>
                  </td>
                  <td class="py-3 px-4 text-right font-mono font-bold text-foreground whitespace-nowrap">
                    {{ formatCurrency(item.effective_cost, item.currency) }}
                  </td>
                  <td class="py-3 px-4 text-center whitespace-nowrap">
                    <Badge
                      :variant="item.status === 'reconciled' ? 'default' : item.status === 'voided' ? 'destructive' : 'outline'"
                      class="text-[10px] uppercase font-mono px-2 py-0.5"
                    >
                      {{ item.status }}
                    </Badge>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination Bar -->
          <Pagination
            v-if="filteredLedger.length > 0"
            v-model:current-page="currentPage"
            :total-items="totalFilteredLedger"
            :page-size="pageSize"
            class="px-4"
          />
        </CardContent>
      </Card>
    </main>

    <!-- Configure Budgets Modal -->
    <Dialog :open="isBudgetModalOpen" @update:open="isBudgetModalOpen = $event">
      <div class="space-y-6">
        <DialogHeader class="space-y-1">
          <DialogTitle class="text-lg font-bold flex items-center gap-2">
            <Icon name="lucide:sliders" class="size-5 text-primary" aria-hidden="true" />
            <span>Configure Budget Ceilings</span>
          </DialogTitle>
          <DialogDescription class="text-xs text-muted-foreground">
            Define daily and monthly spending limits. Requests that would exceed these caps are rejected before API dispatch.
          </DialogDescription>
        </DialogHeader>

        <Alert v-if="budgetSaveError" variant="destructive" class="text-xs py-2">
          <Icon name="lucide:alert-circle" class="size-4 mr-1.5" aria-hidden="true" />
          <AlertDescription>{{ budgetSaveError }}</AlertDescription>
        </Alert>

        <div class="space-y-4">
          <!-- Daily Budget Input -->
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <Label for="daily-budget" class="text-xs font-semibold">Daily Budget Cap (USD)</Label>
              <span class="text-[11px] text-muted-foreground">Min $0.00, Max $1,000.00</span>
            </div>
            <div class="relative">
              <span class="absolute left-3 top-2.5 text-xs text-muted-foreground font-mono">$</span>
              <Input
                id="daily-budget"
                v-model.number="editDailyBudget"
                type="number"
                step="0.50"
                min="0"
                max="1000"
                class="pl-7 font-mono text-sm"
              />
            </div>
          </div>

          <!-- Monthly Budget Input -->
          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <Label for="monthly-budget" class="text-xs font-semibold">Monthly Budget Cap (USD)</Label>
              <span class="text-[11px] text-muted-foreground">Min $0.00, Max $10,000.00</span>
            </div>
            <div class="relative">
              <span class="absolute left-3 top-2.5 text-xs text-muted-foreground font-mono">$</span>
              <Input
                id="monthly-budget"
                v-model.number="editMonthlyBudget"
                type="number"
                step="5.00"
                min="0"
                max="10000"
                class="pl-7 font-mono text-sm"
              />
            </div>
          </div>

          <!-- Warning Notification Toggle -->
          <div class="flex items-center justify-between pt-2 border-t border-border/80">
            <div>
              <h4 class="text-xs font-semibold text-foreground">Budget Warning Alerts</h4>
              <p class="text-[11px] text-muted-foreground">Send notifications when usage reaches 80% of budget.</p>
            </div>
            <input
              id="notify-warning"
              v-model="editNotifyWarning"
              type="checkbox"
              class="size-4 rounded border-input text-primary focus:ring-primary cursor-pointer"
            />
          </div>

          <!-- Emergency Pause Toggle -->
          <div class="flex items-center justify-between pt-2 border-t border-border/80">
            <div>
              <h4 class="text-xs font-semibold text-rose-700">Emergency Stop / Pause Automation</h4>
              <p class="text-[11px] text-muted-foreground">Halt all automated background API calls immediately.</p>
            </div>
            <input
              id="emergency-pause"
              v-model="editIsPaused"
              type="checkbox"
              class="size-4 rounded border-input text-rose-600 focus:ring-rose-500 cursor-pointer"
            />
          </div>
        </div>

        <DialogFooter class="flex items-center justify-end gap-2 pt-3 border-t border-border/80">
          <Button
            variant="outline"
            size="sm"
            class="cursor-pointer font-medium"
            :disabled="isSavingBudget"
            @click="isBudgetModalOpen = false"
          >
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            class="cursor-pointer font-semibold shadow-2xs"
            :disabled="isSavingBudget"
            @click="saveBudgetLimits"
          >
            <Icon v-if="isSavingBudget" name="lucide:loader-circle" class="size-3.5 animate-spin mr-1.5" aria-hidden="true" />
            <span>{{ isSavingBudget ? 'Saving...' : 'Save Changes' }}</span>
          </Button>
        </DialogFooter>
      </div>
    </Dialog>
  </div>
</template>
