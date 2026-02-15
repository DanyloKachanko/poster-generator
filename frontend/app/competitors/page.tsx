'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import {
  getCompetitors,
  syncCompetitor,
  deleteCompetitor,
  CompetitorShop,
  CompetitorSyncResult,
} from '@/lib/api';

type SortKey = 'shop_name' | 'rating' | 'total_reviews' | 'total_listings' | 'updated_at';
type SortDir = 'asc' | 'desc';

export default function CompetitorsPage() {
  const [competitors, setCompetitors] = useState<CompetitorShop[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>('total_listings');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [syncingId, setSyncingId] = useState<number | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getCompetitors();
      setCompetitors(data.competitors);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load competitors');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const sorted = useMemo(() => {
    const arr = [...competitors];
    arr.sort((a, b) => {
      let va: number | string = 0, vb: number | string = 0;
      switch (sortKey) {
        case 'shop_name': va = a.shop_name.toLowerCase(); vb = b.shop_name.toLowerCase(); break;
        case 'rating': va = a.rating; vb = b.rating; break;
        case 'total_reviews': va = a.total_reviews; vb = b.total_reviews; break;
        case 'total_listings': va = a.total_listings; vb = b.total_listings; break;
        case 'updated_at': va = a.updated_at; vb = b.updated_at; break;
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return arr;
  }, [competitors, sortKey, sortDir]);

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
    return sortDir === 'asc' ? ' \u2191' : ' \u2193';
  };

  const handleSync = async (id: number) => {
    setSyncingId(id);
    try {
      await syncCompetitor(id);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed');
    } finally {
      setSyncingId(null);
    }
  };

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Remove "${name}" from tracked competitors?`)) return;
    try {
      await deleteCompetitor(id);
      setCompetitors(competitors.filter((c) => c.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const totals = useMemo(() => ({
    count: competitors.length,
    listings: competitors.reduce((s, c) => s + c.total_listings, 0),
    avgRating: competitors.length > 0
      ? (competitors.reduce((s, c) => s + c.rating, 0) / competitors.length).toFixed(1)
      : '0',
  }), [competitors]);

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Competitor Intelligence</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            className="px-4 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors"
          >
            Refresh
          </button>
          <Link
            href="/competitors/discover"
            className="px-4 py-2 bg-accent text-dark-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            Discover & Add
          </Link>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Competitors</div>
          <div className="text-2xl font-bold text-gray-100">{totals.count}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Total Listings</div>
          <div className="text-2xl font-bold text-gray-100">{totals.listings.toLocaleString()}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Avg Rating</div>
          <div className="text-2xl font-bold text-yellow-400">{totals.avgRating}</div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-12 text-gray-500">Loading competitors...</div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No competitors tracked yet.{' '}
          <Link href="/competitors/discover" className="text-accent hover:underline">
            Search for shops to start tracking.
          </Link>
        </div>
      ) : (
        <div className="bg-dark-card border border-dark-border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-border text-left text-xs text-gray-500 uppercase">
                <th className="px-4 py-3 w-12">#</th>
                <th className="px-4 py-3 cursor-pointer hover:text-gray-300" onClick={() => handleSort('shop_name')}>
                  Shop{sortIcon('shop_name')}
                </th>
                <th className="px-4 py-3 w-24 cursor-pointer hover:text-gray-300 text-center" onClick={() => handleSort('rating')}>
                  Rating{sortIcon('rating')}
                </th>
                <th className="px-4 py-3 w-24 cursor-pointer hover:text-gray-300 text-right" onClick={() => handleSort('total_reviews')}>
                  Reviews{sortIcon('total_reviews')}
                </th>
                <th className="px-4 py-3 w-24 cursor-pointer hover:text-gray-300 text-right" onClick={() => handleSort('total_listings')}>
                  Listings{sortIcon('total_listings')}
                </th>
                <th className="px-4 py-3 w-28 cursor-pointer hover:text-gray-300 text-right" onClick={() => handleSort('updated_at')}>
                  Synced{sortIcon('updated_at')}
                </th>
                <th className="px-4 py-3 w-36 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((comp, idx) => (
                <tr
                  key={comp.id}
                  className="border-b border-dark-border/50 hover:bg-dark-hover/50 transition-colors"
                >
                  <td className="px-4 py-3 text-xs text-gray-600">{idx + 1}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      {comp.icon_url ? (
                        <img src={comp.icon_url} alt="" className="w-8 h-8 rounded-full object-cover flex-shrink-0" />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-dark-border flex-shrink-0" />
                      )}
                      <a
                        href={comp.shop_url || `https://www.etsy.com/shop/${comp.shop_name}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-gray-200 hover:text-accent transition-colors"
                      >
                        {comp.shop_name}
                      </a>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className="text-sm text-yellow-400">{comp.rating.toFixed(1)}</span>
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-300">
                    {comp.total_reviews > 0 ? comp.total_reviews.toLocaleString() : '\u2014'}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-300">
                    {comp.total_listings > 0 ? comp.total_listings.toLocaleString() : '\u2014'}
                  </td>
                  <td className="px-4 py-3 text-right text-xs text-gray-500">
                    {timeAgo(comp.updated_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleSync(comp.id)}
                        disabled={syncingId === comp.id}
                        className="px-3 py-1 text-xs bg-dark-hover border border-dark-border rounded text-gray-300 hover:text-gray-100 transition-colors disabled:opacity-50"
                      >
                        {syncingId === comp.id ? 'Syncing...' : 'Sync'}
                      </button>
                      <button
                        onClick={() => handleDelete(comp.id, comp.shop_name)}
                        className="px-3 py-1 text-xs bg-dark-hover border border-dark-border rounded text-red-400 hover:text-red-300 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
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
