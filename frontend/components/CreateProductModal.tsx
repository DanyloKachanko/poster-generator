'use client';

import { useState, useEffect, useRef } from 'react';
import {
  ImageInfo,
  PosterPreset,
  PriceInfo,
  DpiSizeAnalysis,
  aiFillListing,
  getPricing,
  analyzeDpi,
  createFullProduct,
  addToSchedule,
  CreateFullProductResponse,
} from '@/lib/api';

interface CreateProductModalProps {
  image: ImageInfo;
  preset: PosterPreset | null;
  onClose: () => void;
  autoFill?: boolean;
}

type Step = 'editing' | 'creating' | 'success' | 'error';

export default function CreateProductModal({
  image,
  preset,
  onClose,
  autoFill = false,
}: CreateProductModalProps) {
  const [step, setStep] = useState<Step>('editing');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [newTag, setNewTag] = useState('');
  const [pricing, setPricing] = useState<Record<string, PriceInfo>>({});
  const [pricingStrategy, setPricingStrategy] = useState('standard');
  const [isGeneratingListing, setIsGeneratingListing] = useState(false);
  const [publishToEtsy, setPublishToEtsy] = useState(false);
  const [result, setResult] = useState<CreateFullProductResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dpiAnalysis, setDpiAnalysis] = useState<Record<string, DpiSizeAnalysis>>({});
  const [upscaleBackend, setUpscaleBackend] = useState<string>('');
  const [schedulingProduct, setSchedulingProduct] = useState(false);
  const [scheduledAt, setScheduledAt] = useState<string | null>(null);
  const [creationStep, setCreationStep] = useState<string>('Starting...');

  // Load pricing, DPI analysis, and pre-fill from preset
  useEffect(() => {
    getPricing(pricingStrategy)
      .then(setPricing)
      .catch(console.error);

    // Load image to get dimensions for DPI analysis
    const img = new Image();
    img.onload = () => {
      analyzeDpi(img.naturalWidth, img.naturalHeight)
        .then((res) => {
          setDpiAnalysis(res.sizes);
          setUpscaleBackend(res.upscale_backend);
        })
        .catch(console.error);
    };
    img.src = image.url;

    if (preset) {
      setTags([...preset.tags]);
      setTitle(formatPresetTitle(preset.name));
      setDescription(generateDefaultDescription(preset));
    }
  }, []);

  // Auto-fill when DPI analysis is ready
  const autoFillTriggered = useRef(false);
  useEffect(() => {
    if (autoFill && Object.keys(dpiAnalysis).length > 0 && !autoFillTriggered.current && !title) {
      autoFillTriggered.current = true;
      handleAIFill();
    }
  }, [autoFill, dpiAnalysis]);

  // Reload pricing when strategy changes
  useEffect(() => {
    getPricing(pricingStrategy)
      .then(setPricing)
      .catch(console.error);
  }, [pricingStrategy]);

  const formatPresetTitle = (name: string): string => {
    return `${name} Wall Art Print | Minimalist Poster | Home Decor`;
  };

  const generateDefaultDescription = (p: PosterPreset): string => {
    return `Beautiful ${p.name.toLowerCase()} wall art print. Perfect for adding a touch of elegance to any room.\n\nPrinted on premium matte paper with archival inks for lasting quality. Available in multiple sizes to fit your space.\n\nIdeal for living room, bedroom, office, or as a thoughtful gift.`;
  };

  const handleAIFill = async () => {
    setIsGeneratingListing(true);
    setError(null);
    try {
      // Compute enabled sizes from DPI analysis (only sellable sizes)
      const enabledSizes = Object.entries(dpiAnalysis)
        .filter(([, dpi]) => dpi.is_sellable)
        .map(([key]) => key);
      const result = await aiFillListing({
        image_url: image.url,
        enabled_sizes: enabledSizes.length > 0 ? enabledSizes : undefined,
      });
      setTitle(result.title);
      setDescription(result.description);
      setTags(result.tags);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI Fill failed');
    } finally {
      setIsGeneratingListing(false);
    }
  };

  const handleAddTag = () => {
    const tag = newTag.trim().toLowerCase();
    if (tag && !tags.includes(tag) && tags.length < 13) {
      setTags([...tags, tag]);
      setNewTag('');
    }
  };

  const handleRemoveTag = (index: number) => {
    setTags(tags.filter((_, i) => i !== index));
  };

  const handleTagKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTag();
    }
  };

  const handleCreateProduct = async () => {
    if (!title.trim() || !description.trim()) {
      setError('Title and description are required');
      return;
    }

    setStep('creating');
    setError(null);

    try {
      setCreationStep('Starting...');
      const response = await createFullProduct(
        {
          style: preset?.category || 'custom',
          preset: preset?.id || 'custom',
          description: description,
          image_url: image.url,
          pricing_strategy: pricingStrategy,
          publish_to_etsy: publishToEtsy,
          listing_title: title || undefined,
          listing_tags: tags.length > 0 ? tags : undefined,
          listing_description: description || undefined,
        },
        (step) => setCreationStep(step),
      );
      setResult(response);
      setStep('success');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create product');
      setStep('error');
    }
  };

  const handleAddToSchedule = async () => {
    if (!result) return;
    setSchedulingProduct(true);
    try {
      const schedResult = await addToSchedule(result.printify_product_id, result.title);
      setScheduledAt(schedResult.scheduled_publish_at);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to schedule');
    } finally {
      setSchedulingProduct(false);
    }
  };

  const totalProfit = Object.values(pricing).reduce((sum, p) => sum + p.profit, 0);
  const avgMargin =
    Object.values(pricing).length > 0
      ? Object.values(pricing).reduce((sum, p) => sum + p.margin_percent, 0) /
        Object.values(pricing).length
      : 0;

  const sortedPricing = Object.entries(pricing).sort(
    ([, a], [, b]) => a.recommended_price - b.recommended_price
  );

  const dpiQualityBadge = (sizeKey: string) => {
    const dpi = dpiAnalysis[sizeKey];
    if (!dpi) return null;

    const styles: Record<string, string> = {
      ideal: 'bg-green-500/10 text-green-400 border-green-500/20',
      good: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      acceptable: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
      needs_upscale: 'bg-red-500/10 text-red-400 border-red-500/20',
    };
    const labels: Record<string, string> = {
      ideal: 'Ideal',
      good: 'Good',
      acceptable: 'OK',
      needs_upscale: !dpi.is_sellable ? 'Skip' : 'Upscale',
    };

    return (
      <span
        className={`inline-block ml-1.5 px-1.5 py-0 text-[9px] border rounded font-medium ${styles[dpi.quality] || ''}`}
        title={`${Math.round(dpi.achievable_dpi)} DPI${dpi.upscale_needed ? ' (will upscale)' : ''}`}
      >
        {labels[dpi.quality]}
      </span>
    );
  };

  return (
    <div
      className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-dark-card border border-dark-border rounded-xl w-full max-w-3xl max-h-[92vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-dark-border sticky top-0 bg-dark-card z-10">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Create Product</h2>
            {preset && (
              <span className="text-xs text-accent">{preset.name} preset</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        {step === 'editing' && (
          <div className="p-4 space-y-5">
            {/* Image preview + quick info */}
            <div className="flex gap-4">
              <img
                src={image.url}
                alt="Preview"
                className="w-28 h-36 object-cover rounded-lg border border-dark-border flex-shrink-0"
              />
              <div className="flex-1 space-y-3">
                <div>
                  <label className="text-xs text-gray-500 uppercase tracking-wider mb-1 block">
                    Product Title
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Enter product title..."
                    className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
                  />
                  <p className="text-[10px] text-gray-600 mt-1">{title.length}/140 characters</p>
                </div>
                <button
                  onClick={handleAIFill}
                  disabled={isGeneratingListing || Object.keys(dpiAnalysis).length === 0}
                  className="w-full px-3 py-2 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20 hover:bg-purple-500/20 disabled:opacity-50 transition-colors flex items-center justify-center gap-2 text-sm font-medium"
                >
                  {isGeneratingListing ? (
                    <>
                      <span className="animate-spin inline-block w-3.5 h-3.5 border-2 border-purple-400 border-t-transparent rounded-full" />
                      Analyzing image...
                    </>
                  ) : Object.keys(dpiAnalysis).length === 0 ? (
                    <>
                      <span className="animate-spin inline-block w-3.5 h-3.5 border-2 border-purple-400 border-t-transparent rounded-full" />
                      Loading DPI...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                      </svg>
                      AI Fill from Image
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="text-xs text-gray-500 uppercase tracking-wider mb-1 block">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Product description for Etsy listing..."
                rows={4}
                className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-200 resize-none focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
              />
            </div>

            {/* SEO Tags */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs text-gray-500 uppercase tracking-wider">
                  Etsy SEO Tags
                </label>
                <span className="text-[10px] text-gray-600">{tags.length}/13 tags</span>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-2 min-h-[32px] p-2 bg-dark-bg border border-dark-border rounded-lg">
                {tags.map((tag, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 px-2 py-0.5 bg-accent/10 text-accent border border-accent/20 rounded text-xs"
                  >
                    {tag}
                    <button
                      onClick={() => handleRemoveTag(i)}
                      className="text-accent/50 hover:text-accent ml-0.5"
                    >
                      &times;
                    </button>
                  </span>
                ))}
                {tags.length === 0 && (
                  <span className="text-xs text-gray-600">No tags added</span>
                )}
              </div>
              {tags.length < 13 && (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                    onKeyDown={handleTagKeyDown}
                    placeholder="Add tag..."
                    className="flex-1 px-3 py-1.5 bg-dark-bg border border-dark-border rounded-lg text-xs text-gray-200 focus:outline-none focus:ring-2 focus:ring-accent/50"
                  />
                  <button
                    onClick={handleAddTag}
                    disabled={!newTag.trim()}
                    className="px-3 py-1.5 text-xs bg-dark-bg border border-dark-border rounded-lg text-gray-400 hover:text-gray-200 hover:border-gray-600 disabled:opacity-30 transition-colors"
                  >
                    Add
                  </button>
                </div>
              )}
            </div>

            {/* Pricing */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-gray-500 uppercase tracking-wider">
                  Pricing
                </label>
                <select
                  value={pricingStrategy}
                  onChange={(e) => setPricingStrategy(e.target.value)}
                  className="text-xs px-2 py-1 bg-dark-bg border border-dark-border rounded-lg text-gray-300 focus:outline-none"
                >
                  <option value="budget">Budget</option>
                  <option value="standard">Standard</option>
                  <option value="premium">Premium</option>
                </select>
              </div>

              <div className="bg-dark-bg border border-dark-border rounded-lg overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-dark-border text-gray-500">
                      <th className="text-left px-3 py-2 font-medium">Size</th>
                      <th className="text-right px-3 py-2 font-medium">Cost</th>
                      <th className="text-right px-3 py-2 font-medium">Price</th>
                      <th className="text-right px-3 py-2 font-medium">Profit</th>
                      <th className="text-right px-3 py-2 font-medium">Margin</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedPricing.map(([key, price]) => {
                      const dpi = dpiAnalysis[key];
                      const isSkipped = dpi && !dpi.is_sellable;
                      return (
                        <tr
                          key={key}
                          className={`border-b border-dark-border/50 last:border-0 ${isSkipped ? 'opacity-40' : ''}`}
                        >
                          <td className="px-3 py-2 text-gray-300 font-medium">
                            <span className={isSkipped ? 'line-through' : ''}>{price.size}</span>
                            {dpiQualityBadge(key)}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-500">
                            ${price.base_cost.toFixed(2)}
                          </td>
                          <td className="px-3 py-2 text-right text-gray-200">
                            ${price.recommended_price.toFixed(2)}
                          </td>
                          <td className="px-3 py-2 text-right text-green-400">
                            ${price.profit.toFixed(2)}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <span
                              className={
                                price.margin_percent >= 40
                                  ? 'text-green-400'
                                  : price.margin_percent >= 25
                                  ? 'text-yellow-400'
                                  : 'text-red-400'
                              }
                            >
                              {price.margin_percent.toFixed(0)}%
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Profit summary */}
              <div className="flex gap-4 mt-2">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-gray-600">Total profit (all sizes):</span>
                  <span className="text-xs font-medium text-green-400">
                    ${totalProfit.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-gray-600">Avg margin:</span>
                  <span className="text-xs font-medium text-gray-300">
                    {avgMargin.toFixed(0)}%
                  </span>
                </div>
              </div>
            </div>

            {/* Publish option */}
            <label className="flex items-center gap-2 p-3 bg-dark-bg border border-dark-border rounded-lg cursor-pointer">
              <input
                type="checkbox"
                checked={publishToEtsy}
                onChange={(e) => setPublishToEtsy(e.target.checked)}
                className="accent-accent"
              />
              <div>
                <span className="text-sm text-gray-200">Publish to Etsy</span>
                <p className="text-[10px] text-gray-500">
                  Automatically publish to your connected Etsy shop
                </p>
              </div>
            </label>

            {/* Error */}
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}
          </div>
        )}

        {/* Creating state */}
        {step === 'creating' && (
          <div className="p-8 flex flex-col items-center justify-center">
            <div className="animate-spin w-10 h-10 border-3 border-accent border-t-transparent rounded-full mb-4" />
            <p className="text-gray-300 font-medium">Creating product...</p>
            <p className="text-xs text-gray-500 mt-1">
              {creationStep}
            </p>
          </div>
        )}

        {/* Success state */}
        {step === 'success' && result && (
          <div className="p-6 space-y-4">
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-green-500/15 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-100">Product Created!</h3>
              <p className="text-sm text-gray-400 mt-1">
                {result.published ? 'Published to Etsy' : 'Created on Printify'}
              </p>
            </div>

            <div className="bg-dark-bg border border-dark-border rounded-lg p-4 space-y-3">
              <div>
                <span className="text-[10px] text-gray-600 uppercase tracking-wider">Title</span>
                <p className="text-sm text-gray-200 mt-0.5">{result.title}</p>
              </div>
              <div>
                <span className="text-[10px] text-gray-600 uppercase tracking-wider">Tags</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {result.tags.map((tag, i) => (
                    <span key={i} className="text-[10px] px-1.5 py-0.5 bg-accent/10 text-accent rounded">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
              {result.enabled_sizes && (
                <div>
                  <span className="text-[10px] text-gray-600 uppercase tracking-wider">Enabled Sizes</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {result.enabled_sizes.map((s) => (
                      <span key={s} className="text-[10px] px-1.5 py-0.5 bg-green-500/10 text-green-400 border border-green-500/20 rounded">
                        {s}
                      </span>
                    ))}
                  </div>
                  {result.upscale_backend && (
                    <p className="text-[10px] text-gray-600 mt-1">Upscaler: {result.upscale_backend}</p>
                  )}
                </div>
              )}
              <div>
                <span className="text-[10px] text-gray-600 uppercase tracking-wider">Printify ID</span>
                <p className="text-xs text-gray-400 mt-0.5 font-mono">{result.printify_product_id}</p>
              </div>
            </div>

            {/* Schedule button for draft products */}
            {!result.published && !scheduledAt && (
              <button
                onClick={handleAddToSchedule}
                disabled={schedulingProduct}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-yellow-600/15 text-yellow-400 border border-yellow-600/30 rounded-lg font-medium hover:bg-yellow-600/25 transition-colors text-sm disabled:opacity-50"
              >
                {schedulingProduct ? (
                  <>
                    <span className="animate-spin w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full" />
                    Scheduling...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
                    </svg>
                    Add to Publish Schedule
                  </>
                )}
              </button>
            )}
            {scheduledAt && (
              <div className="text-center text-xs text-yellow-400/70 py-1">
                Scheduled for {new Date(scheduledAt).toLocaleString('en-US', {
                  month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                  timeZone: 'America/New_York', timeZoneName: 'short',
                })}
              </div>
            )}
          </div>
        )}

        {/* Error state */}
        {step === 'error' && (
          <div className="p-6 space-y-4">
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-red-500/15 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-100">Creation Failed</h3>
              <p className="text-sm text-red-400 mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-4 border-t border-dark-border flex justify-end gap-3 sticky bottom-0 bg-dark-card">
          {step === 'editing' && (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateProduct}
                disabled={!title.trim() || !description.trim()}
                className="px-5 py-2 text-sm bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Create Product
              </button>
            </>
          )}
          {step === 'error' && (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
              >
                Close
              </button>
              <button
                onClick={() => { setStep('editing'); setError(null); }}
                className="px-5 py-2 text-sm bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover transition-colors"
              >
                Try Again
              </button>
            </>
          )}
          {step === 'success' && (
            <button
              onClick={onClose}
              className="px-5 py-2 text-sm bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover transition-colors"
            >
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
