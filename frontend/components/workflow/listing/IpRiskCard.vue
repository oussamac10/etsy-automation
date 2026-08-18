<script setup lang="ts">
import { computed } from 'vue';
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
</script>

<template>
  <Card class="border-border shadow-xs">
    <CardHeader class="flex flex-row items-center justify-between pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon name="lucide:shield-check" class="size-4 text-primary" aria-hidden="true" />
          <span>USPTO Trademark Screening & IP Risk</span>
          <Badge
            v-if="isCleared"
            variant="success"
            class="text-[10px] font-bold uppercase tracking-wider"
          >
            Cleared
          </Badge>
          <Badge
            v-else-if="isWarning"
            variant="warning"
            class="text-[10px] font-bold uppercase tracking-wider"
          >
            Warning
          </Badge>
          <Badge
            v-else-if="isHighRisk"
            variant="destructive"
            class="text-[10px] font-bold uppercase tracking-wider"
          >
            High Risk
          </Badge>
          <Badge
            v-else
            variant="outline"
            class="text-[10px] font-bold uppercase tracking-wider"
          >
            Unchecked
          </Badge>

          <!-- Source Badge -->
          <Badge
            v-if="isLocalIndex"
            variant="secondary"
            class="text-[9px] font-medium tracking-normal bg-blue-50 text-blue-700 border-blue-200"
          >
            USPTO Data — Local Index
          </Badge>
          <Badge
            v-else-if="isLocalFallback"
            variant="secondary"
            class="text-[9px] font-medium tracking-normal bg-amber-50 text-amber-800 border-amber-200"
          >
            Local Defense Registry
          </Badge>

          <!-- TSDR Verification Badge -->
          <Badge
            v-if="isTsdrVerified"
            variant="secondary"
            class="text-[9px] font-medium tracking-normal bg-emerald-50 text-emerald-700 border-emerald-200"
          >
            TSDR Verified
          </Badge>
          <Badge
            v-else-if="isTsdrUnavailable"
            variant="secondary"
            class="text-[9px] font-medium tracking-normal bg-slate-100 text-slate-600 border-slate-200"
          >
            TSDR Unavailable
          </Badge>
        </CardTitle>
        <CardDescription class="text-xs flex items-center gap-2 flex-wrap">
          <span>Official USPTO trademark dataset and restricted brand defense indexing.</span>
          <span v-if="datasetFormattedDate" class="text-muted-foreground font-mono text-[10px]">
            • Dataset indexed: {{ datasetFormattedDate }}
          </span>
        </CardDescription>
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        :disabled="isScreening"
        class="text-xs h-8 gap-1.5 cursor-pointer"
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

      <!-- Legal Disclaimer Alert -->
      <div class="bg-blue-50/70 border border-blue-200/80 rounded-lg p-2.5 flex items-center gap-2 text-xs text-blue-900">
        <Icon name="lucide:info" class="size-4 text-blue-600 shrink-0" aria-hidden="true" />
        <p class="text-[11px] leading-snug">
          <b>Notice:</b> Preliminary automated trademark screening only — not legal advice. Searches USPTO registered trademark records and POD-relevant Nice classes (009, 016, 021, 025, 035).
        </p>
      </div>

      <!-- Scanned Terms Pills -->
      <div v-if="scannedPhrases.length > 0" class="space-y-1">
        <p class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          Scanned Listing Terms ({{ scannedPhrases.length }})
        </p>
        <div class="flex flex-wrap gap-1">
          <span
            v-for="phrase in scannedPhrases"
            :key="phrase"
            class="inline-flex items-center px-2 py-0.5 rounded text-[11px] bg-slate-100 text-slate-700 font-mono"
          >
            "{{ phrase }}"
          </span>
        </div>
      </div>

      <!-- High Risk Warning Box -->
      <div v-if="isHighRisk" class="bg-red-50 border border-red-200 rounded-lg p-3 space-y-2 text-xs text-red-950">
        <div class="flex items-center gap-2 font-bold text-red-700">
          <Icon name="lucide:shield-alert" class="size-4 text-red-600 shrink-0" aria-hidden="true" />
          <span>High Risk Detected — Gate 3 Approval Blocked</span>
        </div>
        <p class="text-[11px] leading-relaxed text-red-900">
          Exact or high-confidence registered trademark matches were detected in print-on-demand classes (apparel, graphics, print) or commercial brand registries. You must edit the title, slogan, or tags to remove infringing phrases and re-screen before publishing.
        </p>
        <ul v-if="reasons.length > 0" class="list-disc list-inside text-[11px] space-y-0.5 text-red-800">
          <li v-for="(reason, idx) in reasons" :key="idx">{{ reason }}</li>
        </ul>
      </div>

      <!-- Warning Box with Checkbox -->
      <div v-else-if="isWarning" class="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-2.5 text-xs text-amber-950">
        <div class="flex items-center gap-2 font-bold text-amber-800">
          <Icon name="lucide:alert-triangle" class="size-4 text-amber-600 shrink-0" aria-hidden="true" />
          <span>Trademark Warnings Found (Secondary / Non-POD Classes)</span>
        </div>
        <p class="text-[11px] leading-relaxed text-amber-900">
          Potential trademark matches found in unrelated classifications or containing generic multi-word phrasing. Gate 3 requires explicit manual acknowledgement of this warning before proceeding.
        </p>
        <ul v-if="reasons.length > 0" class="list-disc list-inside text-[11px] space-y-0.5 text-amber-800">
          <li v-for="(reason, idx) in reasons" :key="idx">{{ reason }}</li>
        </ul>

        <!-- Acknowledgment Checkbox -->
        <label class="flex items-start gap-2.5 pt-1.5 border-t border-amber-200/80 cursor-pointer select-none">
          <input
            type="checkbox"
            :checked="warningAcknowledged || acknowledgedAt !== null"
            class="size-4 mt-0.5 rounded border-amber-300 text-amber-600 focus:ring-amber-500 cursor-pointer"
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

      <!-- Cleared State -->
      <div v-else-if="isCleared" class="bg-emerald-50 border border-emerald-200 rounded-lg p-3 flex items-start gap-2.5 text-xs text-emerald-950">
        <Icon name="lucide:badge-check" class="size-4.5 text-emerald-600 shrink-0 mt-0.5" aria-hidden="true" />
        <div class="space-y-0.5">
          <p class="font-bold text-emerald-800 text-xs">Trademark Screening Cleared</p>
          <p class="text-[11px] text-emerald-700 leading-snug">
            No active conflicting registered trademarks were found across scanned terms in print-on-demand Nice classes (009, 016, 021, 025, 035).
          </p>
        </div>
      </div>

      <!-- Matches Table / List -->
      <div v-if="rawMatches.length > 0" class="space-y-2">
        <p class="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          Identified Registry Matches ({{ rawMatches.length }})
        </p>
        <div class="space-y-1.5 max-h-64 overflow-y-auto pr-1">
          <div
            v-for="(match, idx) in rawMatches"
            :key="idx"
            class="p-2.5 bg-slate-50 border border-slate-200 rounded-md text-xs space-y-1"
          >
            <div class="flex items-center justify-between">
              <span class="font-bold text-slate-900 font-mono">"{{ match.mark_text || match.matched_mark }}"</span>
              <div class="flex items-center gap-1.5">
                <Badge
                  :variant="match.is_live ? 'destructive' : 'secondary'"
                  class="text-[9px] px-1 py-0 uppercase font-bold"
                >
                  {{ match.is_live ? 'LIVE' : 'DEAD' }}
                </Badge>
                <Badge
                  v-if="match.tsdr_verified"
                  variant="outline"
                  class="text-[9px] px-1 py-0 text-emerald-700 border-emerald-200 bg-emerald-50 font-medium"
                >
                  TSDR
                </Badge>
                <a
                  v-if="match.source_url"
                  :href="match.source_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-[10px] text-primary hover:underline inline-flex items-center gap-0.5"
                >
                  <span>TSDR Case</span>
                  <Icon name="lucide:external-link" class="size-2.5" aria-hidden="true" />
                </a>
              </div>
            </div>

            <div class="text-[10px] text-slate-600 flex flex-wrap gap-x-3 gap-y-0.5">
              <span v-if="match.serial_number">Serial: <span class="font-mono">{{ match.serial_number }}</span></span>
              <span v-if="match.classes && match.classes.length > 0">Classes: <span class="font-mono font-bold">{{ match.classes.join(', ') }}</span></span>
              <span v-if="match.owner">Owner: {{ match.owner }}</span>
            </div>

            <p v-if="match.risk_reason" class="text-[10px] text-red-700 font-medium">
              {{ match.risk_reason }}
            </p>

            <p v-if="match.recommended_action" class="text-[10px] text-slate-700">
              <b>Action:</b> {{ match.recommended_action }}
            </p>

            <p v-if="match.goods_services" class="text-[10px] text-slate-500 italic line-clamp-2">
              {{ match.goods_services }}
            </p>
          </div>
        </div>
      </div>
    </CardContent>
  </Card>
</template>

