<script setup lang="ts">
import { computed, ref } from 'vue';
import Card from '~/components/ui/Card.vue';
import CardHeader from '~/components/ui/CardHeader.vue';
import CardTitle from '~/components/ui/CardTitle.vue';
import CardDescription from '~/components/ui/CardDescription.vue';
import CardContent from '~/components/ui/CardContent.vue';
import Button from '~/components/ui/Button.vue';
import Badge from '~/components/ui/Badge.vue';
import type { IpFindingsReport, RiskLevel, TrademarkFinding } from '~/types/listing';

const props = defineProps<{
  riskLevel: RiskLevel;
  findings: IpFindingsReport;
  acknowledgedAt?: string | null;
  acknowledgedBy?: string | null;
  warningAcknowledged: boolean;
  isScreening: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:warningAcknowledged', value: boolean): void;
  (e: 'rescreen'): void;
}>();

const isCleared = computed(() => props.riskLevel === 'low');
const isWarning = computed(() => props.riskLevel === 'medium');
const isHighRisk = computed(() => props.riskLevel === 'high');

const isLocalIndex = computed(() =>
  props.findings.screening_source?.startsWith('USPTO_LOCAL_INDEX') ||
  props.findings.screening_source === 'USPTO'
);
const isTsdrVerified = computed(() =>
  props.findings.tsdr_status === 'VERIFIED' ||
  props.findings.screening_source === 'USPTO_LOCAL_INDEX_TSDR_VERIFIED'
);
const isTsdrUnavailable = computed(() =>
  props.findings.tsdr_status === 'UNAVAILABLE' ||
  props.findings.screening_source === 'USPTO_LOCAL_INDEX_TSDR_UNAVAILABLE'
);
const isLocalFallback = computed(() =>
  props.findings.screening_source === 'local_defense_registry' ||
  props.findings.uspto_status === 'UNAVAILABLE'
);

const datasetFormattedDate = computed(() => {
  if (!props.findings.dataset_updated_at) return null;
  try {
    return new Date(props.findings.dataset_updated_at).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return props.findings.dataset_updated_at;
  }
});

const fallbackMessage = computed(() =>
  props.findings.warning_message ||
  'USPTO screening was unavailable. Results below are from the local preliminary screen only.'
);

const rawMatches = computed<TrademarkFinding[]>(() => {
  const list = props.findings.matches || props.findings.findings || [];
  return list as TrademarkFinding[];
});
const scannedPhrases = computed<string[]>(() => props.findings.scanned_phrases || props.findings.searched_phrases || []);
const reasons = computed<string[]>(() => {
  if (props.findings.reasons && props.findings.reasons.length > 0) {
    return props.findings.reasons;
  }
  return rawMatches.value
    .map((m) => m.risk_reason)
    .filter((r): r is string => Boolean(r));
});

// UI State for expanding scanned terms list
const showAllTerms = ref(false);
const INITIAL_TERMS_COUNT = 6;
const displayedPhrases = computed(() => {
  if (showAllTerms.value || scannedPhrases.value.length <= INITIAL_TERMS_COUNT) {
    return scannedPhrases.value;
  }
  return scannedPhrases.value.slice(0, INITIAL_TERMS_COUNT);
});
const hiddenTermsCount = computed(() => Math.max(0, scannedPhrases.value.length - INITIAL_TERMS_COUNT));
</script>

<template>
  <Card class="border-border shadow-xs overflow-hidden">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div class="space-y-1">
        <div class="flex items-center gap-2 flex-wrap">
          <CardTitle class="text-base font-semibold flex items-center gap-2">
            <Icon name="lucide:shield-check" class="size-4.5 text-primary" aria-hidden="true" />
            <span>USPTO Trademark Screening & IP Risk</span>
          </CardTitle>

          <!-- Primary Risk Level Badge -->
          <Badge
            v-if="isCleared"
            variant="success"
            class="text-[10px] font-bold uppercase tracking-wider gap-1"
          >
            <Icon name="lucide:check" class="size-3" aria-hidden="true" />
            <span>Cleared</span>
          </Badge>
          <Badge
            v-else-if="isWarning"
            variant="warning"
            class="text-[10px] font-bold uppercase tracking-wider gap-1"
          >
            <Icon name="lucide:alert-triangle" class="size-3" aria-hidden="true" />
            <span>Warning</span>
          </Badge>
          <Badge
            v-else-if="isHighRisk"
            variant="destructive"
            class="text-[10px] font-bold uppercase tracking-wider gap-1"
          >
            <Icon name="lucide:shield-ban" class="size-3" aria-hidden="true" />
            <span>High Risk</span>
          </Badge>
          <Badge
            v-else
            variant="outline"
            class="text-[10px] font-bold uppercase tracking-wider"
          >
            Unchecked
          </Badge>
        </div>

        <!-- Subtitle & Provenance Metadata -->
        <CardDescription class="text-xs flex items-center gap-2 flex-wrap">
          <span class="inline-flex items-center gap-1.5 font-medium text-slate-600">
            <Icon name="lucide:database" class="size-3 text-slate-400" aria-hidden="true" />
            <span v-if="isLocalIndex">USPTO Local Trademark Index</span>
            <span v-else-if="isLocalFallback">Local Defense Registry</span>
            <span v-else>USPTO Database</span>
          </span>

          <span v-if="datasetFormattedDate" class="text-muted-foreground text-[11px]">
            • Dataset indexed {{ datasetFormattedDate }}
          </span>

          <!-- TSDR Pill -->
          <span
            v-if="isTsdrVerified"
            class="inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"
          >
            <Icon name="lucide:check-check" class="size-3 text-emerald-600" aria-hidden="true" />
            TSDR Verified
          </span>
          <span
            v-else-if="isTsdrUnavailable"
            class="inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200"
          >
            TSDR Unavailable
          </span>
        </CardDescription>
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        :disabled="isScreening"
        class="text-xs h-8 px-2.5 gap-1.5 cursor-pointer self-start sm:self-auto shrink-0 font-medium"
        @click="emit('rescreen')"
      >
        <Icon v-if="isScreening" name="lucide:loader-circle" class="size-3.5 animate-spin text-primary" aria-hidden="true" />
        <Icon v-else name="lucide:refresh-cw" class="size-3.5 text-primary" aria-hidden="true" />
        <span>Re-screen</span>
      </Button>
    </CardHeader>

    <CardContent class="space-y-4 pt-0">
      <!-- Unavailable Fallback Notice Alert -->
      <div
        v-if="isLocalFallback"
        class="bg-amber-50/90 border border-amber-300 rounded-lg p-2.5 flex items-center gap-2 text-xs text-amber-950"
      >
        <Icon name="lucide:alert-circle" class="size-4 text-amber-700 shrink-0" aria-hidden="true" />
        <p class="text-[11px] leading-snug font-medium">
          {{ fallbackMessage }}
        </p>
      </div>

      <!-- Cleared State Banner -->
      <div
        v-if="isCleared"
        class="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-3.5 flex items-start gap-3 text-xs text-emerald-950"
      >
        <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 shrink-0 mt-0.5">
          <Icon name="lucide:shield-check" class="size-4.5 text-emerald-600" aria-hidden="true" />
        </div>
        <div class="space-y-0.5 min-w-0 flex-1">
          <p class="font-bold text-emerald-900 text-xs flex items-center gap-1.5">
            <span>Trademark Screening Cleared</span>
            <span class="text-[10px] font-normal text-emerald-700">(0 conflicting marks found)</span>
          </p>
          <p class="text-[11px] text-emerald-800/90 leading-relaxed">
            Scanned terms show no active registered trademarks in print-on-demand Nice classes (009, 016, 021, 025, 035).
          </p>
        </div>
      </div>

      <!-- High Risk Warning Box -->
      <div
        v-else-if="isHighRisk"
        class="bg-rose-50 border border-rose-200 rounded-xl p-3.5 space-y-2.5 text-xs text-rose-950"
      >
        <div class="flex items-center gap-2 font-bold text-rose-800">
          <Icon name="lucide:shield-ban" class="size-4.5 text-rose-600 shrink-0" aria-hidden="true" />
          <span>High Risk Detected — Gate 3 Approval Blocked</span>
        </div>
        <p class="text-[11px] leading-relaxed text-rose-900">
          Exact or high-confidence registered trademark matches were detected in print-on-demand classes (apparel, graphics, print) or commercial brand registries. Edit the title, slogan, or tags to remove infringing phrases and re-screen before publishing.
        </p>
        <ul v-if="reasons.length > 0" class="list-disc list-inside text-[11px] space-y-0.5 text-rose-800 font-medium">
          <li v-for="(reason, idx) in reasons" :key="idx">{{ reason }}</li>
        </ul>
      </div>

      <!-- Warning Box with Checkbox -->
      <div
        v-else-if="isWarning"
        class="bg-amber-500/10 border border-amber-500/25 rounded-xl p-3.5 space-y-2.5 text-xs text-amber-950"
      >
        <div class="flex items-center gap-2 font-bold text-amber-900">
          <Icon name="lucide:alert-triangle" class="size-4.5 text-amber-600 shrink-0" aria-hidden="true" />
          <span>Trademark Warnings Found (Secondary / Non-POD Classes)</span>
        </div>
        <p class="text-[11px] leading-relaxed text-amber-900">
          Potential trademark matches found in unrelated classifications or containing generic multi-word phrasing. Gate 3 requires explicit manual acknowledgement of this warning before proceeding.
        </p>
        <ul v-if="reasons.length > 0" class="list-disc list-inside text-[11px] space-y-0.5 text-amber-850 font-medium">
          <li v-for="(reason, idx) in reasons" :key="idx">{{ reason }}</li>
        </ul>

        <!-- Acknowledgment Checkbox -->
        <label class="flex items-start gap-2.5 pt-2 border-t border-amber-300/60 cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="warningAcknowledged || acknowledgedAt !== null"
            class="size-4 mt-0.5 rounded border-amber-400 text-amber-600 focus:ring-amber-500 cursor-pointer"
            @change="emit('update:warningAcknowledged', ($event.target as HTMLInputElement).checked)"
          >
          <div class="text-[11px] leading-snug">
            <span class="font-bold text-amber-950">I have reviewed the trademark warning findings above and acknowledge the risk.</span>
            <p v-if="acknowledgedAt" class="text-[10px] text-amber-800 mt-0.5">
              Acknowledged by {{ acknowledgedBy || 'owner' }} at {{ new Date(acknowledgedAt).toLocaleString() }}
            </p>
          </div>
        </label>
      </div>

      <!-- Scanned Terms Pills (Collapsible & Compact) -->
      <div v-if="scannedPhrases.length > 0" class="space-y-1.5">
        <div class="flex items-center justify-between">
          <p class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Icon name="lucide:scan" class="size-3.5 text-slate-400" aria-hidden="true" />
            <span>Scanned Terms ({{ scannedPhrases.length }})</span>
          </p>

          <button
            v-if="scannedPhrases.length > INITIAL_TERMS_COUNT"
            type="button"
            class="text-[11px] text-primary hover:text-primary-hover font-semibold cursor-pointer focus-visible:outline-none"
            @click="showAllTerms = !showAllTerms"
          >
            {{ showAllTerms ? 'Show less' : `+${hiddenTermsCount} more` }}
          </button>
        </div>

        <div class="flex flex-wrap gap-1.5">
          <span
            v-for="phrase in displayedPhrases"
            :key="phrase"
            :title="phrase"
            class="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] bg-slate-100/90 border border-slate-200/80 text-slate-700 font-mono max-w-[220px] sm:max-w-[280px] truncate hover:bg-slate-200/70 transition-colors"
          >
            "{{ phrase }}"
          </span>

          <button
            v-if="!showAllTerms && hiddenTermsCount > 0"
            type="button"
            class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors cursor-pointer"
            @click="showAllTerms = true"
          >
            +{{ hiddenTermsCount }} more...
          </button>
        </div>
      </div>

      <!-- Matches Table / List -->
      <div v-if="rawMatches.length > 0" class="space-y-2">
        <p class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
          <Icon name="lucide:file-search" class="size-3.5 text-slate-400" aria-hidden="true" />
          <span>Identified Registry Matches ({{ rawMatches.length }})</span>
        </p>
        <div class="space-y-2 max-h-64 overflow-y-auto pr-1">
          <div
            v-for="(match, idx) in rawMatches"
            :key="idx"
            class="p-3 bg-slate-50/90 border border-slate-200/90 rounded-lg text-xs space-y-1.5 shadow-2xs"
          >
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <span class="font-bold text-slate-900 font-mono text-xs">"{{ match.mark_text || match.matched_mark }}"</span>
              <div class="flex items-center gap-1.5 shrink-0">
                <Badge
                  :variant="match.is_live ? 'destructive' : 'secondary'"
                  class="text-[9px] px-1.5 py-0 uppercase font-bold"
                >
                  {{ match.is_live ? 'LIVE' : 'DEAD' }}
                </Badge>
                <Badge
                  v-if="match.tsdr_verified"
                  variant="outline"
                  class="text-[9px] px-1.5 py-0 text-emerald-700 border-emerald-200 bg-emerald-50 font-medium"
                >
                  TSDR
                </Badge>
                <a
                  v-if="match.source_url"
                  :href="match.source_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-[11px] text-primary hover:underline inline-flex items-center gap-1 font-medium"
                >
                  <span>TSDR Case</span>
                  <Icon name="lucide:external-link" class="size-3" aria-hidden="true" />
                </a>
              </div>
            </div>

            <div class="text-[11px] text-slate-600 flex flex-wrap gap-x-3 gap-y-0.5 font-sans">
              <span v-if="match.serial_number">Serial: <span class="font-mono font-medium text-slate-800">{{ match.serial_number }}</span></span>
              <span v-if="match.classes && match.classes.length > 0">Nice Classes: <span class="font-mono font-bold text-slate-800">{{ match.classes.join(', ') }}</span></span>
              <span v-if="match.owner">Owner: <span class="text-slate-800 font-medium">{{ match.owner }}</span></span>
            </div>

            <p v-if="match.risk_reason" class="text-[11px] text-red-700 font-medium bg-red-50/60 p-1.5 rounded border border-red-100">
              {{ match.risk_reason }}
            </p>

            <p v-if="match.recommended_action" class="text-[11px] text-slate-700">
              <b>Recommended Action:</b> {{ match.recommended_action }}
            </p>

            <p v-if="match.goods_services" class="text-[10px] text-slate-500 italic line-clamp-2">
              {{ match.goods_services }}
            </p>
          </div>
        </div>
      </div>

      <!-- Legal Disclaimer Footer -->
      <div class="bg-slate-50/70 border border-slate-200/70 rounded-lg p-2.5 flex items-center gap-2 text-xs text-slate-600">
        <Icon name="lucide:info" class="size-3.5 text-slate-400 shrink-0" aria-hidden="true" />
        <p class="text-[10px] leading-tight text-slate-500">
          Preliminary automated trademark screening across USPTO registered marks and POD Nice classes (009, 016, 021, 025, 035) — not legal advice.
        </p>
      </div>
    </CardContent>
  </Card>
</template>

