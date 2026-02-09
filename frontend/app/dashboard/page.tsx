'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  getDashboardStats,
  getPresets,
  getCalendarEvents,
  DashboardStats,
  PosterPreset,
  PresetCategory,
  SeasonalEvent,
} from '@/lib/api';

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [presets, setPresets] = useState<PosterPreset[]>([]);
  const [categories, setCategories] = useState<Record<string, PresetCategory>>({});
  const [usedPresetIds, setUsedPresetIds] = useState<Set<string>>(new Set());
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [calendarEvents, setCalendarEvents] = useState<SeasonalEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [presetsLoading, setPresetsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false));

    getPresets()
      .then((data) => {
        setPresets(data.presets);
        setCategories(data.categories);
        setUsedPresetIds(new Set(data.used_preset_ids || []));
      })
      .catch((err) => setError(err.message))
      .finally(() => setPresetsLoading(false));

    getCalendarEvents(90)
      .then((data) => {
        // Show only active/soon events, max 3
        const active = data.events.filter((e) =>
          ['must_be_live', 'creating', 'soon'].includes(e.status)
        );
        setCalendarEvents(active.slice(0, 3));
      })
      .catch(() => {});
  }, []);

  const handleCategoryFilter = (category: string) => {
    setSelectedCategory(category);
    const fetchCategory = category === 'all' ? undefined : category;
    setPresetsLoading(true);
    getPresets(fetchCategory)
      .then((data) => {
        setPresets(data.presets);
        setUsedPresetIds(new Set(data.used_preset_ids || []));
      })
      .catch((err) => setError(err.message))
      .finally(() => setPresetsLoading(false));
  };

  const formatRevenue = (cents: number) => {
    return `$${(cents / 100).toFixed(2)}`;
  };

  const getCategoryIcon = (iconName: string): string => {
    const icons: Record<string, string> = {
      sakura: '\u{1F338}',
      leaf: '\u{1F343}',
      mountain: '\u{26F0}\uFE0F',
      wave: '\u{1F30A}',
      star: '\u{2B50}',
      moon: '\u{1F319}',
      sun: '\u{2600}\uFE0F',
      fire: '\u{1F525}',
      flower: '\u{1F33A}',
      tree: '\u{1F332}',
      bird: '\u{1F426}',
      butterfly: '\u{1F98B}',
      ocean: '\u{1F30A}',
      city: '\u{1F3D9}\uFE0F',
      abstract: '\u{1F3A8}',
      heart: '\u{2764}\uFE0F',
      crystal: '\u{1F48E}',
      cloud: '\u{2601}\uFE0F',
      palette: '\u{1F3A8}',
      sparkle: '\u{2728}',
      horse: '\u{1F40E}',
      home: '\u{1F3E0}',
    };
    return icons[iconName] || '\u{1F3A8}';
  };

  const getDifficultyConfig = (difficulty: string) => {
    switch (difficulty) {
      case 'easy':
        return { label: 'Easy', classes: 'bg-green-500/15 text-green-400 border-green-500/30' };
      case 'medium':
        return { label: 'Medium', classes: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30' };
      case 'hard':
        return { label: 'Hard', classes: 'bg-red-500/15 text-red-400 border-red-500/30' };
      default:
        return { label: difficulty, classes: 'bg-gray-500/15 text-gray-400 border-gray-500/30' };
    }
  };

  const statusTotal = stats
    ? Object.values(stats.by_status).reduce((sum, count) => sum + count, 0)
    : 0;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Overview of your poster generation business</p>
        </div>
        <Link
          href="/"
          className="px-4 py-2 rounded-lg bg-accent text-dark-bg text-sm font-medium hover:bg-accent-hover transition-colors"
        >
          New Generation
        </Link>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 mb-6 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">
            &#10005;
          </button>
        </div>
      )}

      {/* Stats Cards */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-dark-card border border-dark-border rounded-lg p-4 animate-pulse">
              <div className="h-3 w-16 bg-dark-hover rounded mb-3" />
              <div className="h-7 w-20 bg-dark-hover rounded" />
            </div>
          ))}
        </div>
      ) : stats ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          <StatCard
            label="Generated"
            value={stats.total_generated}
            accent="text-accent"
          />
          <StatCard
            label="Products"
            value={stats.total_products}
            accent="text-blue-400"
          />
          <StatCard
            label="Published"
            value={stats.total_published}
            accent="text-green-400"
          />
          <StatCard
            label="Views"
            value={stats.total_views}
            accent="text-purple-400"
          />
          <StatCard
            label="Favorites"
            value={stats.total_favorites}
            accent="text-pink-400"
          />
          <StatCard
            label="Revenue"
            value={formatRevenue(stats.total_revenue_cents)}
            accent="text-orange-400"
            isString
          />
        </div>
      ) : null}

      {/* Generation Pipeline + Credits */}
      {stats && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
          {/* Pipeline */}
          <div className="lg:col-span-2 bg-dark-card border border-dark-border rounded-lg p-5">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
              Generation Pipeline
            </h2>
            {statusTotal > 0 ? (
              <>
                {/* Status bar */}
                <div className="flex rounded-full overflow-hidden h-3 mb-4 bg-dark-bg">
                  {(stats.by_status['COMPLETE'] || 0) > 0 && (
                    <div
                      className="bg-green-500 transition-all duration-500"
                      style={{
                        width: `${((stats.by_status['COMPLETE'] || 0) / statusTotal) * 100}%`,
                      }}
                      title={`Complete: ${stats.by_status['COMPLETE'] || 0}`}
                    />
                  )}
                  {(stats.by_status['PENDING'] || 0) > 0 && (
                    <div
                      className="bg-yellow-500 transition-all duration-500"
                      style={{
                        width: `${((stats.by_status['PENDING'] || 0) / statusTotal) * 100}%`,
                      }}
                      title={`Pending: ${stats.by_status['PENDING'] || 0}`}
                    />
                  )}
                  {(stats.by_status['FAILED'] || 0) > 0 && (
                    <div
                      className="bg-red-500 transition-all duration-500"
                      style={{
                        width: `${((stats.by_status['FAILED'] || 0) / statusTotal) * 100}%`,
                      }}
                      title={`Failed: ${stats.by_status['FAILED'] || 0}`}
                    />
                  )}
                </div>

                {/* Status legend */}
                <div className="flex flex-wrap gap-4">
                  <PipelineStatus
                    label="Complete"
                    count={stats.by_status['COMPLETE'] || 0}
                    dotColor="bg-green-500"
                    textColor="text-green-400"
                  />
                  <PipelineStatus
                    label="Pending"
                    count={stats.by_status['PENDING'] || 0}
                    dotColor="bg-yellow-500"
                    textColor="text-yellow-400"
                  />
                  <PipelineStatus
                    label="Failed"
                    count={stats.by_status['FAILED'] || 0}
                    dotColor="bg-red-500"
                    textColor="text-red-400"
                  />
                </div>
              </>
            ) : (
              <p className="text-gray-500 text-sm">No generations yet. Start creating posters to see your pipeline.</p>
            )}
          </div>

          {/* Credits Used */}
          <div className="bg-dark-card border border-dark-border rounded-lg p-5 flex flex-col">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
              Credits Used
            </h2>
            <div className="flex-1 flex flex-col items-center justify-center">
              <div className="text-4xl font-bold text-orange-400 tabular-nums">
                {(stats.total_credits_used || 0).toLocaleString()}
              </div>
              <p className="text-xs text-gray-500 mt-2">API tokens consumed</p>
            </div>
            <div className="mt-4 pt-4 border-t border-dark-border">
              <div className="flex justify-between text-xs text-gray-500">
                <span>Total images</span>
                <span className="text-gray-300">{stats.total_images.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-xs text-gray-500 mt-1.5">
                <span>Avg per generation</span>
                <span className="text-gray-300">
                  {stats.total_generated > 0
                    ? Math.round(stats.total_credits_used / stats.total_generated).toLocaleString()
                    : '--'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Upcoming Events */}
      {calendarEvents.length > 0 && (
        <div className="bg-dark-card border border-dark-border rounded-xl p-5 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-100">Upcoming Events</h2>
            <Link
              href="/calendar"
              className="text-xs text-accent hover:text-accent-hover transition-colors"
            >
              View all →
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {calendarEvents.map((ev) => {
              const statusColors: Record<string, string> = {
                must_be_live: 'text-orange-400 bg-orange-500/15',
                creating: 'text-yellow-400 bg-yellow-500/15',
                soon: 'text-blue-400 bg-blue-500/15',
              };
              const statusLabels: Record<string, string> = {
                must_be_live: 'Must Be Live',
                creating: 'Creating',
                soon: 'Soon',
              };
              const cls = statusColors[ev.status] || 'text-gray-400 bg-gray-500/15';
              return (
                <Link
                  key={ev.id}
                  href="/calendar"
                  className="flex items-center gap-3 p-3 rounded-lg bg-dark-bg border border-dark-border hover:border-gray-600 transition-colors"
                >
                  <span className="text-xl flex-shrink-0">{ev.icon}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-200 truncate">{ev.name}</span>
                      <span className={`text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded ${cls}`}>
                        {statusLabels[ev.status] || ev.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-gray-500">
                        {new Date(ev.event_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </span>
                      <span className="text-xs text-gray-600">·</span>
                      <span className="text-xs text-gray-500">
                        {ev.presets_used}/{ev.presets_total} presets
                      </span>
                    </div>
                  </div>
                  <span className={`text-xs tabular-nums ${ev.days_until <= 14 ? 'text-orange-400' : 'text-gray-500'}`}>
                    {ev.days_until}d
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Preset Browser */}
      <div className="bg-dark-card border border-dark-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-100">Preset Browser</h2>
          <span className="text-xs text-gray-500">
            {presets.length} preset{presets.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Category filters */}
        <div className="flex flex-wrap gap-2 mb-5">
          <button
            onClick={() => handleCategoryFilter('all')}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border ${
              selectedCategory === 'all'
                ? 'bg-accent/15 text-accent border-accent/30'
                : 'bg-dark-bg text-gray-400 border-dark-border hover:text-gray-200 hover:border-gray-600'
            }`}
          >
            All
          </button>
          {Object.entries(categories).map(([key, cat]) => (
            <button
              key={key}
              onClick={() => handleCategoryFilter(key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border flex items-center gap-1.5 ${
                selectedCategory === key
                  ? 'bg-accent/15 text-accent border-accent/30'
                  : 'bg-dark-bg text-gray-400 border-dark-border hover:text-gray-200 hover:border-gray-600'
              }`}
            >
              <span className="text-xs">{getCategoryIcon(cat.icon)}</span>
              {cat.name}
            </button>
          ))}
        </div>

        {/* Preset Grid */}
        {presetsLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="bg-dark-bg rounded-lg h-28 animate-pulse" />
            ))}
          </div>
        ) : presets.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 text-sm">No presets found for this category.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {[...presets]
              .sort((a, b) => (usedPresetIds.has(a.id) ? 1 : 0) - (usedPresetIds.has(b.id) ? 1 : 0))
              .map((preset) => {
              const category = categories[preset.category];
              const categoryColor = category?.color || '#6B7280';
              const difficulty = getDifficultyConfig(preset.difficulty);
              const isCompleted = usedPresetIds.has(preset.id);

              return (
                <div
                  key={preset.id}
                  className={`bg-dark-bg border border-dark-border rounded-lg overflow-hidden flex group hover:border-gray-600 transition-colors ${isCompleted ? 'opacity-75' : ''}`}
                >
                  {/* Color band */}
                  <div
                    className="w-1.5 flex-shrink-0"
                    style={{ backgroundColor: isCompleted ? '#22c55e' : categoryColor }}
                  />

                  {/* Content */}
                  <div className="flex-1 p-3 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <h3 className="text-sm font-medium text-gray-200 truncate flex items-center gap-1" title={preset.name}>
                        {isCompleted && (
                          <svg className="w-3.5 h-3.5 text-green-400 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                        )}
                        {preset.name}
                      </h3>
                      {/* Trending score */}
                      {preset.trending_score > 0 && (
                        <div className="flex items-center gap-0.5 flex-shrink-0" title={`Trending: ${preset.trending_score}/10`}>
                          <svg
                            className="w-3.5 h-3.5 text-orange-400"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                          >
                            <path
                              fillRule="evenodd"
                              d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1011.95-4.95c-.592-.591-.98-.985-1.348-1.467-.363-.476-.724-1.063-1.207-2.03zM12.12 15.12A3 3 0 017 13s.879.5 2.5.5c0-1 .5-4 1.25-4.5.5 1 .786 1.293 1.371 1.879A2.99 2.99 0 0113 13a2.99 2.99 0 01-.879 2.121z"
                              clipRule="evenodd"
                            />
                          </svg>
                          <span className="text-[11px] text-orange-400 font-medium tabular-nums">
                            {preset.trending_score}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Tags preview */}
                    {preset.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {preset.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="text-[10px] px-1.5 py-0.5 bg-dark-card text-gray-500 rounded"
                          >
                            {tag}
                          </span>
                        ))}
                        {preset.tags.length > 3 && (
                          <span className="text-[10px] text-gray-600">
                            +{preset.tags.length - 3}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Bottom row */}
                    <div className="flex items-center justify-between">
                      {isCompleted ? (
                        <span className="text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded border text-green-400 border-green-500/30 bg-green-500/10">
                          Completed
                        </span>
                      ) : (
                        <span
                          className={`text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded border ${difficulty.classes}`}
                        >
                          {difficulty.label}
                        </span>
                      )}
                      <button
                        onClick={() => router.push(`/?preset=${preset.id}`)}
                        className="text-xs px-2.5 py-1 rounded-md bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20 transition-colors font-medium opacity-0 group-hover:opacity-100 focus:opacity-100"
                      >
                        Generate
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ----- Sub-components ----- */

function StatCard({
  label,
  value,
  accent,
  isString = false,
}: {
  label: string;
  value: number | string;
  accent: string;
  isString?: boolean;
}) {
  const displayValue = isString ? value : (value as number).toLocaleString();

  return (
    <div className="bg-dark-card border border-dark-border rounded-lg p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold tabular-nums ${accent}`}>{displayValue}</div>
    </div>
  );
}

function PipelineStatus({
  label,
  count,
  dotColor,
  textColor,
}: {
  label: string;
  count: number;
  dotColor: string;
  textColor: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2.5 h-2.5 rounded-full ${dotColor}`} />
      <span className="text-sm text-gray-300">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${textColor}`}>
        {count.toLocaleString()}
      </span>
    </div>
  );
}
