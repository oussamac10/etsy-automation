export const MAX_ETSY_TAGS = 13;
export const MAX_TAG_LENGTH = 20;
export const MAX_TITLE_LENGTH = 140;

export function normalizeTag(tag: string): string {
  return tag
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function validateTag(tag: string, existingTags: string[]): { isValid: boolean; error?: string } {
  const norm = normalizeTag(tag);
  if (!norm) {
    return { isValid: false, error: 'Tag cannot be empty.' };
  }
  if (norm.length > MAX_TAG_LENGTH) {
    return { isValid: false, error: `Tag exceeds maximum of ${MAX_TAG_LENGTH} characters (${norm.length}/20).` };
  }
  if (existingTags.map(t => normalizeTag(t)).includes(norm)) {
    return { isValid: false, error: 'Duplicate tag already added.' };
  }
  return { isValid: true };
}

export function formatCurrencyAmount(minorUnits: number, currency = 'USD'): string {
  const symbolMap: Record<string, string> = {
    USD: '$',
    EUR: '€',
    GBP: '£',
    CAD: 'CA$',
    AUD: 'AU$',
  };
  const symbol = symbolMap[currency.toUpperCase()] || '$';
  const decimal = (minorUnits / 100).toFixed(2);
  return `${symbol}${decimal}`;
}
