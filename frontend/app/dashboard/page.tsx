'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import {
  getDashboardStats,
  getProductManagerData,
  getCalendarEvents,
  syncEtsyAnalytics,
  syncEtsyOrders,
  DashboardStats,
  ProductManagerItem,
  SeasonalEvent,
} from '@/lib/api';
import { analyzeSeo, scoreColor, scoreGrade } from '@/lib/seo-score';

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [products, setProducts] = useState<ProductManagerItem[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<SeasonalEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [showEvents, setShowEvents] = useState(false);

  useEffect(() => {
    Promise.all([
      getDashboardStats().then(setStats),
      getProductManagerData().then((data) => setProducts(data.products)).catch(() => {}),
      getCalendarEvents(90).then((data) => {
        const active = data.events.filter((e: SeasonalEvent) =>
          ['must_be_live', 'creating', 'soon'].includes(e.status)
        );
        setCalendarEvents(active.slice(0, 3));
      }).catch(() => {}),
    ])
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setIsLoading(false));
  }, []);

  const avgSeo = useMemo(() => {
    const scored = products
      .filter((p) => p.etsy_title)
      .map((p) => analyzeSeo(p.etsy_title, p.etsy_tags, p.etsy_description, p.etsy_materials).score);
    if (scored.length === 0) return 0;
    return Math.round(scored.reduce((s, v) => s + v, 0) / scored.length);
  }, [products]);

  // Top performers — products with most views
  const topPerformers = useMemo(() => {
    if (!stats?.top_products || products.length === 0) return [];
    return stats.top_products
      .map((tp) => {
        const product = products.find((p) => p.printify_product_id === tp.printify_product_id);
        return product ? { ...tp, title: product.title, thumbnail: product.thumbnail } : null;
      })
      .filter(Boolean) as (DashboardStats['top_products'][0] & { title: string; thumbnail: string | null })[];
  }, [stats, products]);

  // Needs attention — low SEO or 0 views (published only)
  const needsAttention = useMemo(() => {
    return products
      .filter((p) => p.status === 'on_etsy' && p.etsy_title)
      .map((p) => ({
        ...p,
        seo_score: analyzeSeo(p.etsy_title, p.etsy_tags, p.etsy_description, p.etsy_materials).score,
      }))
      .filter((p) => p.seo_score < 60 || p.total_views === 0)
      .sort((a, b) => a.seo_score - b.seo_score)
      .slice(0, 5);
  }, [products]);

  const handleSync = async () => {
    setSyncing(true);
    setError(null);
    try {
      await Promise.all([syncEtsyAnalytics(), syncEtsyOrders().catch(() => {})]);
      const newStats = await getDashboardStats();
      setStats(newStats);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const formatRevenue = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  const trendArrow = (value: number) => {
    if (value > 0) return <span className="text-green-400 text-xs ml-1">+{value}%</span>;
    if (value < 0) return <span className="text-red-400 text-xs ml-1">{value}%</span>;
    return null;
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-gray-100 mb-8">Dashboard</h1>
        <div className="grid grid-cols-5 gap-4 mb-8">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-dark-card border border-dark-border rounded-lg p-5 animate-pulse">
              <div className="h-3 w-16 bg-dark-hover rounded mb-3" />
              <div className="h-8 w-24 bg-dark-hover rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">DovShopDesign — Business Overview</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="px-4 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors disabled:opacity-50"
          >
            {syncing ? 'Syncing...' : 'Sync Etsy'}
          </button>
          <Link
            href="/"
            className="px-4 py-2 rounded-lg bg-accent text-dark-bg text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            Generate
          </Link>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">&#10005;</button>
        </div>
      )}

      {/* KPI Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="bg-dark-card border border-dark-border rounded-lg p-5">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Revenue</div>
            <div className="text-2xl font-bold text-orange-400 tabular-nums">
              {formatRevenue(stats.total_revenue_cents)}
            </div>
            <div className="mt-1">{trendArrow(stats.trends_7d.revenue)}</div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-5">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Orders</div>
            <div className="text-2xl font-bold text-green-400 tabular-nums">{stats.total_orders}</div>
            <div className="mt-1">{trendArrow(stats.trends_7d.orders)}</div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-5">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Views</div>
            <div className="text-2xl font-bold text-purple-400 tabular-nums">{stats.total_views.toLocaleString()}</div>
            <div className="mt-1">{trendArrow(stats.trends_7d.views)}</div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-5">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Conversion</div>
            <div className="text-2xl font-bold text-blue-400 tabular-nums">{stats.conversion_rate}%</div>
            <div className="text-xs text-gray-600 mt-1">{stats.total_orders}/{stats.total_views}</div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-5">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Avg SEO</div>
            <div className={`text-2xl font-bold tabular-nums ${scoreColor(avgSeo)}`}>
              {avgSeo}/100
            </div>
            <div className="text-xs text-gray-600 mt-1">Grade {scoreGrade(avgSeo)}</div>
          </div>
        </div>
      )}

      {/* Middle row: Chart + Top performers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Views chart (30 days) */}
        <div className="bg-dark-card border border-dark-border rounded-lg p-5">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
            Views — Last 30 Days
          </h2>
          {stats?.daily_views && stats.daily_views.length > 0 ? (
            <ViewsChart data={stats.daily_views} />
          ) : (
            <div className="text-gray-600 text-sm py-8 text-center">No view data yet</div>
          )}
        </div>

        {/* Top performers + Needs attention */}
        <div className="space-y-6">
          <div className="bg-dark-card border border-dark-border rounded-lg p-5">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Top Performers
            </h2>
            {topPerformers.length > 0 ? (
              <div className="space-y-2">
                {topPerformers.map((p, i) => (
                  <div key={p.printify_product_id} className="flex items-center gap-3">
                    <span className="text-xs text-gray-600 w-4">{i + 1}.</span>
                    {p.thumbnail && (
                      <img src={p.thumbnail} alt="" className="w-8 h-8 rounded object-cover" />
                    )}
                    <span className="text-sm text-gray-300 flex-1 truncate">{p.title}</span>
                    <span className="text-sm text-purple-400 tabular-nums">{p.total_views} views</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-600 text-sm">No data yet</div>
            )}
          </div>

          {needsAttention.length > 0 && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-5">
              <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
                Needs Attention
              </h2>
              <div className="space-y-2.5">
                {needsAttention.map((p) => {
                  const reasons: string[] = [];
                  if (p.total_views === 0) reasons.push('No views');
                  if (p.seo_score < 40) reasons.push('Poor SEO');
                  else if (p.seo_score < 60) reasons.push('Low SEO');
                  return (
                    <Link
                      key={p.printify_product_id}
                      href={`/products/${p.printify_product_id}`}
                      className="flex items-center gap-3 group hover:bg-dark-hover/50 rounded-lg p-1.5 -m-1.5 transition-colors"
                    >
                      {p.thumbnail ? (
                        <img src={p.thumbnail} alt="" className="w-8 h-8 rounded object-cover flex-shrink-0" />
                      ) : (
                        <div className="w-8 h-8 rounded bg-dark-bg flex-shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-gray-300 truncate group-hover:text-white transition-colors">{p.title}</div>
                        <div className="flex items-center gap-2 mt-0.5">
                          {reasons.map((r) => (
                            <span key={r} className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400">{r}</span>
                          ))}
                          <span className={`text-[10px] px-1.5 py-0.5 rounded bg-dark-bg ${scoreColor(p.seo_score)}`}>
                            SEO {p.seo_score}
                          </span>
                        </div>
                      </div>
                      <span className="text-xs text-gray-600">{p.total_views} views</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="bg-dark-card border border-dark-border rounded-lg p-5">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Quick Actions</h2>
        <div className="flex flex-wrap gap-3">
          <Link href="/products" className="px-4 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors">
            Products ({stats?.total_products || 0})
          </Link>
          <Link href="/seo" className="px-4 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors">
            SEO Editor
          </Link>
          <Link href="/schedule" className="px-4 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors">
            Schedule
          </Link>
          <Link href="/analytics" className="px-4 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors">
            Analytics
          </Link>
          <Link href="/" className="px-4 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors">
            Generate New
          </Link>
        </div>
      </div>

      {/* Stats summary row */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-dark-card border border-dark-border rounded-lg p-4">
            <div className="text-xs text-gray-500">Generated</div>
            <div className="text-lg font-bold text-gray-200 tabular-nums">{stats.total_generated}</div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-4">
            <div className="text-xs text-gray-500">Products</div>
            <div className="text-lg font-bold text-gray-200 tabular-nums">{stats.total_products}</div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-4">
            <div className="text-xs text-gray-500">Published</div>
            <div className="text-lg font-bold text-green-400 tabular-nums">{stats.total_published}</div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-4">
            <div className="text-xs text-gray-500">Favorites</div>
            <div className="text-lg font-bold text-pink-400 tabular-nums">{stats.total_favorites}</div>
          </div>
        </div>
      )}

      {/* Calendar events (collapsible) */}
      {calendarEvents.length > 0 && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-5">
          <button
            onClick={() => setShowEvents(!showEvents)}
            className="flex items-center justify-between w-full text-left"
          >
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
              Upcoming Events ({calendarEvents.length})
            </h2>
            <span className="text-gray-500 text-xs">{showEvents ? 'Hide' : 'Show'}</span>
          </button>
          {showEvents && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
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
                      <div className="text-xs text-gray-500 mt-0.5">
                        {new Date(ev.event_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        {' · '}
                        {ev.presets_used}/{ev.presets_total} presets
                      </div>
                    </div>
                    <span className={`text-xs tabular-nums ${ev.days_until <= 14 ? 'text-orange-400' : 'text-gray-500'}`}>
                      {ev.days_until}d
                    </span>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ----- Views Chart Component ----- */

function ViewsChart({ data }: { data: { date: string; views: number }[] }) {
  // Fill in missing days with 0 views for a complete 30-day chart
  const filled: { date: string; views: number }[] = [];
  const viewsMap = new Map(data.map((d) => [d.date, d.views]));
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 29);
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const key = d.toISOString().slice(0, 10);
    filled.push({ date: key, views: viewsMap.get(key) || 0 });
  }

  const maxViews = Math.max(...filled.map((d) => d.views), 1);

  return (
    <div className="flex items-end gap-0.5 h-32">
      {filled.map((d) => {
        const height = d.views > 0 ? Math.max((d.views / maxViews) * 100, 4) : 2;
        const dateLabel = new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        return (
          <div
            key={d.date}
            className="flex-1 h-full group relative flex items-end"
            title={`${dateLabel}: ${d.views} views`}
          >
            <div
              className={`${d.views > 0 ? 'bg-purple-500/60 hover:bg-purple-400/80' : 'bg-gray-700/30'} rounded-t transition-colors w-full`}
              style={{ height: `${height}%` }}
            />
            {/* Tooltip on hover */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10">
              <div className="bg-dark-bg border border-dark-border rounded px-2 py-1 text-xs text-gray-300 whitespace-nowrap">
                {dateLabel}: {d.views}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
