'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  getCalendarEvents,
  getCalendarEventPresets,
  SeasonalEvent,
  CalendarEventPreset,
} from '@/lib/api';

type FilterMode = 'all' | 'active' | 'high_priority' | 'next30' | 'next90';

const STATUS_CONFIG: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  must_be_live: { label: 'Must Be Live', bg: 'bg-orange-500/15', text: 'text-orange-400', dot: 'bg-orange-400' },
  creating: { label: 'Creating', bg: 'bg-yellow-500/15', text: 'text-yellow-400', dot: 'bg-yellow-400' },
  soon: { label: 'Soon', bg: 'bg-blue-500/15', text: 'text-blue-400', dot: 'bg-blue-400' },
  upcoming: { label: 'Upcoming', bg: 'bg-gray-500/15', text: 'text-gray-400', dot: 'bg-gray-500' },
  past: { label: 'Past', bg: 'bg-gray-800/50', text: 'text-gray-600', dot: 'bg-gray-700' },
};

function formatDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function CalendarPage() {
  const router = useRouter();
  const [events, setEvents] = useState<SeasonalEvent[]>([]);
  const [filter, setFilter] = useState<FilterMode>('active');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedEvent, setExpandedEvent] = useState<string | null>(null);
  const [eventPresets, setEventPresets] = useState<Record<string, CalendarEventPreset[]>>({});
  const [presetsLoading, setPresetsLoading] = useState<string | null>(null);

  useEffect(() => {
    const days = filter === 'next30' ? 30 : filter === 'next90' ? 90 : 365;
    setIsLoading(true);
    getCalendarEvents(days)
      .then((data) => setEvents(data.events))
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [filter]);

  const filteredEvents = events.filter((ev) => {
    if (filter === 'active') return ['must_be_live', 'creating', 'soon'].includes(ev.status);
    if (filter === 'high_priority') return ev.priority >= 4;
    return ev.status !== 'past';
  });

  const togglePresets = async (eventId: string) => {
    if (expandedEvent === eventId) {
      setExpandedEvent(null);
      return;
    }
    setExpandedEvent(eventId);
    if (!eventPresets[eventId]) {
      setPresetsLoading(eventId);
      try {
        const data = await getCalendarEventPresets(eventId);
        setEventPresets((prev) => ({ ...prev, [eventId]: data.presets }));
      } catch {
        // ignore
      } finally {
        setPresetsLoading(null);
      }
    }
  };

  // Stats
  const activeWindows = events.filter((e) => ['must_be_live', 'creating'].includes(e.status)).length;
  const needAttention = events.filter((e) => e.status === 'must_be_live' && e.presets_used < e.presets_total).length;
  const totalProducts = events.reduce((sum, e) => sum + e.product_count, 0);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Seasonal Calendar</h1>
          <p className="text-sm text-gray-500 mt-1">Plan designs around holidays for Etsy SEO</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 mb-6 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">&#10005;</button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total Events" value={events.length} accent="text-accent" />
        <StatCard label="Active Windows" value={activeWindows} accent="text-yellow-400" />
        <StatCard label="Products Created" value={totalProducts} accent="text-green-400" />
        <StatCard label="Need Attention" value={needAttention} accent={needAttention > 0 ? 'text-orange-400' : 'text-gray-500'} />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-6">
        {([
          ['active', 'Active'],
          ['all', 'All'],
          ['next30', 'Next 30d'],
          ['next90', 'Next 90d'],
          ['high_priority', 'High Priority'],
        ] as [FilterMode, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border ${
              filter === key
                ? 'bg-accent/15 text-accent border-accent/30'
                : 'bg-dark-bg text-gray-400 border-dark-border hover:text-gray-200 hover:border-gray-600'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Events */}
      {isLoading ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-dark-card border border-dark-border rounded-lg h-32 animate-pulse" />
          ))}
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="bg-dark-card border border-dark-border rounded-lg p-12 text-center">
          <p className="text-gray-500">No events match this filter.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredEvents.map((event) => {
            const cfg = STATUS_CONFIG[event.status] || STATUS_CONFIG.upcoming;
            const isExpanded = expandedEvent === event.id;
            const presets = eventPresets[event.id] || [];

            return (
              <div key={event.id} className="bg-dark-card border border-dark-border rounded-lg overflow-hidden">
                {/* Main card */}
                <div className="p-4">
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: icon + info */}
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <span className="text-2xl flex-shrink-0" title={event.name}>
                        {event.icon}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-base font-semibold text-gray-100">{event.name}</h3>
                          <span className={`text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded border ${cfg.bg} ${cfg.text} border-current/20`}>
                            {cfg.label}
                          </span>
                          {/* Priority stars */}
                          <span className="text-xs text-gray-600" title={`Priority: ${event.priority}/5`}>
                            {'★'.repeat(event.priority)}{'☆'.repeat(5 - event.priority)}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">{event.description}</p>

                        {/* Timeline */}
                        <div className="flex items-center gap-1 mt-2 text-xs text-gray-500 flex-wrap">
                          <span>Start: <span className="text-gray-400">{formatDate(event.start_creating)}</span></span>
                          <span className="text-gray-700">→</span>
                          <span>Live by: <span className="text-gray-400">{formatDate(event.must_be_live)}</span></span>
                          <span className="text-gray-700">→</span>
                          <span>Event: <span className="text-gray-300 font-medium">{formatDate(event.event_date)}</span></span>
                        </div>

                        {/* Presets progress */}
                        <div className="flex items-center gap-3 mt-2">
                          <div className="flex items-center gap-1.5">
                            <div className="w-24 h-1.5 rounded-full bg-dark-bg overflow-hidden">
                              <div
                                className="h-full rounded-full bg-accent transition-all"
                                style={{ width: `${event.presets_total > 0 ? (event.presets_used / event.presets_total) * 100 : 0}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-500">
                              {event.presets_used}/{event.presets_total} presets
                            </span>
                          </div>
                          {event.product_count > 0 && (
                            <span className="text-xs text-green-400">
                              {event.product_count} product{event.product_count !== 1 ? 's' : ''}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Right: date + actions */}
                    <div className="flex flex-col items-end gap-2 flex-shrink-0">
                      <div className="text-right">
                        <div className="text-lg font-bold text-gray-200 tabular-nums">
                          {formatDate(event.event_date)}
                        </div>
                        <div className={`text-xs ${event.days_until <= 0 ? 'text-gray-600' : event.days_until <= 14 ? 'text-orange-400' : 'text-gray-500'}`}>
                          {event.days_until <= 0 ? 'Past' : `${event.days_until}d away`}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => togglePresets(event.id)}
                          className="text-xs px-2.5 py-1 rounded-md bg-dark-bg text-gray-400 border border-dark-border hover:text-gray-200 hover:border-gray-600 transition-colors"
                        >
                          {isExpanded ? 'Hide' : 'View'} Presets
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded presets */}
                {isExpanded && (
                  <div className="border-t border-dark-border bg-dark-bg/50 p-4">
                    {presetsLoading === event.id ? (
                      <div className="flex items-center gap-2 text-sm text-gray-500">
                        <div className="w-4 h-4 border-2 border-gray-600 border-t-accent rounded-full animate-spin" />
                        Loading presets...
                      </div>
                    ) : presets.length === 0 ? (
                      <p className="text-sm text-gray-500">No presets found for this event.</p>
                    ) : (
                      <>
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="text-sm font-medium text-gray-300">Suggested Presets</h4>
                          <span className="text-xs text-gray-500">
                            {presets.filter((p) => p.is_used).length}/{presets.length} used
                          </span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                          {presets.map((preset) => (
                            <div
                              key={preset.id}
                              className={`flex items-center justify-between gap-2 p-2.5 rounded-lg border transition-colors ${
                                preset.is_used
                                  ? 'bg-green-500/5 border-green-500/20'
                                  : 'bg-dark-card border-dark-border hover:border-gray-600'
                              }`}
                            >
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-1.5">
                                  {preset.is_used && (
                                    <svg className="w-3.5 h-3.5 text-green-400 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor">
                                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                  )}
                                  <span className={`text-sm truncate ${preset.is_used ? 'text-green-400' : 'text-gray-200'}`}>
                                    {preset.name}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2 mt-0.5">
                                  <span className="text-[10px] text-gray-500">{preset.category_name}</span>
                                  {preset.trending_score >= 8 && (
                                    <span className="text-[10px] text-orange-400 flex items-center gap-0.5">
                                      🔥 {preset.trending_score}
                                    </span>
                                  )}
                                </div>
                              </div>
                              {!preset.is_used && (
                                <button
                                  onClick={() => router.push(`/?preset=${preset.id}`)}
                                  className="text-xs px-2 py-1 rounded bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20 transition-colors flex-shrink-0"
                                >
                                  Generate
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="bg-dark-card border border-dark-border rounded-lg p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold tabular-nums ${accent}`}>{value}</div>
    </div>
  );
}
