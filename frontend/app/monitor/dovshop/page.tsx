'use client';

import { useState, useEffect } from 'react';
import { getDovShopAnalytics, syncDovShopAnalytics, DovShopAnalytics } from '@/lib/api';

export default function DovShopAnalyticsPage() {
  const [data, setData] = useState<DovShopAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getDovShopAnalytics(days)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [days]);

  const handleSync = async () => {
    setSyncing(true);
    setError(null);
    try {
      await syncDovShopAnalytics();
      const fresh = await getDovShopAnalytics(days);
      setData(fresh);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-gray-100 mb-8">DovShop Analytics</h1>
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-dark-card border border-dark-border rounded-lg p-5 animate-pulse">
              <div className="h-3 w-16 bg-dark-hover rounded mb-3" />
              <div className="h-8 w-24 bg-dark-hover rounded" />
            </div>
          ))}
        </div>
        <div className="text-gray-500 text-sm">Loading DovShop analytics...</div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-gray-100 mb-8">DovShop Analytics</h1>
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => {
              setError(null);
              setLoading(true);
              getDovShopAnalytics(days)
                .then(setData)
                .catch((e) => setError(e.message))
                .finally(() => setLoading(false));
            }}
            className="px-3 py-1 bg-red-500/20 rounded text-red-300 hover:bg-red-500/30 transition-colors text-xs"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const { totals, daily, topPosters, topReferrers, devices, scrollDepth } = data;
  const totalDevices = devices.mobile + devices.desktop + devices.tablet;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">DovShop Analytics</h1>
          <p className="text-sm text-gray-500 mt-1">{data.period}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-dark-card border border-dark-border rounded-lg overflow-hidden">
            {[7, 30].map((d) => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-3 py-1.5 text-sm transition-colors ${
                  days === d
                    ? 'bg-accent text-dark-bg font-medium'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {d}d
              </button>
            ))}
          </div>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="px-4 py-1.5 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors disabled:opacity-50"
          >
            {syncing ? 'Syncing...' : 'Sync'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">&#10005;</button>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-dark-card border border-dark-border rounded-lg p-5">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Visitors</div>
          <div className="text-2xl font-bold text-purple-400 tabular-nums">
            {totals.uniqueVisitors.toLocaleString()}
          </div>
          <div className="text-xs text-gray-600 mt-1">{totals.pageViews.toLocaleString()} page views</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-5">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Etsy Clicks</div>
          <div className="text-2xl font-bold text-orange-400 tabular-nums">
            {totals.etsyClicks.toLocaleString()}
          </div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-5">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">CTR</div>
          <div className="text-2xl font-bold text-blue-400 tabular-nums">
            {totals.ctr.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-600 mt-1">clicks / views</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-5">
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Avg Time</div>
          <div className="text-2xl font-bold text-green-400 tabular-nums">
            {totals.avgTimeOnPage > 60
              ? `${Math.floor(totals.avgTimeOnPage / 60)}m ${Math.round(totals.avgTimeOnPage % 60)}s`
              : `${Math.round(totals.avgTimeOnPage)}s`}
          </div>
          <div className="text-xs text-gray-600 mt-1">on page</div>
        </div>
      </div>

      {/* Daily Chart */}
      <div className="bg-dark-card border border-dark-border rounded-lg p-5">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
          Daily Views &amp; Clicks
        </h2>
        <DailyChart data={daily} />
      </div>

      {/* Two columns: Posters + Right side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Posters */}
        <div className="bg-dark-card border border-dark-border rounded-lg p-5">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
            Top Posters
          </h2>
          {topPosters.length > 0 ? (
            <div className="space-y-0">
              <div className="grid grid-cols-[1fr_60px_60px_50px] gap-2 text-xs text-gray-500 uppercase tracking-wider pb-2 border-b border-dark-border">
                <span>Poster</span>
                <span className="text-right">Views</span>
                <span className="text-right">Clicks</span>
                <span className="text-right">CTR</span>
              </div>
              {topPosters.map((p) => (
                <div
                  key={p.posterId}
                  className="grid grid-cols-[1fr_60px_60px_50px] gap-2 py-2.5 border-b border-dark-border/50 text-sm"
                >
                  <a
                    href={`https://dovshop.org/poster/${p.slug}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-300 hover:text-accent transition-colors truncate"
                  >
                    {p.name}
                  </a>
                  <span className="text-right text-gray-400 tabular-nums">{p.views}</span>
                  <span className="text-right text-orange-400 tabular-nums">{p.etsyClicks}</span>
                  <span className="text-right text-blue-400 tabular-nums">{p.ctr.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-600 text-sm py-4 text-center">No poster data yet</div>
          )}
        </div>

        {/* Right column: Referrers + Devices */}
        <div className="space-y-6">
          {/* Referrer Sources */}
          <div className="bg-dark-card border border-dark-border rounded-lg p-5">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
              Referrer Sources
            </h2>
            {topReferrers.length > 0 ? (
              <div className="space-y-3">
                {topReferrers.map((r) => {
                  const maxVisits = topReferrers[0].visits || 1;
                  const width = Math.max((r.visits / maxVisits) * 100, 4);
                  return (
                    <div key={r.source}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-300">{r.source}</span>
                        <span className="text-gray-500 tabular-nums">{r.visits}</span>
                      </div>
                      <div className="w-full bg-dark-bg rounded-full h-2">
                        <div
                          className="bg-accent/60 h-2 rounded-full transition-all"
                          style={{ width: `${width}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-gray-600 text-sm py-4 text-center">No referrer data yet</div>
            )}
          </div>

          {/* Device Split */}
          <div className="bg-dark-card border border-dark-border rounded-lg p-5">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
              Devices
            </h2>
            {totalDevices > 0 ? (
              <div className="space-y-3">
                {[
                  { label: 'Mobile', value: devices.mobile, color: 'bg-blue-500/60' },
                  { label: 'Desktop', value: devices.desktop, color: 'bg-purple-500/60' },
                  { label: 'Tablet', value: devices.tablet, color: 'bg-green-500/60' },
                ].map((d) => {
                  const pct = totalDevices > 0 ? (d.value / totalDevices) * 100 : 0;
                  return (
                    <div key={d.label}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-300">{d.label}</span>
                        <span className="text-gray-500 tabular-nums">{pct.toFixed(1)}%</span>
                      </div>
                      <div className="w-full bg-dark-bg rounded-full h-2">
                        <div
                          className={`${d.color} h-2 rounded-full transition-all`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-gray-600 text-sm py-4 text-center">No device data yet</div>
            )}
          </div>
        </div>
      </div>

      {/* Scroll Depth */}
      {scrollDepth && Object.keys(scrollDepth).length > 0 && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-5">
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
            Scroll Depth
          </h2>
          <div className="flex items-end gap-4 h-32">
            {['25', '50', '75', '100'].map((pct) => {
              const value = scrollDepth[pct] || 0;
              const maxVal = Math.max(...Object.values(scrollDepth), 1);
              const height = value > 0 ? Math.max((value / maxVal) * 100, 4) : 2;
              return (
                <div key={pct} className="flex-1 flex flex-col items-center gap-2">
                  <div className="w-full flex items-end justify-center h-24">
                    <div
                      className="w-full max-w-[60px] bg-accent/50 hover:bg-accent/70 rounded-t transition-colors"
                      style={{ height: `${height}%` }}
                      title={`${pct}%: ${value} users`}
                    />
                  </div>
                  <div className="text-xs text-gray-500">{pct}%</div>
                  <div className="text-xs text-gray-400 tabular-nums">{value}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/** Daily bar chart showing page views and Etsy clicks side by side */
function DailyChart({ data }: { data: DovShopAnalytics['daily'] }) {
  if (!data || data.length === 0) {
    return <div className="text-gray-600 text-sm py-8 text-center">No daily data yet</div>;
  }

  const maxVal = Math.max(...data.map((d) => Math.max(d.pageViews, d.etsyClicks)), 1);

  return (
    <div>
      <div className="flex items-end gap-0.5 h-36">
        {data.map((d) => {
          const viewsH = d.pageViews > 0 ? Math.max((d.pageViews / maxVal) * 100, 3) : 1;
          const clicksH = d.etsyClicks > 0 ? Math.max((d.etsyClicks / maxVal) * 100, 3) : 1;
          const dateLabel = new Date(d.date + 'T00:00:00').toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
          });
          return (
            <div key={d.date} className="flex-1 h-full group relative flex items-end justify-center gap-px">
              <div
                className="flex-1 bg-purple-500/60 hover:bg-purple-400/80 rounded-t transition-colors"
                style={{ height: `${viewsH}%` }}
              />
              <div
                className="flex-1 bg-orange-500/60 hover:bg-orange-400/80 rounded-t transition-colors"
                style={{ height: `${clicksH}%` }}
              />
              {/* Tooltip */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block z-10">
                <div className="bg-dark-bg border border-dark-border rounded px-2 py-1 text-xs text-gray-300 whitespace-nowrap">
                  <div className="font-medium">{dateLabel}</div>
                  <div className="text-purple-400">{d.pageViews} views</div>
                  <div className="text-orange-400">{d.etsyClicks} clicks</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-purple-500/60" />
          <span>Page Views</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm bg-orange-500/60" />
          <span>Etsy Clicks</span>
        </div>
      </div>
    </div>
  );
}
