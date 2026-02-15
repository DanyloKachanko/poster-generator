'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  getMockups,
  MockupProduct,
  getEtsyListingImages,
  uploadEtsyListingImage,
  deleteEtsyListingImage,
  setEtsyListingImagePrimary,
  setProductPrimaryMockup,
  EtsyListingImage,
} from '@/lib/api';

export default function MockupsPage() {
  const [mockups, setMockups] = useState<MockupProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'etsy' | 'draft'>('all');

  // Edit mode
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [etsyImages, setEtsyImages] = useState<EtsyListingImage[]>([]);
  const [etsyLoading, setEtsyLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    getMockups()
      .then(setMockups)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let list = mockups;
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((m) => m.title.toLowerCase().includes(q));
    }
    if (filter === 'etsy') list = list.filter((m) => m.etsy_listing_id);
    if (filter === 'draft') list = list.filter((m) => !m.etsy_listing_id);
    return list;
  }, [mockups, search, filter]);

  const copyUrl = (url: string) => {
    navigator.clipboard.writeText(url);
    setCopied(url);
    setTimeout(() => setCopied(null), 1500);
  };

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  // Fetch Etsy images for expanded product
  const refreshEtsyImages = useCallback(async (listingId: string) => {
    setEtsyLoading(true);
    try {
      const data = await getEtsyListingImages(listingId);
      setEtsyImages(data.results || []);
    } catch {
      setEtsyImages([]);
    } finally {
      setEtsyLoading(false);
    }
  }, []);

  const handleExpand = (product: MockupProduct) => {
    if (expandedId === product.printify_id) {
      setExpandedId(null);
      setEtsyImages([]);
      return;
    }
    setExpandedId(product.printify_id);
    setError(null);
    setSuccessMsg(null);
    if (product.etsy_listing_id) {
      refreshEtsyImages(product.etsy_listing_id);
    } else {
      setEtsyImages([]);
    }
  };

  const handleUploadMockup = async (mockupSrc: string, listingId: string) => {
    if (actionLoading) return;
    if (etsyImages.length >= 10) {
      setError('Etsy allows a maximum of 10 images per listing');
      return;
    }
    setActionLoading(mockupSrc);
    setError(null);
    try {
      const resp = await fetch(mockupSrc);
      const blob = await resp.blob();
      const file = new File([blob], 'mockup.jpg', { type: blob.type || 'image/jpeg' });
      await uploadEtsyListingImage(listingId, file);
      await refreshEtsyImages(listingId);
      showSuccess('Mockup uploaded to Etsy');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload mockup');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteEtsyImage = async (listingId: string, imageId: number) => {
    if (actionLoading) return;
    if (etsyImages.length <= 1) {
      setError('Cannot delete the last image — Etsy requires at least one');
      return;
    }
    setActionLoading(String(imageId));
    setError(null);
    try {
      await deleteEtsyListingImage(listingId, String(imageId));
      await refreshEtsyImages(listingId);
      showSuccess('Image deleted from Etsy');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete image');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSetPrimary = async (listingId: string, imageId: number) => {
    if (actionLoading) return;
    setActionLoading(String(imageId));
    setError(null);
    try {
      await setEtsyListingImagePrimary(listingId, String(imageId));
      await refreshEtsyImages(listingId);
      showSuccess('Primary image updated');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set primary');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSetPrimaryFromPrintify = async (printifyId: string, mockupSrc: string) => {
    if (actionLoading) return;
    setActionLoading(`primary:${mockupSrc}`);
    setError(null);
    try {
      await setProductPrimaryMockup(printifyId, mockupSrc);
      showSuccess('Mockup set as primary on Etsy');
      // Refresh Etsy images if expanded
      const product = mockups.find((m) => m.printify_id === printifyId);
      if (product?.etsy_listing_id) {
        await refreshEtsyImages(product.etsy_listing_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set primary mockup');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <h1 className="text-2xl font-bold text-gray-100 mb-2">Mockups</h1>
        <p className="text-gray-500">Loading mockups...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Mockups</h1>
          <p className="text-sm text-gray-500 mt-1">{mockups.length} products, {mockups.reduce((s, m) => s + m.images.length, 0)} mockup images</p>
        </div>
      </div>

      {/* Status messages */}
      {error && (
        <div className="mb-4 bg-red-900/20 border border-red-800/50 rounded px-3 py-2 text-sm text-red-400">{error}</div>
      )}
      {successMsg && (
        <div className="mb-4 bg-green-900/20 border border-green-800/50 rounded px-3 py-2 text-sm text-green-400">{successMsg}</div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="Search by title..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-dark-bg border border-dark-border rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-accent w-64"
        />
        <div className="flex gap-1">
          {(['all', 'etsy', 'draft'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                filter === f
                  ? 'bg-accent text-dark-bg'
                  : 'bg-dark-card border border-dark-border text-gray-400 hover:text-gray-200'
              }`}
            >
              {f === 'all' ? `All (${mockups.length})` : f === 'etsy' ? `On Etsy (${mockups.filter(m => m.etsy_listing_id).length})` : `Draft (${mockups.filter(m => !m.etsy_listing_id).length})`}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="text-center text-gray-500 py-20">No mockups found</div>
      ) : (
        <div className="space-y-4">
          {filtered.map((product) => {
            const isExpanded = expandedId === product.printify_id;
            const hasEtsy = !!product.etsy_listing_id;

            return (
              <div key={product.printify_id} className={`bg-dark-card border rounded-lg transition-colors ${isExpanded ? 'border-accent/40' : 'border-dark-border'}`}>
                {/* Product header */}
                <div
                  className="flex items-center gap-3 p-4 cursor-pointer hover:bg-dark-hover/50 transition-colors"
                  onClick={() => handleExpand(product)}
                >
                  <span className={`text-gray-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`}>&#9654;</span>
                  <h3 className="text-sm font-medium text-gray-200 flex-1 truncate">{product.title}</h3>
                  <span className="text-[11px] text-gray-500">{product.images.length} mockups</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    hasEtsy
                      ? 'bg-green-900/30 text-green-400 border border-green-800/50'
                      : 'bg-gray-800 text-gray-500 border border-gray-700'
                  }`}>
                    {hasEtsy ? 'On Etsy' : 'Draft'}
                  </span>
                  {product.etsy_url && (
                    <a
                      href={product.etsy_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent text-xs hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View &#8599;
                    </a>
                  )}
                </div>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="border-t border-dark-border px-4 pb-4">
                    {/* Etsy Images section (only for published products) */}
                    {hasEtsy && (
                      <div className="mt-3 mb-4">
                        <div className="flex items-center gap-2 mb-2">
                          <label className="text-xs font-medium text-green-400">Etsy Listing Images</label>
                          <span className="text-[10px] text-gray-500">
                            {etsyLoading ? 'Loading...' : `${etsyImages.length}/10`}
                          </span>
                        </div>
                        {etsyLoading ? (
                          <div className="flex items-center gap-2 py-4 text-gray-500 text-xs">
                            <div className="animate-spin h-4 w-4 border-2 border-accent border-t-transparent rounded-full" />
                            Loading Etsy images...
                          </div>
                        ) : etsyImages.length === 0 ? (
                          <div className="py-3 text-xs text-gray-600">No images on Etsy listing yet. Click mockups below to upload.</div>
                        ) : (
                          <div className="bg-dark-bg border border-dark-border rounded p-2">
                            <div className="flex gap-2 overflow-x-auto pb-1">
                              {etsyImages.map((img, i) => {
                                const isPrimary = i === 0;
                                const isLoadingThis = actionLoading === String(img.listing_image_id);
                                return (
                                  <div
                                    key={img.listing_image_id}
                                    className={`relative flex-shrink-0 w-20 group ${isPrimary ? 'ring-2 ring-green-500 rounded' : ''}`}
                                  >
                                    <img
                                      src={img.url_570xN}
                                      alt={`Etsy image ${i + 1}`}
                                      className={`w-20 h-28 object-cover rounded ${isLoadingThis ? 'opacity-40' : ''}`}
                                    />
                                    {isLoadingThis && (
                                      <div className="absolute inset-0 flex items-center justify-center">
                                        <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
                                      </div>
                                    )}
                                    {isPrimary && (
                                      <div className="absolute top-0.5 left-0.5 px-1 py-0.5 bg-green-500/90 rounded text-[9px] font-bold text-white">
                                        1st
                                      </div>
                                    )}
                                    {!isLoadingThis && (
                                      <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity rounded flex flex-col items-center justify-center gap-1">
                                        {!isPrimary && (
                                          <button
                                            onClick={() => handleSetPrimary(product.etsy_listing_id!, img.listing_image_id)}
                                            className="px-1.5 py-0.5 bg-green-600/80 text-white rounded text-[10px] font-medium hover:bg-green-600"
                                          >
                                            Set 1st
                                          </button>
                                        )}
                                        <button
                                          onClick={() => handleDeleteEtsyImage(product.etsy_listing_id!, img.listing_image_id)}
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
                          </div>
                        )}
                      </div>
                    )}

                    {/* Printify Mockups */}
                    <div className="mt-3">
                      <div className="flex items-center gap-2 mb-2">
                        <label className="text-xs font-medium text-orange-400">Printify Mockups</label>
                        <span className="text-[10px] text-gray-500">{product.images.length} images</span>
                        {hasEtsy && (
                          <span className="text-[10px] text-gray-600">Click to upload to Etsy</span>
                        )}
                      </div>
                      <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-3">
                        {product.images.map((img, i) => {
                          const isUploading = actionLoading === img.src;
                          const isSettingPrimary = actionLoading === `primary:${img.src}`;
                          const canUpload = hasEtsy && etsyImages.length < 10;
                          return (
                            <div
                              key={i}
                              className={`relative group ${canUpload ? 'cursor-pointer' : ''}`}
                              onClick={() => canUpload && !isUploading && handleUploadMockup(img.src, product.etsy_listing_id!)}
                            >
                              <img
                                src={img.src}
                                alt={`${product.title} mockup ${i + 1}`}
                                className={`w-full aspect-[5/7] object-cover rounded-lg transition-all ${
                                  isUploading ? 'opacity-40' : canUpload ? 'hover:ring-2 hover:ring-orange-500' : ''
                                }`}
                              />
                              {(isUploading || isSettingPrimary) && (
                                <div className="absolute inset-0 flex items-center justify-center">
                                  <div className="animate-spin h-6 w-6 border-2 border-orange-400 border-t-transparent rounded-full" />
                                </div>
                              )}
                              {img.is_default && (
                                <div className="absolute top-1 left-1 px-1.5 py-0.5 bg-accent/90 rounded text-[9px] font-bold text-dark-bg">
                                  DEFAULT
                                </div>
                              )}
                              <div className="absolute bottom-1 left-1 flex gap-1">
                                {img.size && (
                                  <span className="px-1.5 py-0.5 bg-dark-bg/90 border border-dark-border rounded text-[10px] text-gray-300 font-medium">
                                    {img.size}
                                  </span>
                                )}
                                {img.camera_label && (
                                  <span className="px-1.5 py-0.5 bg-dark-bg/90 border border-dark-border rounded text-[10px] text-gray-400">
                                    {img.camera_label}
                                  </span>
                                )}
                              </div>
                              {/* Hover overlay */}
                              {!isUploading && !isSettingPrimary && (
                                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2 flex-wrap">
                                  {hasEtsy && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleSetPrimaryFromPrintify(product.printify_id, img.src);
                                      }}
                                      className="px-2 py-1 bg-green-500/90 text-white rounded text-[11px] font-medium hover:bg-green-600"
                                    >
                                      Set Primary
                                    </button>
                                  )}
                                  {canUpload && (
                                    <span className="px-2 py-1 bg-orange-500/90 text-white rounded text-[11px] font-medium">
                                      Upload to Etsy
                                    </span>
                                  )}
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setLightbox(img.src);
                                    }}
                                    className="px-2 py-1 bg-dark-bg/90 text-gray-300 rounded text-[11px] hover:text-white"
                                  >
                                    View
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      copyUrl(img.src);
                                    }}
                                    className="px-2 py-1 bg-dark-bg/90 text-gray-300 rounded text-[11px] hover:text-white"
                                  >
                                    {copied === img.src ? 'Copied!' : 'Copy'}
                                  </button>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Lightbox */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-8"
          onClick={() => setLightbox(null)}
        >
          <img
            src={lightbox}
            alt="Mockup full size"
            className="max-w-full max-h-full object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            onClick={() => setLightbox(null)}
            className="absolute top-4 right-4 text-white/80 hover:text-white text-2xl"
          >
            &times;
          </button>
        </div>
      )}
    </div>
  );
}
