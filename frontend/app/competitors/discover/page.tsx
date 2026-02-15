'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  searchCompetitorShops,
  addCompetitor,
  CompetitorSearchResult,
} from '@/lib/api';

export default function DiscoverCompetitorsPage() {
  const [keywords, setKeywords] = useState('');
  const [results, setResults] = useState<CompetitorSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addingId, setAddingId] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keywords.trim()) return;

    setIsSearching(true);
    setError(null);
    setHasSearched(true);
    try {
      const shops = await searchCompetitorShops(keywords.trim());
      setResults(shops);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleAdd = async (shopId: string) => {
    setAddingId(shopId);
    setError(null);
    try {
      await addCompetitor(shopId);
      // Mark as tracked in results
      setResults(results.map((r) =>
        r.shop_id === shopId ? { ...r, already_tracked: true } : r
      ));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add competitor');
    } finally {
      setAddingId(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Discover Competitors</h1>
        <Link
          href="/competitors"
          className="px-4 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors"
        >
          Back to Competitors
        </Link>
      </div>

      {/* Search form */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <input
          type="text"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="Search keywords (e.g. minimalist wall art, motivational poster)"
          className="flex-1 px-4 py-2.5 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={isSearching || !keywords.trim()}
          className="px-6 py-2.5 bg-accent text-dark-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
        >
          {isSearching ? 'Searching...' : 'Search'}
        </button>
      </form>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {isSearching && (
        <div className="text-center py-12 text-gray-500">
          Searching Etsy for shops...
        </div>
      )}

      {!isSearching && !hasSearched && (
        <div className="text-center py-12 text-gray-500">
          Search for keywords like &quot;minimalist wall art&quot; to find competitor shops
        </div>
      )}

      {!isSearching && hasSearched && results.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          No shops found for &quot;{keywords}&quot;. Try different keywords.
        </div>
      )}

      {!isSearching && results.length > 0 && (
        <>
          <div className="text-sm text-gray-500">
            Found {results.length} shop{results.length !== 1 ? 's' : ''}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {results.map((shop) => (
              <div
                key={shop.shop_id}
                className="bg-dark-card border border-dark-border rounded-lg p-4 flex flex-col gap-3"
              >
                <div className="flex items-center gap-3">
                  {shop.icon_url ? (
                    <img src={shop.icon_url} alt="" className="w-12 h-12 rounded-full object-cover flex-shrink-0" />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-dark-border flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <a
                      href={`https://www.etsy.com/shop/${shop.shop_name}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-gray-100 hover:text-accent transition-colors truncate block"
                    >
                      {shop.shop_name}
                    </a>
                    <div className="flex items-center gap-2 text-xs text-gray-500 mt-0.5">
                      <span className="text-yellow-400">{shop.rating.toFixed(1)}</span>
                      <span>{shop.total_reviews.toLocaleString()} reviews</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">
                    {shop.listing_count.toLocaleString()} listings
                  </span>

                  {shop.already_tracked ? (
                    <span className="flex items-center gap-1 text-xs text-green-400 font-medium">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                      Tracked
                    </span>
                  ) : (
                    <button
                      onClick={() => handleAdd(shop.shop_id)}
                      disabled={addingId === shop.shop_id}
                      className="px-3 py-1.5 bg-accent text-dark-bg rounded text-xs font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
                    >
                      {addingId === shop.shop_id ? 'Adding...' : 'Add'}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
