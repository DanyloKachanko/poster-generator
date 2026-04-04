'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import {
  getApiUrl,
  getDigitalDownloads,
  toggleDigitalEnabled,
  startDigitalCreation,
  getDigitalCreationStatus,
  getEtsyListingImages,
  updateEtsyListing,
  uploadEtsyListingImage,
  deleteEtsyListingImage,
  DigitalDownloadListing,
  DigitalCreationStatus,
  EtsyListingImage,
} from '@/lib/api';
import { authFetch } from '@/lib/auth';

// --- Editor Panel ---
function EditPanel({
  listing,
  onClose,
  onSaved,
}: {
  listing: DigitalDownloadListing;
  onClose: () => void;
  onSaved: () => void;
}) {
  const digitalId = listing.digital_etsy_id;
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState('');
  const [images, setImages] = useState<EtsyListingImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [copyingMockups, setCopyingMockups] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Load listing data from Etsy
  useEffect(() => {
    if (!digitalId) return;
    setLoading(true);
    Promise.all([
      authFetch(`${getApiUrl()}/etsy/listings`).then((r) => r.json()),
      getEtsyListingImages(digitalId),
    ])
      .then(([listingsData, imagesData]) => {
        const li = (listingsData.listings || []).find(
          (l: any) => String(l.listing_id) === digitalId
        );
        if (li) {
          setTitle(li.title || '');
          setDescription(li.description || '');
          setTags(li.tags || []);
        }
        setImages(imagesData.results || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [digitalId]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await updateEtsyListing(digitalId, { title, description, tags });
      setSuccess('Saved');
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleUploadImage = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadEtsyListingImage(digitalId, file);
      const imagesData = await getEtsyListingImages(digitalId);
      setImages(imagesData.results || []);
      if (fileRef.current) fileRef.current.value = '';
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteImage = async (imageId: string) => {
    if (!confirm('Delete this image?')) return;
    try {
      await deleteEtsyListingImage(digitalId, imageId);
      setImages((prev) => prev.filter((img) => String(img.listing_image_id) !== imageId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    }
  };

  const handleCopyMockups = async () => {
    setCopyingMockups(true);
    setError(null);
    try {
      const res = await authFetch(
        `${getApiUrl()}/etsy/digital-copy-mockups/${listing.etsy_listing_id}`,
        { method: 'POST' }
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSuccess(`Copied ${data.copied} mockups`);
      const imagesData = await getEtsyListingImages(digitalId);
      setImages(imagesData.results || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Copy failed');
    } finally {
      setCopyingMockups(false);
    }
  };

  const addTag = () => {
    const t = newTag.trim().slice(0, 20);
    if (t && tags.length < 13 && !tags.includes(t)) {
      setTags([...tags, t]);
      setNewTag('');
    }
  };

  const removeTag = (idx: number) => {
    setTags(tags.filter((_, i) => i !== idx));
  };

  if (!digitalId) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Overlay */}
      <div className="flex-1 bg-black/50" onClick={onClose} />

      {/* Panel */}
      <div className="w-[500px] bg-dark-card border-l border-dark-border overflow-y-auto p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-100">Edit Digital Listing</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">&times;</button>
        </div>

        {loading ? (
          <div className="text-gray-400 text-sm">Loading...</div>
        ) : (
          <>
            {/* Title */}
            <div>
              <label className="text-xs text-gray-500 uppercase">Title</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={140}
                className="w-full bg-dark-hover border border-dark-border rounded-lg px-3 py-2 text-sm text-gray-200 mt-1"
              />
              <div className="text-[10px] text-gray-600 mt-0.5 text-right">{title.length}/140</div>
            </div>

            {/* Tags */}
            <div>
              <label className="text-xs text-gray-500 uppercase">Tags ({tags.length}/13)</label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {tags.map((tag, i) => (
                  <span key={i} className="px-2 py-0.5 bg-dark-hover text-gray-300 text-xs rounded flex items-center gap-1">
                    {tag}
                    <button onClick={() => removeTag(i)} className="text-gray-500 hover:text-red-400">&times;</button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2 mt-1.5">
                <input
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
                  maxLength={20}
                  placeholder="Add tag..."
                  className="flex-1 bg-dark-hover border border-dark-border rounded px-2 py-1 text-xs text-gray-200"
                />
                <button onClick={addTag} className="px-2 py-1 bg-dark-hover text-gray-300 rounded text-xs hover:bg-dark-border">Add</button>
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="text-xs text-gray-500 uppercase">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={8}
                className="w-full bg-dark-hover border border-dark-border rounded-lg px-3 py-2 text-sm text-gray-200 mt-1 resize-y"
              />
            </div>

            {/* Images */}
            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs text-gray-500 uppercase">Images ({images.length})</label>
                <button
                  onClick={handleCopyMockups}
                  disabled={copyingMockups}
                  className="text-xs text-accent hover:underline disabled:opacity-50"
                >
                  {copyingMockups ? 'Copying...' : 'Copy mockups from physical'}
                </button>
              </div>
              <div className="grid grid-cols-4 gap-2 mt-2">
                {images
                  .sort((a, b) => a.rank - b.rank)
                  .map((img) => (
                    <div key={img.listing_image_id} className="relative group">
                      <img
                        src={img.url_570xN}
                        className="w-full aspect-square object-cover rounded"
                        alt=""
                      />
                      <button
                        onClick={() => handleDeleteImage(String(img.listing_image_id))}
                        className="absolute top-0.5 right-0.5 w-4 h-4 bg-red-500/80 text-white rounded-full text-[10px] hidden group-hover:flex items-center justify-center"
                      >
                        &times;
                      </button>
                      {img.rank === 1 && (
                        <div className="absolute bottom-0.5 left-0.5 px-1 bg-accent/80 text-white text-[8px] rounded">
                          Primary
                        </div>
                      )}
                    </div>
                  ))}
              </div>
              <div className="flex gap-2 mt-2">
                <input ref={fileRef} type="file" accept="image/*" className="text-xs text-gray-400 flex-1" />
                <button
                  onClick={handleUploadImage}
                  disabled={uploading}
                  className="px-2 py-1 bg-dark-hover text-gray-300 rounded text-xs hover:bg-dark-border disabled:opacity-50"
                >
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
              </div>
            </div>

            {/* Links */}
            <div className="flex gap-3 text-xs">
              <a
                href={`https://www.etsy.com/listing/${digitalId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                View on Etsy
              </a>
              <a
                href={`${getApiUrl()}/etsy/digital-zip/${listing.etsy_listing_id}`}
                className="text-accent hover:underline"
              >
                Download ZIP
              </a>
            </div>

            {error && <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded p-2 text-xs">{error}</div>}
            {success && <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded p-2 text-xs">{success}</div>}

            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 disabled:opacity-50 transition-colors font-medium"
            >
              {saving ? 'Saving...' : 'Save to Etsy'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// --- Main Page ---
export default function DigitalDownloadsPage() {
  const [listings, setListings] = useState<DigitalDownloadListing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [creation, setCreation] = useState<DigitalCreationStatus | null>(null);
  const [creationPolling, setCreationPolling] = useState(false);
  const [editingListing, setEditingListing] = useState<DigitalDownloadListing | null>(null);

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

  const savedIds = useMemo(
    () => new Set(listings.filter((l) => l.is_digital).map((l) => l.id)),
    [listings]
  );
  const hasChanges = useMemo(() => {
    if (selected.size !== savedIds.size) return true;
    const selectedArr = Array.from(selected);
    for (let i = 0; i < selectedArr.length; i++) if (!savedIds.has(selectedArr[i])) return true;
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

  if (isLoading) {
    return <div className="flex items-center justify-center h-64 text-gray-400">Loading listings...</div>;
  }

  const totalUpscaled = listings.filter((l) => l.has_upscale).length;

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Digital Downloads</h1>
        <div className="text-sm text-gray-500">{totalUpscaled}/{listings.length} upscaled</div>
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
            {selected.size}<span className="text-sm text-gray-500 font-normal">/{totalUpscaled}</span>
          </div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="text-xs text-gray-500 uppercase">Created</div>
          <div className="text-2xl font-bold text-green-400">
            {listings.filter((l) => l.digital_etsy_id).length}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button onClick={selectAll} className="px-3 py-1.5 bg-dark-hover text-gray-200 rounded-lg text-sm hover:bg-dark-border transition-colors">Select All</button>
        <button onClick={deselectAll} className="px-3 py-1.5 bg-dark-hover text-gray-200 rounded-lg text-sm hover:bg-dark-border transition-colors">Deselect All</button>
        <div className="flex-1" />
        {hasChanges && <span className="text-yellow-400 text-sm">Unsaved changes</span>}
        <button onClick={handleSave} disabled={!hasChanges || saving} className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 disabled:opacity-50 transition-colors font-medium">
          {saving ? 'Saving...' : `Save Selection (${selected.size})`}
        </button>
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 text-sm">{error}</div>}
      {successMsg && <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg p-3 text-sm">{successMsg}</div>}

      {/* Create Digital Listings */}
      {savedIds.size > 0 && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-100">Create Etsy Digital Listings</h3>
              <p className="text-xs text-gray-500 mt-1">Creates new Etsy listings (type: digital) with ZIP files for {savedIds.size} saved products.</p>
            </div>
            <button onClick={handleCreateDigital} disabled={creation?.status === 'running'} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors font-medium text-sm">
              {creation?.status === 'running' ? 'Creating...' : `Create ${savedIds.size} Digital Listings`}
            </button>
          </div>
          {creation?.status === 'running' && (
            <div className="mt-3">
              <div className="flex justify-between text-sm text-gray-400 mb-1">
                <span>Creating listings...</span>
                <span>{creation.done}/{creation.total}</span>
              </div>
              <div className="w-full bg-dark-hover rounded-full h-2">
                <div className="bg-green-500 h-2 rounded-full transition-all duration-500" style={{ width: `${creation.total > 0 ? (creation.done / creation.total) * 100 : 0}%` }} />
              </div>
            </div>
          )}
          {creation?.status === 'completed' && (
            <div className="mt-3 text-sm">
              <span className="text-green-400">{creation.ok} created</span>
              {creation.errors.length > 0 && (
                <details className="mt-2">
                  <summary className="text-red-400 cursor-pointer text-xs">{creation.errors.length} failed</summary>
                  <div className="mt-1 space-y-1 text-xs text-gray-500">
                    {creation.errors.map((e, i) => <div key={i}>{e.title || e.listing_id}: {e.error}</div>)}
                  </div>
                </details>
              )}
            </div>
          )}
        </div>
      )}

      {/* Listing Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {listings.map((listing) => {
          const isSelected = selected.has(listing.id);
          const canSelect = listing.has_upscale;
          const wasSaved = savedIds.has(listing.id);
          const hasDigital = !!listing.digital_etsy_id;

          return (
            <div
              key={listing.id}
              onClick={() => {
                if (hasDigital) {
                  setEditingListing(listing);
                } else if (canSelect) {
                  toggleSelect(listing.id);
                }
              }}
              className={`bg-dark-card border rounded-lg overflow-hidden transition-all ${
                hasDigital ? 'cursor-pointer hover:border-green-500/50' : canSelect ? 'cursor-pointer hover:border-accent/50' : 'opacity-60 cursor-not-allowed'
              } ${isSelected ? 'border-accent ring-1 ring-accent/30' : 'border-dark-border'}`}
            >
              <div className="relative aspect-[4/5] bg-dark-hover">
                {listing.thumbnail ? (
                  <img src={listing.thumbnail.startsWith('/') ? `${getApiUrl()}${listing.thumbnail}` : listing.thumbnail} alt={listing.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-600 text-xs">No image</div>
                )}

                {canSelect && !hasDigital && (
                  <div className="absolute top-2 left-2">
                    <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${isSelected ? 'bg-accent border-accent text-white' : 'border-gray-400 bg-black/40'}`}>
                      {isSelected && <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>}
                    </div>
                  </div>
                )}

                {hasDigital && (
                  <div className="absolute top-2 right-2">
                    <span className="px-1.5 py-0.5 bg-green-500/80 text-white text-[10px] font-medium rounded">Digital</span>
                  </div>
                )}

                {listing.has_upscale && (
                  <div className="absolute bottom-2 right-2">
                    <span className="px-1.5 py-0.5 bg-black/70 text-green-400 text-[10px] font-mono rounded">{listing.upscaled_resolution}</span>
                  </div>
                )}
              </div>

              <div className="p-2">
                <div className="text-xs text-gray-300 truncate" title={listing.title}>{listing.title}</div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-[10px] text-gray-500 font-mono">{listing.orig_resolution}</span>
                  {hasDigital ? (
                    <span className="text-[10px] text-green-400 font-medium">Edit</span>
                  ) : listing.has_upscale ? (
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

      {/* Editor Panel */}
      {editingListing && (
        <EditPanel
          listing={editingListing}
          onClose={() => setEditingListing(null)}
          onSaved={() => {}}
        />
      )}
    </div>
  );
}
