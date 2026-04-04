'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  getApiUrl,
  getDigitalDownloads,
  getEtsyListingImages,
  updateEtsyListing,
  uploadEtsyListingImage,
  deleteEtsyListingImage,
  DigitalDownloadListing,
  EtsyListingImage,
} from '@/lib/api';
import { authFetch } from '@/lib/auth';

interface ListingDetail {
  title: string;
  description: string;
  tags: string[];
  images: EtsyListingImage[];
}

export default function DigitalEditorPage() {
  const [listings, setListings] = useState<DigitalDownloadListing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ListingDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Editor state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState('');
  const [images, setImages] = useState<EtsyListingImage[]>([]);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [copyingMockups, setCopyingMockups] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Bulk state
  const [bulkAction, setBulkAction] = useState<string | null>(null);
  const [bulkProgress, setBulkProgress] = useState({ done: 0, total: 0 });

  // Load digital listings
  useEffect(() => {
    getDigitalDownloads()
      .then((data) => {
        const digital = data.listings.filter((l) => l.digital_etsy_id);
        setListings(digital);
        if (digital.length > 0 && !activeId) {
          selectListing(digital[0].digital_etsy_id);
        }
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const selectListing = useCallback(async (digitalEtsyId: string) => {
    setActiveId(digitalEtsyId);
    setDetailLoading(true);
    setError(null);
    setSuccess(null);
    setDirty(false);

    try {
      const [li, imagesData] = await Promise.all([
        authFetch(`${getApiUrl()}/etsy/listing/${digitalEtsyId}`).then((r) => r.json()),
        getEtsyListingImages(digitalEtsyId),
      ]);

      setTitle(li.title || '');
      setDescription(li.description || '');
      setTags(li.tags || []);
      setImages(
        (imagesData.results || []).sort(
          (a: EtsyListingImage, b: EtsyListingImage) => a.rank - b.rank
        )
      );
      setDetail({ title: li.title || '', description: li.description || '', tags: li.tags || [], images: imagesData.results || [] });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const activeListing = listings.find((l) => l.digital_etsy_id === activeId);

  // --- Editor actions ---

  const handleSave = async () => {
    if (!activeId) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await updateEtsyListing(activeId, { title, description, tags });
      setSuccess('Saved');
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file || !activeId) return;
    setUploading(true);
    try {
      await uploadEtsyListingImage(activeId, file);
      const data = await getEtsyListingImages(activeId);
      setImages((data.results || []).sort((a: EtsyListingImage, b: EtsyListingImage) => a.rank - b.rank));
      if (fileRef.current) fileRef.current.value = '';
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteImage = async (imageId: string) => {
    if (!activeId) return;
    try {
      await deleteEtsyListingImage(activeId, imageId);
      setImages((prev) => prev.filter((img) => String(img.listing_image_id) !== imageId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    }
  };

  const handleCopyMockups = async () => {
    if (!activeListing) return;
    setCopyingMockups(true);
    setError(null);
    try {
      const res = await authFetch(
        `${getApiUrl()}/etsy/digital-copy-mockups/${activeListing.etsy_listing_id}`,
        { method: 'POST' }
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSuccess(`Copied ${data.copied} mockups`);
      const imagesData = await getEtsyListingImages(activeId!);
      setImages((imagesData.results || []).sort((a: EtsyListingImage, b: EtsyListingImage) => a.rank - b.rank));
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
      setDirty(true);
    }
  };

  const removeTag = (idx: number) => {
    setTags(tags.filter((_, i) => i !== idx));
    setDirty(true);
  };

  // --- Bulk actions ---

  const bulkCopyMockups = async () => {
    if (!confirm(`Copy mockups from physical listings to all ${listings.length} digital listings?`)) return;
    setBulkAction('copy-mockups');
    setBulkProgress({ done: 0, total: listings.length });

    for (let i = 0; i < listings.length; i++) {
      const li = listings[i];
      try {
        await authFetch(
          `${getApiUrl()}/etsy/digital-copy-mockups/${li.etsy_listing_id}`,
          { method: 'POST' }
        );
      } catch { /* continue */ }
      setBulkProgress({ done: i + 1, total: listings.length });
      await new Promise((r) => setTimeout(r, 500));
    }

    setBulkAction(null);
    if (activeId) selectListing(activeId);
  };

  const handleExportCsv = async () => {
    try {
      const res = await authFetch(`${getApiUrl()}/etsy/digital-export-csv`);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'digital_listings.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed');
    }
  };

  const handleImportCsv = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      setBulkAction('import');
      setError(null);
      try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await authFetch(`${getApiUrl()}/etsy/digital-import-csv`, {
          method: 'POST',
          body: formData,
        });
        if (!res.ok) throw new Error('Import failed');
        const data = await res.json();
        setSuccess(`Import: ${data.updated} updated, ${data.errors} errors`);
        if (activeId) selectListing(activeId);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Import failed');
      } finally {
        setBulkAction(null);
      }
    };
    input.click();
  };

  // --- Render ---

  if (isLoading) {
    return <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>;
  }

  if (listings.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        No digital listings created yet. Go to Digital Downloads tab to create them.
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)]">
      {/* Left: Listing list */}
      <div className="w-64 border-r border-dark-border overflow-y-auto flex-shrink-0">
        {/* Bulk actions */}
        <div className="p-3 border-b border-dark-border space-y-2">
          <div className="text-xs text-gray-500 uppercase">{listings.length} Digital Listings</div>
          <button
            onClick={bulkCopyMockups}
            disabled={!!bulkAction}
            className="w-full px-2 py-1.5 bg-dark-hover text-gray-200 rounded text-xs hover:bg-dark-border disabled:opacity-50 transition-colors"
          >
            {bulkAction === 'copy-mockups'
              ? `Copying... ${bulkProgress.done}/${bulkProgress.total}`
              : 'Copy all mockups'}
          </button>
          <div className="flex gap-1.5">
            <button
              onClick={handleExportCsv}
              disabled={!!bulkAction}
              className="flex-1 px-2 py-1.5 bg-dark-hover text-gray-200 rounded text-xs hover:bg-dark-border disabled:opacity-50"
            >
              Export CSV
            </button>
            <button
              onClick={handleImportCsv}
              disabled={!!bulkAction}
              className="flex-1 px-2 py-1.5 bg-dark-hover text-gray-200 rounded text-xs hover:bg-dark-border disabled:opacity-50"
            >
              {bulkAction === 'import' ? 'Importing...' : 'Import CSV'}
            </button>
          </div>
        </div>

        {/* Bulk progress */}
        {bulkAction && (
          <div className="px-3 py-2 border-b border-dark-border">
            <div className="w-full bg-dark-hover rounded-full h-1.5">
              <div
                className="bg-accent h-1.5 rounded-full transition-all"
                style={{ width: `${bulkProgress.total > 0 ? (bulkProgress.done / bulkProgress.total) * 100 : 0}%` }}
              />
            </div>
          </div>
        )}

        {/* Listing items */}
        {listings.map((li) => (
          <div
            key={li.digital_etsy_id}
            onClick={() => selectListing(li.digital_etsy_id)}
            className={`flex items-center gap-2 px-3 py-2 cursor-pointer border-b border-dark-border/50 transition-colors ${
              activeId === li.digital_etsy_id ? 'bg-accent/10 border-l-2 border-l-accent' : 'hover:bg-dark-hover'
            }`}
          >
            {li.thumbnail ? (
              <img
                src={li.thumbnail.startsWith('/') ? `${getApiUrl()}${li.thumbnail}` : li.thumbnail}
                className="w-10 h-12 object-cover rounded flex-shrink-0"
                alt=""
              />
            ) : (
              <div className="w-10 h-12 bg-dark-hover rounded flex-shrink-0" />
            )}
            <div className="min-w-0 flex-1">
              <div className="text-xs text-gray-300 truncate">{li.title}</div>
              <div className="text-[10px] text-gray-500 font-mono">{li.upscaled_resolution}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Right: Editor */}
      <div className="flex-1 overflow-y-auto p-6">
        {detailLoading ? (
          <div className="text-gray-400 text-sm">Loading listing...</div>
        ) : !activeId ? (
          <div className="text-gray-500 text-sm">Select a listing to edit</div>
        ) : (
          <div className="max-w-2xl space-y-5">
            {/* Header */}
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-100">
                {activeListing?.title.slice(0, 50)}...
              </h2>
              <div className="flex gap-2 text-xs">
                <a
                  href={`https://www.etsy.com/listing/${activeId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:underline"
                >
                  View on Etsy
                </a>
                <a
                  href={`${getApiUrl()}/etsy/digital-zip/${activeListing?.etsy_listing_id}`}
                  className="text-accent hover:underline"
                >
                  Download ZIP
                </a>
              </div>
            </div>

            {/* Title */}
            <div>
              <label className="text-xs text-gray-500 uppercase">Title</label>
              <input
                value={title}
                onChange={(e) => { setTitle(e.target.value); setDirty(true); }}
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
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                  maxLength={20}
                  placeholder="Add tag..."
                  className="flex-1 bg-dark-hover border border-dark-border rounded px-2 py-1.5 text-xs text-gray-200"
                />
                <button onClick={addTag} className="px-3 py-1.5 bg-dark-hover text-gray-300 rounded text-xs hover:bg-dark-border">Add</button>
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="text-xs text-gray-500 uppercase">Description</label>
              <textarea
                value={description}
                onChange={(e) => { setDescription(e.target.value); setDirty(true); }}
                rows={12}
                className="w-full bg-dark-hover border border-dark-border rounded-lg px-3 py-2 text-sm text-gray-200 mt-1 resize-y font-mono"
              />
            </div>

            {/* Images */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-gray-500 uppercase">Images ({images.length})</label>
                <button
                  onClick={handleCopyMockups}
                  disabled={copyingMockups}
                  className="text-xs text-accent hover:underline disabled:opacity-50"
                >
                  {copyingMockups ? 'Copying...' : 'Copy mockups from physical'}
                </button>
              </div>
              <div className="grid grid-cols-5 gap-2">
                {images.map((img) => (
                  <div key={img.listing_image_id} className="relative group">
                    <img src={img.url_570xN} className="w-full aspect-[4/5] object-cover rounded" alt="" />
                    <button
                      onClick={() => handleDeleteImage(String(img.listing_image_id))}
                      className="absolute top-1 right-1 w-5 h-5 bg-red-500/80 text-white rounded-full text-xs hidden group-hover:flex items-center justify-center"
                    >
                      &times;
                    </button>
                    {img.rank === 1 && (
                      <div className="absolute bottom-1 left-1 px-1 bg-accent/80 text-white text-[8px] rounded">Primary</div>
                    )}
                  </div>
                ))}
              </div>
              <div className="flex gap-2 mt-2">
                <input ref={fileRef} type="file" accept="image/*" className="text-xs text-gray-400 flex-1" />
                <button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="px-3 py-1.5 bg-dark-hover text-gray-300 rounded text-xs hover:bg-dark-border disabled:opacity-50"
                >
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
              </div>
            </div>

            {/* Messages */}
            {error && <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded p-2 text-sm">{error}</div>}
            {success && <div className="bg-green-500/10 border border-green-500/30 text-green-400 rounded p-2 text-sm">{success}</div>}

            {/* Save */}
            <div className="flex gap-3">
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-6 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 disabled:opacity-50 transition-colors font-medium"
              >
                {saving ? 'Saving...' : 'Save to Etsy'}
              </button>
              {dirty && <span className="text-yellow-400 text-sm self-center">Unsaved changes</span>}
            </div>

            {/* Navigation */}
            <div className="flex justify-between pt-4 border-t border-dark-border">
              <button
                onClick={() => {
                  const idx = listings.findIndex((l) => l.digital_etsy_id === activeId);
                  if (idx > 0) selectListing(listings[idx - 1].digital_etsy_id);
                }}
                disabled={listings.findIndex((l) => l.digital_etsy_id === activeId) === 0}
                className="px-3 py-1.5 bg-dark-hover text-gray-300 rounded text-sm hover:bg-dark-border disabled:opacity-30"
              >
                Prev
              </button>
              <span className="text-sm text-gray-500 self-center">
                {listings.findIndex((l) => l.digital_etsy_id === activeId) + 1} / {listings.length}
              </span>
              <button
                onClick={() => {
                  const idx = listings.findIndex((l) => l.digital_etsy_id === activeId);
                  if (idx < listings.length - 1) selectListing(listings[idx + 1].digital_etsy_id);
                }}
                disabled={listings.findIndex((l) => l.digital_etsy_id === activeId) === listings.length - 1}
                className="px-3 py-1.5 bg-dark-hover text-gray-300 rounded text-sm hover:bg-dark-border disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
