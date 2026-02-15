'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  getProviders,
  compareProviders,
  ProvidersResponse,
  ProviderComparison,
} from '@/lib/api';

const SIZES = ['8x10', '11x14', '12x16', '16x20', '18x24'];
const DEFAULT_SIZE = '18x24';

const RECOMMENDATION_LABELS: Record<string, { label: string; icon: string }> = {
  starting_out: { label: 'Starting Out', icon: 'M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25' },
  premium_quality: { label: 'Premium Quality', icon: 'M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.602a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z' },
  budget_focus: { label: 'Budget Focus', icon: 'M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z' },
  global_shipping: { label: 'Global Shipping', icon: 'M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418' },
  fine_art: { label: 'Fine Art', icon: 'M9.53 16.122a3 3 0 0 0-5.78 1.128 2.25 2.25 0 0 1-2.4 2.245 4.5 4.5 0 0 0 8.4-2.245c0-.399-.078-.78-.22-1.128Zm0 0a15.998 15.998 0 0 0 3.388-1.62m-5.043-.025a15.994 15.994 0 0 1 1.622-3.395m3.42 3.42a15.995 15.995 0 0 0 4.764-4.648l3.876-5.814a1.151 1.151 0 0 0-1.597-1.597L14.146 6.32a15.996 15.996 0 0 0-4.649 4.763m3.42 3.42a6.776 6.776 0 0 0-3.42-3.42' },
};

function formatUSD(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

function StarRating({ rating, max = 5 }: { rating: number; max?: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: max }, (_, i) => (
        <svg
          key={i}
          className={`w-4 h-4 ${i < rating ? 'text-yellow-400' : 'text-gray-600'}`}
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ))}
    </div>
  );
}

function CheckIcon() {
  return (
    <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
    </svg>
  );
}

export default function ProvidersPage() {
  const [providersData, setProvidersData] = useState<ProvidersResponse | null>(null);
  const [comparison, setComparison] = useState<ProviderComparison[]>([]);
  const [selectedSize, setSelectedSize] = useState(DEFAULT_SIZE);
  const [expandedProvider, setExpandedProvider] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isComparing, setIsComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadProviders = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getProviders();
      setProvidersData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load providers');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadComparison = useCallback(async (size: string) => {
    setIsComparing(true);
    try {
      const data = await compareProviders(size);
      setComparison(data.providers);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compare providers');
    } finally {
      setIsComparing(false);
    }
  }, []);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  useEffect(() => {
    loadComparison(selectedSize);
  }, [selectedSize, loadComparison]);

  const cheapestTotal = comparison.length > 0
    ? Math.min(...comparison.map((p) => p.total))
    : 0;

  const toggleProvider = (id: string) => {
    setExpandedProvider((prev) => (prev === id ? null : id));
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-100 mb-2">POD Providers</h1>
        <p className="text-gray-400 text-sm max-w-2xl">
          Compare print-on-demand providers for poster fulfillment. See pricing, quality ratings,
          and features side-by-side to find the best fit for your shop.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 mb-6 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">&#10005;</button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      )}

      {!isLoading && providersData && (
        <>
          {/* Size Selector */}
          <div className="mb-6">
            <label className="block text-xs text-gray-500 uppercase tracking-wider mb-2 font-medium">
              Compare prices for size
            </label>
            <div className="flex flex-wrap gap-2">
              {SIZES.map((size) => (
                <button
                  key={size}
                  onClick={() => setSelectedSize(size)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                    selectedSize === size
                      ? 'bg-accent/15 text-accent border-accent/40'
                      : 'bg-dark-card text-gray-400 border-dark-border hover:text-gray-200 hover:border-gray-600'
                  }`}
                >
                  {size}&quot;
                </button>
              ))}
            </div>
          </div>

          {/* Comparison Table */}
          <div className="bg-dark-card border border-dark-border rounded-lg overflow-hidden mb-8">
            <div className="px-5 py-4 border-b border-dark-border flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-100">
                Price Comparison
                <span className="text-sm font-normal text-gray-500 ml-2">({selectedSize}&quot;)</span>
              </h2>
              {isComparing && (
                <div className="w-4 h-4 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-dark-border text-left">
                    <th className="px-5 py-3 text-gray-500 font-medium">Provider</th>
                    <th className="px-5 py-3 text-gray-500 font-medium text-right">Base Cost</th>
                    <th className="px-5 py-3 text-gray-500 font-medium text-right">Shipping</th>
                    <th className="px-5 py-3 text-gray-500 font-medium text-right">Total</th>
                    <th className="px-5 py-3 text-gray-500 font-medium">Quality</th>
                    <th className="px-5 py-3 text-gray-500 font-medium">Production</th>
                    <th className="px-5 py-3 text-gray-500 font-medium text-center">Etsy</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.length === 0 && !isComparing && (
                    <tr>
                      <td colSpan={7} className="px-5 py-8 text-center text-gray-500">
                        No pricing data available for this size.
                      </td>
                    </tr>
                  )}
                  {comparison.map((provider) => {
                    const isCheapest = provider.total === cheapestTotal && comparison.length > 1;
                    return (
                      <tr
                        key={provider.provider_id}
                        className="border-b border-dark-border/50 hover:bg-dark-hover/30 transition-colors"
                      >
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-200 font-medium">{provider.provider}</span>
                            {isCheapest && (
                              <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-green-500/15 text-green-400 border border-green-500/30">
                                Cheapest
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-300 tabular-nums">
                          {formatUSD(provider.base_cost)}
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-300 tabular-nums">
                          {formatUSD(provider.shipping)}
                        </td>
                        <td className={`px-5 py-3.5 text-right font-semibold tabular-nums ${isCheapest ? 'text-green-400' : 'text-gray-100'}`}>
                          {formatUSD(provider.total)}
                        </td>
                        <td className="px-5 py-3.5">
                          <StarRating rating={provider.quality} />
                        </td>
                        <td className="px-5 py-3.5 text-gray-400 text-xs">
                          {provider.production_days}
                        </td>
                        <td className="px-5 py-3.5">
                          <div className="flex justify-center">
                            {provider.has_etsy ? <CheckIcon /> : <XIcon />}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Provider Detail Cards */}
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-gray-100 mb-4">Provider Details</h2>
            <div className="space-y-3">
              {providersData.providers.map((provider) => (
                <div
                  key={provider.id}
                  className="bg-dark-card border border-dark-border rounded-lg overflow-hidden"
                >
                  {/* Card Header */}
                  <button
                    onClick={() => toggleProvider(provider.id)}
                    className="w-full px-5 py-4 flex items-center justify-between text-left hover:bg-dark-hover/30 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <div>
                        <h3 className="text-gray-100 font-medium">{provider.name}</h3>
                        <div className="flex items-center gap-3 mt-1">
                          <StarRating rating={provider.quality_rating} />
                          <span className="text-xs text-gray-500">
                            {provider.production_days} production
                          </span>
                          {provider.has_etsy_integration && (
                            <span className="text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full bg-orange-500/15 text-orange-400 border border-orange-500/30">
                              Etsy
                            </span>
                          )}
                          {provider.has_api && (
                            <span className="text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-400 border border-blue-500/30">
                              API
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <ChevronIcon open={expandedProvider === provider.id} />
                  </button>

                  {/* Expanded Content */}
                  {expandedProvider === provider.id && (
                    <div className="px-5 pb-5 border-t border-dark-border/50">
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 pt-4">
                        {/* Prices by Size */}
                        <div>
                          <h4 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-3">
                            Poster Prices
                          </h4>
                          <div className="space-y-1.5">
                            {Object.entries(provider.poster_prices).length > 0 ? (
                              Object.entries(provider.poster_prices).map(([size, price]) => (
                                <div key={size} className="flex items-center justify-between text-sm">
                                  <span className="text-gray-400">{size}&quot;</span>
                                  <span className="text-gray-200 tabular-nums font-medium">
                                    {formatUSD(price)}
                                  </span>
                                </div>
                              ))
                            ) : (
                              <span className="text-gray-600 text-sm">No pricing data</span>
                            )}
                          </div>
                          {Object.entries(provider.shipping_us).length > 0 && (
                            <>
                              <h4 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-3 mt-5">
                                US Shipping
                              </h4>
                              <div className="space-y-1.5">
                                {Object.entries(provider.shipping_us).map(([size, cost]) => (
                                  <div key={size} className="flex items-center justify-between text-sm">
                                    <span className="text-gray-400">{size}&quot;</span>
                                    <span className="text-gray-200 tabular-nums font-medium">
                                      {formatUSD(cost)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </>
                          )}
                        </div>

                        {/* Paper Types */}
                        <div>
                          <h4 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-3">
                            Paper Types
                          </h4>
                          {provider.paper_types.length > 0 ? (
                            <ul className="space-y-1.5">
                              {provider.paper_types.map((type) => (
                                <li key={type} className="flex items-center gap-2 text-sm text-gray-300">
                                  <div className="w-1.5 h-1.5 rounded-full bg-accent/60 flex-shrink-0" />
                                  {type}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <span className="text-gray-600 text-sm">Not specified</span>
                          )}
                        </div>

                        {/* Finishes */}
                        <div>
                          <h4 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-3">
                            Finishes
                          </h4>
                          {provider.finishes.length > 0 ? (
                            <ul className="space-y-1.5">
                              {provider.finishes.map((finish) => (
                                <li key={finish} className="flex items-center gap-2 text-sm text-gray-300">
                                  <div className="w-1.5 h-1.5 rounded-full bg-accent/60 flex-shrink-0" />
                                  {finish}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <span className="text-gray-600 text-sm">Not specified</span>
                          )}
                        </div>

                        {/* Branding & Details */}
                        <div>
                          <h4 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-3">
                            Branding Options
                          </h4>
                          {provider.branding_options.length > 0 ? (
                            <ul className="space-y-1.5">
                              {provider.branding_options.map((option) => (
                                <li key={option} className="flex items-center gap-2 text-sm text-gray-300">
                                  <div className="w-1.5 h-1.5 rounded-full bg-accent/60 flex-shrink-0" />
                                  {option}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <span className="text-gray-600 text-sm">Not specified</span>
                          )}

                          <h4 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-2 mt-5">
                            Shipping Time (US)
                          </h4>
                          <p className="text-sm text-gray-300">{provider.shipping_days_us || 'Not specified'}</p>
                        </div>
                      </div>

                      {/* Notes */}
                      {provider.notes && (
                        <div className="mt-5 pt-4 border-t border-dark-border/50">
                          <h4 className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-2">Notes</h4>
                          <p className="text-sm text-gray-400 leading-relaxed">{provider.notes}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Recommendations */}
          {providersData.recommendations && Object.keys(providersData.recommendations).length > 0 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Recommendations</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(providersData.recommendations).map(([useCase, rec]) => {
                  const meta = RECOMMENDATION_LABELS[useCase];
                  return (
                    <div
                      key={useCase}
                      className="bg-dark-card border border-dark-border rounded-lg p-5 hover:border-accent/30 transition-colors"
                    >
                      {/* Use Case Header */}
                      <div className="flex items-center gap-3 mb-3">
                        <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0">
                          <svg
                            className="w-5 h-5 text-accent"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d={meta?.icon || 'M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 0 0-2.455 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z'}
                            />
                          </svg>
                        </div>
                        <div>
                          <h3 className="text-sm font-semibold text-gray-100">
                            {meta?.label || useCase.replace(/_/g, ' ')}
                          </h3>
                          <p className="text-xs text-accent font-medium">{rec.provider}</p>
                        </div>
                      </div>

                      {/* Reason */}
                      <p className="text-sm text-gray-400 leading-relaxed mb-3">{rec.reason}</p>

                      {/* Tips */}
                      {rec.tips && rec.tips.length > 0 && (
                        <div>
                          <h4 className="text-[10px] text-gray-500 uppercase tracking-wider font-medium mb-2">Tips</h4>
                          <ul className="space-y-1.5">
                            {rec.tips.map((tip, i) => (
                              <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                                <svg
                                  className="w-3.5 h-3.5 text-accent/70 mt-0.5 flex-shrink-0"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  strokeWidth={2}
                                  stroke="currentColor"
                                >
                                  <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                                </svg>
                                {tip}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* Empty state */}
      {!isLoading && !providersData && !error && (
        <div className="text-center py-20">
          <div className="text-5xl mb-4 opacity-30">&#128230;</div>
          <h2 className="text-lg font-medium text-gray-400 mb-2">No provider data available</h2>
          <p className="text-gray-600">Provider information could not be loaded.</p>
        </div>
      )}
    </div>
  );
}
