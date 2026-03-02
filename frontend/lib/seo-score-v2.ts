/**
 * SEO Scoring V3 — Etsy Keywords 101 (March 2026) compliant
 *
 * Key changes from V2:
 * - Title: 30 pts (was 35) — Etsy moved to holistic ranking
 * - Tags: 30 pts (was 35) — quality > quantity, 7 tag types required
 * - Description: 20 pts (was 15) — NOW INDEXED by Etsy for search
 * - Attributes: 10 pts (was 5) — act as free tag slots
 * - Market Fit: 10 pts (unchanged)
 *
 * Works in two modes:
 * - Offline: max 73 pts (no API call)
 * - Online: max 100 pts (with autocomplete data)
 */

// --- Types ---

export type Grade = 'A+' | 'A' | 'B' | 'C' | 'D' | 'F';

export interface AutocompleteResult {
  tag: string;
  found: boolean;
  position: number | null;
  suggestions: string[];
}

export interface AutocompleteData {
  total: number;
  found: number;
  not_found: number;
  results: AutocompleteResult[];
  score: number;
}

export interface SeoIssueV2 {
  type: 'error' | 'warning' | 'good';
  area: 'title' | 'tags' | 'description' | 'metadata' | 'market';
  message: string;
}

export interface TitleScore {
  length: number;          // 6 pts
  skAtStart: number;       // 7 pts
  pipeStructure: number;   // 4 pts
  noRepeatedWords: number; // 4 pts
  noFillerWords: number;   // 4 pts
  highVolumeTerms: number; // 5 pts (online only)
  total: number;           // max 30
}

export interface TagsScore {
  count: number;             // 3 pts
  formatValid: number;       // 3 pts
  multiWord: number;         // 3 pts
  noWastedTags: number;      // 4 pts
  searchVolume: number;      // 8 pts (online only)
  categoryDiversity: number; // 5 pts
  noStuffingOrDups: number;  // 2 pts
  hasSizeTag: number;        // 1 pt (V3 new)
  hasMaterialTag: number;    // 1 pt (V3 new)
  total: number;             // max 30
}

export interface DescriptionScore {
  length: number;             // 3 pts
  skInFirst160: number;       // 5 pts
  tagsWovenIn: number;        // 4 pts
  structuredSections: number; // 2 pts
  noBannedPhrases: number;    // 3 pts (V3 new)
  hasRoomKeywords: number;    // 2 pts (V3 new)
  hasOccasionKeywords: number; // 1 pt (V3 new)
  total: number;              // max 20
}

export interface MetadataScore {
  materialsFilled: number;   // 3 pts
  colorsFilled: number;      // 3 pts
  altTexts: number;          // 2 pts
  shopSection: number;       // 2 pts
  total: number;             // max 10
}

export interface MarketFitScore {
  skInAutocomplete: number;   // 4 pts
  tagsInAutocomplete: number; // 3 pts
  priceCompetitive: number;   // 3 pts (placeholder)
  total: number;              // max 10
}

export interface SEOScoreResultV2 {
  total: number;
  max: number;        // 73 offline, 100 online
  grade: Grade;
  isOnline: boolean;
  sections: {
    title: TitleScore;
    tags: TagsScore;
    description: DescriptionScore;
    metadata: MetadataScore;
    marketFit?: MarketFitScore;
  };
  issues: SeoIssueV2[];
  suggestions: string[];
}

// --- Constants ---

const TITLE_FILLER_WORDS = [
  'beautiful', 'stunning', 'amazing', 'gorgeous', 'lovely',
  'perfect', 'unique', 'elegant', 'exquisite', 'captivating',
  'breathtaking', 'magnificent', 'wonderful', 'fantastic',
  'incredible', 'remarkable', 'exceptional', 'splendid',
];

const WASTED_STANDALONE_TAGS = [
  'poster', 'print', 'art', 'wall art', 'decor',
  'home decor', 'art print', 'wall decor', 'artwork',
  'poster print', 'art poster',
];

const GIFT_WORDS = ['gift', 'present', 'for her', 'for him', 'for mom', 'for dad', 'for wife', 'for husband', 'lover'];
const ROOM_WORDS = ['bedroom', 'living room', 'office', 'bathroom', 'kitchen', 'nursery', 'hallway', 'den', 'cabin', 'studio', 'entryway'];
const OCCASION_WORDS = ['christmas', 'birthday', 'housewarming', 'anniversary', 'valentine', 'mother', 'father', 'wedding', 'baby shower', 'easter', 'halloween', 'thanksgiving', 'new year', 'retirement'];
const AESTHETIC_WORDS = ['minimalist', 'boho', 'japandi', 'cottagecore', 'mid century', 'scandinavian', 'nordic', 'vintage', 'retro', 'modern', 'contemporary', 'dark academia', 'wabi sabi', 'art deco', 'farmhouse'];
const TECHNIQUE_WORDS = ['watercolor', 'ink', 'oil painting', 'drawing', 'photography', 'illustration', 'sketch', 'print style', 'digital', 'acrylic', 'pastel', 'charcoal', 'woodblock', 'ukiyo'];
const SIZE_WORDS = ['large', 'small', 'oversized', 'big', 'mini', 'tall', 'wide'];
const MATERIAL_WORDS = ['matte', 'paper', 'archival', 'canvas', 'glossy', 'museum', 'premium'];

const BANNED_DESC_PHRASES = [
  'transform your space', 'elevate', 'stunning', 'perfect addition',
  'captivating', 'add a touch of', 'breathtaking', 'magnificent',
  'statement piece', 'bring nature indoors',
];

type TagCategory = 'core' | 'buyer_intent' | 'style' | 'room' | 'occasion' | 'niche' | 'size' | 'material';

// --- Helpers ---

function classifyTag(tag: string, skWords: string[]): TagCategory[] {
  const lower = tag.toLowerCase();
  const categories: TagCategory[] = [];

  if (skWords.length > 0 && skWords.some(w => lower.includes(w))) categories.push('core');
  if (GIFT_WORDS.some(w => lower.includes(w)) || lower.includes('decor idea') || lower.includes('makeover')) categories.push('buyer_intent');
  if (ROOM_WORDS.some(w => lower.includes(w))) categories.push('room');
  if (OCCASION_WORDS.some(w => lower.includes(w))) categories.push('occasion');
  if (AESTHETIC_WORDS.some(w => lower.includes(w)) || TECHNIQUE_WORDS.some(w => lower.includes(w))) categories.push('style');
  if (SIZE_WORDS.some(w => lower.includes(w))) categories.push('size');
  if (MATERIAL_WORDS.some(w => lower.includes(w))) categories.push('material');
  if (categories.length === 0) categories.push('niche');

  return categories;
}

function getRootWords(tags: string[]): Map<string, number> {
  const roots = new Map<string, number>();
  for (const tag of tags) {
    const words = tag.toLowerCase().trim().split(/\s+/).filter(w => w.length > 3);
    for (const word of words) {
      roots.set(word, (roots.get(word) || 0) + 1);
    }
  }
  return roots;
}

// --- Grade ---

export function getGradeV2(score: number, max: number): Grade {
  const pct = (score / max) * 100;
  if (pct >= 92) return 'A+';
  if (pct >= 82) return 'A';
  if (pct >= 70) return 'B';
  if (pct >= 55) return 'C';
  if (pct >= 40) return 'D';
  return 'F';
}

export function gradeColorV2(grade: Grade): string {
  switch (grade) {
    case 'A+': case 'A': return 'text-green-400';
    case 'B': return 'text-yellow-400';
    case 'C': return 'text-orange-400';
    case 'D': return 'text-red-500';
    case 'F': return 'text-red-700';
  }
}

export function gradeBgV2(grade: Grade): string {
  switch (grade) {
    case 'A+': case 'A': return 'bg-green-400';
    case 'B': return 'bg-yellow-400';
    case 'C': return 'bg-orange-400';
    case 'D': return 'bg-red-500';
    case 'F': return 'bg-red-700';
  }
}

// Compatibility helpers for dashboard (score-based, not grade-based)
export function scoreColorV2(score: number, max: number = 100): string {
  return gradeColorV2(getGradeV2(score, max));
}

export function scoreGradeV2(score: number, max: number = 100): string {
  return getGradeV2(score, max);
}

// --- Main scoring function ---

export function calculateSEOScoreV2(
  title: string,
  tags: string[],
  description: string,
  materials: string[] = [],
  colors?: { primary?: string; secondary?: string },
  altTexts?: string[],
  autocompleteData?: AutocompleteData,
  shopSectionId?: number | null,
): SEOScoreResultV2 {
  const issues: SeoIssueV2[] = [];
  const suggestions: string[] = [];
  const sk = tags[0] || '';
  const skWords = sk.toLowerCase().split(/\s+/).filter(w => w.length > 2);
  const isOnline = !!autocompleteData;

  // ============ TITLE (max 30 pts) ============
  const titleResult: TitleScore = { length: 0, skAtStart: 0, pipeStructure: 0, noRepeatedWords: 0, noFillerWords: 0, highVolumeTerms: 0, total: 0 };

  if (!title) {
    issues.push({ type: 'error', area: 'title', message: 'Title is empty' });
  } else {
    const len = title.length;

    // Length (6 pts) — ideal 40-70
    if (len >= 40 && len <= 70) {
      titleResult.length = 6;
    } else if ((len >= 30 && len < 40) || (len > 70 && len <= 80)) {
      titleResult.length = 4;
      issues.push({ type: 'warning', area: 'title', message: `Title ${len} chars — ideal is 40-70` });
    } else if (len < 30 || (len > 80 && len <= 140)) {
      titleResult.length = 2;
      issues.push({ type: 'warning', area: 'title', message: `Title ${len < 30 ? 'too short' : 'too long'} (${len} chars)` });
    } else {
      issues.push({ type: 'error', area: 'title', message: `Title exceeds 140 chars (${len})` });
    }

    // SK at start (7 pts)
    if (sk) {
      const titleLower = title.toLowerCase();
      const skLower = sk.toLowerCase();
      if (titleLower.startsWith(skLower) || titleLower.startsWith(skLower.split(' ')[0])) {
        titleResult.skAtStart = 7;
      } else if (titleLower.includes(skLower)) {
        titleResult.skAtStart = 3;
        issues.push({ type: 'warning', area: 'title', message: 'SK in title but not at start — move it to front' });
      } else {
        issues.push({ type: 'error', area: 'title', message: 'Superstar Keyword missing from title' });
      }
    }

    // Pipe/colon structure (4 pts)
    const hasPipes = title.includes('|');
    const hasColon = title.includes(':');
    const sections = title.split(/[|:]/).map(s => s.trim()).filter(Boolean);
    if (sections.length >= 2 && sections.length <= 3) {
      titleResult.pipeStructure = 4;
    } else {
      titleResult.pipeStructure = 2;
      if (sections.length === 1) issues.push({ type: 'warning', area: 'title', message: 'No separators — add | or : to structure title' });
      else issues.push({ type: 'warning', area: 'title', message: `${sections.length} sections — max 3` });
    }

    // No repeated words (4 pts)
    const titleWords = title.toLowerCase().replace(/[|:,]/g, ' ').split(/\s+/).filter(w => w.length > 3);
    const wordCounts: Record<string, number> = {};
    titleWords.forEach(w => { wordCounts[w] = (wordCounts[w] || 0) + 1; });
    const repeatedWords = Object.entries(wordCounts).filter(([, c]) => c > 1).map(([w]) => w);
    if (repeatedWords.length === 0) {
      titleResult.noRepeatedWords = 4;
    } else if (repeatedWords.length === 1) {
      titleResult.noRepeatedWords = 2;
      issues.push({ type: 'warning', area: 'title', message: `Repeated word in title: "${repeatedWords[0]}"` });
    } else {
      issues.push({ type: 'error', area: 'title', message: `Repeated words: ${repeatedWords.join(', ')}` });
    }

    // No filler words (4 pts)
    const fillerFound = TITLE_FILLER_WORDS.filter(f => title.toLowerCase().includes(f));
    if (fillerFound.length === 0) {
      titleResult.noFillerWords = 4;
    } else if (fillerFound.length === 1) {
      titleResult.noFillerWords = 2;
      issues.push({ type: 'warning', area: 'title', message: `Filler word "${fillerFound[0]}" — be specific instead` });
    } else {
      issues.push({ type: 'error', area: 'title', message: `Filler words: ${fillerFound.join(', ')} — nobody searches these` });
    }

    // High-volume terms (5 pts) — online only
    if (autocompleteData) {
      const skResult = autocompleteData.results.find(r => r.tag.toLowerCase() === sk.toLowerCase());
      if (skResult?.found) {
        titleResult.highVolumeTerms = 5;
      } else if (autocompleteData.results.some(r => r.found)) {
        titleResult.highVolumeTerms = 2;
        issues.push({ type: 'warning', area: 'title', message: 'SK not in autocomplete — consider a higher-volume keyword' });
      } else {
        issues.push({ type: 'error', area: 'title', message: 'Title keywords not found in search autocomplete' });
        suggestions.push('Research what buyers actually search for in this niche');
      }
    }
  }

  titleResult.total = Math.min(30, titleResult.length + titleResult.skAtStart + titleResult.pipeStructure + titleResult.noRepeatedWords + titleResult.noFillerWords + titleResult.highVolumeTerms);

  // ============ TAGS (max 30 pts) ============
  const tagsResult: TagsScore = { count: 0, formatValid: 0, multiWord: 0, noWastedTags: 0, searchVolume: 0, categoryDiversity: 0, noStuffingOrDups: 0, hasSizeTag: 0, hasMaterialTag: 0, total: 0 };

  if (tags.length === 0) {
    issues.push({ type: 'error', area: 'tags', message: 'No tags' });
  } else {
    // Count (3 pts)
    if (tags.length === 13) {
      tagsResult.count = 3;
    } else {
      tagsResult.count = Math.round((tags.length / 13) * 3);
      issues.push({ type: 'error', area: 'tags', message: `Only ${tags.length}/13 tags` });
    }

    // Format valid (3 pts)
    const overLength = tags.filter(t => t.length > 20);
    if (overLength.length > 0) {
      tagsResult.formatValid = Math.max(0, 3 - overLength.length);
      issues.push({ type: 'error', area: 'tags', message: `${overLength.length} tag(s) over 20 chars` });
    } else {
      tagsResult.formatValid = 3;
    }

    // Multi-word (3 pts)
    const singleWordTags = tags.filter(t => t.trim().split(/\s+/).length === 1);
    if (singleWordTags.length === 0) {
      tagsResult.multiWord = 3;
    } else {
      tagsResult.multiWord = Math.max(0, 3 - singleWordTags.length);
      issues.push({ type: 'warning', area: 'tags', message: `Single-word tags waste slots: ${singleWordTags.join(', ')}` });
      suggestions.push('Replace single-word tags with 2-3 word phrases buyers search');
    }

    // No wasted tags (4 pts)
    const wastedTags = tags.filter(t => WASTED_STANDALONE_TAGS.includes(t.toLowerCase().trim()));
    if (wastedTags.length === 0) {
      tagsResult.noWastedTags = 4;
    } else {
      tagsResult.noWastedTags = Math.max(0, 4 - wastedTags.length * 2);
      issues.push({ type: 'error', area: 'tags', message: `Wasted tags (already in Etsy category): ${wastedTags.join(', ')}` });
      suggestions.push(`Replace "${wastedTags[0]}" with a specific phrase like "japanese wall art"`);
    }

    // Search volume (8 pts) — online only
    if (autocompleteData) {
      const ratio = autocompleteData.found / Math.max(autocompleteData.total, 1);
      tagsResult.searchVolume = Math.round(ratio * 8);

      const notFound = autocompleteData.results.filter(r => !r.found);
      if (notFound.length > 0) {
        issues.push({ type: 'error', area: 'tags', message: `${notFound.length} tags not found in search: ${notFound.map(r => `"${r.tag}"`).join(', ')}` });
        for (const nf of notFound.slice(0, 3)) {
          suggestions.push(`Replace "${nf.tag}" with a term buyers actually search for`);
        }
      }
      if (ratio >= 0.8) {
        issues.push({ type: 'good', area: 'tags', message: `${autocompleteData.found}/${autocompleteData.total} tags validated in search` });
      }
    }

    // Category diversity (5 pts) — now checks 7+ categories
    const covered = new Set<TagCategory>();
    for (const tag of tags) {
      classifyTag(tag.toLowerCase(), skWords).forEach(c => covered.add(c));
    }
    const catCount = covered.size;
    if (catCount >= 7) {
      tagsResult.categoryDiversity = 5;
    } else if (catCount >= 6) {
      tagsResult.categoryDiversity = 4;
    } else if (catCount >= 5) {
      tagsResult.categoryDiversity = 3;
      issues.push({ type: 'warning', area: 'tags', message: `${catCount}/7 tag types covered — add more variety` });
    } else {
      tagsResult.categoryDiversity = Math.max(1, catCount - 1);
      issues.push({ type: 'error', area: 'tags', message: `Only ${catCount}/7 tag types covered` });

      const missing: string[] = [];
      if (!covered.has('room')) missing.push('room-specific (e.g., "bedroom wall art")');
      if (!covered.has('occasion')) missing.push('occasion (e.g., "housewarming gift")');
      if (!covered.has('buyer_intent')) missing.push('buyer intent (e.g., "gift for nature lover")');
      if (!covered.has('style')) missing.push('style (e.g., "japandi decor")');
      if (!covered.has('size')) missing.push('size (e.g., "large wall poster")');
      if (!covered.has('material')) missing.push('material (e.g., "matte paper print")');
      if (missing.length > 0) suggestions.push(`Add tags for: ${missing.join(', ')}`);
    }

    // No stuffing or dups (2 pts)
    const rootWordCounts = getRootWords(tags);
    const stuffedWords = Array.from(rootWordCounts.entries()).filter(([, count]) => count > 3).map(([word]) => word);
    const lowerTags = tags.map(t => t.toLowerCase().trim());
    const dupes = lowerTags.filter((t, i) => lowerTags.indexOf(t) !== i);

    if (stuffedWords.length === 0 && dupes.length === 0) {
      tagsResult.noStuffingOrDups = 2;
    } else {
      if (stuffedWords.length > 0) issues.push({ type: 'warning', area: 'tags', message: `Root word "${stuffedWords[0]}" in ${rootWordCounts.get(stuffedWords[0])} tags — max 3` });
      if (dupes.length > 0) issues.push({ type: 'error', area: 'tags', message: `Duplicate tags: ${Array.from(new Set(dupes)).join(', ')}` });
    }

    // Has size tag (1 pt) — V3 new
    const hasSizeTag = tags.some(t => SIZE_WORDS.some(sw => t.toLowerCase().includes(sw)));
    if (hasSizeTag) {
      tagsResult.hasSizeTag = 1;
    } else {
      issues.push({ type: 'warning', area: 'tags', message: 'No size tag — add "large wall poster" or "small art print"' });
    }

    // Has material tag (1 pt) — V3 new
    const hasMaterialTag = tags.some(t => MATERIAL_WORDS.some(mw => t.toLowerCase().includes(mw)));
    if (hasMaterialTag) {
      tagsResult.hasMaterialTag = 1;
    } else {
      issues.push({ type: 'warning', area: 'tags', message: 'No material tag — add "matte paper print" or "archival ink art"' });
    }
  }

  tagsResult.total = Math.min(30, tagsResult.count + tagsResult.formatValid + tagsResult.multiWord + tagsResult.noWastedTags + tagsResult.searchVolume + tagsResult.categoryDiversity + tagsResult.noStuffingOrDups + tagsResult.hasSizeTag + tagsResult.hasMaterialTag);

  // ============ DESCRIPTION (max 20 pts) ============
  const descResult: DescriptionScore = { length: 0, skInFirst160: 0, tagsWovenIn: 0, structuredSections: 0, noBannedPhrases: 0, hasRoomKeywords: 0, hasOccasionKeywords: 0, total: 0 };

  if (!description) {
    issues.push({ type: 'error', area: 'description', message: 'Description is empty' });
  } else {
    const descLower = description.toLowerCase();

    // Length (3 pts)
    if (description.length >= 500) {
      descResult.length = 3;
    } else if (description.length >= 300) {
      descResult.length = 2;
      issues.push({ type: 'warning', area: 'description', message: `Short (${description.length} chars, aim for 500+)` });
    } else {
      issues.push({ type: 'error', area: 'description', message: `Only ${description.length} chars — too short` });
    }

    // SK in first 160 chars (5 pts) — Google + Etsy snippet
    const first160 = description.slice(0, 160).toLowerCase();
    if (sk && first160.includes(sk.toLowerCase())) {
      descResult.skInFirst160 = 5;
    } else {
      issues.push({ type: 'error', area: 'description', message: 'SK missing from first 160 chars — critical for Google + Etsy search' });
    }

    // Tags woven in (4 pts) — more important now that descriptions are indexed
    const tagKeywordsFound = tags.filter(t => t && descLower.includes(t.toLowerCase())).length;
    if (tagKeywordsFound >= 10) {
      descResult.tagsWovenIn = 4;
    } else if (tagKeywordsFound >= 8) {
      descResult.tagsWovenIn = 3;
    } else if (tagKeywordsFound >= 5) {
      descResult.tagsWovenIn = 2;
      issues.push({ type: 'warning', area: 'description', message: `Only ${tagKeywordsFound}/13 tags in description — aim for 8-10` });
    } else {
      descResult.tagsWovenIn = 1;
      issues.push({ type: 'warning', area: 'description', message: `Only ${tagKeywordsFound}/13 tags in description — Etsy now indexes descriptions` });
    }

    // Structured sections (2 pts)
    const hasPerfectFor = /PERFECT FOR/i.test(description);
    const hasPrintDetails = /PRINT DETAILS/i.test(description);
    if (hasPerfectFor && hasPrintDetails) {
      descResult.structuredSections = 2;
    } else if (hasPerfectFor || hasPrintDetails) {
      descResult.structuredSections = 1;
    } else {
      issues.push({ type: 'warning', area: 'description', message: 'Missing structured sections (PERFECT FOR, PRINT DETAILS)' });
    }

    // No banned phrases (3 pts) — V3 new
    const foundBanned = BANNED_DESC_PHRASES.filter(bp => descLower.includes(bp));
    if (foundBanned.length === 0) {
      descResult.noBannedPhrases = 3;
    } else {
      descResult.noBannedPhrases = Math.max(0, 3 - foundBanned.length);
      issues.push({ type: 'error', area: 'description', message: `Banned phrases: ${foundBanned.map(b => `"${b}"`).join(', ')}` });
    }

    // Has room keywords (2 pts) — V3 new
    const roomsFound = ROOM_WORDS.filter(rw => descLower.includes(rw));
    if (roomsFound.length >= 2) {
      descResult.hasRoomKeywords = 2;
    } else if (roomsFound.length === 1) {
      descResult.hasRoomKeywords = 1;
      issues.push({ type: 'warning', area: 'description', message: 'Only 1 room keyword — add more (bedroom, living room, office)' });
    } else {
      issues.push({ type: 'warning', area: 'description', message: 'No room keywords in description — Etsy indexes these for search' });
    }

    // Has occasion keywords (1 pt) — V3 new
    const occasionsFound = OCCASION_WORDS.filter(ow => descLower.includes(ow));
    if (occasionsFound.length >= 1) {
      descResult.hasOccasionKeywords = 1;
    } else {
      issues.push({ type: 'warning', area: 'description', message: 'No occasion keywords — add "housewarming", "birthday" etc.' });
    }
  }

  descResult.total = Math.min(20, descResult.length + descResult.skInFirst160 + descResult.tagsWovenIn + descResult.structuredSections + descResult.noBannedPhrases + descResult.hasRoomKeywords + descResult.hasOccasionKeywords);

  // ============ ATTRIBUTES (max 10 pts) — was METADATA (5 pts) ============
  const metaResult: MetadataScore = { materialsFilled: 0, colorsFilled: 0, altTexts: 0, shopSection: 0, total: 0 };

  // Materials specificity (3 pts)
  if (materials.length > 0) {
    const hasSpecific = materials.some(m => m.length > 10);
    if (hasSpecific) {
      metaResult.materialsFilled = 3;
    } else {
      metaResult.materialsFilled = 1;
      issues.push({ type: 'warning', area: 'metadata', message: 'Materials too generic — use specific terms like "Museum quality 250gsm matte paper"' });
    }
  } else {
    issues.push({ type: 'warning', area: 'metadata', message: 'No materials set — free keyword slots wasted' });
  }

  // Colors (3 pts)
  const hasPrimary = colors?.primary && colors.primary.length > 0;
  const hasSecondary = colors?.secondary && colors.secondary.length > 0;
  if (hasPrimary && hasSecondary) {
    metaResult.colorsFilled = 3;
  } else if (hasPrimary) {
    metaResult.colorsFilled = 2;
    issues.push({ type: 'warning', area: 'metadata', message: 'No secondary color — set for better filter visibility' });
  } else {
    issues.push({ type: 'warning', area: 'metadata', message: 'No colors set — buyers use color filters' });
  }

  // Alt texts (2 pts)
  const altCount = altTexts?.filter(a => a && a.trim().length > 0).length || 0;
  if (altCount >= 5) {
    metaResult.altTexts = 2;
  } else if (altCount >= 3) {
    metaResult.altTexts = 1;
  }

  // Shop section (2 pts)
  if (shopSectionId) {
    metaResult.shopSection = 2;
  } else {
    issues.push({ type: 'warning', area: 'metadata', message: 'No shop section assigned' });
  }

  metaResult.total = metaResult.materialsFilled + metaResult.colorsFilled + metaResult.altTexts + metaResult.shopSection;

  // ============ MARKET FIT (max 10 pts) — online only ============
  let marketFit: MarketFitScore | undefined;
  if (autocompleteData) {
    marketFit = { skInAutocomplete: 0, tagsInAutocomplete: 0, priceCompetitive: 3, total: 0 };

    // SK in autocomplete (4 pts)
    const skResult = autocompleteData.results.find(r => r.tag.toLowerCase() === sk.toLowerCase());
    if (skResult?.found) {
      marketFit.skInAutocomplete = 4;
      issues.push({ type: 'good', area: 'market', message: `Superstar Keyword "${sk}" found in search` });
    } else {
      issues.push({ type: 'error', area: 'market', message: `SK "${sk}" NOT found in search — buyers don't search this term` });
      suggestions.push(`Change Superstar Keyword to a term that appears in autocomplete`);
    }

    // Tags in autocomplete (3 pts)
    if (autocompleteData.found >= 5) {
      marketFit.tagsInAutocomplete = 3;
    } else if (autocompleteData.found >= 3) {
      marketFit.tagsInAutocomplete = 2;
    } else {
      issues.push({ type: 'error', area: 'market', message: `Only ${autocompleteData.found} tags found in search — most tags are not real search terms` });
    }

    // Price competitive (3 pts) — placeholder, always awarded
    marketFit.priceCompetitive = 3;

    marketFit.total = marketFit.skInAutocomplete + marketFit.tagsInAutocomplete + marketFit.priceCompetitive;
  }

  // ============ TOTAL ============
  const max = isOnline ? 100 : 73;
  const total = titleResult.total + tagsResult.total + descResult.total + metaResult.total + (marketFit?.total || 0);
  const grade = getGradeV2(total, max);

  return {
    total,
    max,
    grade,
    isOnline,
    sections: {
      title: titleResult,
      tags: tagsResult,
      description: descResult,
      metadata: metaResult,
      marketFit,
    },
    issues,
    suggestions,
  };
}
