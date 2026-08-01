/**
 * Etsy tag normalisation and validation.
 *
 * Limits are current-Etsy rules held in one place rather than scattered
 * constants (root CLAUDE.md, "SEO, legal review, and package"). If Etsy
 * changes a limit, it changes here and in the Python mirror only.
 */

export const MAX_ETSY_TAGS = 13;
export const MAX_TAG_LENGTH = 20;

/** Letters, digits, spaces and hyphens. Etsy rejects most other punctuation. */
const ALLOWED_TAG_PATTERN = /^[\p{L}\p{N}][\p{L}\p{N} \-']*$/u;

export interface TagValidationResult {
  readonly valid: boolean;
  readonly tags: readonly string[];
  readonly errors: readonly string[];
}

/** Trim, collapse internal whitespace and lower-case for comparison. */
export function normalizeTag(raw: string): string {
  return raw.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

/**
 * Validate a tag list against Etsy's constraints.
 *
 * Returns the normalised, de-duplicated list plus every violation found —
 * callers surface all errors at once instead of failing on the first.
 */
export function validateTags(rawTags: readonly string[]): TagValidationResult {
  const errors: string[] = [];
  const accepted: string[] = [];
  const seen = new Set<string>();

  for (const raw of rawTags) {
    const tag = normalizeTag(raw);

    if (tag.length === 0) {
      errors.push("Empty tag is not allowed.");
      continue;
    }
    if (tag.length > MAX_TAG_LENGTH) {
      errors.push(`Tag "${tag}" exceeds ${MAX_TAG_LENGTH} characters.`);
      continue;
    }
    if (!ALLOWED_TAG_PATTERN.test(tag)) {
      errors.push(`Tag "${tag}" contains unsupported characters.`);
      continue;
    }
    if (seen.has(tag)) {
      errors.push(`Tag "${tag}" is duplicated after normalisation.`);
      continue;
    }

    seen.add(tag);
    accepted.push(tag);
  }

  if (accepted.length > MAX_ETSY_TAGS) {
    errors.push(
      `Too many tags: ${accepted.length} accepted, limit is ${MAX_ETSY_TAGS}.`,
    );
  }

  return { valid: errors.length === 0, tags: accepted, errors };
}
