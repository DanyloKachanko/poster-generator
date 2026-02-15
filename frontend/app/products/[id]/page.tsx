'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  getTrackedProduct,
  getProductMockups,
  setProductPrimaryMockup,
  getProductAnalyticsHistory,
  addToSchedule,
  retrySchedule,
  getUnlinkedImages,
  linkSourceImage,
  TrackedProduct,
  ProductMockup,
  AnalyticsEntry,
  SourceImage,
  UnlinkedImage,
} from '@/lib/api';
import { analyzeSeo, scoreColor, scoreGrade } from '@/lib/seo-score';

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  draft: { bg: 'bg-gray-500/15', text: 'text-gray-400', label: 'Draft' },
  scheduled: { bg: 'bg-yellow-500/15', text: 'text-yellow-400', label: 'Scheduled' },
  published: { bg: 'bg-green-500/15', text: 'text-green-400', label: 'Live' },
  failed: { bg: 'bg-red-500/15', text: 'text-red-400', label: 'Failed' },
};

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productId = params.id as string;

  const [product, setProduct] = useState<TrackedProduct | null>(null);
  const [mockups, setMockups] = useState<ProductMockup[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [showImagePicker, setShowImagePicker] = useState(false);
  const [unlinkedImages, setUnlinkedImages] = useState<UnlinkedImage[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const prod = await getTrackedProduct(productId);
      setProduct(prod);

      // Load mockups and analytics in parallel
      const [mockupData, analyticsData] = await Promise.all([
        getProductMockups(productId).catch(() => ({ mockups: [] as ProductMockup[] })),
        getProductAnalyticsHistory(productId).catch(() => ({ entries: [] as AnalyticsEntry[] })),
      ]);
      setMockups(mockupData.mockups || []);
      setAnalytics(analyticsData.entries || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load product');
    } finally {
      setIsLoading(false);
    }
  }, [productId]);

  useEffect(() => { loadData(); }, [loadData]);

  const showAction = (msg: string) => {
    setActionMessage(msg);
    setTimeout(() => setActionMessage(null), 3000);
  };

  const handleSetPrimary = async (mockupUrl: string) => {
    setActionLoading(`primary:${mockupUrl}`);
    try {
      await setProductPrimaryMockup(productId, mockupUrl);
      showAction('Primary image set on Etsy');
    } catch (err) {
      showAction(err instanceof Error ? err.message : 'Failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSchedule = async () => {
    if (!product) return;
    setActionLoading('schedule');
    try {
      const result = await addToSchedule(productId, product.title);
      showAction(`Scheduled for ${new Date(result.scheduled_publish_at).toLocaleString()}`);
      await loadData();
    } catch (err) {
      showAction(err instanceof Error ? err.message : 'Failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetry = async () => {
    setActionLoading('retry');
    try {
      await retrySchedule(productId);
      showAction('Rescheduled for publish');
      await loadData();
    } catch (err) {
      showAction(err instanceof Error ? err.message : 'Failed');
    } finally {
      setActionLoading(null);
    }
  };

  const openImagePicker = async () => {
    setShowImagePicker(true);
    setPickerLoading(true);
    try {
      const data = await getUnlinkedImages(100);
      setUnlinkedImages(data.items);
    } catch (err) {
      showAction(err instanceof Error ? err.message : 'Failed to load images');
      setShowImagePicker(false);
    } finally {
      setPickerLoading(false);
    }
  };

  const handleLinkImage = async (imageId: number) => {
    setActionLoading(`link:${imageId}`);
    try {
      await linkSourceImage(productId, imageId);
      showAction('Source image linked');
      setShowImagePicker(false);
      await loadData();
    } catch (err) {
      showAction(err instanceof Error ? err.message : 'Failed to link');
    } finally {
      setActionLoading(null);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-12 text-center text-gray-500">
        Loading product...
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-12">
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
          {error || 'Product not found'}
        </div>
        <Link href="/products" className="mt-4 inline-block text-sm text-accent hover:underline">
          Back to Products
        </Link>
      </div>
    );
  }

  const status = STATUS_STYLES[product.status] || STATUS_STYLES.draft;

  // SEO analysis
  const seoAnalysis = product.tags
    ? analyzeSeo(product.title, product.tags, product.description || '', [])
    : null;
  const seoScore = seoAnalysis?.score ?? -1;

  // Analytics totals
  const totalViews = analytics.reduce((s, e) => s + e.views, 0);
  const totalFavs = analytics.reduce((s, e) => s + e.favorites, 0);
  const totalOrders = analytics.reduce((s, e) => s + e.orders, 0);
  const totalRevenue = analytics.reduce((s, e) => s + e.revenue_cents, 0);

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <Link href="/products" className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Products
          </Link>
          <h1 className="text-xl font-bold text-gray-100 mt-1 line-clamp-2">{product.title}</h1>
          <div className="flex items-center gap-3 mt-2">
            <span className={`inline-block px-2.5 py-0.5 rounded text-xs font-medium ${status.bg} ${status.text}`}>
              {status.label}
            </span>
            {product.etsy_listing_id && (
              <a
                href={`https://www.etsy.com/listing/${product.etsy_listing_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-accent hover:underline"
              >
                Etsy #{product.etsy_listing_id}
              </a>
            )}
            <span className="text-xs text-gray-600">
              Created {new Date(product.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {product.image_url && (
            <img src={product.image_url} alt="" className="w-20 h-20 rounded-lg object-cover" />
          )}
          {(product as TrackedProduct & { source_image?: SourceImage }).source_image ? (
            <span className="w-3 h-3 rounded-full bg-green-500" title="Source image linked" />
          ) : (
            <span className="w-3 h-3 rounded-full bg-gray-600" title="No source image linked" />
          )}
        </div>
      </div>

      {/* Action message */}
      {actionMessage && (
        <div className="bg-accent/10 border border-accent/30 rounded-lg px-3 py-2 text-sm text-accent">
          {actionMessage}
        </div>
      )}

      {/* Quick actions */}
      <div className="flex gap-2 flex-wrap">
        {product.status === 'draft' && (
          <button
            onClick={handleSchedule}
            disabled={actionLoading === 'schedule'}
            className="px-3 py-1.5 bg-yellow-500/15 text-yellow-400 rounded-md text-sm font-medium hover:bg-yellow-500/25 transition-colors disabled:opacity-50"
          >
            {actionLoading === 'schedule' ? 'Scheduling...' : 'Add to Publish Schedule'}
          </button>
        )}
        {product.status === 'failed' && (
          <button
            onClick={handleRetry}
            disabled={actionLoading === 'retry'}
            className="px-3 py-1.5 bg-yellow-500/15 text-yellow-400 rounded-md text-sm font-medium hover:bg-yellow-500/25 transition-colors disabled:opacity-50"
          >
            {actionLoading === 'retry' ? 'Retrying...' : 'Retry Publish'}
          </button>
        )}
        <button
          onClick={loadData}
          className="px-3 py-1.5 bg-dark-card border border-dark-border rounded-md text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="bg-dark-card border border-dark-border rounded-lg p-3">
          <div className="text-xs text-gray-500 uppercase">Views</div>
          <div className="text-lg font-bold text-gray-100">{totalViews || '—'}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-3">
          <div className="text-xs text-gray-500 uppercase">Favorites</div>
          <div className="text-lg font-bold text-gray-100">{totalFavs || '—'}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-3">
          <div className="text-xs text-gray-500 uppercase">Orders</div>
          <div className="text-lg font-bold text-gray-100">{totalOrders || '—'}</div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-3">
          <div className="text-xs text-gray-500 uppercase">Revenue</div>
          <div className="text-lg font-bold text-gray-100">
            {totalRevenue > 0 ? `$${(totalRevenue / 100).toFixed(2)}` : '—'}
          </div>
        </div>
        <div className="bg-dark-card border border-dark-border rounded-lg p-3">
          <div className="text-xs text-gray-500 uppercase">SEO Score</div>
          <div className={`text-lg font-bold ${seoScore >= 0 ? scoreColor(seoScore) : 'text-gray-600'}`}>
            {seoScore >= 0 ? `${scoreGrade(seoScore)} ${seoScore}` : '—'}
          </div>
        </div>
      </div>

      {/* Product details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Source Image + Tags + Sizes + Description */}
        <div className="space-y-4">
          {/* Source Image */}
          {(() => {
            const src = (product as TrackedProduct & { source_image?: SourceImage }).source_image;
            return (
              <div className="bg-dark-card border border-dark-border rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-3">Source Image</h3>
                {src ? (
                  <div className="flex gap-3">
                    <a href={src.url} target="_blank" rel="noopener noreferrer">
                      <img src={src.url} alt="" className="w-24 h-24 rounded-lg object-cover hover:opacity-80 transition-opacity" />
                    </a>
                    <div className="space-y-1.5 text-xs">
                      <div className="text-gray-500">ID: <span className="text-gray-300">{src.id}</span></div>
                      <div className="text-gray-500">Generation: <span className="text-gray-300 font-mono">{src.generation_id.slice(0, 12)}...</span></div>
                      <div className="text-gray-500">Mockup: {
                        src.mockup_status === 'approved'
                          ? <span className="text-green-400">Approved</span>
                          : src.mockup_status === 'needs_attention'
                          ? <span className="text-yellow-400">Needs attention</span>
                          : <span className="text-gray-400">Pending</span>
                      }</div>
                      <button
                        onClick={openImagePicker}
                        className="mt-1 text-accent hover:underline"
                      >
                        Change
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={openImagePicker}
                    className="w-full py-3 border border-dashed border-dark-border rounded-lg text-sm text-gray-500 hover:text-gray-300 hover:border-gray-500 transition-colors"
                  >
                    Link Source Image
                  </button>
                )}
              </div>
            );
          })()}

          {/* Tags */}
          {product.tags && product.tags.length > 0 && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2">Tags ({product.tags.length})</h3>
              <div className="flex flex-wrap gap-1.5">
                {product.tags.map((tag, i) => (
                  <span key={i} className="px-2 py-0.5 bg-dark-hover rounded text-xs text-gray-300">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Enabled sizes */}
          {product.enabled_sizes && product.enabled_sizes.length > 0 && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2">Enabled Sizes</h3>
              <div className="flex flex-wrap gap-2">
                {product.enabled_sizes.map((size) => (
                  <span key={size} className="px-2.5 py-1 bg-accent/10 text-accent rounded text-xs font-medium">
                    {size}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Description */}
          {product.description && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-2">Description</h3>
              <p className="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
                {product.description}
              </p>
            </div>
          )}
        </div>

        {/* Right: Mockups */}
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-3">
            Mockups ({mockups.length})
          </h3>
          {mockups.length === 0 ? (
            <p className="text-sm text-gray-600">No mockups available</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {mockups.map((mockup, i) => (
                <div key={i} className="relative group rounded-lg overflow-hidden border border-dark-border">
                  <img
                    src={mockup.src}
                    alt={mockup.camera_label || `Mockup ${i + 1}`}
                    className="w-full aspect-[4/5] object-cover"
                  />
                  <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
                    <span className="text-xs text-white font-medium">
                      {mockup.camera_label || 'Unknown'}
                    </span>
                    {product.etsy_listing_id && (
                      <button
                        onClick={() => handleSetPrimary(mockup.src)}
                        disabled={actionLoading === `primary:${mockup.src}`}
                        className="px-2.5 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-500 transition-colors disabled:opacity-50"
                      >
                        {actionLoading === `primary:${mockup.src}` ? 'Setting...' : 'Set Primary'}
                      </button>
                    )}
                  </div>
                  {mockup.is_default && (
                    <span className="absolute top-1 left-1 bg-accent/80 text-white text-[10px] px-1.5 py-0.5 rounded">
                      Default
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Analytics history */}
      {analytics.length > 0 && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-3">Analytics History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 uppercase border-b border-dark-border">
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2 text-right">Views</th>
                  <th className="px-3 py-2 text-right">Favs</th>
                  <th className="px-3 py-2 text-right">Orders</th>
                  <th className="px-3 py-2 text-right">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {analytics.slice(0, 14).map((entry) => (
                  <tr key={entry.id} className="border-b border-dark-border/30">
                    <td className="px-3 py-1.5 text-gray-400">{entry.date}</td>
                    <td className="px-3 py-1.5 text-right text-gray-300">{entry.views || '—'}</td>
                    <td className="px-3 py-1.5 text-right text-gray-300">{entry.favorites || '—'}</td>
                    <td className="px-3 py-1.5 text-right text-gray-300">{entry.orders || '—'}</td>
                    <td className="px-3 py-1.5 text-right text-gray-300">
                      {entry.revenue_cents > 0 ? `$${(entry.revenue_cents / 100).toFixed(2)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Meta info */}
      <div className="text-xs text-gray-600 flex gap-4">
        <span>Printify: {product.printify_product_id}</span>
        <span>Strategy: {product.pricing_strategy}</span>
        <span>Updated: {new Date(product.updated_at).toLocaleString()}</span>
      </div>

      {/* Image picker modal */}
      {showImagePicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={() => setShowImagePicker(false)}>
          <div className="bg-dark-card border border-dark-border rounded-xl w-full max-w-3xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-dark-border">
              <h2 className="text-lg font-semibold text-gray-100">Select Source Image</h2>
              <button onClick={() => setShowImagePicker(false)} className="text-gray-500 hover:text-gray-300 text-xl">&times;</button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              {pickerLoading ? (
                <div className="text-center py-12 text-gray-500">Loading images...</div>
              ) : unlinkedImages.length === 0 ? (
                <div className="text-center py-12 text-gray-500">No unlinked images available</div>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
                  {unlinkedImages.map((img) => (
                    <button
                      key={img.id}
                      onClick={() => handleLinkImage(img.id)}
                      disabled={actionLoading === `link:${img.id}`}
                      className="group relative rounded-lg overflow-hidden border border-dark-border hover:border-accent transition-colors disabled:opacity-50"
                    >
                      <img src={img.url} alt="" className="w-full aspect-square object-cover" />
                      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
                        <span className="text-[10px] text-white leading-tight line-clamp-2">
                          {img.prompt?.slice(0, 60) || img.style || `#${img.id}`}
                        </span>
                      </div>
                      {actionLoading === `link:${img.id}` && (
                        <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
                          <span className="text-xs text-accent">Linking...</span>
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
