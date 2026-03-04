'use client';

import { useState, useEffect } from 'react';
import {
  getPinterestStatus,
  getPinterestAuthUrl,
  disconnectPinterest,
  getPinterestBoards,
  getPinterestQueuedPins,
  getPinterestPublishedPins,
  publishPinterestPinsNow,
  getPinterestAnalyticsSummary,
  syncPinterestAnalytics,
  deletePinterestPin,
  bulkGeneratePinterestPins,
  PinterestStatus,
  PinterestBoard,
  PinterestPin,
  PinterestStats,
} from '@/lib/api';

type Tab = 'queue' | 'published' | 'bulk' | 'analytics';

export default function PinterestPage() {
  const [status, setStatus] = useState<PinterestStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('queue');

  // Boards
  const [boards, setBoards] = useState<PinterestBoard[]>([]);

  // Queue
  const [queuedPins, setQueuedPins] = useState<PinterestPin[]>([]);
  const [queueLoading, setQueueLoading] = useState(false);
  const [publishing, setPublishing] = useState(false);

  // Published
  const [publishedPins, setPublishedPins] = useState<PinterestPin[]>([]);
  const [publishedLoading, setPublishedLoading] = useState(false);

  // Bulk
  const [selectedBoard, setSelectedBoard] = useState('');
  const [productIds, setProductIds] = useState('');
  const [pinsPerProduct, setPinsPerProduct] = useState(2);
  const [intervalHours, setIntervalHours] = useState(3);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResult, setBulkResult] = useState<{ results: Array<{ product_id: number; pin_id?: number; title?: string; error?: string }>; queued: number; first_post?: string; interval_hours?: number } | null>(null);

  // Analytics
  const [stats, setStats] = useState<PinterestStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    loadStatus();

    // Listen for OAuth callback
    const handler = (event: MessageEvent) => {
      if (event.data === 'pinterest-connected') {
        loadStatus();
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  useEffect(() => {
    if (!status?.connected) return;
    if (tab === 'queue') loadQueue();
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
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Disconnect Pinterest?')) return;
    await disconnectPinterest();
    setStatus({ configured: true, connected: false });
    setBoards([]);
  };

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
      loadQueue();
      loadPublished();
    } catch (err) { setError((err as Error).message); }
  };

  const handleBulkGenerate = async () => {
    if (!selectedBoard || !productIds.trim()) return;
    setBulkLoading(true);
    setBulkResult(null);
    try {
      const ids = productIds.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
      const result = await bulkGeneratePinterestPins(ids, selectedBoard, pinsPerProduct, intervalHours);
      setBulkResult(result);
      loadQueue();
    } catch (err) { setError((err as Error).message); }
    finally { setBulkLoading(false); }
  };

  const handleSyncAnalytics = async () => {
    setSyncing(true);
    try {
      await syncPinterestAnalytics();
      loadAnalytics();
    } catch (err) { setError((err as Error).message); }
    finally { setSyncing(false); }
  };

  if (loading) return <div className="p-6 text-gray-400">Loading...</div>;

  // Not configured
  if (!status?.configured) {
    return (
      <div className="p-6">
        <h2 className="text-xl font-bold text-white mb-4">Pinterest</h2>
        <p className="text-gray-400">PINTEREST_APP_ID and PINTEREST_APP_SECRET not configured in .env</p>
      </div>
    );
  }

  // Not connected
  if (!status?.connected) {
    return (
      <div className="p-6">
        <h2 className="text-xl font-bold text-white mb-4">Pinterest</h2>
        <p className="text-gray-400 mb-4">Connect your Pinterest account to start pinning your products.</p>
        {status?.error && <p className="text-red-400 mb-4">{status.error}</p>}
        <button
          onClick={handleConnect}
          className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded font-medium"
        >
          Connect Pinterest
        </button>
      </div>
    );
  }

  // Connected
  return (
    <div className="p-6">
      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 text-red-400 hover:text-red-200">X</button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white">Pinterest</h2>
          <p className="text-sm text-gray-400">
            Connected as <span className="text-green-400">{status.username || 'user'}</span>
            {' '}&middot;{' '}
            {boards.length} board{boards.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={handleDisconnect}
          className="px-3 py-1.5 text-sm text-gray-400 hover:text-red-400 border border-gray-700 rounded"
        >
          Disconnect
        </button>
      </div>

      {/* Sub-tabs */}
      <div className="flex gap-1 mb-6 bg-gray-800/50 rounded-lg p-1">
        {(['queue', 'published', 'bulk', 'analytics'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === t ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {t === 'queue' ? `Queue (${queuedPins.length})` : t === 'published' ? 'Published' : t === 'bulk' ? 'Bulk Generate' : 'Analytics'}
          </button>
        ))}
      </div>

      {/* Queue Tab */}
      {tab === 'queue' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Pin Queue</h3>
            <button
              onClick={handlePublishNow}
              disabled={publishing || queuedPins.length === 0}
              className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded text-sm font-medium"
            >
              {publishing ? 'Publishing...' : 'Publish All Now'}
            </button>
          </div>
          {queueLoading ? (
            <p className="text-gray-400">Loading queue...</p>
          ) : queuedPins.length === 0 ? (
            <p className="text-gray-500">No pins in queue. Use Bulk Generate to add pins.</p>
          ) : (
            <div className="space-y-3">
              {queuedPins.map(pin => (
                <div key={pin.id} className="flex gap-4 p-4 bg-gray-800 rounded-lg border border-gray-700">
                  {pin.image_url && (
                    <img src={pin.image_url} alt="" className="w-16 h-20 object-cover rounded" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium truncate">{pin.title}</p>
                    <p className="text-gray-400 text-sm truncate">{pin.description}</p>
                    <p className="text-gray-500 text-xs mt-1">Board: {pin.board_id}</p>
                  </div>
                  <button
                    onClick={() => handleDeletePin(pin.id)}
                    className="text-gray-500 hover:text-red-400 text-sm"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Published Tab */}
      {tab === 'published' && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">Published Pins</h3>
          {publishedLoading ? (
            <p className="text-gray-400">Loading...</p>
          ) : publishedPins.length === 0 ? (
            <p className="text-gray-500">No published pins yet.</p>
          ) : (
            <div className="space-y-3">
              {publishedPins.map(pin => (
                <div key={pin.id} className="flex gap-4 p-4 bg-gray-800 rounded-lg border border-gray-700">
                  {(pin.product_image_url || pin.image_url) && (
                    <img src={pin.product_image_url || pin.image_url} alt="" className="w-16 h-20 object-cover rounded" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium truncate">{pin.title}</p>
                    <p className="text-gray-400 text-sm">{pin.product_title}</p>
                    <div className="flex gap-4 mt-2 text-xs text-gray-500">
                      <span>{pin.impressions || 0} impressions</span>
                      <span>{pin.saves || 0} saves</span>
                      <span>{pin.clicks || 0} clicks</span>
                      <span>{pin.outbound_clicks || 0} outbound</span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeletePin(pin.id, true)}
                    className="text-gray-500 hover:text-red-400 text-sm"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Bulk Generate Tab */}
      {tab === 'bulk' && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">Bulk Generate Pins</h3>
          <p className="text-gray-400 text-sm mb-4">
            AI-generate Pinterest-optimized pin content for multiple products and add them to the queue.
          </p>
          <div className="space-y-4 max-w-lg">
            <div>
              <label className="block text-sm text-gray-300 mb-1">Board</label>
              <select
                value={selectedBoard}
                onChange={e => setSelectedBoard(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white"
              >
                {boards.map(b => (
                  <option key={b.id || b.board_id} value={b.id || b.board_id}>
                    {b.name} ({b.pin_count || 0} pins)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">Product IDs (comma-separated)</label>
              <input
                type="text"
                value={productIds}
                onChange={e => setProductIds(e.target.value)}
                placeholder="1, 2, 3, 4, 5"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white"
              />
            </div>
            <div className="flex gap-4">
              <div>
                <label className="block text-sm text-gray-300 mb-1">Pins per product</label>
                <select
                  value={pinsPerProduct}
                  onChange={e => setPinsPerProduct(parseInt(e.target.value))}
                  className="px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white"
                >
                  <option value={1}>1 pin</option>
                  <option value={2}>2 pins</option>
                  <option value={3}>3 pins</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-300 mb-1">Interval between pins</label>
                <select
                  value={intervalHours}
                  onChange={e => setIntervalHours(parseInt(e.target.value))}
                  className="px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white"
                >
                  <option value={2}>2 hours</option>
                  <option value={3}>3 hours</option>
                  <option value={4}>4 hours</option>
                  <option value={6}>6 hours</option>
                  <option value={12}>12 hours</option>
                </select>
              </div>
            </div>
            <button
              onClick={handleBulkGenerate}
              disabled={bulkLoading || !selectedBoard || !productIds.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded text-sm font-medium"
            >
              {bulkLoading ? 'Generating...' : 'Generate & Queue Pins'}
            </button>
          </div>
          {bulkResult && (
            <div className="mt-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
              <p className="text-green-400 font-medium mb-2">{bulkResult.queued} pins queued</p>
              <div className="space-y-1">
                {bulkResult.results.map((r, i) => (
                  <p key={i} className={`text-sm ${r.error ? 'text-red-400' : 'text-gray-300'}`}>
                    Product #{r.product_id}: {r.error || r.title}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Analytics Tab */}
      {tab === 'analytics' && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Analytics</h3>
            <button
              onClick={handleSyncAnalytics}
              disabled={syncing}
              className="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white rounded"
            >
              {syncing ? 'Syncing...' : 'Sync Analytics'}
            </button>
          </div>
          {statsLoading ? (
            <p className="text-gray-400">Loading...</p>
          ) : stats ? (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {[
                { label: 'Published', value: stats.total_published, color: 'text-green-400' },
                { label: 'Queued', value: stats.total_queued, color: 'text-yellow-400' },
                { label: 'Impressions', value: stats.total_impressions.toLocaleString(), color: 'text-blue-400' },
                { label: 'Saves', value: stats.total_saves.toLocaleString(), color: 'text-pink-400' },
                { label: 'Clicks', value: stats.total_clicks.toLocaleString(), color: 'text-purple-400' },
                { label: 'Outbound Clicks', value: stats.total_outbound_clicks.toLocaleString(), color: 'text-orange-400' },
              ].map(stat => (
                <div key={stat.label} className="p-4 bg-gray-800 rounded-lg border border-gray-700">
                  <p className="text-gray-400 text-sm">{stat.label}</p>
                  <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">No analytics data yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
