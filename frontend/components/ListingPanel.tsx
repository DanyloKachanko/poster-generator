'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  aiFillListing,
  regenerateTitle,
  regenerateDescription,
  createFullProduct,
  addToSchedule,
  ListingData,
  PriceInfo,
  CreateFullProductResponse,
} from '@/lib/api';

interface ListingPanelProps {
  style: string;
  preset: string;
  imageDescription: string;
  imageUrl: string;
  onClose: () => void;
}

export default function ListingPanel({
  style,
  preset,
  imageDescription,
  imageUrl,
  onClose,
}: ListingPanelProps) {
  const [listing, setListing] = useState<ListingData | null>(null);
  const [loading, setLoading] = useState(false);
  const [regeneratingTitle, setRegeneratingTitle] = useState(false);
  const [regeneratingDesc, setRegeneratingDesc] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [descTone, setDescTone] = useState('warm');
  const [showPricing, setShowPricing] = useState(false);

  // Product creation state
  const [creatingProduct, setCreatingProduct] = useState(false);
  const [createdProduct, setCreatedProduct] = useState<CreateFullProductResponse | null>(null);
  const [publishToEtsy, setPublishToEtsy] = useState(false);
  const [schedulingProduct, setSchedulingProduct] = useState(false);
  const [scheduledAt, setScheduledAt] = useState<string | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const aiResult = await aiFillListing({ image_url: imageUrl });
      setListing({
        title: aiResult.title,
        tags: aiResult.tags,
        tags_string: aiResult.tags.join(', '),
        description: aiResult.description,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI Fill failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerateTitle = async () => {
    if (!listing) return;
    setRegeneratingTitle(true);
    try {
      const newTitle = await regenerateTitle(
        style || 'abstract',
        preset || 'general',
        listing.title
      );
      setListing({ ...listing, title: newTitle });
    } catch (err) {
      console.error(err);
    } finally {
      setRegeneratingTitle(false);
    }
  };

  const handleRegenerateDescription = async () => {
    if (!listing) return;
    setRegeneratingDesc(true);
    try {
      const newDesc = await regenerateDescription(
        style || 'abstract',
        preset || 'general',
        listing.description,
        descTone
      );
      setListing({ ...listing, description: newDesc });
    } catch (err) {
      console.error(err);
    } finally {
      setRegeneratingDesc(false);
    }
  };

  const handleCreateProduct = async () => {
    setCreatingProduct(true);
    setError(null);
    try {
      const result = await createFullProduct({
        style: style || 'abstract',
        preset: preset || 'general',
        description: imageDescription,
        image_url: imageUrl,
        publish_to_etsy: publishToEtsy,
        listing_title: listing?.title,
        listing_tags: listing?.tags,
        listing_description: listing?.description,
      });
      setCreatedProduct(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create product');
    } finally {
      setCreatingProduct(false);
    }
  };

  const handleAddToSchedule = async () => {
    if (!createdProduct) return;
    setSchedulingProduct(true);
    try {
      const result = await addToSchedule(
        createdProduct.printify_product_id,
        createdProduct.title
      );
      setScheduledAt(result.scheduled_publish_at);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to schedule');
    } finally {
      setSchedulingProduct(false);
    }
  };

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };

  const copyAll = () => {
    if (!listing) return;
    const all = `${listing.title}\n\n${listing.tags_string}\n\n${listing.description}`;
    copyToClipboard(all, 'all');
  };

  return (
    <div
      className="fixed inset-0 bg-black/85 z-[60] flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-dark-card border border-dark-border rounded-xl w-full max-w-2xl max-h-[90vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-dark-border">
          <h2 className="text-lg font-semibold text-gray-100">
            {createdProduct ? 'Product Created' : 'Create Product'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 text-xl"
          >
            &times;
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* === SUCCESS STATE === */}
          {createdProduct ? (
            <div className="space-y-5 py-4">
              <div className="text-center">
                <div className="w-14 h-14 mx-auto bg-green-500/15 rounded-full flex items-center justify-center mb-4">
                  <svg className="w-7 h-7 text-green-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-gray-100 mb-1">
                  {createdProduct.title}
                </h3>
                <span className={`inline-block text-[10px] font-medium uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${
                  createdProduct.published
                    ? 'bg-green-500/15 text-green-400 border-green-500/30'
                    : 'bg-blue-500/15 text-blue-400 border-blue-500/30'
                }`}>
                  {createdProduct.published ? 'Published to Etsy' : 'Draft on Printify'}
                </span>
              </div>

              {createdProduct.published && (
                <p className="text-xs text-gray-500 text-center">
                  Changes may take a few minutes to appear on Etsy.
                </p>
              )}

              <div className="flex flex-col gap-2">
                <Link
                  href={`/shop/${createdProduct.printify_product_id}`}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover transition-colors text-sm"
                  onClick={onClose}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                  </svg>
                  View in Shop
                </Link>
                {!createdProduct.published && !scheduledAt && (
                  <button
                    onClick={handleAddToSchedule}
                    disabled={schedulingProduct}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-yellow-600/15 text-yellow-400 border border-yellow-600/30 rounded-lg font-medium hover:bg-yellow-600/25 transition-colors text-sm disabled:opacity-50"
                  >
                    {schedulingProduct ? (
                      <span className="flex items-center gap-2">
                        <span className="animate-spin w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full" />
                        Scheduling...
                      </span>
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
                <button
                  onClick={onClose}
                  className="w-full px-4 py-2.5 border border-dark-border rounded-lg text-gray-400 hover:text-gray-200 transition-colors text-sm"
                >
                  Done
                </button>
              </div>
            </div>
          ) : !listing ? (
            /* === GENERATE STATE === */
            <div className="space-y-4">
              <div className="text-sm text-gray-400">
                <p>AI analyzes your poster image to generate unique SEO listing:</p>
                <ul className="mt-2 ml-4 list-disc text-gray-500 space-y-1">
                  <li>Vision-based title, tags &amp; description from image</li>
                  <li>Auto-upload image to Printify</li>
                  <li>Set up all poster sizes with pricing</li>
                  <li>Optional: publish directly to Etsy</li>
                </ul>
              </div>

              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              <button
                onClick={handleGenerate}
                disabled={loading}
                className="w-full px-4 py-3 bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="animate-spin w-4 h-4 border-2 border-dark-bg border-t-transparent rounded-full" />
                    Analyzing image...
                  </span>
                ) : (
                  'AI Fill from Image'
                )}
              </button>
            </div>
          ) : (
            /* === EDIT & CREATE STATE === */
            <div className="space-y-4">
              {/* TITLE */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-gray-500 uppercase">
                    Title ({listing.title.length}/140)
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleRegenerateTitle}
                      disabled={regeneratingTitle}
                      className="text-xs px-2 py-1 bg-dark-bg border border-dark-border rounded text-gray-400 hover:text-gray-200 disabled:opacity-50 transition-colors"
                      title="Regenerate title"
                    >
                      {regeneratingTitle ? (
                        <span className="animate-spin inline-block w-3 h-3 border border-gray-400 border-t-transparent rounded-full" />
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={() => copyToClipboard(listing.title, 'title')}
                      className="text-xs px-2 py-1 bg-dark-bg border border-dark-border rounded text-gray-400 hover:text-accent transition-colors"
                    >
                      {copied === 'title' ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                </div>
                <input
                  type="text"
                  value={listing.title}
                  onChange={(e) =>
                    setListing({ ...listing, title: e.target.value })
                  }
                  maxLength={140}
                  className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
                />
              </div>

              {/* TAGS */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-gray-500 uppercase">
                    Tags ({listing.tags.length}/13)
                  </span>
                  <button
                    onClick={() =>
                      copyToClipboard(listing.tags_string, 'tags')
                    }
                    className="text-xs px-2 py-1 bg-dark-bg border border-dark-border rounded text-gray-400 hover:text-accent transition-colors"
                  >
                    {copied === 'tags' ? 'Copied!' : 'Copy All'}
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {listing.tags.map((tag, i) => (
                    <span
                      key={i}
                      className="text-xs px-2 py-1 bg-accent/15 text-accent rounded cursor-pointer hover:bg-accent/25 transition-colors"
                      onClick={() => copyToClipboard(tag, `tag-${i}`)}
                      title="Click to copy"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <input
                  type="text"
                  value={listing.tags_string}
                  onChange={(e) => {
                    const newTags = e.target.value
                      .split(',')
                      .map((t) => t.trim());
                    setListing({
                      ...listing,
                      tags: newTags,
                      tags_string: e.target.value,
                    });
                  }}
                  className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-100 text-xs focus:outline-none focus:ring-2 focus:ring-accent/50"
                  placeholder="tag1, tag2, tag3..."
                />
              </div>

              {/* DESCRIPTION */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-medium text-gray-500 uppercase">
                    Description ({listing.description.length} chars)
                  </span>
                  <div className="flex items-center gap-2">
                    <select
                      value={descTone}
                      onChange={(e) => setDescTone(e.target.value)}
                      className="text-xs px-1.5 py-1 bg-dark-bg border border-dark-border rounded text-gray-400 focus:outline-none"
                    >
                      <option value="warm">Warm</option>
                      <option value="professional">Professional</option>
                      <option value="playful">Playful</option>
                    </select>
                    <button
                      onClick={handleRegenerateDescription}
                      disabled={regeneratingDesc}
                      className="text-xs px-2 py-1 bg-dark-bg border border-dark-border rounded text-gray-400 hover:text-gray-200 disabled:opacity-50 transition-colors"
                      title="Regenerate description"
                    >
                      {regeneratingDesc ? (
                        <span className="animate-spin inline-block w-3 h-3 border border-gray-400 border-t-transparent rounded-full" />
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={() =>
                        copyToClipboard(listing.description, 'desc')
                      }
                      className="text-xs px-2 py-1 bg-dark-bg border border-dark-border rounded text-gray-400 hover:text-accent transition-colors"
                    >
                      {copied === 'desc' ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                </div>
                <textarea
                  value={listing.description}
                  onChange={(e) =>
                    setListing({ ...listing, description: e.target.value })
                  }
                  rows={6}
                  className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 resize-y min-h-[120px]"
                />
              </div>

              {/* Pricing */}
              {listing.pricing && (
                <div>
                  <button
                    onClick={() => setShowPricing(!showPricing)}
                    className="flex items-center gap-2 text-xs font-medium text-gray-500 uppercase hover:text-gray-300 transition-colors"
                  >
                    <svg
                      className={`w-3 h-3 transition-transform ${showPricing ? 'rotate-90' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2}
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                    </svg>
                    Recommended Pricing
                  </button>
                  {showPricing && (
                    <div className="mt-2 border border-dark-border rounded-lg overflow-hidden">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="bg-dark-bg text-gray-500">
                            <th className="px-3 py-2 text-left font-medium">Size</th>
                            <th className="px-3 py-2 text-right font-medium">Price</th>
                            <th className="px-3 py-2 text-right font-medium">Cost</th>
                            <th className="px-3 py-2 text-right font-medium">Profit</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(listing.pricing)
                            .sort(([a], [b]) => {
                              const sizeOrder = ['8x10', '11x14', '12x16', '16x20', '18x24'];
                              return sizeOrder.indexOf(a) - sizeOrder.indexOf(b);
                            })
                            .map(([size, info]) => (
                              <tr key={size} className="border-t border-dark-border">
                                <td className="px-3 py-1.5 text-gray-300">{size}&quot;</td>
                                <td className="px-3 py-1.5 text-right text-gray-200 font-medium">
                                  ${info.recommended_price.toFixed(2)}
                                </td>
                                <td className="px-3 py-1.5 text-right text-gray-500">
                                  ${(info.base_cost + info.shipping_included).toFixed(2)}
                                </td>
                                <td className="px-3 py-1.5 text-right text-green-400">
                                  ${info.profit.toFixed(2)}
                                  <span className="text-gray-600 ml-1">
                                    ({info.margin_percent}%)
                                  </span>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              {/* Separator */}
              <div className="border-t border-dark-border pt-4 space-y-3">
                {/* Publish to Etsy checkbox */}
                <label className="flex items-center gap-2.5 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={publishToEtsy}
                    onChange={(e) => setPublishToEtsy(e.target.checked)}
                    className="w-4 h-4 rounded border-dark-border bg-dark-bg text-accent focus:ring-accent/50 cursor-pointer"
                  />
                  <span className="text-sm text-gray-400 group-hover:text-gray-300 transition-colors">
                    Publish to Etsy immediately
                  </span>
                </label>

                {/* Create Product button */}
                <button
                  onClick={handleCreateProduct}
                  disabled={creatingProduct}
                  className="w-full px-4 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
                >
                  {creatingProduct ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                      Creating product...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                      </svg>
                      Create Product on Printify
                    </span>
                  )}
                </button>
              </div>

              {/* Copy All */}
              <button
                onClick={copyAll}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-dark-bg border border-dark-border rounded-lg text-gray-200 hover:bg-dark-hover transition-colors text-sm"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9.75a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184"
                  />
                </svg>
                {copied === 'all' ? 'All Copied!' : 'Copy Everything'}
              </button>

              {/* Start over */}
              <button
                onClick={() => {
                  setListing(null);
                  setError(null);
                }}
                className="w-full text-xs text-gray-500 hover:text-gray-300 transition-colors py-1"
              >
                Start over
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
