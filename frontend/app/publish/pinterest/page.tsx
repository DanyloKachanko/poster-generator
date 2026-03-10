'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  getPinterestStatus,
  getPinterestAuthUrl,
  disconnectPinterest,
  getPinterestBoards,
  getPinterestProducts,
  getPinterestQueuedPins,
  getPinterestPublishedPins,
  publishPinterestPinsNow,
  getPinterestAnalyticsSummary,
  syncPinterestAnalytics,
  deletePinterestPin,
  bulkGeneratePinterestPins,
  PinterestStatus,
  PinterestBoard,
  PinterestProduct,
  PinterestPin,
  PinterestStats,
} from '@/lib/api';

type Tab = 'products' | 'queue' | 'published' | 'analytics';

export default function PinterestPage() {
  const [status, setStatus] = useState<PinterestStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('products');

  // Boards
  const [boards, setBoards] = useState<PinterestBoard[]>([]);
  const [selectedBoard, setSelectedBoard] = useState('');

  // Products
  const [products, setProducts] = useState<PinterestProduct[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [generateResult, setGenerateResult] = useState<{
    results: Array<{ product_id: number; pin_id?: number; title?: string; error?: string; scheduled_est?: string; image_url?: string }>;
    queued: number;
  } | null>(null);

  // Queue
  const [queuedPins, setQueuedPins] = useState<PinterestPin[]>([]);
  const [queueLoading, setQueueLoading] = useState(false);
  const [publishing, setPublishing] = useState(false);

  // Published
  const [publishedPins, setPublishedPins] = useState<PinterestPin[]>([]);
  const [publishedLoading, setPublishedLoading] = useState(false);

  // Analytics
  const [stats, setStats] = useState<PinterestStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    loadStatus();
    const handler = (event: MessageEvent) => {
      if (event.data === 'pinterest-connected') loadStatus();
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  useEffect(() => {
    if (!status?.connected) return;
    if (tab === 'products') loadProducts();
    else if (tab === 'queue') loadQueue();
    else if (tab === 'published') loadPublished();
    else if (tab === 'analytics') loadAnalytics();
  }, [tab, status?.connected]);

  const loadStatus = async () => {
    try {
      const s = await getPinterestStatus();
      setStatus(s);
      if (s.connected) {
        const { boards: b } = await getPinterestBoards();
        setBoards(b);
        if (b.length > 0 && !selectedBoard) {
          setSelectedBoard(b[0].id || b[0].board_id || '');
        }
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadProducts = async () => {
    setProductsLoading(true);
    try {
      const { products: p } = await getPinterestProducts();
      setProducts(p);
    } catch (err) { setError((err as Error).message); }
    finally { setProductsLoading(false); }
  };

  const loadQueue = async () => {
    setQueueLoading(true);
    try {
      const { pins } = await getPinterestQueuedPins();
      setQueuedPins(pins);
    } catch (err) { setError((err as Error).message); }
    finally { setQueueLoading(false); }
  };

  const loadPublished = async () => {
    setPublishedLoading(true);
    try {
      const { pins } = await getPinterestPublishedPins();
      setPublishedPins(pins);
    } catch (err) { setError((err as Error).message); }
    finally { setPublishedLoading(false); }
  };

  const loadAnalytics = async () => {
    setStatsLoading(true);
    try {
      const s = await getPinterestAnalyticsSummary();
      setStats(s);
    } catch (err) { setError((err as Error).message); }
    finally { setStatsLoading(false); }
  };

  const handleConnect = async () => {
    try {
      const { url } = await getPinterestAuthUrl();
      window.open(url, 'pinterest-auth', 'width=600,height=700');
    } catch (err) { setError((err as Error).message); }
  };

  const handleDisconnect = async () => {
    if (!confirm('Disconnect Pinterest?')) return;
    await disconnectPinterest();
    setStatus({ configured: true, connected: false });
    setBoards([]);
  };

  // Products tab
  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === products.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(products.map(p => p.id)));
    }
  };

  const handleGenerate = async () => {
    if (!selectedBoard || selectedIds.size === 0) return;
    setGenerating(true);
    setGenerateResult(null);
    try {
      const result = await bulkGeneratePinterestPins(Array.from(selectedIds), selectedBoard);
      setGenerateResult(result);
      setSelectedIds(new Set());
      loadProducts();
    } catch (err) { setError((err as Error).message); }
    finally { setGenerating(false); }
  };

  // Queue tab
  const handlePublishNow = async () => {
    setPublishing(true);
    try {
      const result = await publishPinterestPinsNow();
      alert(`Published: ${result.published}, Failed: ${result.failed}`);
      loadQueue();
    } catch (err) { setError((err as Error).message); }
    finally { setPublishing(false); }
  };

  const handleDeletePin = async (pinId: number, fromPinterest: boolean = false) => {
    if (!confirm('Delete this pin?')) return;
    try {
      await deletePinterestPin(pinId, fromPinterest);
      if (tab === 'queue') loadQueue();
      else loadPublished();
    } catch (err) { setError((err as Error).message); }
  };

  // Analytics
  const handleSyncAnalytics = async () => {
    setSyncing(true);
    try {
      await syncPinterestAnalytics();
      loadAnalytics();
    } catch (err) { setError((err as Error).message); }
    finally { setSyncing(false); }
  };

  // Group queued pins by day for timeline view
  const queueByDay = useMemo(() => {
    const groups: Record<string, PinterestPin[]> = {};
    for (const pin of queuedPins) {
      const dateStr = pin.scheduled_at
        ? new Date(pin.scheduled_at).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'America/New_York' })
        : 'Unscheduled';
      if (!groups[dateStr]) groups[dateStr] = [];
      groups[dateStr].push(pin);
    }
    return groups;
  }, [queuedPins]);

  if (loading) return <div className="p-8 text-gray-400 text-lg">Loading...</div>;

  if (!status?.configured) {
    return (
      <div className="p-8">
        <h2 className="text-2xl font-bold text-white mb-4">Pinterest</h2>
        <p className="text-gray-400 text-lg">PINTEREST_APP_ID and PINTEREST_APP_SECRET not configured in .env</p>
      </div>
    );
  }

  if (!status?.connected) {
    return (
      <div className="p-8">
        <h2 className="text-2xl font-bold text-white mb-4">Pinterest</h2>
        <p className="text-gray-400 mb-6 text-lg">Connect your Pinterest account to start pinning your products.</p>
        {status?.error && <p className="text-red-400 mb-4 text-base">{status.error}</p>}
        <button onClick={handleConnect} className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium text-base">
          Connect Pinterest
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-[1600px] mx-auto">
      {error && (
        <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-lg text-red-300 text-base flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-4 text-red-400 hover:text-red-200 font-bold text-lg">X</button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-white">Pinterest</h2>
          <p className="text-base text-gray-400 mt-1">
            Connected as <span className="text-green-400 font-medium">{status.username || 'user'}</span>
            {' '}&middot;{' '}
            {boards.length} board{boards.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button onClick={handleDisconnect} className="px-4 py-2 text-base text-gray-400 hover:text-red-400 border border-gray-700 rounded-lg transition-colors">
          Disconnect
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-8 bg-gray-800/50 rounded-xl p-1.5">
        {([
          { key: 'products' as Tab, label: `Products (${products.length})` },
          { key: 'queue' as Tab, label: `Queue (${queuedPins.length})` },
          { key: 'published' as Tab, label: 'Published' },
          { key: 'analytics' as Tab, label: 'Analytics' },
        ]).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-6 py-2.5 rounded-lg text-base font-medium transition-colors ${
              tab === t.key ? 'bg-gray-700 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ===== Products Tab ===== */}
      {tab === 'products' && (
        <div>
          {/* Top bar: board selector + generate button */}
          <div className="flex items-center gap-4 mb-6 p-4 bg-gray-800/50 rounded-xl border border-gray-700/50">
            <select
              value={selectedBoard}
              onChange={e => setSelectedBoard(e.target.value)}
              className="px-4 py-2.5 bg-gray-800 border border-gray-600 rounded-lg text-white text-base min-w-[250px]"
            >
              {boards.map(b => (
                <option key={b.id || b.board_id} value={b.id || b.board_id}>
                  {b.name} ({b.pin_count || 0} pins)
                </option>
              ))}
            </select>
            <button
              onClick={handleGenerate}
              disabled={generating || selectedIds.size === 0 || !selectedBoard}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-base font-medium transition-colors"
            >
              {generating ? `Generating ${selectedIds.size} pins...` : `Generate & Queue (${selectedIds.size})`}
            </button>
            {selectedIds.size > 0 && (
              <span className="text-gray-400 text-base ml-2">{selectedIds.size} selected</span>
            )}
          </div>

          {/* Generate result */}
          {generateResult && (
            <div className="mb-6 p-5 bg-gray-800 rounded-xl border border-gray-700">
              <p className="text-green-400 font-semibold text-lg mb-3">{generateResult.queued} pins queued</p>
              <div className="space-y-2">
                {generateResult.results.map((r, i) => (
                  <p key={i} className={`text-base ${r.error ? 'text-red-400' : 'text-gray-300'}`}>
                    Product #{r.product_id}: {r.error || `${r.title} — ${r.scheduled_est}`}
                  </p>
                ))}
              </div>
            </div>
          )}

          {productsLoading ? (
            <p className="text-gray-400 text-lg">Loading products...</p>
          ) : products.length === 0 ? (
            <p className="text-gray-500 text-lg">No published products found (need etsy_listing_id).</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {/* Select All header */}
              <div className="col-span-full flex items-center gap-3 mb-2">
                <input
                  type="checkbox"
                  checked={selectedIds.size === products.length && products.length > 0}
                  onChange={toggleSelectAll}
                  className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-blue-500"
                />
                <span className="text-gray-400 text-base">
                  {selectedIds.size === products.length ? 'Deselect all' : 'Select all'} ({products.length} products)
                </span>
              </div>

              {products.map(p => (
                <div
                  key={p.id}
                  onClick={() => toggleSelect(p.id)}
                  className={`flex gap-4 p-4 rounded-xl border cursor-pointer transition-all ${
                    selectedIds.has(p.id)
                      ? 'bg-blue-900/20 border-blue-600/50 ring-1 ring-blue-500/30'
                      : 'bg-gray-800/60 border-gray-700/50 hover:bg-gray-800 hover:border-gray-600'
                  }`}
                >
                  <div className="relative shrink-0">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(p.id)}
                      onChange={() => toggleSelect(p.id)}
                      onClick={e => e.stopPropagation()}
                      className="absolute top-1 left-1 w-4 h-4 rounded bg-gray-700/80 border-gray-600 text-blue-500 z-10"
                    />
                    {p.image_url ? (
                      <img src={p.image_url} alt="" className="w-20 h-24 object-cover rounded-lg" />
                    ) : (
                      <div className="w-20 h-24 bg-gray-700 rounded-lg" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0 flex flex-col justify-between">
                    <p className="text-white font-medium text-base leading-snug line-clamp-2">{p.title}</p>
                    <div className="flex gap-4 mt-2">
                      <div className="text-center">
                        <p className={`text-lg font-semibold ${p.mockup_count > 0 ? 'text-green-400' : 'text-gray-600'}`}>{p.mockup_count}</p>
                        <p className="text-xs text-gray-500">mockups</p>
                      </div>
                      <div className="text-center">
                        <p className={`text-lg font-semibold ${p.queued_pins > 0 ? 'text-yellow-400' : 'text-gray-600'}`}>{p.queued_pins}</p>
                        <p className="text-xs text-gray-500">queued</p>
                      </div>
                      <div className="text-center">
                        <p className={`text-lg font-semibold ${p.published_pins > 0 ? 'text-blue-400' : 'text-gray-600'}`}>{p.published_pins}</p>
                        <p className="text-xs text-gray-500">published</p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===== Queue Tab ===== */}
      {tab === 'queue' && (
        <div>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-white">Pin Queue</h3>
            <button
              onClick={handlePublishNow}
              disabled={publishing || queuedPins.length === 0}
              className="px-6 py-2.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg text-base font-medium transition-colors"
            >
              {publishing ? 'Publishing...' : 'Publish All Now'}
            </button>
          </div>
          {queueLoading ? (
            <p className="text-gray-400 text-lg">Loading queue...</p>
          ) : queuedPins.length === 0 ? (
            <p className="text-gray-500 text-lg">No pins in queue. Go to Products tab to generate pins.</p>
          ) : (
            <div className="space-y-8">
              {Object.entries(queueByDay).map(([day, pins]) => (
                <div key={day}>
                  <h4 className="text-base font-semibold text-gray-300 mb-3 pb-2 border-b border-gray-700">{day}</h4>
                  <div className="space-y-3">
                    {pins.map(pin => {
                      const timeStr = pin.scheduled_at
                        ? new Date(pin.scheduled_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'America/New_York' })
                        : '--:--';
                      return (
                        <div key={pin.id} className="flex items-center gap-4 p-4 bg-gray-800/60 rounded-xl border border-gray-700/50 hover:bg-gray-800 transition-colors">
                          <span className="text-base text-gray-300 font-mono w-20 shrink-0 font-medium">{timeStr}</span>
                          {pin.image_url && (
                            <img src={pin.image_url} alt="" className="w-14 h-18 object-cover rounded-lg shrink-0" />
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-white text-base font-medium truncate">{pin.title}</p>
                            <p className="text-gray-500 text-sm truncate mt-0.5">{pin.description}</p>
                          </div>
                          <button
                            onClick={() => handleDeletePin(pin.id)}
                            className="text-gray-500 hover:text-red-400 text-base px-3 py-1.5 rounded-lg hover:bg-red-900/20 transition-colors shrink-0"
                          >
                            Remove
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===== Published Tab ===== */}
      {tab === 'published' && (
        <div>
          <h3 className="text-xl font-semibold text-white mb-6">Published Pins</h3>
          {publishedLoading ? (
            <p className="text-gray-400 text-lg">Loading...</p>
          ) : publishedPins.length === 0 ? (
            <p className="text-gray-500 text-lg">No published pins yet.</p>
          ) : (
            <div className="space-y-4">
              {publishedPins.map(pin => (
                <div key={pin.id} className="flex gap-5 p-5 bg-gray-800/60 rounded-xl border border-gray-700/50 hover:bg-gray-800 transition-colors">
                  {(pin.product_image_url || pin.image_url) && (
                    <img src={pin.product_image_url || pin.image_url} alt="" className="w-20 h-24 object-cover rounded-lg shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium text-base truncate">{pin.title}</p>
                    <p className="text-gray-400 text-sm mt-1">{pin.product_title}</p>
                    <div className="flex gap-6 mt-3 text-sm">
                      <span className="text-blue-400"><span className="font-semibold">{pin.impressions || 0}</span> <span className="text-gray-500">impressions</span></span>
                      <span className="text-pink-400"><span className="font-semibold">{pin.saves || 0}</span> <span className="text-gray-500">saves</span></span>
                      <span className="text-purple-400"><span className="font-semibold">{pin.clicks || 0}</span> <span className="text-gray-500">clicks</span></span>
                      <span className="text-orange-400"><span className="font-semibold">{pin.outbound_clicks || 0}</span> <span className="text-gray-500">outbound</span></span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeletePin(pin.id, true)}
                    className="text-gray-500 hover:text-red-400 text-base px-3 py-1.5 rounded-lg hover:bg-red-900/20 transition-colors shrink-0"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===== Analytics Tab ===== */}
      {tab === 'analytics' && (
        <div>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-semibold text-white">Analytics</h3>
            <button
              onClick={handleSyncAnalytics}
              disabled={syncing}
              className="px-5 py-2.5 text-base bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white rounded-lg transition-colors"
            >
              {syncing ? 'Syncing...' : 'Sync Analytics'}
            </button>
          </div>
          {statsLoading ? (
            <p className="text-gray-400 text-lg">Loading...</p>
          ) : stats ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
              {[
                { label: 'Published', value: stats.total_published, color: 'text-green-400' },
                { label: 'Queued', value: stats.total_queued, color: 'text-yellow-400' },
                { label: 'Impressions', value: stats.total_impressions.toLocaleString(), color: 'text-blue-400' },
                { label: 'Saves', value: stats.total_saves.toLocaleString(), color: 'text-pink-400' },
                { label: 'Clicks', value: stats.total_clicks.toLocaleString(), color: 'text-purple-400' },
                { label: 'Outbound Clicks', value: stats.total_outbound_clicks.toLocaleString(), color: 'text-orange-400' },
              ].map(stat => (
                <div key={stat.label} className="p-6 bg-gray-800/60 rounded-xl border border-gray-700/50">
                  <p className="text-gray-400 text-base mb-1">{stat.label}</p>
                  <p className={`text-3xl font-bold ${stat.color}`}>{stat.value}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-lg">No analytics data yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
