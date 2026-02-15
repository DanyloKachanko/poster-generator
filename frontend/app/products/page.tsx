'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { getProductManagerData, ProductManagerItem, getTrackedProducts, TrackedProduct, syncProductsFromPrintify } from '@/lib/api';
import { analyzeSeo, scoreColor, scoreGrade } from '@/lib/seo-score';

type SortKey = 'title' | 'seo' | 'views' | 'favorites' | 'orders' | 'revenue' | 'price';
type SortDir = 'asc' | 'desc';
type Filter = 'all' | 'live' | 'draft' | 'scheduled' | 'failed' | 'low_seo' | 'no_views';

interface ProductWithScore extends ProductManagerItem {
  seo_score: number;
  seo_grade: string;
  pipeline_status: string; // draft | scheduled | published | failed
  has_source_image: boolean;
}

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductWithScore[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('views');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [filter, setFilter] = useState<Filter>('all');
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const result = await syncProductsFromPrintify();
      setSyncMessage(`Synced: ${result.imported} imported, ${result.skipped} already exist (${result.total} total)`);
      if (result.imported > 0) await loadData();
    } catch (err) {
      setSyncMessage(err instanceof Error ? err.message : 'Sync failed');
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMessage(null), 5000);
    }
  };

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [data, tracked] = await Promise.all([
        getProductManagerData(),
        getTrackedProducts(undefined, 200).catch(() => ({ items: [] as TrackedProduct[], total: 0, limit: 200, offset: 0 })),
      ]);
      // Build lookup from local tracking DB
      const trackMap = new Map<string, TrackedProduct>();
      for (const t of tracked.items) {
        trackMap.set(t.printify_product_id, t);
      }
      const withScores = data.products.map((p) => {
        const analysis = p.etsy_title
          ? analyzeSeo(p.etsy_title, p.etsy_tags, p.etsy_description, p.etsy_materials)
          : null;
        const local = trackMap.get(p.printify_product_id);
        return {
          ...p,
          seo_score: analysis?.score ?? -1,
          seo_grade: analysis ? scoreGrade(analysis.score) : '—',
          pipeline_status: local?.status ?? (p.status === 'on_etsy' ? 'published' : 'draft'),
          has_source_image: !!local?.source_image_id,
        };
      });
      setProducts(withScores);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load products');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const filtered = useMemo(() => {
    switch (filter) {
      case 'live': return products.filter((p) => p.status === 'on_etsy');
      case 'draft': return products.filter((p) => p.pipeline_status === 'draft');
      case 'scheduled': return products.filter((p) => p.pipeline_status === 'scheduled');
      case 'failed': return products.filter((p) => p.pipeline_status === 'failed');
      case 'low_seo': return products.filter((p) => p.seo_score >= 0 && p.seo_score < 60);
      case 'no_views': return products.filter((p) => p.status === 'on_etsy' && p.total_views === 0);
      default: return products;
    }
  }, [products, filter]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      let va: number | string = 0, vb: number | string = 0;
      switch (sortKey) {
        case 'title': va = a.title.toLowerCase(); vb = b.title.toLowerCase(); break;
        case 'seo': va = a.seo_score; vb = b.seo_score; break;
        case 'views': va = a.total_views; vb = b.total_views; break;
        case 'favorites': va = a.total_favorites; vb = b.total_favorites; break;
        case 'orders': va = a.total_orders; vb = b.total_orders; break;
        case 'revenue': va = a.total_revenue_cents; vb = b.total_revenue_cents; break;
        case 'price': va = a.min_price; vb = b.min_price; break;
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sortIcon = (key: SortKey) => {
    if (sortKey !== key) return '';
    return sortDir === 'asc' ? ' ↑' : ' ↓';
  };

  // Totals
  const totals = useMemo(() => ({
    views: filtered.reduce((s, p) => s + p.total_views, 0),
    favorites: filtered.reduce((s, p) => s + p.total_favorites, 0),
    orders: filtered.reduce((s, p) => s + p.total_orders, 0),
    revenue: filtered.reduce((s, p) => s + p.total_revenue_cents, 0),
    avgSeo: filtered.filter((p) => p.seo_score >= 0).length > 0
      ? Math.round(filtered.filter((p) => p.seo_score >= 0).reduce((s, p) => s + p.seo_score, 0) / filtered.filter((p) => p.seo_score >= 0).length)
      : 0,
  }), [filtered]);

  const filters: { key: Filter; label: string; count: number }[] = [
    { key: 'all', label: 'All', count: products.length },
    { key: 'live', label: 'Live', count: products.filter((p) => p.status === 'on_etsy').length },
    { key: 'scheduled', label: 'Scheduled', count: products.filter((p) => p.pipeline_status === 'scheduled').length },
    { key: 'draft', label: 'Draft', count: products.filter((p) => p.pipeline_status === 'draft').length },
    { key: 'failed', label: 'Failed', count: products.filter((p) => p.pipeline_status === 'failed').length },
    { key: 'low_seo', label: 'Low SEO', count: products.filter((p) => p.seo_score >= 0 && p.seo_score < 60).length },
    { key: 'no_views', label: 'No Views', count: products.filter((p) => p.status === 'on_etsy' && p.total_views === 0).length },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Product Manager</h1>
        <div className="flex items-center gap-2">
          {syncMessage && (
            <span className="text-xs text-accent">{syncMessage}</span>
          )}
          <button
            onClick={handleSync}
            disabled={syncing}
            className="px-4 py-2 bg-accent/15 text-accent rounded-lg text-sm font-medium hover:bg-accent/25 transition-colors disabled:opacity-50"
          >
            {syncing ? 'Syncing...' : 'Sync Printify'}
          </button>
          <button
            onClick={loadData}
            className="px-4 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Views</div>
          <div className="text-2xl font-bold text-gray-100">{totals.views.toLocaleString()}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Favorites</div>
          <div className="text-2xl font-bold text-gray-100">{totals.favorites.toLocaleString()}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Orders</div>
          <div className="text-2xl font-bold text-gray-100">{totals.orders}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Revenue</div>
          <div className="text-2xl font-bold text-gray-100">${(totals.revenue / 100).toFixed(2)}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Avg SEO</div>
          <div className={`text-2xl font-bold ${scoreColor(totals.avgSeo)}`}>
            {totals.avgSeo}/100
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {filters.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              filter === f.key
                ? 'bg-accent/15 text-accent'
                : 'bg-dark-card border border-dark-border text-gray-400 hover:text-gray-200'
            }`}
          >
            {f.label} ({f.count})
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Loading products...</div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No products found</div>
      ) : (
        <div className="bg-dark-card border border-dark-border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-border text-left text-xs text-gray-500 uppercase">
                <th className="px-4 py-3 w-12">#</th>
                <th className="px-4 py-3 w-16"></th>
                <th className="px-4 py-3 cursor-pointer hover:text-gray-300" onClick={() => handleSort('title')}>
                  Title{sortIcon('title')}
                </th>
                <th className="px-4 py-3 w-20">Status</th>
                <th className="px-4 py-3 w-20 cursor-pointer hover:text-gray-300 text-center" onClick={() => handleSort('seo')}>
                  SEO{sortIcon('seo')}
                </th>
                <th className="px-4 py-3 w-20 cursor-pointer hover:text-gray-300 text-right" onClick={() => handleSort('views')}>
                  Views{sortIcon('views')}
                </th>
                <th className="px-4 py-3 w-20 cursor-pointer hover:text-gray-300 text-right" onClick={() => handleSort('favorites')}>
                  Favs{sortIcon('favorites')}
                </th>
                <th className="px-4 py-3 w-20 cursor-pointer hover:text-gray-300 text-right" onClick={() => handleSort('orders')}>
                  Orders{sortIcon('orders')}
                </th>
                <th className="px-4 py-3 w-24 cursor-pointer hover:text-gray-300 text-right" onClick={() => handleSort('revenue')}>
                  Revenue{sortIcon('revenue')}
                </th>
                <th className="px-4 py-3 w-24 cursor-pointer hover:text-gray-300 text-right" onClick={() => handleSort('price')}>
                  Price{sortIcon('price')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((product, idx) => (
                <tr
                  key={product.printify_product_id}
                  className="border-b border-dark-border/50 hover:bg-dark-hover/50 transition-colors"
                >
                  <td className="px-4 py-3 text-xs text-gray-600">{idx + 1}</td>
                  <td className="px-4 py-3">
                    <div className="relative w-10 h-10">
                      {product.thumbnail ? (
                        <img
                          src={product.thumbnail}
                          alt=""
                          className="w-10 h-10 rounded object-cover"
                        />
                      ) : (
                        <div className="w-10 h-10 rounded bg-dark-border" />
                      )}
                      <span
                        className={`absolute -top-1 -right-1 w-3 h-3 rounded-full border-2 border-dark-card ${
                          product.has_source_image ? 'bg-green-500' : 'bg-gray-600'
                        }`}
                        title={product.has_source_image ? 'Source image linked' : 'No source image'}
                      />
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/products/${product.printify_product_id}`}
                      className="text-sm text-gray-200 hover:text-accent transition-colors line-clamp-1"
                      title={product.title}
                    >
                      {product.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                      product.pipeline_status === 'published'
                        ? 'bg-green-500/15 text-green-400'
                        : product.pipeline_status === 'scheduled'
                        ? 'bg-yellow-500/15 text-yellow-400'
                        : product.pipeline_status === 'failed'
                        ? 'bg-red-500/15 text-red-400'
                        : 'bg-gray-500/15 text-gray-400'
                    }`}>
                      {product.pipeline_status === 'published' ? 'Live' : product.pipeline_status === 'scheduled' ? 'Scheduled' : product.pipeline_status === 'failed' ? 'Failed' : 'Draft'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {product.seo_score >= 0 ? (
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${scoreColor(product.seo_score)}`}>
                        {product.seo_grade} {product.seo_score}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-300">
                    {product.total_views > 0 ? product.total_views.toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-300">
                    {product.total_favorites > 0 ? product.total_favorites.toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-300">
                    {product.total_orders > 0 ? product.total_orders : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-300">
                    {product.total_revenue_cents > 0
                      ? `$${(product.total_revenue_cents / 100).toFixed(2)}`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-300">
                    ${(product.min_price / 100).toFixed(2)}
                    {product.max_price !== product.min_price && (
                      <span className="text-gray-600"> - ${(product.max_price / 100).toFixed(2)}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
