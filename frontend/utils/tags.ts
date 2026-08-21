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

export function countSequentialCapitalWords(rawTitle: string): number {
  const matches = rawTitle.match(/\b[A-Z]{2,}/g);
  return matches ? matches.length : 0;
}

export function sanitizeEtsyTitle(rawTitle: string): string {
  const title = rawTitle.trim().replace(/\s+/g, ' ');
  if (!title) return '';

  const tokens = title.split(/(\s+)/);
  let capsCount = 0;
  const newTokens: string[] = [];

  for (const token of tokens) {
    const m = token.match(/^([^\w]*)([A-Z]{2,})(\w*)([^\w]*)$/);
    if (m) {
      const [, prefix, capsPart, rest, suffix] = m;
      capsCount += 1;
      if (capsCount > 3) {
        const fullWord = capsPart + rest;
        const fixed = fullWord.charAt(0).toUpperCase() + fullWord.slice(1).toLowerCase();
        newTokens.push(`${prefix}${fixed}${suffix}`);
      } else {
        newTokens.push(token);
      }
    } else {
      newTokens.push(token);
    }
  }

  let sanitized = newTokens.join('');
  if (sanitized.length > MAX_TITLE_LENGTH) {
    const lastSpace = sanitized.slice(0, MAX_TITLE_LENGTH).lastIndexOf(' ');
    sanitized = lastSpace > 0 ? sanitized.slice(0, lastSpace) : sanitized.slice(0, MAX_TITLE_LENGTH);
  }
  return sanitized;
}

export function validateListingTitle(rawTitle: string): { isValid: boolean; error?: string } {
  const title = rawTitle.trim();
  if (!title) {
    return { isValid: false, error: 'Listing title cannot be empty.' };
  }
  if (title.length > MAX_TITLE_LENGTH) {
    return { isValid: false, error: `Listing title exceeds ${MAX_TITLE_LENGTH} characters (${title.length}/${MAX_TITLE_LENGTH}).` };
  }
  if (countSequentialCapitalWords(title) > 3) {
    return {
      isValid: false,
      error: 'Etsy limits titles to at most 3 words starting with two sequential capital letters (e.g. PNG, SVG, MRI).',
    };
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

