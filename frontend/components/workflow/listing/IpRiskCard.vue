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
import { sanitizeUrl } from '~/utils/sanitize';

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

const showDetails = ref(false);

const _isCleared = computed(() => props.riskLevel === 'low');
const isWarning = computed(() => props.riskLevel === 'medium');
const isHighRisk = computed(() => props.riskLevel === 'high');

const _isLocalIndex = computed(() =>
  props.findings.screening_source?.startsWith('USPTO_LOCAL_INDEX') ||
  props.findings.screening_source === 'USPTO'
);
const _isTsdrVerified = computed(() =>
  props.findings.tsdr_status === 'VERIFIED' ||
  props.findings.screening_source === 'USPTO_LOCAL_INDEX_TSDR_VERIFIED'
);
const _isTsdrUnavailable = computed(() =>
  props.findings.tsdr_status === 'UNAVAILABLE' ||
  props.findings.screening_source === 'USPTO_LOCAL_INDEX_TSDR_UNAVAILABLE'
);
const _isLocalFallback = computed(() =>
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

const rawMatches = computed<TrademarkFinding[]>(() => {
  const list = props.findings.matches || props.findings.findings || [];
  return list as TrademarkFinding[];
});
const liveMatchesCount = computed(() => {
  return rawMatches.value.filter((m) => m.is_live).length;
});

const scannedPhrases = computed<string[]>(() => props.findings.scanned_phrases || props.findings.searched_phrases || []);
const _reasons = computed<string[]>(() => {
  if (props.findings.reasons && props.findings.reasons.length > 0) {
    return props.findings.reasons;
  }
  return rawMatches.value
    .map((m) => m.risk_reason)
    .filter((r): r is string => Boolean(r));
});

</script>

<template>
  <Card class="border-border bg-card shadow-xs overflow-hidden" data-testid="ip-risk-card">
    <CardHeader class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
      <div>
        <CardTitle class="text-base font-semibold flex items-center gap-2 flex-wrap">
          <Icon
            :name="isHighRisk ? 'lucide:shield-ban' : isWarning ? 'lucide:shield-alert' : 'lucide:shield-check'"
            class="size-4 text-primary"
            aria-hidden="true"
          />
          <span>Trademark Screening</span>
          <Badge
            :variant="isHighRisk ? 'destructive' : isWarning ? 'warning' : 'success'"
            class="text-[10px] font-mono"
          >
            {{ riskLevel.toUpperCase() }} RISK
          </Badge>
        </CardTitle>
        <CardDescription class="text-xs">
          Automated USPTO trademark screening.
        </CardDescription>
      </div>

        <div class="flex items-center gap-2 shrink-0">
          <Button
            type="button"
            variant="outline"
            size="sm"
            class="h-8 gap-1.5 text-xs font-medium cursor-pointer"
            :disabled="isScreening"
            @click="emit('rescreen')"
          >
            <Icon v-if="isScreening" name="lucide:loader-circle" class="size-3.5 animate-spin" aria-hidden="true" />
            <Icon v-else name="lucide:refresh-cw" class="size-3.5 text-primary" aria-hidden="true" />
            <span>Re-screen</span>
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            class="h-8 px-2 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
            @click="showDetails = !showDetails"
          >
            <span>{{ showDetails ? 'Hide Details' : 'View Details' }}</span>
          </Button>
        </div>
    </CardHeader>

    <CardContent class="p-4 sm:p-5 pt-0 space-y-3">
      <!-- High-Level Summary Card -->
      <div
        class="p-3 rounded-lg border text-xs space-y-1.5"
        :class="
          isHighRisk
            ? 'bg-red-500/10 border-red-500/20'
            : isWarning
            ? 'bg-amber-500/10 border-amber-500/20'
            : 'bg-muted/40 border-border'
        "
      >
        <p class="font-semibold text-foreground flex items-center gap-2">
          <Icon
            :name="isHighRisk ? 'lucide:alert-octagon' : isWarning ? 'lucide:alert-triangle' : 'lucide:check-circle-2'"
            class="size-4 shrink-0"
            :class="isHighRisk ? 'text-red-600 dark:text-red-400' : isWarning ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'"
            aria-hidden="true"
          />
          <span>
            {{
              isHighRisk
                ? 'High Risk: Approval blocked due to direct trademark conflict.'
                : isWarning
                ? 'Medium Risk: Potential matches need review before approval.'
                : 'Low Risk: No material conflicts identified in current automated screening.'
            }}
          </span>
        </p>
        <p class="text-[11px] text-muted-foreground">
          {{ liveMatchesCount }} conflicting LIVE mark{{ liveMatchesCount === 1 ? '' : 's' }} found • Screened: {{ scannedPhrases.length }} term{{ scannedPhrases.length === 1 ? '' : 's' }} • Dataset: {{ datasetFormattedDate || 'Aug 2026' }}
        </p>
      </div>

      <!-- Warning Acknowledgement Checkbox (only shown for Medium Risk) -->
      <div v-if="isWarning && !acknowledgedAt" class="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs space-y-2">
        <p class="font-semibold text-foreground">Acknowledgement Required</p>
        <label class="flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            class="mt-0.5 rounded border-amber-500 text-amber-600 focus:ring-amber-500"
            :checked="warningAcknowledged"
            @change="emit('update:warningAcknowledged', ($event.target as HTMLInputElement).checked)"
          />
          <span class="text-[11px] text-foreground/80 dark:text-foreground/90 leading-relaxed">
            I acknowledge this automated screening is preliminary and does not constitute legal clearance advice.
          </span>
        </label>
      </div>

      <!-- Detailed Breakdown (Shown when expanded) -->
      <div v-if="showDetails" class="space-y-3 pt-2 border-t border-border/50 text-xs">
        <!-- Scanned terms chips -->
        <div class="space-y-1.5">
          <p class="font-semibold text-foreground">Scanned Terms ({{ scannedPhrases.length }})</p>
          <div class="flex flex-wrap gap-1">
            <Badge
              v-for="term in scannedPhrases"
              :key="term"
              variant="outline"
              class="text-[10px] font-mono text-muted-foreground bg-muted/30"
            >
              {{ term }}
            </Badge>
          </div>
        </div>

        <!-- Registered Trademark Matches List -->
        <div v-if="rawMatches.length > 0" class="space-y-2 pt-1">
          <p class="font-semibold text-foreground">Matched Records ({{ rawMatches.length }})</p>
          <div
            v-for="m in rawMatches"
            :key="m.serial_number || m.mark_text || m.matched_mark"
            class="p-2.5 rounded-md bg-muted/40 border border-border space-y-1 text-xs"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="font-semibold text-foreground">{{ m.mark_text || m.matched_mark || 'Registered Trademark' }}</span>
              <Badge :variant="m.is_live ? 'destructive' : 'outline'" class="text-[9px] py-0 px-1 font-mono">
                {{ m.status || (m.is_live ? 'LIVE' : 'DEAD') }}
              </Badge>
            </div>
            <p v-if="m.goods_services" class="text-[11px] text-muted-foreground line-clamp-2">
              {{ m.goods_services }}
            </p>
            <div class="flex items-center justify-between text-[10px] text-muted-foreground pt-1">
              <span>Serial #{{ m.serial_number || 'N/A' }}</span>
              <a
                v-if="m.source_url"
                :href="sanitizeUrl(m.source_url)"
                target="_blank"
                rel="noopener noreferrer"
                class="text-primary hover:underline flex items-center gap-1 font-medium"
              >
                <span>USPTO TSDR</span>
                <Icon name="lucide:external-link" class="size-2.5" aria-hidden="true" />
              </a>
            </div>
          </div>
        </div>

        <p class="text-[10px] text-muted-foreground italic">
          Disclaimer: Preliminary automated USPTO database search only. It does not replace full legal clearance by a qualified IP attorney.
        </p>
      </div>
    </CardContent>
  </Card>
</template>
