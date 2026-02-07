'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  getPrintifyStatus,
  getPrintifyProducts,
  PrintifyStatus,
  PrintifyProduct,
  PrintifyProductsResponse,
} from '@/lib/api';

export default function ShopPage() {
  const [status, setStatus] = useState<PrintifyStatus | null>(null);
  const [products, setProducts] = useState<PrintifyProductsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const limit = 20;

  useEffect(() => {
    getPrintifyStatus().then(setStatus).catch(console.error);
  }, []);

  const loadProducts = useCallback(() => {
    setIsLoading(true);
    setError(null);
    getPrintifyProducts(page, limit)
      .then((data) => {
        setProducts(data);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });
  }, [page]);

  useEffect(() => {
    if (status?.connected) {
      loadProducts();
    } else {
      setIsLoading(false);
    }
  }, [status, loadProducts]);

  const getProductImage = (product: PrintifyProduct): string | null => {
    if (product.images && product.images.length > 0) {
      return product.images[0].src;
    }
    return null;
  };

  const getProductStatus = (product: PrintifyProduct): string => {
    if (product.external?.id) return 'on etsy';
    if (product.visible) return 'visible';
    return 'draft';
  };

  const getStatusBadge = (statusText: string) => {
    switch (statusText) {
      case 'on etsy':
        return 'bg-green-500/15 text-green-400 border-green-500/30';
      case 'visible':
        return 'bg-blue-500/15 text-blue-400 border-blue-500/30';
      default:
        return 'bg-gray-500/15 text-gray-400 border-gray-500/30';
    }
  };

  const formatPrice = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  // Not configured banner
  if (status && !status.configured) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-gray-100 mb-6">Shop Management</h1>
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-6 text-center">
          <div className="text-4xl mb-3">&#9888;</div>
          <h2 className="text-lg font-semibold text-yellow-400 mb-2">Printify Not Configured</h2>
          <p className="text-gray-400">
            Add <code className="bg-dark-hover px-1.5 py-0.5 rounded text-sm">PRINTIFY_API_TOKEN</code> and{' '}
            <code className="bg-dark-hover px-1.5 py-0.5 rounded text-sm">PRINTIFY_SHOP_ID</code> to your .env file to manage your shop.
          </p>
        </div>
      </div>
    );
  }

  // Connection error banner
  if (status && status.configured && !status.connected) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-gray-100 mb-6">Shop Management</h1>
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6 text-center">
          <div className="text-4xl mb-3">&#10060;</div>
          <h2 className="text-lg font-semibold text-red-400 mb-2">Connection Failed</h2>
          <p className="text-gray-400">
            Could not connect to Printify. {status.error && <span>Error: {status.error}</span>}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Shop Management</h1>
          {status?.shops && status.shops.length > 0 && (
            <p className="text-sm text-gray-500 mt-1">
              {status.shops[0].title} &middot; {products?.total ?? 0} products
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/history"
            className="px-4 py-2 rounded-lg bg-accent text-dark-bg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            + New Product
          </Link>
          <button
            onClick={loadProducts}
            disabled={isLoading}
            className="px-4 py-2 rounded-lg bg-dark-card border border-dark-border text-sm text-gray-300 hover:bg-dark-hover transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 mb-6 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">&#10005;</button>
        </div>
      )}

      {/* Loading */}
      {isLoading && !products && (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && products && products.data.length === 0 && (
        <div className="text-center py-20">
          <div className="text-5xl mb-4 opacity-30">&#128722;</div>
          <h2 className="text-lg font-medium text-gray-400 mb-2">No products yet</h2>
          <p className="text-gray-600 mb-4">Create products from the History page using &ldquo;Etsy Listing&rdquo; and full automation.</p>
          <Link
            href="/history"
            className="inline-block px-4 py-2 rounded-lg bg-accent text-dark-bg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Go to History
          </Link>
        </div>
      )}

      {/* Product grid */}
      {products && products.data.length > 0 && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {products.data.map((product) => {
              const image = getProductImage(product);
              const productStatus = getProductStatus(product);
              const enabledVariants = product.variants.filter((v) => v.is_enabled);
              const priceRange = enabledVariants.length > 0
                ? `${formatPrice(Math.min(...enabledVariants.map((v) => v.price)))} - ${formatPrice(Math.max(...enabledVariants.map((v) => v.price)))}`
                : '';

              return (
                <Link
                  key={product.id}
                  href={`/shop/${product.id}`}
                  className="bg-dark-card border border-dark-border rounded-lg overflow-hidden hover:border-gray-600 transition-colors group block"
                >
                  {/* Image */}
                  <div className="aspect-[4/5] bg-dark-bg relative">
                    {image ? (
                      <img
                        src={image}
                        alt={product.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-700">
                        <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                    )}
                    {/* Status badge */}
                    <span className={`absolute top-2 right-2 text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full border ${getStatusBadge(productStatus)}`}>
                      {productStatus}
                    </span>
                  </div>

                  {/* Info */}
                  <div className="p-3">
                    <h3
                      className="text-sm font-medium text-gray-200 truncate group-hover:text-accent transition-colors"
                      title={product.title}
                    >
                      {product.title}
                    </h3>
                    <div className="flex items-center justify-between mt-1.5">
                      <span className="text-xs text-gray-500">
                        {enabledVariants.length} variants
                      </span>
                      {priceRange && (
                        <span className="text-xs text-gray-400 font-medium">{priceRange}</span>
                      )}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>

          {/* Pagination */}
          {products.last_page > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 rounded-md text-sm bg-dark-card border border-dark-border text-gray-400 hover:bg-dark-hover disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-sm text-gray-500">
                Page {page} of {products.last_page}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(products.last_page, p + 1))}
                disabled={page === products.last_page}
                className="px-3 py-1.5 rounded-md text-sm bg-dark-card border border-dark-border text-gray-400 hover:bg-dark-hover disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
