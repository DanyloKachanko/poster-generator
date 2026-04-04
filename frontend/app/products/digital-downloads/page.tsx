'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  getApiUrl,
  getDigitalDownloads,
  toggleDigitalEnabled,
  DigitalDownloadListing,
} from '@/lib/api';

export default function DigitalDownloadsPage() {
  const [listings, setListings] = useState<DigitalDownloadListing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const load = () => {
    setIsLoading(true);
    getDigitalDownloads()
      .then((data) => {
        setListings(data.listings);
        // Init selection from saved state
        setSelected(new Set(data.listings.filter((l) => l.is_digital).map((l) => l.id)));
      })
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => { load(); }, []);

  const upscaledListings = useMemo(
    () => listings.filter((l) => l.has_upscale),
    [listings]
  );

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setSuccessMsg(null);
  };

  const selectAll = () => {
    setSelected(new Set(upscaledListings.map((l) => l.id)));
    setSuccessMsg(null);
  };

  const deselectAll = () => {
    setSelected(new Set());
    setSuccessMsg(null);
  };

  // Compute diff from saved state
  const savedIds = useMemo(
    () => new Set(listings.filter((l) => l.is_digital).map((l) => l.id)),
    [listings]
  );
  const hasChanges = useMemo(() => {
    if (selected.size !== savedIds.size) return true;
    for (const id of selected) if (!savedIds.has(id)) return true;
    return false;
  }, [selected, savedIds]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      // Enable newly selected
      const toEnable = [...selected].filter((id) => !savedIds.has(id));
      const toDisable = [...savedIds].filter((id) => !selected.has(id));

      if (toEnable.length > 0) {
        await toggleDigitalEnabled(toEnable, true);
      }
      if (toDisable.length > 0) {
        await toggleDigitalEnabled(toDisable, false);
      }

      setSuccessMsg(`Saved: ${selected.size} products marked for digital downloads`);
      load(); // Refresh
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
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

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Digital Downloads</h1>
        <div className="text-sm text-gray-500">
          {totalUpscaled}/{listings.length} upscaled
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
            <span className="text-sm text-gray-500 font-normal">/{totalUpscaled}</span>
          </div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Saved</div>
          <div className="text-2xl font-bold text-gray-100">{savedIds.size}</div>
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
        {hasChanges && (
          <span className="text-yellow-400 text-sm">Unsaved changes</span>
        )}
        <button
          onClick={handleSave}
          disabled={!hasChanges || saving}
          className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 disabled:opacity-50 transition-colors font-medium"
        >
          {saving ? 'Saving...' : `Save Selection (${selected.size})`}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 text-sm">
          {error}
        </div>
      )}

      {successMsg && (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg p-3 text-sm">
          {successMsg}
        </div>
      )}

      {/* Listing Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {listings.map((listing) => {
          const isSelected = selected.has(listing.id);
          const canSelect = listing.has_upscale;
          const wasSaved = savedIds.has(listing.id);

          return (
            <div
              key={listing.id}
              onClick={() => canSelect && toggleSelect(listing.id)}
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

                {/* Saved badge */}
                {wasSaved && (
                  <div className="absolute top-2 right-2">
                    <span className="px-1.5 py-0.5 bg-green-500/80 text-white text-[10px] font-medium rounded">
                      Digital
                    </span>
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
                    <span className="text-[10px] text-green-400 font-medium">Ready</span>
                  ) : (
                    <span className="text-[10px] text-gray-500">Not upscaled</span>
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
