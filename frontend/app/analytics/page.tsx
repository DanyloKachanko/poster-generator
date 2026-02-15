'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  getAnalytics,
  saveAnalytics,
  getEtsyStatus,
  getEtsyAuthUrl,
  syncEtsyAnalytics,
  syncEtsyOrders,
  disconnectEtsy,
  AnalyticsProduct,
  AnalyticsTotals,
  EtsyStatus,
} from '@/lib/api';

type SortKey = 'title' | 'total_views' | 'total_favorites' | 'total_orders' | 'total_revenue_cents' | 'latest_date';
type SortDir = 'asc' | 'desc';
type StatusFilter = 'all' | 'on_etsy' | 'deleted' | 'draft';

export default function AnalyticsPage() {
  const [products, setProducts] = useState<AnalyticsProduct[]>([]);
  const [totals, setTotals] = useState<AnalyticsTotals | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('total_views');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ views: 0, favorites: 0, orders: 0, revenue_cents: 0, notes: '' });
  const [saving, setSaving] = useState(false);

  // Etsy state
  const [etsyStatus, setEtsyStatus] = useState<EtsyStatus | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const loadData = useCallback(() => {
    setIsLoading(true);
    setError(null);
    getAnalytics()
      .then((data) => {
        setProducts(data.products);
        setTotals(data.totals);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });
  }, []);

  const loadEtsyStatus = useCallback(() => {
    getEtsyStatus().then(setEtsyStatus).catch(() => {});
  }, []);

  useEffect(() => {
    loadData();
    loadEtsyStatus();
  }, [loadData, loadEtsyStatus]);

  // Listen for OAuth callback message
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data === 'etsy-connected') {
        loadEtsyStatus();
        setSyncMessage('Etsy connected! Click "Sync from Etsy" to fetch data.');
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [loadEtsyStatus]);

  const handleConnectEtsy = async () => {
    try {
      const { url } = await getEtsyAuthUrl();
      window.open(url, 'etsy-oauth', 'width=600,height=700');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start Etsy connection');
    }
  };

  const handleDisconnectEtsy = async () => {
    try {
      await disconnectEtsy();
      setEtsyStatus({ configured: true, connected: false });
      setSyncMessage(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncMessage(null);
    setError(null);
    try {
      const result = await syncEtsyAnalytics();
      const ordersResult = await syncEtsyOrders().catch(() => ({ synced: 0 }));
      setSyncMessage(`Synced ${result.synced} listings + ${ordersResult.synced} orders (${result.date})`);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const filtered = statusFilter === 'all'
    ? products
    : products.filter((p) => p.status === statusFilter);

  const sorted = [...filtered].sort((a, b) => {
    let av: string | number = a[sortKey] ?? '';
    let bv: string | number = b[sortKey] ?? '';
    if (typeof av === 'string') {
      const cmp = av.localeCompare(bv as string);
      return sortDir === 'asc' ? cmp : -cmp;
    }
    return sortDir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number);
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sortIcon = (key: SortKey) => {
    if (sortKey !== key) return '';
    return sortDir === 'asc' ? ' \u2191' : ' \u2193';
  };

  const startEdit = (p: AnalyticsProduct) => {
    setEditingId(p.printify_product_id);
    setEditForm({
      views: p.total_views,
      favorites: p.total_favorites,
      orders: p.total_orders,
      revenue_cents: p.total_revenue_cents,
      notes: '',
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const handleSave = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      await saveAnalytics({
        printify_product_id: editingId,
        date: today,
        views: editForm.views,
        favorites: editForm.favorites,
        orders: editForm.orders,
        revenue_cents: editForm.revenue_cents,
        notes: editForm.notes || undefined,
      });
      setEditingId(null);
      loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const formatPrice = (cents: number) => `$${(cents / 100).toFixed(2)}`;
  const formatRevenue = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'on_etsy':
        return 'bg-green-500/15 text-green-400 border-green-500/30';
      case 'visible':
        return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
      case 'deleted':
        return 'bg-red-500/15 text-red-400 border-red-500/30';
      default:
        return 'bg-gray-500/15 text-gray-400 border-gray-500/30';
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case 'on_etsy': return 'on etsy';
      case 'deleted': return 'deleted';
      default: return status;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-100">Analytics</h1>
        <div className="flex items-center gap-2">
          {etsyStatus?.connected && (
            <button
              onClick={handleSync}
              disabled={syncing}
              className="px-4 py-2 rounded-lg bg-orange-600 text-white text-sm font-medium hover:bg-orange-700 transition-colors disabled:opacity-50"
            >
              {syncing ? 'Syncing...' : 'Sync from Etsy'}
            </button>
          )}
          <button
            onClick={loadData}
            disabled={isLoading}
            className="px-4 py-2 rounded-lg bg-dark-card border border-dark-border text-sm text-gray-300 hover:bg-dark-hover transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Etsy connection banner */}
      {etsyStatus && !etsyStatus.connected && etsyStatus.configured && (
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg px-4 py-3 mb-6 flex items-center justify-between">
          <div>
            <span className="text-sm text-orange-400 font-medium">Etsy not connected</span>
            <span className="text-sm text-gray-400 ml-2">Connect to automatically sync views and favorites</span>
          </div>
          <button
            onClick={handleConnectEtsy}
            className="px-4 py-1.5 rounded-md bg-orange-600 text-white text-sm font-medium hover:bg-orange-700 transition-colors"
          >
            Connect Etsy
          </button>
        </div>
      )}

      {etsyStatus && !etsyStatus.configured && (
        <div className="bg-gray-500/10 border border-gray-500/30 rounded-lg px-4 py-3 mb-6 text-sm text-gray-400">
          Add <code className="bg-dark-hover px-1.5 py-0.5 rounded text-xs">ETSY_API_KEY</code> to .env to enable Etsy sync
        </div>
      )}

      {etsyStatus?.connected && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-3 mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400" />
            <span className="text-sm text-green-400 font-medium">Etsy connected</span>
            {syncMessage && <span className="text-sm text-gray-400 ml-2">{syncMessage}</span>}
          </div>
          <button
            onClick={handleDisconnectEtsy}
            className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            Disconnect
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 mb-6 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">&#10005;</button>
        </div>
      )}

      {/* Summary cards */}
      {totals && (
        <div className="space-y-4 mb-8">
          {/* Row 1: Main metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Views</div>
              <div className="text-2xl font-bold text-gray-100">{totals.total_views.toLocaleString()}</div>
              <div className="text-[10px] text-gray-600 mt-1">
                avg {totals.avg_views}/product
              </div>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Favorites</div>
              <div className="text-2xl font-bold text-gray-100">{totals.total_favorites.toLocaleString()}</div>
              <div className="text-[10px] text-gray-600 mt-1">
                {totals.fav_rate}% fav rate
              </div>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Orders</div>
              <div className="text-2xl font-bold text-gray-100">{totals.total_orders.toLocaleString()}</div>
              <div className="text-[10px] text-gray-600 mt-1">
                {totals.total_views > 0 ? ((totals.total_orders / totals.total_views) * 100).toFixed(1) : '0'}% conversion
              </div>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Revenue</div>
              <div className="text-2xl font-bold text-gray-100">{formatRevenue(totals.total_revenue_cents)}</div>
              <div className="text-[10px] text-gray-600 mt-1">
                {totals.total_orders > 0 ? formatRevenue(Math.round(totals.total_revenue_cents / totals.total_orders)) : '$0.00'} avg order
              </div>
            </div>
          </div>

          {/* Row 2: Product counts + best performer */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <div className="bg-dark-card border border-dark-border rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Total Products</div>
              <div className="text-lg font-bold text-gray-100">{totals.total_products}</div>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Live on Etsy</div>
              <div className="text-lg font-bold text-green-400">{totals.live_products}</div>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Drafts</div>
              <div className="text-lg font-bold text-gray-400">{totals.draft_products}</div>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Deleted</div>
              <div className={`text-lg font-bold ${(totals.deleted_products ?? 0) > 0 ? 'text-red-400' : 'text-gray-400'}`}>
                {totals.deleted_products ?? 0}
              </div>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-3">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">No Views Yet</div>
              <div className={`text-lg font-bold ${totals.products_no_views > 0 ? 'text-yellow-400' : 'text-gray-400'}`}>
                {totals.products_no_views}
              </div>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-3 md:col-span-1 col-span-2">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Top Performer</div>
              {totals.best_performer ? (
                <div className="text-sm font-medium text-accent truncate" title={totals.best_performer}>
                  {totals.best_performer}
                  <span className="text-[10px] text-gray-500 ml-1">({totals.best_performer_views} views)</span>
                </div>
              ) : (
                <div className="text-sm text-gray-600">--</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && products.length === 0 && (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && products.length === 0 && (
        <div className="text-center py-20">
          <div className="text-5xl mb-4 opacity-30">&#128202;</div>
          <h2 className="text-lg font-medium text-gray-400 mb-2">No products found</h2>
          <p className="text-gray-600 mb-4">Products from your Printify shop will appear here.</p>
          <Link
            href="/shop"
            className="inline-block px-4 py-2 rounded-lg bg-accent text-dark-bg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Go to Shop
          </Link>
        </div>
      )}

      {/* Filter tabs */}
      {products.length > 0 && (
        <div className="flex items-center gap-1 mb-4">
          {([
            { key: 'all' as StatusFilter, label: 'All', count: products.length },
            { key: 'on_etsy' as StatusFilter, label: 'On Etsy', count: products.filter(p => p.status === 'on_etsy').length },
            { key: 'draft' as StatusFilter, label: 'Drafts', count: products.filter(p => p.status === 'draft').length },
            { key: 'deleted' as StatusFilter, label: 'Deleted', count: products.filter(p => p.status === 'deleted').length },
          ]).filter(tab => tab.key === 'all' || tab.count > 0).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setStatusFilter(tab.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                statusFilter === tab.key
                  ? 'bg-accent/15 text-accent border border-accent/30'
                  : 'bg-dark-card border border-dark-border text-gray-400 hover:text-gray-300 hover:bg-dark-hover'
              }`}
            >
              {tab.label}
              <span className="ml-1.5 text-[10px] opacity-70">{tab.count}</span>
            </button>
          ))}
        </div>
      )}

      {/* Table */}
      {products.length > 0 && (
        <div className="bg-dark-card border border-dark-border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-dark-border text-left">
                  <th className="px-4 py-3 text-gray-500 font-medium w-12"></th>
                  <th
                    className="px-4 py-3 text-gray-500 font-medium cursor-pointer hover:text-gray-300 select-none"
                    onClick={() => handleSort('title')}
                  >
                    Product{sortIcon('title')}
                  </th>
                  <th className="px-4 py-3 text-gray-500 font-medium">Status</th>
                  <th className="px-4 py-3 text-gray-500 font-medium">Price</th>
                  <th
                    className="px-4 py-3 text-gray-500 font-medium cursor-pointer hover:text-gray-300 text-right select-none"
                    onClick={() => handleSort('total_views')}
                  >
                    Views{sortIcon('total_views')}
                  </th>
                  <th
                    className="px-4 py-3 text-gray-500 font-medium cursor-pointer hover:text-gray-300 text-right select-none"
                    onClick={() => handleSort('total_favorites')}
                  >
                    Favs{sortIcon('total_favorites')}
                  </th>
                  <th
                    className="px-4 py-3 text-gray-500 font-medium cursor-pointer hover:text-gray-300 text-right select-none"
                    onClick={() => handleSort('total_orders')}
                  >
                    Orders{sortIcon('total_orders')}
                  </th>
                  <th
                    className="px-4 py-3 text-gray-500 font-medium cursor-pointer hover:text-gray-300 text-right select-none"
                    onClick={() => handleSort('total_revenue_cents')}
                  >
                    Revenue{sortIcon('total_revenue_cents')}
                  </th>
                  <th
                    className="px-4 py-3 text-gray-500 font-medium cursor-pointer hover:text-gray-300 select-none"
                    onClick={() => handleSort('latest_date')}
                  >
                    Updated{sortIcon('latest_date')}
                  </th>
                  <th className="px-4 py-3 text-gray-500 font-medium w-20"></th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((p) => (
                  <tr key={p.printify_product_id} className="border-b border-dark-border/50 hover:bg-dark-hover/30">
                    {/* Thumbnail */}
                    <td className="px-4 py-3">
                      <div className="w-10 h-10 rounded bg-dark-bg overflow-hidden flex-shrink-0">
                        {p.thumbnail ? (
                          <img src={p.thumbnail} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-gray-700 text-xs">--</div>
                        )}
                      </div>
                    </td>
                    {/* Title */}
                    <td className="px-4 py-3">
                      {p.status !== 'deleted' ? (
                        <Link
                          href={`/shop/${p.printify_product_id}`}
                          className="text-gray-200 hover:text-accent transition-colors font-medium truncate block max-w-[200px]"
                          title={p.title}
                        >
                          {p.title}
                        </Link>
                      ) : (
                        <span className="text-gray-500 truncate block max-w-[200px]" title={p.title}>
                          {p.title}
                        </span>
                      )}
                      {p.etsy_url && (
                        <a
                          href={p.etsy_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] text-orange-400/70 hover:text-orange-400 transition-colors"
                        >
                          Etsy &#8599;
                        </a>
                      )}
                    </td>
                    {/* Status */}
                    <td className="px-4 py-3">
                      <span className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full border ${getStatusBadge(p.status)}`}>
                        {statusLabel(p.status)}
                      </span>
                    </td>
                    {/* Price */}
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {p.min_price > 0 ? (
                        p.min_price === p.max_price
                          ? formatPrice(p.min_price)
                          : `${formatPrice(p.min_price)} - ${formatPrice(p.max_price)}`
                      ) : (
                        '--'
                      )}
                    </td>
                    {/* Views */}
                    <td className="px-4 py-3 text-right text-gray-300 tabular-nums">
                      {p.total_views > 0 ? p.total_views.toLocaleString() : '--'}
                    </td>
                    {/* Favorites */}
                    <td className="px-4 py-3 text-right text-gray-300 tabular-nums">
                      {p.total_favorites > 0 ? p.total_favorites.toLocaleString() : '--'}
                    </td>
                    {/* Orders */}
                    <td className="px-4 py-3 text-right text-gray-300 tabular-nums">
                      {p.total_orders > 0 ? p.total_orders.toLocaleString() : '--'}
                    </td>
                    {/* Revenue */}
                    <td className="px-4 py-3 text-right text-gray-300 tabular-nums">
                      {p.total_revenue_cents > 0 ? formatRevenue(p.total_revenue_cents) : '--'}
                    </td>
                    {/* Last updated */}
                    <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">
                      {p.latest_date ?? '--'}
                    </td>
                    {/* Actions */}
                    <td className="px-4 py-3">
                      {editingId !== p.printify_product_id ? (
                        <button
                          onClick={() => startEdit(p)}
                          className="text-xs text-accent hover:text-accent/80 transition-colors"
                        >
                          Update
                        </button>
                      ) : (
                        <button
                          onClick={cancelEdit}
                          className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Inline edit form */}
          {editingId && (
            <div className="border-t border-dark-border bg-dark-bg/50 px-6 py-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm font-medium text-gray-300">
                  Update stats for: {products.find((p) => p.printify_product_id === editingId)?.title}
                </span>
                <span className="text-xs text-gray-500">
                  (today: {new Date().toISOString().split('T')[0]})
                </span>
              </div>
              <div className="flex flex-wrap items-end gap-4">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Views</label>
                  <input
                    type="number"
                    min={0}
                    value={editForm.views}
                    onChange={(e) => setEditForm({ ...editForm, views: parseInt(e.target.value) || 0 })}
                    className="w-24 px-3 py-1.5 rounded-md bg-dark-card border border-dark-border text-gray-200 text-sm focus:outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Favorites</label>
                  <input
                    type="number"
                    min={0}
                    value={editForm.favorites}
                    onChange={(e) => setEditForm({ ...editForm, favorites: parseInt(e.target.value) || 0 })}
                    className="w-24 px-3 py-1.5 rounded-md bg-dark-card border border-dark-border text-gray-200 text-sm focus:outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Orders</label>
                  <input
                    type="number"
                    min={0}
                    value={editForm.orders}
                    onChange={(e) => setEditForm({ ...editForm, orders: parseInt(e.target.value) || 0 })}
                    className="w-24 px-3 py-1.5 rounded-md bg-dark-card border border-dark-border text-gray-200 text-sm focus:outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Revenue ($)</label>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={(editForm.revenue_cents / 100).toFixed(2)}
                    onChange={(e) => setEditForm({ ...editForm, revenue_cents: Math.round(parseFloat(e.target.value || '0') * 100) })}
                    className="w-28 px-3 py-1.5 rounded-md bg-dark-card border border-dark-border text-gray-200 text-sm focus:outline-none focus:border-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Notes</label>
                  <input
                    type="text"
                    value={editForm.notes}
                    onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                    placeholder="Optional"
                    className="w-40 px-3 py-1.5 rounded-md bg-dark-card border border-dark-border text-gray-200 text-sm focus:outline-none focus:border-accent placeholder:text-gray-600"
                  />
                </div>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-4 py-1.5 rounded-md bg-accent text-dark-bg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={cancelEdit}
                  className="px-4 py-1.5 rounded-md bg-dark-card border border-dark-border text-gray-400 text-sm hover:bg-dark-hover transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
