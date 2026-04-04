'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import {
  getApiUrl,
  getDigitalDownloads,
  toggleDigitalEnabled,
  startDigitalCreation,
  getDigitalCreationStatus,
  DigitalDownloadListing,
  DigitalCreationStatus,
} from '@/lib/api';

export default function DigitalDownloadsPage() {
  const [listings, setListings] = useState<DigitalDownloadListing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [creation, setCreation] = useState<DigitalCreationStatus | null>(null);
  const [creationPolling, setCreationPolling] = useState(false);

  const pollCreation = async () => {
    try {
      const data = await getDigitalCreationStatus();
      setCreation(data);
      if (data.status === 'running') {
        setCreationPolling(true);
      } else {
        setCreationPolling(false);
        if (data.status === 'completed') load();
      }
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (!creationPolling) return;
    const id = setInterval(pollCreation, 3000);
    return () => clearInterval(id);
  }, [creationPolling]);

  const handleCreateDigital = async () => {
    if (!confirm('Create digital listings on Etsy for all saved products?')) return;
    setError(null);
    try {
      const data = await startDigitalCreation();
      if (data.started) {
        setCreation({ status: 'running', total: data.total, done: 0, ok: 0, errors: [] });
        setCreationPolling(true);
      } else {
        setSuccessMsg(data.message);
        pollCreation();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed');
    }
  };

  const load = () => {
    setIsLoading(true);
    getDigitalDownloads()
      .then((data) => {
        setListings(data.listings);
        setSelected(new Set(data.listings.filter((l) => l.is_digital).map((l) => l.id)));
      })
      .catch((e) => setError(e.message))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => { load(); pollCreation(); }, []);

  const upscaledListings = useMemo(() => listings.filter((l) => l.has_upscale), [listings]);

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setSuccessMsg(null);
  };

  const selectAll = () => { setSelected(new Set(upscaledListings.map((l) => l.id))); setSuccessMsg(null); };
  const deselectAll = () => { setSelected(new Set()); setSuccessMsg(null); };

  const savedIds = useMemo(() => new Set(listings.filter((l) => l.is_digital).map((l) => l.id)), [listings]);
  const hasChanges = useMemo(() => {
    if (selected.size !== savedIds.size) return true;
    const arr = Array.from(selected);
    for (let i = 0; i < arr.length; i++) if (!savedIds.has(arr[i])) return true;
    return false;
  }, [selected, savedIds]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const toEnable = Array.from(selected).filter((id) => !savedIds.has(id));
      const toDisable = Array.from(savedIds).filter((id) => !selected.has(id));
      if (toEnable.length > 0) await toggleDigitalEnabled(toEnable, true);
      if (toDisable.length > 0) await toggleDigitalEnabled(toDisable, false);
      setSuccessMsg(`Saved: ${selected.size} products marked for digital downloads`);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) return <div className="flex items-center justify-center h-64 text-gray-400">Loading listings...</div>;

  const totalUpscaled = listings.filter((l) => l.has_upscale).length;
  const createdCount = listings.filter((l) => l.digital_etsy_id).length;

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Digital Downloads</h1>
        <div className="flex items-center gap-4">
          {createdCount > 0 && (
            <Link href="/products/digital-editor" className="px-3 py-1.5 bg-dark-hover text-accent rounded-lg text-sm hover:bg-dark-border transition-colors">
              Edit {createdCount} Digital Listings
            </Link>
          )}
          <span className="text-sm text-gray-500">{totalUpscaled}/{listings.length} upscaled</span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Total</div>
          <div className="text-2xl font-bold text-gray-100">{listings.length}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Upscaled</div>
          <div className="text-2xl font-bold text-green-400">{totalUpscaled}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Selected</div>
          <div className="text-2xl font-bold text-accent">{selected.size}<span className="text-sm text-gray-500 font-normal">/{totalUpscaled}</span></div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Created</div>
          <div className="text-2xl font-bold text-green-400">{createdCount}</div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button onClick={selectAll} className="px-3 py-1.5 bg-dark-hover text-gray-200 rounded-lg text-sm hover:bg-dark-border">Select All</button>
        <button onClick={deselectAll} className="px-3 py-1.5 bg-dark-hover text-gray-200 rounded-lg text-sm hover:bg-dark-border">Deselect All</button>
        <div className="flex-1" />
        {hasChanges && <span className="text-yellow-400 text-sm">Unsaved changes</span>}
        <button onClick={handleSave} disabled={!hasChanges || saving} className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 disabled:opacity-50 font-medium">
          {saving ? 'Saving...' : `Save Selection (${selected.size})`}
        </button>
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 text-sm">{error}</div>}
      {successMsg && <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg p-3 text-sm">{successMsg}</div>}

      {/* Create */}
      {savedIds.size > 0 && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-100">Create Etsy Digital Listings</h3>
              <p className="text-xs text-gray-500 mt-1">Creates digital listings with ZIP files for {savedIds.size} products.</p>
            </div>
            <button onClick={handleCreateDigital} disabled={creation?.status === 'running'} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 font-medium text-sm">
              {creation?.status === 'running' ? 'Creating...' : `Create ${savedIds.size} Digital Listings`}
            </button>
          </div>
          {creation?.status === 'running' && (
            <div className="mt-3">
              <div className="flex justify-between text-sm text-gray-400 mb-1"><span>Creating...</span><span>{creation.done}/{creation.total}</span></div>
              <div className="w-full bg-dark-hover rounded-full h-2">
                <div className="bg-green-500 h-2 rounded-full transition-all" style={{ width: `${creation.total > 0 ? (creation.done / creation.total) * 100 : 0}%` }} />
              </div>
            </div>
          )}
          {creation?.status === 'completed' && (
            <div className="mt-3 text-sm">
              <span className="text-green-400">{creation.ok} created</span>
              {creation.errors.length > 0 && (
                <details className="mt-2"><summary className="text-red-400 cursor-pointer text-xs">{creation.errors.length} failed</summary>
                  <div className="mt-1 space-y-1 text-xs text-gray-500">{creation.errors.map((e, i) => <div key={i}>{e.title || e.listing_id}: {e.error}</div>)}</div>
                </details>
              )}
            </div>
          )}
        </div>
      )}

      {/* Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {listings.map((listing) => {
          const isSelected = selected.has(listing.id);
          const canSelect = listing.has_upscale;
          const hasDigital = !!listing.digital_etsy_id;

          return (
            <div
              key={listing.id}
              onClick={() => canSelect && !hasDigital && toggleSelect(listing.id)}
              className={`bg-dark-card border rounded-lg overflow-hidden transition-all ${
                hasDigital ? 'border-green-500/30' : canSelect ? 'cursor-pointer hover:border-accent/50' : 'opacity-60 cursor-not-allowed'
              } ${isSelected && !hasDigital ? 'border-accent ring-1 ring-accent/30' : ''}`}
            >
              <div className="relative aspect-[4/5] bg-dark-hover">
                {listing.thumbnail ? (
                  <img src={listing.thumbnail.startsWith('/') ? `${getApiUrl()}${listing.thumbnail}` : listing.thumbnail} alt={listing.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-600 text-xs">No image</div>
                )}
                {canSelect && !hasDigital && (
                  <div className="absolute top-2 left-2">
                    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center ${isSelected ? 'bg-accent border-accent text-white' : 'border-gray-400 bg-black/40'}`}>
                      {isSelected && <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>}
                    </div>
                  </div>
                )}
                {hasDigital && <div className="absolute top-2 right-2"><span className="px-1.5 py-0.5 bg-green-500/80 text-white text-[10px] font-medium rounded">Digital</span></div>}
                {listing.has_upscale && <div className="absolute bottom-2 right-2"><span className="px-1.5 py-0.5 bg-black/70 text-green-400 text-[10px] font-mono rounded">{listing.upscaled_resolution}</span></div>}
              </div>
              <div className="p-2">
                <div className="text-xs text-gray-300 truncate" title={listing.title}>{listing.title}</div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-[10px] text-gray-500 font-mono">{listing.orig_resolution}</span>
                  {listing.has_upscale ? <span className="text-[10px] text-green-400 font-medium">Ready</span> : <span className="text-[10px] text-gray-500">Not upscaled</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
