import { describe, expect, it } from 'vitest';
import {
  formatWorkflowStage,
  formatApprovalAction,
  formatProviderName,
  sanitizeUserErrorMessage,
} from '../utils/formatters';
import { sanitizeUrl } from '../utils/sanitize';
import {
  formatCurrencyAmount,
  normalizeTag,
  validateTag,
  sanitizeEtsyTitle,
  validateListingTitle,
  countSequentialCapitalWords,
} from '../utils/tags';

describe('Workflow Formatters & Sanitization', () => {
  describe('Workflow Stage Formatter', () => {
    it('maps raw statuses to clean product names', () => {
      expect(formatWorkflowStage('READY_FOR_ETSY_DRAFT')).toBe('Ready for Etsy');
      expect(formatWorkflowStage('IDEA_REVIEW')).toBe('Review Concepts');
      expect(formatWorkflowStage('ART_REVIEW')).toBe('Review Artwork');
      expect(formatWorkflowStage('ARTWORK_APPROVED')).toBe('Artwork Approved');
      expect(formatWorkflowStage('PRODUCTION')).toBe('Production & Mockups');
      expect(formatWorkflowStage('ETSY_DRAFT_CREATED')).toBe('Draft Created');
      expect(formatWorkflowStage('PUBLISHED')).toBe('Published');
      expect(formatWorkflowStage('CANCELLED')).toBe('Stopped');
    });

    it('handles empty or unrecognized states gracefully', () => {
      expect(formatWorkflowStage('')).toBe('');
      expect(formatWorkflowStage('CUSTOM_STATE_NAME')).toBe('Custom State Name');
    });
  });

  describe('Approval Actions Formatter', () => {
    it('maps approval gates to action verbs', () => {
      expect(formatApprovalAction('IDEA_APPROVAL')).toBe('Approve Concept');
      expect(formatApprovalAction('ARTWORK_APPROVAL')).toBe('Approve Artwork');
      expect(formatApprovalAction('LISTING_APPROVAL')).toBe('Approve Listing');
      expect(formatApprovalAction('')).toBe('');
      expect(formatApprovalAction('UNKNOWN_GATE')).toBe('Approve');
    });
  });

  describe('Provider Name Formatter', () => {
    it('maps providers to clean display names', () => {
      expect(formatProviderName('recraft')).toBe('Recraft');
      expect(formatProviderName('gemini')).toBe('Google Gemini');
      expect(formatProviderName('openai')).toBe('OpenAI');
      expect(formatProviderName('tavily')).toBe('Tavily');
      expect(formatProviderName('etsy')).toBe('Etsy');
      expect(formatProviderName('printful')).toBe('Printful');
      expect(formatProviderName('')).toBe('');
    });
  });

  describe('User Error Sanitizer', () => {
    it('sanitizes technical gate error messages for end users', () => {
      expect(sanitizeUserErrorMessage('requires gate IDEA_APPROVAL to be approved')).toBe(
        'Please approve the concept before proceeding.'
      );
      expect(sanitizeUserErrorMessage('requires gate ARTWORK_APPROVAL to be approved')).toBe(
        'Please approve an artwork design before proceeding.'
      );
      expect(sanitizeUserErrorMessage('requires gate LISTING_APPROVAL to be approved')).toBe(
        'Please complete the listing review before proceeding.'
      );
      expect(sanitizeUserErrorMessage('GateNotSatisfiedError: cannot be decided while in RESEARCHING')).toBe(
        'This milestone is not ready for review yet.'
      );
    });

    it('sanitizes infrastructure and database errors', () => {
      expect(sanitizeUserErrorMessage('SQLAlchemy OperationalError: connection refused')).toBe(
        'An unexpected error occurred. Please try again.'
      );
      expect(sanitizeUserErrorMessage('MinIO bucket not found')).toBe(
        'An unexpected error occurred. Please try again.'
      );
    });

    it('extracts detail from structured error objects', () => {
      expect(sanitizeUserErrorMessage({ data: { detail: 'Custom error message' } })).toBe(
        'Custom error message'
      );
    });
  });
});

describe('URL Sanitization (XSS Prevention)', () => {
  it('allows safe http, https, and blob URLs', () => {
    expect(sanitizeUrl('https://example.com/asset.png')).toBe('https://example.com/asset.png');
    expect(sanitizeUrl('http://localhost:8000/download.zip')).toBe('http://localhost:8000/download.zip');
    expect(sanitizeUrl('blob:http://localhost/1234')).toBe('blob:http://localhost/1234');
    expect(sanitizeUrl('/relative/path/image.png')).toBe('/relative/path/image.png');
  });

  it('rejects and neutralizes javascript:, data:, and vbscript: URIs', () => {
    expect(sanitizeUrl('javascript:alert(1)')).toBe('#');
    expect(sanitizeUrl('data:text/html,<script>alert(1)</script>')).toBe('#');
    expect(sanitizeUrl('vbscript:msgbox(1)')).toBe('#');
    expect(sanitizeUrl(null)).toBe('#');
    expect(sanitizeUrl(undefined)).toBe('#');
    expect(sanitizeUrl('')).toBe('#');
  });
});

describe('Etsy Listing Tags & Title Utilities', () => {
  it('normalizes tags to lowercase alphanumeric and dashes', () => {
    expect(normalizeTag('  Vintage Mushroom!!  ')).toBe('vintage mushroom');
    expect(normalizeTag('PNG--Graphic')).toBe('png--graphic');
  });

  it('validates tag constraints (max length, duplicates, empty)', () => {
    expect(validateTag('', []).isValid).toBe(false);
    expect(validateTag('a'.repeat(21), []).isValid).toBe(false);
    expect(validateTag('cute cat', ['cute cat']).isValid).toBe(false);
    expect(validateTag('cute cat', ['dog']).isValid).toBe(true);
  });

  it('counts sequential capital words according to Etsy rules', () => {
    expect(countSequentialCapitalWords('Vintage PNG Sublimation Graphic')).toBe(1);
    expect(countSequentialCapitalWords('PNG SVG DXF MRI File')).toBe(4);
  });

  it('sanitizes Etsy titles with >3 sequential capital words', () => {
    const raw = 'PNG SVG DXF EPS Clipart';
    const sanitized = sanitizeEtsyTitle(raw);
    expect(countSequentialCapitalWords(sanitized)).toBeLessThanOrEqual(3);
  });

  it('validates listing titles', () => {
    expect(validateListingTitle('').isValid).toBe(false);
    expect(validateListingTitle('A'.repeat(141)).isValid).toBe(false);
    expect(validateListingTitle('PNG SVG DXF EPS Clipart').isValid).toBe(false);
    expect(validateListingTitle('Vintage Mushroom PNG Clipart').isValid).toBe(true);
  });

  it('formats currency amounts in minor units to symbols and decimals', () => {
    expect(formatCurrencyAmount(499, 'USD')).toBe('$4.99');
    expect(formatCurrencyAmount(1250, 'EUR')).toBe('€12.50');
    expect(formatCurrencyAmount(1000, 'GBP')).toBe('£10.00');
    expect(formatCurrencyAmount(0, 'USD')).toBe('$0.00');
  });
});
