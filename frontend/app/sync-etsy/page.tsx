'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

interface Product {
  printify_product_id: string;
  title: string;
  status: string;
  etsy_listing_id: string | null;
  image_url: string | null;
  created_at: string | null;
}

interface EtsyListing {
  listing_id: string;
  title: string;
  state: string;
  url: string;
  image_url: string | null;
}

interface UnmatchedData {
  products_without_listing: Product[];
  products_with_listing: Product[];
  unmatched_etsy_listings: EtsyListing[];
  total_unmatched_products: number;
  total_unmatched_listings: number;
}

export default function SyncEtsyPage() {
  const [data, setData] = useState<UnmatchedData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [selectedListings, setSelectedListings] = useState<Record<string, string>>({});
  const [linking, setLinking] = useState<Set<string>>(new Set());
  const [openDropdowns, setOpenDropdowns] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('http://localhost:8001/sync/etsy-unmatched');
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Failed to load' }));
        throw new Error(errData.detail || 'Failed to load data');
      }
      const result = await res.json();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleLink = async (productId: string, listingId: string) => {
    setLinking((prev) => new Set(prev).add(productId));
    setError(null);
    try {
      const res = await fetch('http://localhost:8001/sync/etsy-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          printify_product_id: productId,
          etsy_listing_id: listingId,
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Link failed' }));
        throw new Error(errData.detail || 'Failed to link');
      }
      setSuccessMsg('Linked successfully!');
      setTimeout(() => setSuccessMsg(null), 3000);
      // Reload data
      await loadData();
      // Clear selection
      setSelectedListings((prev) => {
        const next = { ...prev };
        delete next[productId];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to link');
    } finally {
      setLinking((prev) => {
        const next = new Set(prev);
        next.delete(productId);
        return next;
      });
    }
  };

  const handleUnlink = async (productId: string) => {
    if (!confirm('Unlink this product from Etsy?')) return;

    setError(null);
    try {
      const res = await fetch(`http://localhost:8001/sync/etsy-unlink/${productId}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Unlink failed' }));
        throw new Error(errData.detail || 'Failed to unlink');
      }
      setSuccessMsg('Unlinked successfully!');
      setTimeout(() => setSuccessMsg(null), 3000);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to unlink');
    }
  };

  const handleImport = async (listingId: string) => {
    setImporting((prev) => new Set(prev).add(listingId));
    setError(null);
    try {
      const res = await fetch(`http://localhost:8001/sync/etsy-import/${listingId}`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Import failed' }));
        throw new Error(errData.detail || 'Failed to import');
      }
      const result = await res.json();
      setSuccessMsg(`Imported: ${result.title}`);
      setTimeout(() => setSuccessMsg(null), 3000);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import');
    } finally {
      setImporting((prev) => {
        const next = new Set(prev);
        next.delete(listingId);
        return next;
      });
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Link Products to Etsy</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manually match database products with Etsy listings
          </p>
        </div>
        <Link
          href="/dashboard"
          className="px-4 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors"
        >
          ← Back
        </Link>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 text-green-400 text-sm">
          {successMsg}
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : !data ? (
        <div className="text-center py-12 text-gray-500">No data</div>
      ) : (
        <>
          {/* Stats */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-1">Products without listing</p>
              <p className="text-2xl font-bold text-gray-100">{data.total_unmatched_products}</p>
              <p className="text-[10px] text-gray-600 mt-1">
                Published: {data.products_without_listing.filter(p => p.status === 'published').length} |
                Draft: {data.products_without_listing.filter(p => p.status === 'draft').length}
              </p>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-1">Unmatched Etsy listings</p>
              <p className="text-2xl font-bold text-yellow-400">{data.total_unmatched_listings}</p>
              <p className="text-[10px] text-gray-600 mt-1">Not in database</p>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-1">Already linked</p>
              <p className="text-2xl font-bold text-green-400">{data.products_with_listing.length}</p>
              <p className="text-[10px] text-gray-600 mt-1">Synced</p>
            </div>
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-1">Total Etsy listings</p>
              <p className="text-2xl font-bold text-blue-400">{data.total_unmatched_listings + data.products_with_listing.length}</p>
              <p className="text-[10px] text-gray-600 mt-1">On Etsy shop</p>
            </div>
          </div>

          {/* Unmatched products */}
          {data.products_without_listing.length > 0 && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Products to Link</h2>
              <div className="space-y-3">
                {data.products_without_listing.map((product) => {
                  const isLinking = linking.has(product.printify_product_id);
                  const selectedListing = selectedListings[product.printify_product_id];

                  return (
                    <div
                      key={product.printify_product_id}
                      className="bg-dark-bg border border-dark-border rounded-lg p-3"
                    >
                      <div className="flex items-start gap-3">
                        {product.image_url ? (
                          <img
                            src={product.image_url}
                            alt={product.title}
                            className="w-16 h-20 object-cover rounded flex-shrink-0"
                          />
                        ) : (
                          <div className="w-16 h-20 bg-dark-hover rounded flex-shrink-0 flex items-center justify-center">
                            <span className="text-xs text-gray-600">No image</span>
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-200 truncate">
                            {product.title}
                          </p>
                          <div className="flex gap-2 mt-1">
                            <span className={`px-2 py-0.5 rounded text-xs ${
                              product.status === 'published'
                                ? 'bg-green-500/10 text-green-400'
                                : 'bg-gray-500/10 text-gray-400'
                            }`}>
                              {product.status}
                            </span>
                            <span className="text-xs text-gray-600">
                              {product.printify_product_id}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 flex-1">
                          {/* Custom dropdown with images */}
                          <div className="relative flex-1 max-w-md">
                            <button
                              onClick={() => {
                                if (!isLinking) {
                                  setOpenDropdowns((prev) => {
                                    const next = new Set(prev);
                                    if (next.has(product.printify_product_id)) {
                                      next.delete(product.printify_product_id);
                                    } else {
                                      next.clear();
                                      next.add(product.printify_product_id);
                                    }
                                    return next;
                                  });
                                }
                              }}
                              disabled={isLinking}
                              className="w-full px-3 py-2 bg-dark-card border border-dark-border rounded text-sm text-gray-200 disabled:opacity-50 flex items-center gap-2 hover:bg-dark-hover transition-colors"
                            >
                              {selectedListing ? (() => {
                                const listing = data.unmatched_etsy_listings.find(l => l.listing_id === selectedListing);
                                return listing ? (
                                  <>
                                    {listing.image_url && (
                                      <img
                                        src={listing.image_url}
                                        alt={listing.title}
                                        className="w-12 h-16 object-cover rounded flex-shrink-0"
                                      />
                                    )}
                                    <span className="flex-1 truncate text-left">{listing.title}</span>
                                  </>
                                ) : <span className="text-gray-500">Select Etsy listing...</span>;
                              })() : <span className="text-gray-500">Select Etsy listing...</span>}
                              <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                              </svg>
                            </button>

                            {openDropdowns.has(product.printify_product_id) && (
                              <>
                                <div
                                  className="fixed inset-0 z-10"
                                  onClick={() => setOpenDropdowns(new Set())}
                                />
                                <div className="absolute top-full left-0 right-0 mt-1 bg-dark-card border border-dark-border rounded-lg shadow-xl max-h-96 overflow-y-auto z-20">
                                  {data.unmatched_etsy_listings.map((listing) => (
                                    <button
                                      key={listing.listing_id}
                                      onClick={() => {
                                        setSelectedListings((prev) => ({
                                          ...prev,
                                          [product.printify_product_id]: listing.listing_id,
                                        }));
                                        setOpenDropdowns(new Set());
                                      }}
                                      className="w-full px-3 py-2 flex items-center gap-2 hover:bg-dark-hover transition-colors text-left border-b border-dark-border last:border-b-0"
                                    >
                                      {listing.image_url && (
                                        <img
                                          src={listing.image_url}
                                          alt={listing.title}
                                          className="w-12 h-16 object-cover rounded flex-shrink-0"
                                        />
                                      )}
                                      <span className="flex-1 text-sm text-gray-200 truncate">
                                        {listing.title}
                                      </span>
                                    </button>
                                  ))}
                                </div>
                              </>
                            )}
                          </div>

                          <button
                            onClick={() => handleLink(product.printify_product_id, selectedListing)}
                            disabled={!selectedListing || isLinking}
                            className="px-4 py-2 bg-accent/20 text-accent rounded text-sm font-medium hover:bg-accent/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
                          >
                            {isLinking ? 'Linking...' : 'Link'}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Etsy listings without database products */}
          {data.unmatched_etsy_listings.length > 0 && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-yellow-400 mb-2">
                ⚠️ Etsy Listings Not in Database ({data.unmatched_etsy_listings.length})
              </h2>
              <p className="text-xs text-gray-500 mb-4">
                These listings exist on Etsy but have no matching product in your database.
                You may need to import them or they might be old listings.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {data.unmatched_etsy_listings.map((listing) => (
                  <div
                    key={listing.listing_id}
                    className="bg-dark-card border border-dark-border rounded-lg overflow-hidden"
                  >
                    {listing.image_url && (
                      <img
                        src={listing.image_url}
                        alt={listing.title}
                        className="w-full aspect-[4/5] object-cover"
                      />
                    )}
                    <div className="p-2">
                      <p className="text-xs text-gray-200 truncate mb-1">{listing.title}</p>
                      <a
                        href={listing.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-accent hover:underline"
                      >
                        View on Etsy →
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Already linked products */}
          {data.products_with_listing.length > 0 && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <h2 className="text-lg font-semibold text-gray-100 mb-4">
                Already Linked ({data.products_with_listing.length})
              </h2>
              <div className="space-y-2">
                {data.products_with_listing.map((product) => (
                  <div
                    key={product.printify_product_id}
                    className="bg-dark-bg border border-dark-border rounded-lg p-3 flex items-center gap-3"
                  >
                    {product.image_url && (
                      <img
                        src={product.image_url}
                        alt={product.title}
                        className="w-16 h-20 object-cover rounded flex-shrink-0"
                      />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-200 truncate">{product.title}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        Etsy listing: {product.etsy_listing_id}
                      </p>
                    </div>
                    <button
                      onClick={() => handleUnlink(product.printify_product_id)}
                      className="px-3 py-1.5 bg-red-500/10 text-red-400 rounded text-xs hover:bg-red-500/20 transition-colors"
                    >
                      Unlink
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
