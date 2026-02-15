'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  getEtsyStatus,
  getEtsyAuthUrl,
  disconnectEtsy,
  getEtsyListings,
  updateEtsyListing,
  aiFillListing,
  getEtsyShopSections,
  getEtsyShippingProfiles,
  getEtsyListingImages,
  uploadEtsyListingImage,
  deleteEtsyListingImage,
  setEtsyListingImagePrimary,
  getEtsyListingProperties,
  updateEtsyImagesAltTexts,
  getMockups,
  EtsyStatus,
  EtsyListing,
  AIFillResponse,
  EtsyShopSection,
  EtsyShippingProfile,
  MockupProduct,
  ETSY_COLORS,
} from '@/lib/api';
import { analyzeSeo, scoreColor, scoreBg, scoreGrade, SeoIssue, SeoAnalysis } from '@/lib/seo-score';

type SortKey = 'title' | 'views' | 'favs' | 'score';

function issueIcon(type: SeoIssue['type']): string {
  if (type === 'good') return '✓';
  if (type === 'warning') return '!';
  return '✗';
}

function issueColor(type: SeoIssue['type']): string {
  if (type === 'good') return 'text-green-400';
  if (type === 'warning') return 'text-yellow-400';
  return 'text-red-400';
}

function quickScore(listing: EtsyListing): number {
  return analyzeSeo(listing.title, listing.tags, listing.description, listing.materials || []).score;
}

export default function SeoPage() {
  const [listings, setListings] = useState<EtsyListing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [etsyStatus, setEtsyStatus] = useState<EtsyStatus | null>(null);

  // Editor
  const [activeId, setActiveId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editDesc, setEditDesc] = useState('');
  const [editMaterials, setEditMaterials] = useState<string[]>([]);
  const [editWhoMade, setEditWhoMade] = useState('i_did');
  const [editWhenMade, setEditWhenMade] = useState('made_to_order');
  const [editIsSupply, setEditIsSupply] = useState(false);
  const [editSectionId, setEditSectionId] = useState<number | null>(null);
  const [editShippingId, setEditShippingId] = useState<number | null>(null);
  const [editAutoRenew, setEditAutoRenew] = useState(true);
  const [editPrimaryColor, setEditPrimaryColor] = useState('');
  const [editSecondaryColor, setEditSecondaryColor] = useState('');
  const [editAltTexts, setEditAltTexts] = useState<string[]>(['', '', '', '', '']);
  const [newTag, setNewTag] = useState('');
  const [newMaterial, setNewMaterial] = useState('');
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  // AI Fill
  const [aiFilling, setAiFilling] = useState(false);
  const [changedFields, setChangedFields] = useState<Set<string>>(new Set());
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [aiFillAllProgress, setAiFillAllProgress] = useState<{ current: number; total: number } | null>(null);
  const [aiFillCache, setAiFillCache] = useState<Record<number, AIFillResponse>>(() => {
    if (typeof window === 'undefined') return {};
    try {
      const stored = localStorage.getItem('seo-ai-fill-cache');
      return stored ? JSON.parse(stored) : {};
    } catch { return {}; }
  });
  const aiFillAllCancelled = useRef(false);

  // Persist AI fill cache to localStorage
  useEffect(() => {
    try {
      if (Object.keys(aiFillCache).length > 0) {
        localStorage.setItem('seo-ai-fill-cache', JSON.stringify(aiFillCache));
      } else {
        localStorage.removeItem('seo-ai-fill-cache');
      }
    } catch { /* ignore quota errors */ }
  }, [aiFillCache]);

  // Image management
  const [imageLoading, setImageLoading] = useState<string | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mockupMap, setMockupMap] = useState<Record<string, MockupProduct>>({});
  const [showMockupPicker, setShowMockupPicker] = useState(false);
  const [mockupUploading, setMockupUploading] = useState<string | null>(null);

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Shop metadata
  const [shopSections, setShopSections] = useState<EtsyShopSection[]>([]);
  const [shippingProfiles, setShippingProfiles] = useState<EtsyShippingProfile[]>([]);

  // Search & Sort
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortAsc, setSortAsc] = useState(true);

  const listingScores = useMemo(() => {
    const map: Record<number, number> = {};
    listings.forEach((l) => { map[l.listing_id] = quickScore(l); });
    return map;
  }, [listings]);

  const filteredListings = useMemo(() => {
    let result = listings;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (l) =>
          l.title.toLowerCase().includes(q) ||
          l.tags.some((t) => t.toLowerCase().includes(q))
      );
    }
    result = [...result].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'title') cmp = a.title.localeCompare(b.title);
      else if (sortKey === 'views') cmp = (a.views || 0) - (b.views || 0);
      else if (sortKey === 'favs') cmp = (a.num_favorers || 0) - (b.num_favorers || 0);
      else if (sortKey === 'score') cmp = (listingScores[a.listing_id] || 0) - (listingScores[b.listing_id] || 0);
      return sortAsc ? cmp : -cmp;
    });
    return result;
  }, [listings, search, sortKey, sortAsc, listingScores]);

  const analysis = useMemo(
    () => analyzeSeo(editTitle, editTags, editDesc, editMaterials),
    [editTitle, editTags, editDesc, editMaterials]
  );

  const activeListing = listings.find((l) => l.listing_id === activeId);

  // Count listings that need AI fill
  const needsFillCount = useMemo(
    () => listings.filter((l) => l.tags.length < 13 || l.description.length < 300).length,
    [listings]
  );

  const loadEtsyStatus = useCallback(() => {
    getEtsyStatus().then(setEtsyStatus).catch(() => {});
  }, []);

  const loadListings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getEtsyListings();
      setListings(data.listings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load listings');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadEtsyStatus(); }, [loadEtsyStatus]);

  useEffect(() => {
    if (etsyStatus?.connected) {
      loadListings();
      getEtsyShopSections().then((d) => setShopSections(d.results || [])).catch(() => {});
      getEtsyShippingProfiles().then((d) => setShippingProfiles(d.results || [])).catch(() => {});
      getMockups().then((list) => {
        const map: Record<string, MockupProduct> = {};
        for (const m of list) {
          if (m.etsy_listing_id) map[m.etsy_listing_id] = m;
        }
        setMockupMap(map);
      }).catch(() => {});
    } else {
      setIsLoading(false);
    }
  }, [etsyStatus?.connected, loadListings]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data === 'etsy-connected') loadEtsyStatus();
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
    await disconnectEtsy().catch(() => {});
    setEtsyStatus({ configured: true, connected: false });
    setListings([]);
    setActiveId(null);
  };

  // === Editor ===

  const applyAiFillResult = (result: AIFillResponse) => {
    const changed = new Set<string>();
    if (result.title !== editTitle) { setEditTitle(result.title); changed.add('title'); }
    if (JSON.stringify(result.tags) !== JSON.stringify(editTags)) { setEditTags([...result.tags]); changed.add('tags'); }
    if (result.description !== editDesc) { setEditDesc(result.description); changed.add('description'); }
    if (result.materials && JSON.stringify(result.materials) !== JSON.stringify(editMaterials)) {
      setEditMaterials([...result.materials]); changed.add('materials');
    }
    if (result.primary_color && result.primary_color !== editPrimaryColor) {
      setEditPrimaryColor(result.primary_color); changed.add('primary_color');
    }
    if (result.secondary_color && result.secondary_color !== editSecondaryColor) {
      setEditSecondaryColor(result.secondary_color); changed.add('secondary_color');
    }
    if (result.alt_texts?.length) {
      setEditAltTexts([...result.alt_texts, '', '', '', '', ''].slice(0, 5)); changed.add('alt_texts');
    }
    setChangedFields(changed);
    setDirty(true);
    setValidationWarnings(result.validation_errors || []);
  };

  const openEditor = (listing: EtsyListing) => {
    setActiveId(listing.listing_id);
    setEditTitle(listing.title);
    setEditTags([...listing.tags]);
    setEditDesc(listing.description);
    setEditMaterials([...(listing.materials || [])]);
    setEditWhoMade(listing.who_made || 'i_did');
    setEditWhenMade(listing.when_made || 'made_to_order');
    setEditIsSupply(listing.is_supply ?? false);
    setEditSectionId(listing.shop_section_id ?? null);
    setEditShippingId(listing.shipping_profile_id ?? null);
    setEditAutoRenew(listing.should_auto_renew ?? true);
    setEditPrimaryColor('');
    setEditSecondaryColor('');
    setEditAltTexts(['', '', '', '', '']);
    setNewTag('');
    setNewMaterial('');
    setDirty(false);
    setChangedFields(new Set());
    setValidationWarnings([]);
    setError(null);
    setSuccessMsg(null);
    setShowMockupPicker(false);

    // Fetch current color properties (non-blocking)
    getEtsyListingProperties(String(listing.listing_id)).then((data) => {
      if (data.colors.primary_color) setEditPrimaryColor(data.colors.primary_color);
      if (data.colors.secondary_color) setEditSecondaryColor(data.colors.secondary_color);
    }).catch(() => {});

    // Apply cached AI fill result if available
    const cached = aiFillCache[listing.listing_id];
    if (cached) {
      setEditTitle(cached.title);
      setEditTags([...cached.tags]);
      setEditDesc(cached.description);
      if (cached.materials) setEditMaterials([...cached.materials]);
      if (cached.primary_color) setEditPrimaryColor(cached.primary_color);
      if (cached.secondary_color) setEditSecondaryColor(cached.secondary_color);
      if (cached.alt_texts?.length) setEditAltTexts([...cached.alt_texts, '', '', '', '', ''].slice(0, 5));
      setDirty(true);
      setChangedFields(new Set(['title', 'tags', 'description', 'materials']));
      setValidationWarnings(cached.validation_errors || []);
    }
  };

  const handleSave = async () => {
    if (!activeId) return;
    setSaving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await updateEtsyListing(String(activeId), {
        title: editTitle,
        tags: editTags,
        description: editDesc,
        materials: editMaterials,
        who_made: editWhoMade,
        when_made: editWhenMade,
        is_supply: editIsSupply,
        ...(editSectionId != null ? { shop_section_id: editSectionId } : {}),
        ...(editShippingId != null ? { shipping_profile_id: editShippingId } : {}),
        should_auto_renew: editAutoRenew,
        ...(editPrimaryColor ? { primary_color: editPrimaryColor } : {}),
        ...(editSecondaryColor ? { secondary_color: editSecondaryColor } : {}),
      });
      // Update alt texts on images if any are set
      const nonEmptyAltTexts = editAltTexts.filter(t => t.trim());
      if (nonEmptyAltTexts.length > 0) {
        try {
          await updateEtsyImagesAltTexts(String(activeId), editAltTexts);
        } catch (e) {
          console.warn('Failed to set alt texts:', e);
        }
      }
      setSuccessMsg('Saved to Etsy!');
      setDirty(false);
      setChangedFields(new Set());
      // Remove from cache after successful save
      if (aiFillCache[activeId]) {
        const newCache = { ...aiFillCache };
        delete newCache[activeId];
        setAiFillCache(newCache);
      }
      // Update local listing data immediately so sidebar score reflects saved content
      // (Etsy API may return stale data if refetched too soon)
      setListings(prev => prev.map(l =>
        l.listing_id === activeId
          ? { ...l, title: editTitle, tags: editTags, description: editDesc, materials: editMaterials }
          : l
      ));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save';
      // Preserve current edits in cache so they survive page refresh
      if (activeId && dirty) {
        setAiFillCache(prev => ({
          ...prev,
          [activeId]: {
            title: editTitle, tags: editTags, description: editDesc,
            materials: editMaterials, superstar_keyword: editTags[0] || '',
            primary_color: editPrimaryColor, secondary_color: editSecondaryColor,
            alt_texts: editAltTexts,
            validation_errors: [], is_valid: true,
          },
        }));
      }
      if (msg.includes('404')) {
        // Auto-refresh listings to remove stale entries, then show error
        loadListings().then(() => {
          setError(`Listing not found on Etsy (deleted or expired). AI content saved locally.`);
        });
      } else {
        setError(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  // === AI Fill ===

  const handleAiFill = async () => {
    if (!activeListing) return;
    const imageUrl = activeListing.images?.[0]?.url_570xN;
    if (!imageUrl) {
      setError('No image available for this listing');
      return;
    }

    setAiFilling(true);
    setError(null);
    setChangedFields(new Set());
    setValidationWarnings([]);

    try {
      const result = await aiFillListing({
        image_url: imageUrl,
        current_title: editTitle,
      });
      applyAiFillResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI Fill failed');
    } finally {
      setAiFilling(false);
    }
  };

  const handleAiFillAll = async () => {
    const toFill = filteredListings.filter(
      (l) => l.tags.length < 13 || l.description.length < 300
    );
    if (toFill.length === 0) {
      setError('All listings already have good SEO (13 tags + 300+ char description)');
      return;
    }

    aiFillAllCancelled.current = false;
    setAiFillAllProgress({ current: 0, total: toFill.length });
    const cache: Record<number, AIFillResponse> = { ...aiFillCache };

    for (let i = 0; i < toFill.length; i++) {
      if (aiFillAllCancelled.current) break;

      const listing = toFill[i];
      setAiFillAllProgress({ current: i + 1, total: toFill.length });

      const imageUrl = listing.images?.[0]?.url_570xN;
      if (!imageUrl) continue;

      try {
        const result = await aiFillListing({
          image_url: imageUrl,
          current_title: listing.title,
        });
        cache[listing.listing_id] = result;
      } catch {
        // Skip failed listings
      }

      // Rate limit
      if (i < toFill.length - 1 && !aiFillAllCancelled.current) {
        await new Promise((r) => setTimeout(r, 1500));
      }
    }

    setAiFillCache(cache);
    setAiFillAllProgress(null);

    // Apply to current listing if it was filled
    if (activeId && cache[activeId]) {
      applyAiFillResult(cache[activeId]);
    }

    setSuccessMsg(
      `AI Fill complete: ${Object.keys(cache).length} listings ready. Open each to review & save.`
    );
  };

  const cancelAiFillAll = () => {
    aiFillAllCancelled.current = true;
  };

  const markDirty = () => setDirty(true);

  const removeTag = (index: number) => {
    setEditTags(editTags.filter((_, i) => i !== index));
    markDirty();
  };

  const addTag = () => {
    const tag = newTag.trim().toLowerCase();
    if (!tag || tag.length > 20 || editTags.length >= 13) return;
    setEditTags([...editTags, tag]);
    setNewTag('');
    markDirty();
  };

  const removeMaterial = (index: number) => {
    setEditMaterials(editMaterials.filter((_, i) => i !== index));
    markDirty();
  };

  const addMaterial = () => {
    const mat = newMaterial.trim();
    if (!mat || editMaterials.length >= 13) return;
    setEditMaterials([...editMaterials, mat]);
    setNewMaterial('');
    markDirty();
  };

  const toggleSelect = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(key === 'title'); }
  };

  // Helper for highlight ring on AI-filled fields
  const fieldHighlight = (field: string) =>
    changedFields.has(field) ? 'ring-2 ring-yellow-500/40' : '';

  // === Image Management ===

  const refreshImages = useCallback(async () => {
    if (!activeId) return;
    try {
      const data = await getEtsyListingImages(String(activeId));
      setListings(prev => prev.map(l =>
        l.listing_id === activeId
          ? { ...l, images: data.results }
          : l
      ));
    } catch {
      // Silent — images still show from last load
    }
  }, [activeId]);

  const handleSetPrimary = async (imageId: number) => {
    if (!activeId || imageLoading) return;
    setImageLoading(String(imageId));
    try {
      await setEtsyListingImagePrimary(String(activeId), String(imageId));
      await refreshImages();
      setSuccessMsg('Primary image updated');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set primary');
    } finally {
      setImageLoading(null);
    }
  };

  const handleDeleteImage = async (imageId: number) => {
    if (!activeId || imageLoading) return;
    const images = activeListing?.images || [];
    if (images.length <= 1) {
      setError('Cannot delete the last image — Etsy requires at least one');
      return;
    }
    setImageLoading(String(imageId));
    try {
      await deleteEtsyListingImage(String(activeId), String(imageId));
      await refreshImages();
      setSuccessMsg('Image deleted');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete image');
    } finally {
      setImageLoading(null);
    }
  };

  const handleUploadImage = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!activeId || !e.target.files?.length) return;
    const images = activeListing?.images || [];
    if (images.length >= 10) {
      setError('Etsy allows a maximum of 10 images per listing');
      return;
    }
    setImageUploading(true);
    setError(null);
    try {
      await uploadEtsyListingImage(String(activeId), e.target.files[0]);
      await refreshImages();
      setSuccessMsg('Image uploaded');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload image');
    } finally {
      setImageUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleUploadMockup = async (mockupSrc: string) => {
    if (!activeId || mockupUploading) return;
    const images = activeListing?.images || [];
    if (images.length >= 10) {
      setError('Etsy allows a maximum of 10 images per listing');
      return;
    }
    setMockupUploading(mockupSrc);
    setError(null);
    try {
      const resp = await fetch(mockupSrc);
      const blob = await resp.blob();
      const file = new File([blob], 'mockup.jpg', { type: blob.type || 'image/jpeg' });
      await uploadEtsyListingImage(String(activeId), file);
      await refreshImages();
      setSuccessMsg('Mockup uploaded to Etsy');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload mockup');
    } finally {
      setMockupUploading(null);
    }
  };

  const activeMockups = activeId ? mockupMap[String(activeId)] : null;

  // === Not connected ===

  if (!etsyStatus || !etsyStatus.connected) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-20 text-center">
        <h1 className="text-2xl font-bold text-gray-100 mb-2">SEO Editor</h1>
        <p className="text-gray-500 mb-8">Connect your Etsy shop to manage listing SEO</p>
        {etsyStatus && !etsyStatus.connected && (
          <button
            onClick={handleConnectEtsy}
            className="px-6 py-3 bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent/90 transition-colors"
          >
            Connect Etsy
          </button>
        )}
        {!etsyStatus && <p className="text-gray-600">Loading...</p>}
      </div>
    );
  }

  // === Main layout ===

  const cachedCount = Object.keys(aiFillCache).length;

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Top bar */}
      <div className="flex-shrink-0 border-b border-dark-border bg-dark-card/50 px-4 py-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold text-gray-100">SEO Editor</h1>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-green-400" />
              <span className="text-xs text-gray-500">{listings.length} listings</span>
            </div>
            {cachedCount > 0 && (
              <span className="px-2 py-0.5 bg-yellow-900/30 border border-yellow-700/30 rounded text-[11px] text-yellow-400">
                {cachedCount} AI-filled, unsaved
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {aiFillAllProgress ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-purple-300">
                  AI Fill {aiFillAllProgress.current}/{aiFillAllProgress.total}...
                </span>
                <div className="w-24 h-1.5 bg-dark-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full transition-all"
                    style={{ width: `${(aiFillAllProgress.current / aiFillAllProgress.total) * 100}%` }}
                  />
                </div>
                <button
                  onClick={cancelAiFillAll}
                  className="px-2 py-1 text-xs text-red-400 hover:text-red-300"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={handleAiFillAll}
                disabled={isLoading || needsFillCount === 0}
                className="px-3 py-1.5 bg-purple-600/20 border border-purple-500/30 text-purple-300 rounded-md text-xs font-medium hover:bg-purple-600/30 transition-colors disabled:opacity-40"
                title={needsFillCount > 0 ? `Fill ${needsFillCount} listings with <13 tags or <300 char desc` : 'All listings have good SEO'}
              >
                AI Fill All ({needsFillCount})
              </button>
            )}
            <button
              onClick={loadListings}
              disabled={isLoading}
              className="px-3 py-1.5 bg-dark-card border border-dark-border rounded-md text-xs text-gray-400 hover:text-gray-200 transition-colors disabled:opacity-50"
            >
              Refresh
            </button>
            <button
              onClick={handleDisconnectEtsy}
              className="px-3 py-1.5 text-xs text-gray-600 hover:text-red-400 transition-colors"
            >
              Disconnect
            </button>
          </div>
        </div>
        {error && (
          <div className="mt-2 bg-red-900/20 border border-red-800/50 rounded px-3 py-2 text-sm text-red-400">{error}</div>
        )}
        {successMsg && (
          <div className="mt-2 bg-green-900/20 border border-green-800/50 rounded px-3 py-2 text-sm text-green-400">{successMsg}</div>
        )}
      </div>

      {/* Content: sidebar + editor */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Listing sidebar */}
        <div className="w-[360px] flex-shrink-0 border-r border-dark-border flex flex-col">
          {/* Search + Sort */}
          <div className="flex-shrink-0 px-2 py-2 border-b border-dark-border space-y-1.5">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search listings..."
              className="w-full bg-dark-bg border border-dark-border rounded px-2.5 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-accent placeholder-gray-600"
            />
            <div className="flex items-center gap-1">
              {(['score', 'title', 'views', 'favs'] as SortKey[]).map((key) => (
                <button
                  key={key}
                  onClick={() => handleSort(key)}
                  className={`px-2 py-0.5 rounded text-[11px] transition-colors ${
                    sortKey === key ? 'bg-accent/15 text-accent' : 'text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {key}{sortKey === key ? (sortAsc ? ' ↑' : ' ↓') : ''}
                </button>
              ))}
              <div className="flex-1" />
              <label className="flex items-center gap-1.5 cursor-pointer text-[11px] text-gray-500 hover:text-gray-300">
                <input
                  type="checkbox"
                  checked={selectedIds.size === filteredListings.length && filteredListings.length > 0}
                  onChange={() => {
                    if (selectedIds.size === filteredListings.length) setSelectedIds(new Set());
                    else setSelectedIds(new Set(filteredListings.map((l) => String(l.listing_id))));
                  }}
                  className="w-3 h-3 rounded accent-accent"
                />
                All
              </label>
            </div>
          </div>

          {/* Listing items */}
          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="p-8 text-center text-gray-500">Loading...</div>
            ) : filteredListings.length === 0 ? (
              <div className="p-8 text-center text-gray-600 text-xs">
                {search ? 'No matching listings' : 'No listings found'}
              </div>
            ) : (
              filteredListings.map((listing) => {
                const isActive = activeId === listing.listing_id;
                const isSelected = selectedIds.has(String(listing.listing_id));
                const thumb = listing.images?.[0]?.url_570xN;
                const lScore = listingScores[listing.listing_id] ?? 0;
                const hasCached = !!aiFillCache[listing.listing_id];

                return (
                  <div
                    key={listing.listing_id}
                    className={`flex items-center gap-2.5 px-2 py-2 border-b border-dark-border cursor-pointer transition-colors ${
                      isActive
                        ? 'bg-accent/10 border-l-2 border-l-accent'
                        : isSelected
                          ? 'bg-accent/5'
                          : 'hover:bg-dark-hover'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => { e.stopPropagation(); toggleSelect(String(listing.listing_id)); }}
                      className="w-3 h-3 rounded accent-accent flex-shrink-0"
                    />
                    {thumb && (
                      <img
                        src={thumb}
                        alt=""
                        onClick={() => openEditor(listing)}
                        className="w-20 h-28 rounded object-cover flex-shrink-0"
                      />
                    )}
                    <div className="flex-1 min-w-0" onClick={() => openEditor(listing)}>
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className={`text-[11px] font-bold ${scoreColor(lScore)}`}>
                          {scoreGrade(lScore)} {lScore}
                        </span>
                        <div className="flex-1 h-1 bg-dark-border rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${scoreBg(lScore)}`} style={{ width: `${lScore}%` }} />
                        </div>
                        {hasCached && (
                          <span className="text-[10px] text-yellow-400 flex-shrink-0">AI</span>
                        )}
                      </div>
                      <h3 className="text-xs text-gray-200 leading-tight line-clamp-2">{listing.title}</h3>
                      <div className="flex items-center gap-2 mt-0.5 text-[11px] text-gray-500">
                        <span>{listing.views || 0} views</span>
                        <span>{listing.num_favorers || 0} favs</span>
                        <span>{listing.tags.length}/13 tags</span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Selection bar */}
          {selectedIds.size > 0 && (
            <div className="flex-shrink-0 border-t border-dark-border bg-dark-card/80 px-3 py-2 flex items-center justify-between">
              <span className="text-xs text-gray-300">{selectedIds.size} selected</span>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-[11px] text-gray-500 hover:text-gray-300"
              >
                Clear
              </button>
            </div>
          )}
        </div>

        {/* Right: Editor panel */}
        <div className="flex-1 overflow-y-auto">
          {!activeListing ? (
            <div className="flex items-center justify-center h-full text-gray-600 text-sm">
              Select a listing to edit
            </div>
          ) : (
            <div className="p-4">
              {/* Header */}
              <div className="flex items-center gap-3 mb-3">
                {activeListing.images?.[0]?.url_570xN && (
                  <img src={activeListing.images[0].url_570xN} alt="" className="w-10 h-10 rounded object-cover flex-shrink-0" />
                )}
                <div className="flex items-center gap-3 flex-1 min-w-0 text-xs text-gray-500">
                  <span>#{activeListing.listing_id}</span>
                  <span>{activeListing.views || 0} views / {activeListing.num_favorers || 0} favs</span>
                  {activeListing.url && (
                    <a href={activeListing.url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">Etsy &#8599;</a>
                  )}
                </div>
              </div>

              {/* Image Manager */}
              {(activeListing.images?.length || 0) > 0 && (
                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-medium text-gray-400">
                      Images ({activeListing.images?.length || 0}/10)
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/jpeg,image/png,image/gif,image/webp"
                        onChange={handleUploadImage}
                        className="hidden"
                      />
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        disabled={imageUploading || (activeListing.images?.length || 0) >= 10}
                        className="px-2 py-1 bg-dark-card border border-dark-border rounded text-[11px] text-gray-400 hover:text-gray-200 transition-colors disabled:opacity-40"
                      >
                        {imageUploading ? 'Uploading...' : '+ Upload'}
                      </button>
                      {activeMockups && activeMockups.images.length > 0 && (
                        <button
                          onClick={() => setShowMockupPicker(!showMockupPicker)}
                          disabled={(activeListing.images?.length || 0) >= 10}
                          className={`px-2 py-1 border rounded text-[11px] font-medium transition-colors disabled:opacity-40 ${
                            showMockupPicker
                              ? 'bg-orange-600/20 border-orange-500/40 text-orange-300'
                              : 'bg-orange-900/15 border-orange-700/30 text-orange-400 hover:bg-orange-600/20'
                          }`}
                        >
                          Printify ({activeMockups.images.length})
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="bg-dark-bg border border-dark-border rounded p-2">
                    <div className="flex gap-2 overflow-x-auto pb-1">
                      {(activeListing.images || []).map((img, i) => {
                        const isPrimary = i === 0;
                        const isLoadingThis = imageLoading === String(img.listing_image_id);
                        return (
                          <div
                            key={img.listing_image_id}
                            className={`relative flex-shrink-0 w-20 group ${isPrimary ? 'ring-2 ring-accent rounded' : ''}`}
                          >
                            <img
                              src={img.url_570xN}
                              alt={`Image ${i + 1}`}
                              className={`w-20 h-28 object-cover rounded ${isLoadingThis ? 'opacity-40' : ''}`}
                            />
                            {isLoadingThis && (
                              <div className="absolute inset-0 flex items-center justify-center">
                                <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
                              </div>
                            )}
                            {isPrimary && (
                              <div className="absolute top-0.5 left-0.5 px-1 py-0.5 bg-accent/90 rounded text-[9px] font-bold text-dark-bg">
                                1st
                              </div>
                            )}
                            {!isLoadingThis && (
                              <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity rounded flex flex-col items-center justify-center gap-1">
                                {!isPrimary && (
                                  <button
                                    onClick={() => handleSetPrimary(img.listing_image_id)}
                                    className="px-1.5 py-0.5 bg-accent/80 text-dark-bg rounded text-[10px] font-medium hover:bg-accent"
                                  >
                                    Set 1st
                                  </button>
                                )}
                                <button
                                  onClick={() => handleDeleteImage(img.listing_image_id)}
                                  className="px-1.5 py-0.5 bg-red-600/80 text-white rounded text-[10px] font-medium hover:bg-red-600"
                                >
                                  Delete
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {/* Printify Mockup Picker */}
                    {showMockupPicker && activeMockups && activeMockups.images.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-dark-border">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-[11px] font-medium text-orange-400">Printify Mockups</span>
                          <span className="text-[10px] text-gray-500">{activeMockups.title}</span>
                        </div>
                        <div className="flex gap-2 overflow-x-auto pb-1">
                          {activeMockups.images.map((mockup, i) => {
                            const isUploading = mockupUploading === mockup.src;
                            return (
                              <div
                                key={i}
                                className="relative flex-shrink-0 w-20 group cursor-pointer"
                                onClick={() => !isUploading && handleUploadMockup(mockup.src)}
                              >
                                <img
                                  src={mockup.src}
                                  alt={`Mockup ${i + 1}`}
                                  className={`w-20 h-28 object-cover rounded border border-orange-700/30 ${isUploading ? 'opacity-40' : ''}`}
                                />
                                {isUploading && (
                                  <div className="absolute inset-0 flex items-center justify-center">
                                    <div className="animate-spin h-5 w-5 border-2 border-orange-400 border-t-transparent rounded-full" />
                                  </div>
                                )}
                                {mockup.is_default && (
                                  <div className="absolute top-0.5 left-0.5 px-1 py-0.5 bg-orange-500/90 rounded text-[9px] font-bold text-white">
                                    DEF
                                  </div>
                                )}
                                {mockup.size && (
                                  <div className="absolute bottom-0.5 left-0.5 px-1 py-0.5 bg-dark-bg/90 rounded text-[9px] text-gray-300 font-medium">
                                    {mockup.size}
                                  </div>
                                )}
                                {!isUploading && (
                                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity rounded flex items-center justify-center">
                                    <span className="px-1.5 py-0.5 bg-orange-500/80 text-white rounded text-[10px] font-medium">
                                      Upload
                                    </span>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* SEO Score Panel */}
              <div className="mb-3 bg-dark-bg border border-dark-border rounded p-3">
                <div className="flex items-center gap-4 mb-2">
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${scoreColor(analysis.score)}`}>{analysis.score}</div>
                    <div className={`text-[10px] font-bold ${scoreColor(analysis.score)}`}>{scoreGrade(analysis.score)}</div>
                  </div>
                  <div className="flex-1 grid grid-cols-3 gap-2">
                    {([['Title', analysis.titleScore, 25], ['Tags', analysis.tagsScore, 25], ['Desc', analysis.descScore, 25]] as const).map(([label, s, max]) => (
                      <div key={label} className="text-center">
                        <div className={`text-sm font-semibold ${scoreColor((s / max) * 100)}`}>{s}/{max}</div>
                        <div className="text-[10px] text-gray-500">{label}</div>
                        <div className="h-1 bg-dark-border rounded-full mt-1 overflow-hidden">
                          <div className={`h-full rounded-full ${scoreBg((s / max) * 100)}`} style={{ width: `${(s / max) * 100}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="space-y-0.5 max-h-28 overflow-y-auto">
                  {analysis.issues.map((issue, i) => (
                    <div key={i} className={`flex items-start gap-1.5 text-[11px] ${issueColor(issue.type)}`}>
                      <span className="w-3 text-center flex-shrink-0 font-bold">{issueIcon(issue.type)}</span>
                      <span className="text-gray-500 w-12 flex-shrink-0">{issue.area}</span>
                      <span>{issue.message}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Validation warnings from AI Fill */}
              {validationWarnings.length > 0 && (
                <div className="mb-3 bg-yellow-900/15 border border-yellow-700/30 rounded p-2.5">
                  <div className="text-[11px] font-medium text-yellow-400 mb-1">AI Fill Warnings</div>
                  {validationWarnings.map((w, i) => (
                    <div key={i} className="text-[11px] text-yellow-400/80">• {w}</div>
                  ))}
                </div>
              )}

              {/* Title */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-400">
                    Title
                    {changedFields.has('title') && <span className="text-yellow-400 ml-1.5">● AI</span>}
                  </label>
                  <span className={`text-[11px] font-mono ${editTitle.length > 140 ? 'text-red-400' : editTitle.length > 120 ? 'text-yellow-400' : 'text-gray-600'}`}>
                    {editTitle.length}/140
                  </span>
                </div>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => { setEditTitle(e.target.value); markDirty(); }}
                  className={`w-full bg-dark-bg border border-dark-border rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-accent transition-colors ${fieldHighlight('title')}`}
                />
              </div>

              {/* Tags */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-400">
                    Tags
                    {changedFields.has('tags') && <span className="text-yellow-400 ml-1.5">● AI</span>}
                  </label>
                  <span className={`text-[11px] font-mono ${editTags.length > 13 ? 'text-red-400' : editTags.length < 13 ? 'text-yellow-400' : 'text-green-400'}`}>
                    {editTags.length}/13
                  </span>
                </div>
                <div className={`bg-dark-bg border border-dark-border rounded p-2 ${fieldHighlight('tags')}`}>
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {editTags.map((tag, i) => (
                      <span
                        key={i}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border ${
                          tag.length > 20
                            ? 'border-red-800 bg-red-900/20 text-red-300'
                            : 'border-dark-border bg-dark-card text-gray-300'
                        }`}
                      >
                        {tag}
                        <button
                          onClick={() => removeTag(i)}
                          className="text-gray-500 hover:text-red-400 ml-0.5 leading-none"
                        >
                          &times;
                        </button>
                      </span>
                    ))}
                  </div>
                  {editTags.length < 13 && (
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newTag}
                        onChange={(e) => setNewTag(e.target.value.toLowerCase())}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                        placeholder="Add tag + Enter"
                        maxLength={20}
                        className="flex-1 bg-transparent border-b border-dark-border px-1 py-1 text-xs text-gray-200 focus:outline-none focus:border-accent placeholder-gray-600"
                      />
                      <span className="text-[11px] text-gray-600 self-end py-1">{newTag.length}/20</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Description */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-400">
                    Description
                    {changedFields.has('description') && <span className="text-yellow-400 ml-1.5">● AI</span>}
                  </label>
                  <span className={`text-[11px] font-mono ${editDesc.length < 300 ? 'text-yellow-400' : 'text-gray-600'}`}>
                    {editDesc.length} chars
                  </span>
                </div>
                <textarea
                  value={editDesc}
                  onChange={(e) => { setEditDesc(e.target.value); markDirty(); }}
                  rows={8}
                  className={`w-full bg-dark-bg border border-dark-border rounded px-3 py-1.5 text-xs text-gray-300 leading-relaxed focus:outline-none focus:border-accent transition-colors resize-y ${fieldHighlight('description')}`}
                />
              </div>

              {/* Materials */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-400">
                    Materials
                    {changedFields.has('materials') && <span className="text-yellow-400 ml-1.5">● AI</span>}
                  </label>
                  <span className="text-[11px] text-gray-600">{editMaterials.length}/13</span>
                </div>
                <div className={`bg-dark-bg border border-dark-border rounded p-2 ${fieldHighlight('materials')}`}>
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {editMaterials.map((mat, i) => (
                      <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border border-dark-border bg-dark-card text-gray-300">
                        {mat}
                        <button onClick={() => removeMaterial(i)} className="text-gray-500 hover:text-red-400 ml-0.5 leading-none">&times;</button>
                      </span>
                    ))}
                  </div>
                  {editMaterials.length < 13 && (
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newMaterial}
                        onChange={(e) => setNewMaterial(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addMaterial(); } }}
                        placeholder="Add material + Enter"
                        className="flex-1 bg-transparent border-b border-dark-border px-1 py-1 text-xs text-gray-200 focus:outline-none focus:border-accent placeholder-gray-600"
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Colors */}
              <div className="mb-3">
                <label className="text-xs font-medium text-gray-400 block mb-1.5">
                  Colors
                  {(changedFields.has('primary_color') || changedFields.has('secondary_color')) && <span className="text-yellow-400 ml-1.5">● AI</span>}
                </label>
                <div className={`bg-dark-bg border border-dark-border rounded p-3 grid grid-cols-2 gap-3 ${changedFields.has('primary_color') || changedFields.has('secondary_color') ? 'border-yellow-400/30' : ''}`}>
                  <div>
                    <label className="text-[11px] text-gray-500 block mb-1">Primary color</label>
                    <select
                      value={editPrimaryColor}
                      onChange={(e) => { setEditPrimaryColor(e.target.value); markDirty(); }}
                      className="w-full bg-dark-card border border-dark-border rounded px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-accent"
                    >
                      <option value="">None</option>
                      {ETSY_COLORS.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] text-gray-500 block mb-1">Secondary color</label>
                    <select
                      value={editSecondaryColor}
                      onChange={(e) => { setEditSecondaryColor(e.target.value); markDirty(); }}
                      className="w-full bg-dark-card border border-dark-border rounded px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-accent"
                    >
                      <option value="">None</option>
                      {ETSY_COLORS.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Alt Texts (5 images) */}
              <div className="mb-3">
                <label className="text-xs font-medium text-gray-400 block mb-1.5">
                  Image Alt Texts
                  {changedFields.has('alt_texts') && <span className="text-yellow-400 ml-1.5">● AI</span>}
                </label>
                <div className={`bg-dark-bg border border-dark-border rounded p-2 space-y-1.5 ${changedFields.has('alt_texts') ? 'border-yellow-400/30' : ''}`}>
                  {editAltTexts.map((alt, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <span className="text-[10px] text-gray-600 w-3 flex-shrink-0">{i + 1}</span>
                      <input
                        type="text"
                        value={alt}
                        onChange={(e) => {
                          const updated = [...editAltTexts];
                          updated[i] = e.target.value.slice(0, 250);
                          setEditAltTexts(updated);
                          markDirty();
                        }}
                        placeholder={i === 0 ? 'Poster artwork description...' : `Image ${i + 1} alt text...`}
                        className="flex-1 bg-dark-card border border-dark-border rounded px-2 py-1 text-[11px] text-gray-200 focus:outline-none focus:border-accent"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Listing Details */}
              <div className="mb-3">
                <label className="text-xs font-medium text-gray-400 block mb-1.5">Details</label>
                <div className="bg-dark-bg border border-dark-border rounded p-3 grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] text-gray-500 block mb-1">Who made it</label>
                    <select
                      value={editWhoMade}
                      onChange={(e) => { setEditWhoMade(e.target.value); markDirty(); }}
                      className="w-full bg-dark-card border border-dark-border rounded px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-accent"
                    >
                      <option value="i_did">I did</option>
                      <option value="someone_else">Someone else</option>
                      <option value="collective">A member of my shop</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] text-gray-500 block mb-1">When was it made</label>
                    <select
                      value={editWhenMade}
                      onChange={(e) => { setEditWhenMade(e.target.value); markDirty(); }}
                      className="w-full bg-dark-card border border-dark-border rounded px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-accent"
                    >
                      <option value="made_to_order">Made to order</option>
                      <option value="2020_2025">2020-2025</option>
                      <option value="2010_2019">2010-2019</option>
                      <option value="2000_2009">2000-2009</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] text-gray-500 block mb-1">Shop section</label>
                    <select
                      value={editSectionId ?? ''}
                      onChange={(e) => { setEditSectionId(e.target.value ? Number(e.target.value) : null); markDirty(); }}
                      className="w-full bg-dark-card border border-dark-border rounded px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-accent"
                    >
                      <option value="">None</option>
                      {shopSections.map((s) => (
                        <option key={s.shop_section_id} value={s.shop_section_id}>
                          {s.title} ({s.active_listing_count})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="text-[11px] text-gray-500 block mb-1">Shipping profile</label>
                    <select
                      value={editShippingId ?? ''}
                      onChange={(e) => { setEditShippingId(e.target.value ? Number(e.target.value) : null); markDirty(); }}
                      className="w-full bg-dark-card border border-dark-border rounded px-2 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-accent"
                    >
                      <option value="">None</option>
                      {shippingProfiles.map((p) => (
                        <option key={p.shipping_profile_id} value={p.shipping_profile_id}>
                          {p.title} ({p.min_processing_days}-{p.max_processing_days}d)
                        </option>
                      ))}
                    </select>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editIsSupply}
                      onChange={(e) => { setEditIsSupply(e.target.checked); markDirty(); }}
                      className="w-3 h-3 rounded accent-accent"
                    />
                    <span className="text-xs text-gray-300">Is a supply</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editAutoRenew}
                      onChange={(e) => { setEditAutoRenew(e.target.checked); markDirty(); }}
                      className="w-3 h-3 rounded accent-accent"
                    />
                    <span className="text-xs text-gray-300">Auto-renew</span>
                  </label>
                </div>
              </div>

              {/* Save bar */}
              <div className="sticky bottom-0 bg-dark-bg/90 backdrop-blur border-t border-dark-border -mx-4 px-4 py-2 flex items-center gap-3">
                <button
                  onClick={handleAiFill}
                  disabled={aiFilling || saving || !activeListing.images?.[0]?.url_570xN}
                  className="px-3 py-1.5 bg-purple-600/20 border border-purple-500/30 text-purple-300 rounded text-xs font-medium hover:bg-purple-600/30 transition-colors disabled:opacity-40 flex-shrink-0"
                >
                  {aiFilling ? 'Generating...' : 'AI Fill'}
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || !dirty || editTitle.length > 140 || editTags.length > 13}
                  className="px-4 py-1.5 bg-accent text-dark-bg rounded text-xs font-medium hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {saving ? 'Saving...' : 'Save to Etsy'}
                </button>
                {dirty && <span className="text-xs text-yellow-400">Unsaved</span>}
                {!dirty && successMsg && <span className="text-xs text-green-400">{successMsg}</span>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
