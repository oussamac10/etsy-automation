const SKU_STOPWORDS = new Set([
  'a', 'an', 'the', 'and', 'or', 'for', 'with', 'in', 'on', 'at', 'by',
  'png', 'digital', 'download', 'design', 'clipart', 'sublimation',
  'instant', 'file', 'files', 'art', 'graphic', 'graphics', 'print', 'dtg',
]);

export function generateFrontendSku(title?: string | null, workflowId?: string | null): string {
  const words = (title || 'digital art')
    .replace(/[^a-zA-Z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length >= 3 && !SKU_STOPWORDS.has(w.toLowerCase()))
    .map((w) => w.toUpperCase().slice(0, 6));

  const keywordPart = words.slice(0, 2).join('-') || 'ART';
  const cleanId = (workflowId || '').replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
  const hashPart = cleanId.slice(0, 4) || Math.random().toString(36).substring(2, 6).toUpperCase();

  return `NCP-${keywordPart}-${hashPart}`;
}
