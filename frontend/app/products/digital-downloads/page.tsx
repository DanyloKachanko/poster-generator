'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  getApiUrl,
  getDigitalDownloads,
  createDigitalListings,
  DigitalDownloadListing,
} from '@/lib/api';

export default function DigitalDownloadsPage() {
  const [listings, setListings] = useState<DigitalDownloadListing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [creating, setCreating] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    getDigitalDownloads()
      .then((data) => setListings(data.listings))
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false));
  }, []);

  const upscaledListings = useMemo(
    () => listings.filter((l) => l.has_upscale),
    [listings]
  );

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(upscaledListings.map((l) => l.etsy_listing_id)));
  };

  const deselectAll = () => {
    setSelected(new Set());
  };

  const handleCreate = async () => {
    if (selected.size === 0) return;
    if (
      !confirm(
        `Create digital listings for ${selected.size} products? Estimated cost: $${(selected.size * 0.2).toFixed(2)}`
      )
    )
      return;

    setCreating(true);
    setError(null);
    setResult(null);
    try {
      const data = await createDigitalListings(Array.from(selected));
      setResult(data.message);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed');
    } finally {
      setCreating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading listings...
      </div>
    );
  }

  const totalUpscaled = listings.filter((l) => l.has_upscale).length;
  const notUpscaled = listings.length - totalUpscaled;

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Digital Downloads</h1>
        <div className="text-sm text-gray-500">
          {totalUpscaled}/{listings.length} upscaled
          {notUpscaled > 0 && (
            <span className="text-yellow-400 ml-2">
              ({notUpscaled} need upscaling)
            </span>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Total Listings</div>
          <div className="text-2xl font-bold text-gray-100">{listings.length}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Upscaled</div>
          <div className="text-2xl font-bold text-green-400">{totalUpscaled}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Selected</div>
          <div className="text-2xl font-bold text-accent">
            {selected.size}
            <span className="text-sm text-gray-500 font-normal">
              /{totalUpscaled}
            </span>
          </div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Est. Cost</div>
          <div className="text-2xl font-bold text-gray-100">
            ${(selected.size * 0.2).toFixed(2)}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={selectAll}
          className="px-3 py-1.5 bg-dark-hover text-gray-200 rounded-lg text-sm hover:bg-dark-border transition-colors"
        >
          Select All
        </button>
        <button
          onClick={deselectAll}
          className="px-3 py-1.5 bg-dark-hover text-gray-200 rounded-lg text-sm hover:bg-dark-border transition-colors"
        >
          Deselect All
        </button>
        <div className="flex-1" />
        {selected.size > 20 && (
          <span className="text-yellow-400 text-sm">
            Warning: {selected.size} selected (recommended max 20 per batch)
          </span>
        )}
        <button
          onClick={handleCreate}
          disabled={selected.size === 0 || creating}
          className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 disabled:opacity-50 transition-colors font-medium"
        >
          {creating
            ? 'Creating...'
            : `Create Digital Listings ($${(selected.size * 0.2).toFixed(2)})`}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg p-3 text-sm">
          {result}
        </div>
      )}

      {/* Listing Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {listings.map((listing) => {
          const isSelected = selected.has(listing.etsy_listing_id);
          const canSelect = listing.has_upscale;

          return (
            <div
              key={listing.id}
              onClick={() => canSelect && toggleSelect(listing.etsy_listing_id)}
              className={`bg-dark-card border rounded-lg overflow-hidden transition-all ${
                canSelect ? 'cursor-pointer hover:border-accent/50' : 'opacity-60 cursor-not-allowed'
              } ${isSelected ? 'border-accent ring-1 ring-accent/30' : 'border-dark-border'}`}
            >
              {/* Thumbnail */}
              <div className="relative aspect-[4/5] bg-dark-hover">
                {listing.thumbnail ? (
                  <img
                    src={listing.thumbnail.startsWith('/') ? `${getApiUrl()}${listing.thumbnail}` : listing.thumbnail}
                    alt={listing.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-600 text-xs">
                    No image
                  </div>
                )}

                {/* Checkbox */}
                {canSelect && (
                  <div className="absolute top-2 left-2">
                    <div
                      className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                        isSelected
                          ? 'bg-accent border-accent text-white'
                          : 'border-gray-400 bg-black/40'
                      }`}
                    >
                      {isSelected && (
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      )}
                    </div>
                  </div>
                )}

                {/* Resolution badge */}
                {listing.has_upscale && (
                  <div className="absolute bottom-2 right-2">
                    <span className="px-1.5 py-0.5 bg-black/70 text-green-400 text-[10px] font-mono rounded">
                      {listing.upscaled_resolution}
                    </span>
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="p-2">
                <div className="text-xs text-gray-300 truncate" title={listing.title}>
                  {listing.title}
                </div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-[10px] text-gray-500 font-mono">
                    {listing.orig_resolution}
                  </span>
                  {listing.has_upscale ? (
                    <span className="text-[10px] text-green-400 font-medium">
                      Ready
                    </span>
                  ) : (
                    <span className="text-[10px] text-gray-500">
                      Not upscaled
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
