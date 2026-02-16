// SEO scoring utilities — v2 (Feb 2026) with buyer-intent tag diversity

export interface SeoIssue {
  type: 'error' | 'warning' | 'good';
  area: 'title' | 'tags' | 'description' | 'materials';
  message: string;
}

export interface SeoAnalysis {
  score: number;
  titleScore: number;
  tagsScore: number;
  descScore: number;
  issues: SeoIssue[];
}

// --- Tag category classifier ---

const GIFT_WORDS = ['gift', 'present', 'for her', 'for him', 'for mom', 'for dad', 'for wife', 'for husband', 'lover'];
const ROOM_WORDS = ['bedroom', 'living room', 'office', 'bathroom', 'kitchen', 'nursery', 'hallway', 'den', 'cabin', 'studio', 'entryway'];
const OCCASION_WORDS = ['christmas', 'birthday', 'housewarming', 'anniversary', 'valentine', 'mother', 'father', 'wedding', 'baby shower', 'easter', 'halloween', 'thanksgiving', 'new year', 'retirement'];
const AESTHETIC_WORDS = ['minimalist', 'boho', 'japandi', 'cottagecore', 'mid century', 'scandinavian', 'nordic', 'vintage', 'retro', 'modern', 'contemporary', 'dark academia', 'wabi sabi', 'art deco', 'farmhouse'];
const TECHNIQUE_WORDS = ['watercolor', 'ink', 'oil painting', 'drawing', 'photography', 'illustration', 'sketch', 'print style', 'digital', 'acrylic', 'pastel', 'charcoal', 'woodblock', 'ukiyo'];
const BROAD_CATEGORY_WORDS = ['wall art', 'poster', 'print', 'decor', 'art print'];

type TagCategory = 'core' | 'buyer_intent' | 'style' | 'room' | 'occasion' | 'niche';

function classifyTag(tag: string, skWords: string[]): TagCategory[] {
  const lower = tag.toLowerCase();
  const categories: TagCategory[] = [];

  // Check if it's the SK or a close variation
  const isSkMatch = skWords.length > 0 && skWords.some(w => lower.includes(w));
  if (isSkMatch) categories.push('core');

  // Gift / buyer intent
  if (GIFT_WORDS.some(w => lower.includes(w))) categories.push('buyer_intent');
  if (lower.includes('decor idea') || lower.includes('makeover') || lower.includes('lover')) categories.push('buyer_intent');

  // Room / space
  if (ROOM_WORDS.some(w => lower.includes(w))) categories.push('room');

  // Occasion
  if (OCCASION_WORDS.some(w => lower.includes(w))) categories.push('occasion');

  // Style / aesthetic / technique
  if (AESTHETIC_WORDS.some(w => lower.includes(w))) categories.push('style');
  if (TECHNIQUE_WORDS.some(w => lower.includes(w))) categories.push('style');

  // If no category matched, it's likely a niche/long-tail tag
  if (categories.length === 0) categories.push('niche');

  return categories;
}

function getTagDiversity(tags: string[], sk: string): { covered: Set<TagCategory>; wastedTags: string[] } {
  const skWords = sk.toLowerCase().split(/\s+/).filter(w => w.length > 2);
  const covered = new Set<TagCategory>();
  const wastedTags: string[] = [];

  for (const tag of tags) {
    const lower = tag.toLowerCase().trim();

    // Check for wasted broad category tags
    if (BROAD_CATEGORY_WORDS.some(w => lower === w)) {
      wastedTags.push(tag);
    }

    const cats = classifyTag(lower, skWords);
    cats.forEach(c => covered.add(c));
  }

  return { covered, wastedTags };
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

// --- Main scoring function ---

export function analyzeSeo(title: string, tags: string[], description: string, materials: string[] = [], colors?: { primary?: string; secondary?: string }, altTexts?: string[]): SeoAnalysis {
  const issues: SeoIssue[] = [];
  let titleScore = 0;
  let tagsScore = 0;
  let descScore = 0;
  let metaScore = 0;

  const sk = tags[0] || '';

  // === TITLE (max 30 pts) ===
  if (!title) {
    issues.push({ type: 'error', area: 'title', message: 'Title is empty' });
  } else {
    // Length scoring (10 pts)
    const len = title.length;
    if (len >= 50 && len <= 80) {
      titleScore += 10;
      issues.push({ type: 'good', area: 'title', message: `Optimal length (${len} chars)` });
    } else if ((len >= 40 && len < 50) || (len > 80 && len <= 100)) {
      titleScore += 7;
      issues.push({ type: 'warning', area: 'title', message: `Acceptable length (${len} chars, ideal 50-80)` });
    } else if (len < 40 || (len > 100 && len <= 140)) {
      titleScore += 4;
      issues.push({ type: 'warning', area: 'title', message: `Title ${len < 40 ? 'too short' : 'too long'} (${len} chars, ideal 50-80)` });
    } else {
      issues.push({ type: 'error', area: 'title', message: `Title exceeds 140 chars (${len})` });
    }

    // SK at start (8 pts)
    if (sk) {
      const titleLower = title.toLowerCase();
      const skLower = sk.toLowerCase();
      if (titleLower.startsWith(skLower) || titleLower.startsWith(skLower.split(' ')[0])) {
        titleScore += 8;
        issues.push({ type: 'good', area: 'title', message: 'SK keyword at start of title' });
      } else if (titleLower.includes(skLower)) {
        titleScore += 4;
        issues.push({ type: 'warning', area: 'title', message: 'SK in title but not at start' });
      } else {
        issues.push({ type: 'error', area: 'title', message: 'SK missing from title' });
      }
    }

    // Pipe structure (5 pts)
    const sections = title.split('|').map(s => s.trim()).filter(Boolean);
    if (sections.length >= 2 && sections.length <= 3) {
      titleScore += 5;
      issues.push({ type: 'good', area: 'title', message: `${sections.length} pipe sections (ideal)` });
    } else if (sections.length === 1) {
      titleScore += 2;
      issues.push({ type: 'warning', area: 'title', message: 'No pipe separators — add structure' });
    } else if (sections.length > 3) {
      titleScore += 2;
      issues.push({ type: 'warning', area: 'title', message: `${sections.length} pipe sections — too many (max 3)` });
    }

    // No repeated words (7 pts)
    const titleWords = title.toLowerCase().replace(/[|,]/g, ' ').split(/\s+/).filter(w => w.length > 3);
    const wordCounts: Record<string, number> = {};
    titleWords.forEach(w => { wordCounts[w] = (wordCounts[w] || 0) + 1; });
    const repeatedWords = Object.entries(wordCounts).filter(([, c]) => c > 1).map(([w]) => w);
    if (repeatedWords.length === 0) {
      titleScore += 7;
    } else if (repeatedWords.length === 1) {
      titleScore += 4;
      issues.push({ type: 'warning', area: 'title', message: `Repeated word: "${repeatedWords[0]}"` });
    } else {
      issues.push({ type: 'warning', area: 'title', message: `Repeated words: ${repeatedWords.join(', ')}` });
    }
  }

  // === TAGS (max 30 pts) ===
  if (tags.length === 0) {
    issues.push({ type: 'error', area: 'tags', message: 'No tags' });
  } else {
    // Count (6 pts)
    if (tags.length === 13) {
      tagsScore += 6;
      issues.push({ type: 'good', area: 'tags', message: 'All 13 tags used' });
    } else {
      issues.push({ type: 'error', area: 'tags', message: `Only ${tags.length}/13 tags` });
      tagsScore += Math.round((tags.length / 13) * 6);
    }

    // Format valid (6 pts)
    const overLength = tags.filter(t => t.length > 20);
    if (overLength.length > 0) {
      issues.push({ type: 'error', area: 'tags', message: `${overLength.length} tag(s) over 20 chars` });
      tagsScore += Math.max(0, 6 - overLength.length * 2);
    } else {
      tagsScore += 6;
      issues.push({ type: 'good', area: 'tags', message: 'All tags valid length (≤20 chars)' });
    }

    // Category diversity (10 pts) — the key new check
    const { covered, wastedTags } = getTagDiversity(tags, sk);
    const catCount = covered.size;
    if (catCount >= 6) {
      tagsScore += 10;
      issues.push({ type: 'good', area: 'tags', message: `Excellent diversity — ${catCount}/6 intent categories covered` });
    } else if (catCount >= 5) {
      tagsScore += 8;
      issues.push({ type: 'good', area: 'tags', message: `Good diversity — ${catCount}/6 intent categories` });
    } else if (catCount >= 4) {
      tagsScore += 6;
      issues.push({ type: 'warning', area: 'tags', message: `Moderate diversity — ${catCount}/6 categories (add more variety)` });
    } else if (catCount >= 3) {
      tagsScore += 4;
      issues.push({ type: 'warning', area: 'tags', message: `Low diversity — only ${catCount}/6 categories covered` });
    } else {
      tagsScore += 2;
      issues.push({ type: 'error', area: 'tags', message: `Poor diversity — only ${catCount}/6 categories. Tags all serve the same intent` });
    }

    if (wastedTags.length > 0) {
      issues.push({ type: 'warning', area: 'tags', message: `Wasted tags (already in category): ${wastedTags.join(', ')}` });
    }

    // Keyword stuffing check (5 pts)
    const rootWordCounts = getRootWords(tags);
    const stuffedWords = Array.from(rootWordCounts.entries()).filter(([, count]) => count > 3).map(([word]) => word);
    if (stuffedWords.length === 0) {
      tagsScore += 5;
    } else {
      issues.push({ type: 'warning', area: 'tags', message: `Keyword stuffing: "${stuffedWords.join('", "')}" appears in 4+ tags` });
      tagsScore += Math.max(0, 5 - stuffedWords.length * 2);
    }

    // No duplicates (3 pts)
    const lowerTags = tags.map(t => t.toLowerCase().trim());
    const dupes = lowerTags.filter((t, i) => lowerTags.indexOf(t) !== i);
    if (dupes.length === 0) {
      tagsScore += 3;
    } else {
      issues.push({ type: 'error', area: 'tags', message: `Duplicate tags: ${Array.from(new Set(dupes)).join(', ')}` });
    }
  }

  // === DESCRIPTION (max 25 pts) ===
  if (!description) {
    issues.push({ type: 'error', area: 'description', message: 'Description is empty' });
  } else {
    // Length (5 pts)
    if (description.length >= 500) {
      descScore += 5;
      issues.push({ type: 'good', area: 'description', message: `Good length (${description.length} chars)` });
    } else if (description.length >= 300) {
      descScore += 3;
      issues.push({ type: 'warning', area: 'description', message: `Short description (${description.length} chars, aim for 500+)` });
    } else {
      issues.push({ type: 'error', area: 'description', message: `Only ${description.length} chars (min 300, ideal 500+)` });
    }

    // SK in first 160 chars (8 pts)
    const first160 = description.slice(0, 160).toLowerCase();
    if (sk && first160.includes(sk.toLowerCase())) {
      descScore += 8;
      issues.push({ type: 'good', area: 'description', message: 'SK in first 160 chars (Google snippet)' });
    } else {
      issues.push({ type: 'error', area: 'description', message: 'SK missing from first 160 chars — critical for Google' });
    }

    // Tag keywords in description (7 pts)
    const descLower = description.toLowerCase();
    const tagKeywordsFound = tags.filter(t => t && descLower.includes(t.toLowerCase())).length;
    if (tagKeywordsFound >= 8) {
      descScore += 7;
      issues.push({ type: 'good', area: 'description', message: `${tagKeywordsFound}/13 tag keywords woven into description` });
    } else if (tagKeywordsFound >= 5) {
      descScore += 5;
      issues.push({ type: 'good', area: 'description', message: `${tagKeywordsFound}/13 tag keywords in description (aim for 8+)` });
    } else if (tagKeywordsFound >= 3) {
      descScore += 3;
      issues.push({ type: 'warning', area: 'description', message: `Only ${tagKeywordsFound}/13 tag keywords in description (aim for 8+)` });
    } else {
      issues.push({ type: 'error', area: 'description', message: `Only ${tagKeywordsFound}/13 tag keywords in description — Etsy indexes description keywords` });
    }

    // Structured sections (5 pts)
    const hasPerfectFor = /PERFECT FOR/i.test(description);
    const hasPrintDetails = /PRINT DETAILS/i.test(description);
    if (hasPerfectFor && hasPrintDetails) {
      descScore += 5;
      issues.push({ type: 'good', area: 'description', message: 'Has PERFECT FOR + PRINT DETAILS sections' });
    } else if (hasPerfectFor || hasPrintDetails) {
      descScore += 3;
      if (!hasPerfectFor) issues.push({ type: 'warning', area: 'description', message: 'Missing PERFECT FOR section' });
      if (!hasPrintDetails) issues.push({ type: 'warning', area: 'description', message: 'Missing PRINT DETAILS section' });
    } else {
      issues.push({ type: 'warning', area: 'description', message: 'Missing structured sections (PERFECT FOR, PRINT DETAILS)' });
    }
  }

  // === METADATA (max 15 pts) ===
  // Materials (5 pts)
  if (materials.length > 0) {
    metaScore += 5;
    issues.push({ type: 'good', area: 'materials', message: `Materials filled (${materials.length})` });
  } else {
    issues.push({ type: 'warning', area: 'materials', message: 'No materials set' });
  }

  // Colors (5 pts)
  const hasPrimary = colors?.primary && colors.primary.length > 0;
  const hasSecondary = colors?.secondary && colors.secondary.length > 0;
  if (hasPrimary && hasSecondary) {
    metaScore += 5;
    issues.push({ type: 'good', area: 'materials', message: `Colors set: ${colors!.primary}, ${colors!.secondary}` });
  } else if (hasPrimary || hasSecondary) {
    metaScore += 3;
    issues.push({ type: 'warning', area: 'materials', message: 'Only one color set — add both primary and secondary' });
  } else {
    issues.push({ type: 'warning', area: 'materials', message: 'No colors set' });
  }

  // Alt texts (5 pts)
  const altCount = altTexts?.filter(a => a && a.trim().length > 0).length || 0;
  if (altCount >= 5) {
    metaScore += 5;
    issues.push({ type: 'good', area: 'materials', message: `All ${altCount} alt texts filled` });
  } else if (altCount > 0) {
    metaScore += Math.round((altCount / 5) * 5);
    issues.push({ type: 'warning', area: 'materials', message: `Only ${altCount}/5 alt texts filled` });
  } else {
    issues.push({ type: 'warning', area: 'materials', message: 'No alt texts — important for SEO and accessibility' });
  }

  // Cap each section
  titleScore = Math.min(30, Math.max(0, titleScore));
  tagsScore = Math.min(30, Math.max(0, tagsScore));
  descScore = Math.min(25, Math.max(0, descScore));
  metaScore = Math.min(15, Math.max(0, metaScore));
  const score = titleScore + tagsScore + descScore + metaScore;

  return { score, titleScore, tagsScore, descScore, issues };
}

export function scoreColor(score: number): string {
  if (score >= 90) return 'text-green-400';
  if (score >= 80) return 'text-green-400';
  if (score >= 65) return 'text-yellow-400';
  if (score >= 50) return 'text-orange-400';
  return 'text-red-400';
}

export function scoreBg(score: number): string {
  if (score >= 90) return 'bg-green-400';
  if (score >= 80) return 'bg-green-400';
  if (score >= 65) return 'bg-yellow-400';
  if (score >= 50) return 'bg-orange-400';
  return 'bg-red-400';
}

export function scoreGrade(score: number): string {
  if (score >= 90) return 'A+';
  if (score >= 80) return 'A';
  if (score >= 65) return 'B';
  if (score >= 50) return 'C';
  return 'D';
}
