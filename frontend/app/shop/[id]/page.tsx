'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  getPrintifyProduct,
  updatePrintifyProduct,
  publishPrintifyProduct,
  unpublishPrintifyProduct,
  deletePrintifyProduct,
  republishPrintifyProduct,
  regenerateTitle,
  regenerateDescription,
  regenerateTags,
  PrintifyProduct,
} from '@/lib/api';

interface EditData {
  title: string;
  description: string;
  tags: string;
  variants: { id: number; title: string; price: string; is_enabled: boolean }[];
}

export default function ProductPage() {
  const params = useParams();
  const router = useRouter();
  const productId = params.id as string;

  const [product, setProduct] = useState<PrintifyProduct | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  // Edit mode
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<EditData | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [regeneratingTitle, setRegeneratingTitle] = useState(false);
  const [regeneratingDesc, setRegeneratingDesc] = useState(false);
  const [regeneratingTags, setRegeneratingTags] = useState(false);
  const [descTone, setDescTone] = useState('warm');

  const loadProduct = () => {
    setIsLoading(true);
    getPrintifyProduct(productId)
      .then((data) => {
        setProduct(data);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });
  };

  useEffect(() => {
    loadProduct();
  }, [productId]);

  // Auto-hide success
  useEffect(() => {
    if (successMsg) {
      const t = setTimeout(() => setSuccessMsg(null), 5000);
      return () => clearTimeout(t);
    }
  }, [successMsg]);

  // === Helpers ===

  const getProductImage = (): string | null => {
    if (product?.images && product.images.length > 0) {
      return product.images[0].src;
    }
    return null;
  };

  const getProductStatus = (): string => {
    if (!product) return 'draft';
    if (product.external?.id) return 'on etsy';
    if (product.visible) return 'visible';
    return 'draft';
  };

  const getStatusBadge = (s: string) => {
    switch (s) {
      case 'on etsy':
        return 'bg-green-500/15 text-green-400 border-green-500/30';
      case 'visible':
        return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
      default:
        return 'bg-gray-500/15 text-gray-400 border-gray-500/30';
    }
  };

  const formatPrice = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  // === Actions ===

  const handlePublish = async () => {
    setActionLoading(true);
    try {
      await publishPrintifyProduct(productId);
      setSuccessMsg('Published to Etsy');
      loadProduct();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish');
    } finally {
      setActionLoading(false);
    }
  };

  const handleUnpublish = async () => {
    setActionLoading(true);
    try {
      await unpublishPrintifyProduct(productId);
      setSuccessMsg('Unpublished from Etsy');
      loadProduct();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unpublish');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    setActionLoading(true);
    try {
      await deletePrintifyProduct(productId);
      router.push('/shop');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
      setActionLoading(false);
    }
  };

  // === Edit mode ===

  const startEditing = () => {
    if (!product) return;
    setEditData({
      title: product.title,
      description: product.description || '',
      tags: (product.tags || []).join(', '),
      variants: product.variants.map((v) => ({
        id: v.id,
        title: v.title || `Variant ${v.id}`,
        price: (v.price / 100).toFixed(2),
        is_enabled: v.is_enabled,
      })),
    });
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setIsEditing(false);
    setEditData(null);
  };

  const handleSave = async (andRepublish = false) => {
    if (!product || !editData) return;
    setSaveLoading(true);
    setError(null);
    try {
      const tags = editData.tags.split(',').map((t) => t.trim()).filter(Boolean);
      const variants = editData.variants.map((v) => ({
        id: v.id,
        price: Math.round(parseFloat(v.price) * 100),
        is_enabled: v.is_enabled,
      }));

      await updatePrintifyProduct(productId, {
        title: editData.title,
        description: editData.description,
        tags,
        variants,
      });

      if (andRepublish) {
        await republishPrintifyProduct(productId);
        setSuccessMsg('Saved & synced to Etsy. Changes may take a few minutes to appear.');
      } else {
        setSuccessMsg('Saved to Printify');
      }

      setIsEditing(false);
      setEditData(null);
      loadProduct();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaveLoading(false);
    }
  };

  const handleRegenerateTitle = async () => {
    if (!editData) return;
    setRegeneratingTitle(true);
    try {
      const newTitle = await regenerateTitle('abstract', 'general', editData.title);
      setEditData({ ...editData, title: newTitle });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate title');
    } finally {
      setRegeneratingTitle(false);
    }
  };

  const handleRegenerateDesc = async () => {
    if (!editData) return;
    setRegeneratingDesc(true);
    try {
      const newDesc = await regenerateDescription('abstract', 'general', editData.description, descTone);
      setEditData({ ...editData, description: newDesc });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate description');
    } finally {
      setRegeneratingDesc(false);
    }
  };

  const handleRegenerateTags = async () => {
    if (!editData || !product) return;
    setRegeneratingTags(true);
    try {
      const currentTags = editData.tags.split(',').map((t) => t.trim()).filter(Boolean);
      const newTags = await regenerateTags('abstract', 'general', currentTags, editData.title);
      setEditData({ ...editData, tags: newTags.join(', ') });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate tags');
    } finally {
      setRegeneratingTags(false);
    }
  };

  // === Loading / Error states ===

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="text-center py-20">
          <h2 className="text-lg font-medium text-gray-400 mb-2">Product not found</h2>
          <p className="text-gray-600 mb-4">{error || 'Could not load this product.'}</p>
          <Link href="/shop" className="text-accent hover:underline text-sm">
            Back to Shop
          </Link>
        </div>
      </div>
    );
  }

  const productStatus = getProductStatus();
  const image = getProductImage();

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-6">
        <Link href="/shop" className="hover:text-gray-300 transition-colors">Shop</Link>
        <span>/</span>
        <span className="text-gray-400 truncate max-w-[300px]">{product.title}</span>
      </div>

      {/* Success message */}
      {successMsg && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-3 mb-6 text-green-400 text-sm flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-green-400 hover:text-green-300 ml-4">&#10005;</button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 mb-6 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">&#10005;</button>
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-8">
        {/* Left: Image */}
        <div className="lg:w-1/2">
          <div className="sticky top-20">
            {image ? (
              <img src={image} alt={product.title} className="w-full rounded-lg" />
            ) : (
              <div className="aspect-[4/5] bg-dark-card border border-dark-border rounded-lg flex items-center justify-center text-gray-700">
                <svg className="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
            )}
            {/* Multiple images */}
            {product.images && product.images.length > 1 && (
              <div className="flex gap-2 mt-3 overflow-x-auto">
                {product.images.map((img, i) => (
                  <img
                    key={i}
                    src={img.src}
                    alt={`${product.title} ${i + 1}`}
                    className="w-16 h-16 rounded object-cover border border-dark-border"
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Details / Edit */}
        <div className="lg:w-1/2">
          {!isEditing ? (
            <>
              {/* VIEW MODE */}
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1 min-w-0 mr-4">
                  <h1 className="text-xl font-bold text-gray-100">{product.title}</h1>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full border ${getStatusBadge(productStatus)}`}>
                      {productStatus}
                    </span>
                    <span className="text-xs text-gray-600">ID: {product.id}</span>
                    {product.external?.handle && (
                      <a
                        href={product.external.handle}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-orange-400 hover:text-orange-300 flex items-center gap-1 transition-colors"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                        View on Etsy
                      </a>
                    )}
                  </div>
                </div>
                {!product.is_locked && (
                  <button
                    onClick={startEditing}
                    className="px-3 py-1.5 rounded-lg text-sm bg-accent/15 text-accent hover:bg-accent/25 border border-accent/30 transition-colors flex items-center gap-1.5"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                    Edit
                  </button>
                )}
              </div>

              {/* Description */}
              {product.description && (
                <div className="mb-6">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Description</h4>
                  <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">{product.description}</p>
                </div>
              )}

              {/* Tags */}
              {product.tags && product.tags.length > 0 && (
                <div className="mb-6">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Tags</h4>
                  <div className="flex flex-wrap gap-1.5">
                    {product.tags.map((tag, i) => (
                      <span key={i} className="text-xs bg-dark-hover px-2.5 py-1 rounded-full text-gray-400">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Variants / Pricing */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Variants &amp; Pricing</h4>
                  <span className="text-[10px] text-gray-600">
                    {product.variants.filter((v) => v.is_enabled).length}/{product.variants.length} enabled
                  </span>
                </div>
                <div className="bg-dark-card border border-dark-border rounded-lg overflow-hidden">
                  {product.variants.map((v, i, arr) => (
                    <div
                      key={v.id}
                      className={`flex items-center justify-between text-sm py-2.5 px-4 ${i < arr.length - 1 ? 'border-b border-dark-border' : ''} ${!v.is_enabled ? 'opacity-40' : ''}`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`w-1.5 h-1.5 rounded-full ${v.is_enabled ? 'bg-green-400' : 'bg-gray-600'}`} />
                        <span className={`text-gray-300 ${!v.is_enabled ? 'line-through' : ''}`}>{v.title || `Variant ${v.id}`}</span>
                      </div>
                      <span className="text-gray-100 font-medium">{formatPrice(v.price)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Meta */}
              <div className="text-xs text-gray-600 space-y-1 mb-6">
                <div>Created: {new Date(product.created_at).toLocaleDateString()}</div>
                <div>Updated: {new Date(product.updated_at).toLocaleDateString()}</div>
              </div>

              {/* Actions */}
              <div className="flex flex-wrap gap-2 pt-4 border-t border-dark-border">
                {productStatus !== 'on etsy' && (
                  <button
                    onClick={handlePublish}
                    disabled={actionLoading}
                    className="px-5 py-2.5 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 transition-colors disabled:opacity-50"
                  >
                    {actionLoading ? 'Publishing...' : 'Publish to Etsy'}
                  </button>
                )}
                {productStatus === 'on etsy' && (
                  <button
                    onClick={handleUnpublish}
                    disabled={actionLoading}
                    className="px-5 py-2.5 rounded-lg text-sm font-medium bg-yellow-600 text-white hover:bg-yellow-700 transition-colors disabled:opacity-50"
                  >
                    {actionLoading ? 'Unpublishing...' : 'Unpublish from Etsy'}
                  </button>
                )}
                <button
                  onClick={() => setDeleteConfirm(true)}
                  disabled={actionLoading}
                  className="px-5 py-2.5 rounded-lg text-sm font-medium bg-red-600/15 text-red-400 hover:bg-red-600/25 border border-red-500/30 transition-colors disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            </>
          ) : editData ? (
            <>
              {/* EDIT MODE */}
              <div className="mb-4">
                <span className="text-sm text-accent font-medium">Editing product</span>
              </div>

              {/* Title */}
              <div className="mb-5">
                <div className="flex items-center justify-between mb-1.5">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Title</h4>
                  <button
                    onClick={handleRegenerateTitle}
                    disabled={regeneratingTitle}
                    className="text-xs px-2.5 py-1 bg-dark-card border border-dark-border rounded-md text-gray-400 hover:text-accent disabled:opacity-50 transition-colors flex items-center gap-1.5"
                  >
                    {regeneratingTitle ? (
                      <span className="inline-block w-3 h-3 border border-gray-500 border-t-accent rounded-full animate-spin" />
                    ) : (
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    )}
                    AI Regenerate
                  </button>
                </div>
                <input
                  type="text"
                  value={editData.title}
                  onChange={(e) => setEditData({ ...editData, title: e.target.value })}
                  className="w-full px-3 py-2.5 bg-dark-bg border border-dark-border rounded-lg text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
                  maxLength={140}
                />
                <span className="text-[10px] text-gray-600 mt-1 block text-right">{editData.title.length}/140</span>
              </div>

              {/* Description */}
              <div className="mb-5">
                <div className="flex items-center justify-between mb-1.5">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Description</h4>
                  <div className="flex items-center gap-1.5">
                    <select
                      value={descTone}
                      onChange={(e) => setDescTone(e.target.value)}
                      className="text-xs px-2 py-1 bg-dark-card border border-dark-border rounded-md text-gray-400"
                    >
                      <option value="warm">Warm</option>
                      <option value="professional">Professional</option>
                      <option value="playful">Playful</option>
                    </select>
                    <button
                      onClick={handleRegenerateDesc}
                      disabled={regeneratingDesc}
                      className="text-xs px-2.5 py-1 bg-dark-card border border-dark-border rounded-md text-gray-400 hover:text-accent disabled:opacity-50 transition-colors flex items-center gap-1.5"
                    >
                      {regeneratingDesc ? (
                        <span className="inline-block w-3 h-3 border border-gray-500 border-t-accent rounded-full animate-spin" />
                      ) : (
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                      )}
                      AI Regenerate
                    </button>
                  </div>
                </div>
                <textarea
                  value={editData.description}
                  onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                  rows={8}
                  className="w-full px-3 py-2.5 bg-dark-bg border border-dark-border rounded-lg text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 resize-none"
                />
              </div>

              {/* Tags */}
              <div className="mb-5">
                <div className="flex items-center justify-between mb-1.5">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Tags (comma-separated)</h4>
                  <button
                    onClick={handleRegenerateTags}
                    disabled={regeneratingTags}
                    className="text-xs px-2.5 py-1 bg-dark-card border border-dark-border rounded-md text-gray-400 hover:text-accent disabled:opacity-50 transition-colors flex items-center gap-1.5"
                  >
                    {regeneratingTags ? (
                      <span className="inline-block w-3 h-3 border border-gray-500 border-t-accent rounded-full animate-spin" />
                    ) : (
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    )}
                    AI Regenerate
                  </button>
                </div>
                <input
                  type="text"
                  value={editData.tags}
                  onChange={(e) => setEditData({ ...editData, tags: e.target.value })}
                  className="w-full px-3 py-2.5 bg-dark-bg border border-dark-border rounded-lg text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
                  placeholder="wall art, poster, minimalist..."
                />
                <span className="text-[10px] text-gray-600 mt-1 block text-right">
                  {editData.tags.split(',').filter((t) => t.trim()).length} tags
                </span>
              </div>

              {/* Variant Pricing & Toggles */}
              <div className="mb-5">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider">Sizes &amp; Pricing</h4>
                  <span className="text-[10px] text-gray-600">
                    {editData.variants.filter((v) => v.is_enabled).length}/{editData.variants.length} enabled
                  </span>
                </div>
                <div className="bg-dark-card border border-dark-border rounded-lg overflow-hidden">
                  {editData.variants.map((v, idx, arr) => (
                    <div
                      key={v.id}
                      className={`flex items-center justify-between text-sm py-2.5 px-4 ${idx < arr.length - 1 ? 'border-b border-dark-border' : ''} ${!v.is_enabled ? 'opacity-50' : ''}`}
                    >
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => {
                            const updated = [...editData.variants];
                            updated[idx] = { ...updated[idx], is_enabled: !updated[idx].is_enabled };
                            setEditData({ ...editData, variants: updated });
                          }}
                          className={`relative w-8 h-[18px] rounded-full transition-colors ${v.is_enabled ? 'bg-green-500' : 'bg-gray-600'}`}
                        >
                          <span className={`absolute top-[2px] w-[14px] h-[14px] rounded-full bg-white transition-transform ${v.is_enabled ? 'left-[16px]' : 'left-[2px]'}`} />
                        </button>
                        <span className={`text-gray-300 text-sm ${!v.is_enabled ? 'line-through text-gray-500' : ''}`}>{v.title}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-gray-500 text-sm">$</span>
                        <input
                          type="number"
                          value={v.price}
                          onChange={(e) => {
                            const updated = [...editData.variants];
                            updated[idx] = { ...updated[idx], price: e.target.value };
                            setEditData({ ...editData, variants: updated });
                          }}
                          step="0.01"
                          min="0"
                          className="w-24 px-2 py-1 bg-dark-bg border border-dark-border rounded text-gray-100 text-sm text-right focus:outline-none focus:ring-1 focus:ring-accent/50 disabled:opacity-40"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Save actions */}
              <div className="flex flex-col gap-2 pt-4 border-t border-dark-border">
                <div className="flex gap-2">
                  <button
                    onClick={() => handleSave(false)}
                    disabled={saveLoading}
                    className="flex-1 py-2.5 rounded-lg text-sm font-medium bg-accent text-dark-bg hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    {saveLoading ? 'Saving...' : 'Save to Printify'}
                  </button>
                  <button
                    onClick={cancelEditing}
                    disabled={saveLoading}
                    className="py-2.5 px-5 rounded-lg text-sm text-gray-400 hover:text-gray-200 border border-dark-border transition-colors"
                  >
                    Cancel
                  </button>
                </div>
                {productStatus === 'on etsy' && (
                  <button
                    onClick={() => handleSave(true)}
                    disabled={saveLoading}
                    className="w-full py-2.5 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 transition-colors disabled:opacity-50"
                  >
                    {saveLoading ? 'Saving & syncing...' : 'Save & Sync to Etsy'}
                  </button>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>

      {/* Delete confirmation modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={() => setDeleteConfirm(false)}>
          <div className="bg-dark-card border border-dark-border rounded-lg p-6 max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-100 mb-2">Delete Product?</h3>
            <p className="text-sm text-gray-400 mb-6">
              This will permanently delete the product from Printify. If published on Etsy, unpublish it first.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteConfirm(false)}
                className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={actionLoading}
                className="px-4 py-2 rounded-lg text-sm bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {actionLoading ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
