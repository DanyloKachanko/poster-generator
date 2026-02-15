// SEO scoring utilities — extracted from seo/page.tsx for reuse

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

export function analyzeSeo(title: string, tags: string[], description: string, materials: string[] = []): SeoAnalysis {
  const issues: SeoIssue[] = [];
  let titleScore = 0;
  let tagsScore = 0;
  let descScore = 0;
  let extrasScore = 0;

  // === TITLE (max 25 pts) ===
  if (!title) {
    issues.push({ type: 'error', area: 'title', message: 'Title is empty' });
  } else {
    if (title.length >= 80 && title.length <= 140) {
      titleScore += 10;
      issues.push({ type: 'good', area: 'title', message: `Good length (${title.length}/140)` });
    } else if (title.length > 140) {
      issues.push({ type: 'error', area: 'title', message: `Title too long (${title.length}/140)` });
    } else {
      titleScore += 5;
      issues.push({ type: 'warning', area: 'title', message: `Title short (${title.length}/140) — use more chars` });
    }

    if (title.includes(' | ')) {
      titleScore += 5;
      const sections = title.split('|').map((s) => s.trim()).filter(Boolean);
      if (sections.length >= 3) {
        issues.push({ type: 'good', area: 'title', message: `${sections.length} pipe sections` });
      }
    } else {
      issues.push({ type: 'warning', area: 'title', message: 'No pipe separators' });
    }

    // SK at start of title (check first tag as proxy for SK)
    if (tags[0] && title.toLowerCase().startsWith(tags[0].toLowerCase().split(' ')[0])) {
      titleScore += 10;
      issues.push({ type: 'good', area: 'title', message: 'SK keyword at start of title' });
    } else if (tags[0] && title.toLowerCase().includes(tags[0].toLowerCase())) {
      titleScore += 5;
      issues.push({ type: 'warning', area: 'title', message: 'SK in title but not at start' });
    }

    // Repeated words
    const titleWords = title.toLowerCase().replace(/[|,]/g, ' ').split(/\s+/).filter((w) => w.length > 3);
    const wordCounts: Record<string, number> = {};
    titleWords.forEach((w) => { wordCounts[w] = (wordCounts[w] || 0) + 1; });
    const repeatedWords = Object.entries(wordCounts).filter(([, c]) => c > 1).map(([w]) => w);
    if (repeatedWords.length > 0) {
      issues.push({ type: 'warning', area: 'title', message: `Repeated: ${repeatedWords.join(', ')}` });
      titleScore = Math.max(0, titleScore - repeatedWords.length * 3);
    }
  }

  // === TAGS (max 25 pts) ===
  if (tags.length === 0) {
    issues.push({ type: 'error', area: 'tags', message: 'No tags' });
  } else {
    if (tags.length === 13) {
      tagsScore += 10;
      issues.push({ type: 'good', area: 'tags', message: 'All 13 tags used' });
    } else {
      issues.push({ type: 'error', area: 'tags', message: `Only ${tags.length}/13 tags` });
      tagsScore += Math.round((tags.length / 13) * 10);
    }

    const allValid = tags.every((t) => t.length >= 1 && t.length <= 20 && t.includes(' '));
    if (allValid) {
      tagsScore += 10;
      issues.push({ type: 'good', area: 'tags', message: 'All tags valid format (multi-word, ≤20 chars)' });
    } else {
      const singleWordTags = tags.filter((t) => !t.includes(' '));
      const overLength = tags.filter((t) => t.length > 20);
      if (singleWordTags.length > 0) {
        issues.push({ type: 'warning', area: 'tags', message: `${singleWordTags.length} single-word tag(s)` });
        tagsScore += 5;
      }
      if (overLength.length > 0) {
        issues.push({ type: 'error', area: 'tags', message: `${overLength.length} tag(s) over 20 chars` });
        tagsScore += 3;
      }
      if (singleWordTags.length === 0 && overLength.length === 0) {
        tagsScore += 10;
      }
    }

    // SK in tags
    if (tags[0] && title.toLowerCase().includes(tags[0].toLowerCase())) {
      tagsScore += 5;
      issues.push({ type: 'good', area: 'tags', message: `SK "${tags[0]}" aligned with title` });
    } else if (tags[0]) {
      issues.push({ type: 'warning', area: 'tags', message: `First tag "${tags[0]}" not in title` });
    }

    // Duplicates
    const lowerTags = tags.map((t) => t.toLowerCase().trim());
    const dupes = lowerTags.filter((t, i) => lowerTags.indexOf(t) !== i);
    if (dupes.length > 0) {
      issues.push({ type: 'error', area: 'tags', message: `Duplicates: ${Array.from(new Set(dupes)).join(', ')}` });
      tagsScore = Math.max(0, tagsScore - dupes.length * 5);
    }
  }

  // === DESCRIPTION (max 25 pts) ===
  if (!description) {
    issues.push({ type: 'error', area: 'description', message: 'Description is empty' });
  } else {
    if (description.length >= 300) {
      descScore += 5;
      issues.push({ type: 'good', area: 'description', message: `Good length (${description.length} chars)` });
    } else {
      issues.push({ type: 'error', area: 'description', message: `Only ${description.length} chars (min 300)` });
    }

    const first160 = description.slice(0, 160).toLowerCase();
    if (tags[0] && first160.includes(tags[0].toLowerCase())) {
      descScore += 10;
      issues.push({ type: 'good', area: 'description', message: 'SK in first 160 chars (Google snippet)' });
    } else {
      issues.push({ type: 'warning', area: 'description', message: 'SK missing from first 160 chars' });
    }

    if (/PERFECT FOR/i.test(description)) {
      descScore += 5;
      issues.push({ type: 'good', area: 'description', message: 'Has PERFECT FOR section' });
    } else {
      issues.push({ type: 'warning', area: 'description', message: 'Missing PERFECT FOR section' });
    }

    if (/PRINT DETAILS/i.test(description)) {
      descScore += 5;
      issues.push({ type: 'good', area: 'description', message: 'Has PRINT DETAILS section' });
    } else {
      issues.push({ type: 'warning', area: 'description', message: 'Missing PRINT DETAILS section' });
    }
  }

  // === EXTRAS (max 25 pts) ===
  if (materials.length > 0) {
    extrasScore += 5;
    issues.push({ type: 'good', area: 'materials', message: `Materials filled (${materials.length})` });
  } else {
    issues.push({ type: 'warning', area: 'materials', message: 'No materials set' });
  }

  // Cap each section
  titleScore = Math.min(25, Math.max(0, titleScore));
  tagsScore = Math.min(25, Math.max(0, tagsScore));
  descScore = Math.min(25, Math.max(0, descScore));
  extrasScore = Math.min(25, Math.max(0, extrasScore));
  const score = titleScore + tagsScore + descScore + extrasScore;

  return { score, titleScore, tagsScore, descScore, issues };
}

export function scoreColor(score: number): string {
  if (score >= 80) return 'text-green-400';
  if (score >= 60) return 'text-yellow-400';
  if (score >= 40) return 'text-orange-400';
  return 'text-red-400';
}

export function scoreBg(score: number): string {
  if (score >= 80) return 'bg-green-400';
  if (score >= 60) return 'bg-yellow-400';
  if (score >= 40) return 'bg-orange-400';
  return 'bg-red-400';
}

export function scoreGrade(score: number): string {
  if (score >= 80) return 'A';
  if (score >= 60) return 'B';
  if (score >= 40) return 'C';
  return 'D';
}
