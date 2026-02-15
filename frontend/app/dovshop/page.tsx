'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  getDovShopStatus,
  getDovShopProducts,
  getDovShopCollections,
  pushProductToDovShop,
  deleteDovShopProduct,
  createDovShopCollection,
  deleteDovShopCollection,
  getTrackedProducts,
  syncAllToDovShop,
  type DovShopStatus,
  type DovShopProduct,
  type DovShopCollection,
  type TrackedProduct,
  type DovShopSyncResponse,
} from '@/lib/api';

type Tab = 'collections' | 'products' | 'push' | 'sync';

export default function DovShopPage() {
  const [tab, setTab] = useState<Tab>('collections');
  const [status, setStatus] = useState<DovShopStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Collections tab state
  const [collections, setCollections] = useState<DovShopCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [showCreateCollection, setShowCreateCollection] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [newCollectionDesc, setNewCollectionDesc] = useState('');
  const [creating, setCreating] = useState(false);

  // Products tab state
  const [products, setProducts] = useState<DovShopProduct[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [deletingProduct, setDeletingProduct] = useState<string | null>(null);

  // Push tab state
  const [panelProducts, setPanelProducts] = useState<TrackedProduct[]>([]);
  const [panelProductsLoading, setPanelProductsLoading] = useState(false);
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
  const [pushing, setPushing] = useState(false);
  const [pushProgress, setPushProgress] = useState<Record<string, { status: string; message?: string }>>({});

  // Sync tab state
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<DovShopSyncResponse | null>(null);

  // Load status on mount
  useEffect(() => {
    loadStatus();
  }, []);

  // Load data when tab changes
  useEffect(() => {
    if (tab === 'collections') loadCollections();
    else if (tab === 'products') loadProducts();
    else if (tab === 'push') loadPanelProducts();
  }, [tab]);

  const loadStatus = async () => {
    try {
      const statusData = await getDovShopStatus();
      setStatus(statusData);
      setLoading(false);
    } catch (err) {
      setError((err as Error).message);
      setLoading(false);
    }
  };

  const loadCollections = async () => {
    setCollectionsLoading(true);
    try {
      const data = await getDovShopCollections();
      setCollections(data.collections);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCollectionsLoading(false);
    }
  };

  const loadProducts = async () => {
    setProductsLoading(true);
    try {
      const data = await getDovShopProducts();
      setProducts(data.products);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setProductsLoading(false);
    }
  };

  const loadPanelProducts = async () => {
    setPanelProductsLoading(true);
    try {
      const data = await getTrackedProducts(undefined, 100);
      setPanelProducts(data.items);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setPanelProductsLoading(false);
    }
  };

  const handleCreateCollection = async () => {
    if (!newCollectionName.trim()) return;
    setCreating(true);
    try {
      await createDovShopCollection({
        name: newCollectionName,
        description: newCollectionDesc,
      });
      setNewCollectionName('');
      setNewCollectionDesc('');
      setShowCreateCollection(false);
      await loadCollections();
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteCollection = async (collectionId: string) => {
    if (!confirm('Are you sure you want to delete this collection?')) return;
    try {
      await deleteDovShopCollection(collectionId);
      await loadCollections();
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleDeleteProduct = async (productId: string) => {
    if (!confirm('Are you sure you want to delete this product from DovShop?')) return;
    setDeletingProduct(productId);
    try {
      await deleteDovShopProduct(productId);
      await loadProducts();
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setDeletingProduct(null);
    }
  };

  const handleToggleProduct = (productId: string) => {
    const newSelected = new Set(selectedProducts);
    if (newSelected.has(productId)) {
      newSelected.delete(productId);
    } else {
      newSelected.add(productId);
    }
    setSelectedProducts(newSelected);
  };

  const unsyncedProducts = panelProducts.filter(p => !p.dovshop_product_id);

  const handleSelectAll = () => {
    if (selectedProducts.size === unsyncedProducts.length) {
      setSelectedProducts(new Set());
    } else {
      setSelectedProducts(new Set(unsyncedProducts.map(p => p.printify_product_id)));
    }
  };

  const handlePushProducts = async () => {
    if (selectedProducts.size === 0) return;
    setPushing(true);
    const progress: Record<string, { status: string; message?: string }> = {};

    for (const productId of Array.from(selectedProducts)) {
      try {
        progress[productId] = { status: 'pushing' };
        setPushProgress({ ...progress });

        await pushProductToDovShop({ printify_product_id: productId });
        progress[productId] = { status: 'success', message: 'Pushed successfully' };
      } catch (err) {
        progress[productId] = { status: 'failed', message: (err as Error).message };
      }
      setPushProgress({ ...progress });

      // Small delay between requests
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    setPushing(false);
    // Refresh products list
    await loadProducts();
  };

  const completedCount = Object.values(pushProgress).filter(p => p.status === 'success' || p.status === 'failed').length;
  const progressPercent = selectedProducts.size > 0 ? (completedCount / selectedProducts.size) * 100 : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-400">Loading DovShop status...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">DovShop Integration</h1>
        <p className="text-sm text-gray-400 mt-1">Manage products and collections on DovShop</p>
      </div>

      {/* Status Banner */}
      {status && !status.connected && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-4 py-3 text-yellow-400 text-sm">
          <strong>Warning:</strong> DovShop is not connected. {status.message || status.error || 'Check your API key configuration in .env'}
        </div>
      )}

      {status && status.connected && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg px-4 py-3 text-green-400 text-sm">
          <strong>Connected:</strong> DovShop API is working correctly
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300">✕</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-dark-border">
        {([
          { key: 'sync' as Tab, label: 'Sync All' },
          { key: 'collections' as Tab, label: 'Collections' },
          { key: 'products' as Tab, label: 'Products' },
          { key: 'push' as Tab, label: 'Push New' },
        ]).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 font-medium transition-colors ${
              tab === t.key
                ? 'border-b-2 border-accent text-accent -mb-px'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'collections' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-200">Collections on DovShop</h2>
            <button
              onClick={() => setShowCreateCollection(!showCreateCollection)}
              className="px-4 py-2 bg-accent/15 hover:bg-accent/25 border border-accent/30 rounded-lg text-accent text-sm font-medium transition-colors"
            >
              {showCreateCollection ? '✕ Cancel' : '+ New Collection'}
            </button>
          </div>

          {showCreateCollection && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Collection Name *</label>
                <input
                  type="text"
                  value={newCollectionName}
                  onChange={(e) => setNewCollectionName(e.target.value)}
                  placeholder="e.g., Summer Posters 2024"
                  className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-200 text-sm focus:outline-none focus:border-accent"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Description</label>
                <textarea
                  value={newCollectionDesc}
                  onChange={(e) => setNewCollectionDesc(e.target.value)}
                  placeholder="Optional description..."
                  rows={2}
                  className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-200 text-sm focus:outline-none focus:border-accent resize-none"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleCreateCollection}
                  disabled={creating || !newCollectionName.trim()}
                  className="px-4 py-2 bg-accent hover:bg-accent/80 rounded-lg text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {creating ? 'Creating...' : 'Create Collection'}
                </button>
              </div>
            </div>
          )}

          {collectionsLoading ? (
            <div className="text-center py-12 text-gray-400">Loading collections...</div>
          ) : collections.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              No collections yet. Create one to organize your products.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {collections.map((collection) => (
                <div key={collection.id} className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
                  {collection.cover_url && (
                    <div className="aspect-square rounded-lg overflow-hidden bg-dark-bg">
                      <img src={collection.cover_url} alt={collection.name} className="w-full h-full object-cover" />
                    </div>
                  )}
                  <div>
                    <h3 className="font-medium text-gray-100 text-sm">{collection.name}</h3>
                    {collection.description && (
                      <p className="text-xs text-gray-400 mt-1 line-clamp-2">{collection.description}</p>
                    )}
                    <p className="text-xs text-gray-500 mt-2">
                      {collection.product_count || 0} products
                    </p>
                  </div>
                  <button
                    onClick={() => handleDeleteCollection(collection.id)}
                    className="w-full px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded text-red-400 text-xs font-medium transition-colors"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'products' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-200">Products on DovShop</h2>
            <button
              onClick={loadProducts}
              disabled={productsLoading}
              className="px-4 py-2 bg-dark-card hover:bg-dark-hover border border-dark-border rounded-lg text-gray-300 text-sm font-medium transition-colors disabled:opacity-50"
            >
              {productsLoading ? 'Refreshing...' : '↻ Refresh'}
            </button>
          </div>

          {productsLoading ? (
            <div className="text-center py-12 text-gray-400">Loading products...</div>
          ) : products.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              No products on DovShop yet. Push some from the "Push New" tab.
            </div>
          ) : (
            <div className="bg-dark-card border border-dark-border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-dark-bg border-b border-dark-border">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Image</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Title</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-border">
                  {products.map((product) => (
                    <tr key={product.id} className="hover:bg-dark-hover transition-colors">
                      <td className="px-4 py-3">
                        <div className="w-12 h-12 rounded bg-dark-bg overflow-hidden">
                          {product.image_url && (
                            <img src={product.image_url} alt={product.title} className="w-full h-full object-cover" />
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-200">{product.title}</td>
                      <td className="px-4 py-3 text-sm text-gray-300">${product.price.toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-gray-400">
                        {new Date(product.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDeleteProduct(product.id)}
                          disabled={deletingProduct === product.id}
                          className="px-3 py-1 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded text-red-400 text-xs font-medium transition-colors disabled:opacity-50"
                        >
                          {deletingProduct === product.id ? 'Deleting...' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'push' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-200">Push Products to DovShop</h2>
            <div className="flex gap-2">
              <button
                onClick={handleSelectAll}
                disabled={unsyncedProducts.length === 0}
                className="px-4 py-2 bg-dark-card hover:bg-dark-hover border border-dark-border rounded-lg text-gray-300 text-sm font-medium transition-colors disabled:opacity-50"
              >
                {selectedProducts.size === unsyncedProducts.length && unsyncedProducts.length > 0 ? 'Deselect All' : `Select All (${unsyncedProducts.length})`}
              </button>
              <button
                onClick={handlePushProducts}
                disabled={pushing || selectedProducts.size === 0}
                className="px-4 py-2 bg-accent hover:bg-accent/80 rounded-lg text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {pushing ? `Pushing... ${completedCount}/${selectedProducts.size}` : `Push Selected (${selectedProducts.size})`}
              </button>
            </div>
          </div>

          {pushing && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-300">Progress</span>
                <span className="text-gray-400">{completedCount} / {selectedProducts.size}</span>
              </div>
              <div className="w-full h-2 bg-dark-bg rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent rounded-full transition-all duration-300"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
          )}

          {panelProductsLoading ? (
            <div className="text-center py-12 text-gray-400">Loading panel products...</div>
          ) : panelProducts.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              No products in the panel yet. Create some products first.
            </div>
          ) : (
            <div className="space-y-2">
              {panelProducts.map((product) => {
                const progress = pushProgress[product.printify_product_id];
                const isSelected = selectedProducts.has(product.printify_product_id);
                const alreadySynced = !!product.dovshop_product_id;

                return (
                  <div
                    key={product.printify_product_id}
                    className={`flex items-center gap-4 p-3 bg-dark-card border rounded-lg hover:bg-dark-hover transition-colors ${
                      alreadySynced ? 'border-green-500/30' : 'border-dark-border'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleToggleProduct(product.printify_product_id)}
                      disabled={pushing || alreadySynced}
                      className="w-4 h-4 rounded border-gray-600 bg-dark-bg text-accent focus:ring-accent focus:ring-offset-0 disabled:opacity-40"
                    />

                    {product.image_url && (
                      <div className="w-12 h-12 rounded bg-dark-bg overflow-hidden flex-shrink-0">
                        <img src={product.image_url} alt={product.title} className="w-full h-full object-cover" />
                      </div>
                    )}

                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-gray-200 truncate">{product.title}</h3>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">{product.status}</span>
                        {alreadySynced && (
                          <span className="text-xs text-green-400/80 bg-green-500/10 px-1.5 py-0.5 rounded">
                            on DovShop
                          </span>
                        )}
                      </div>
                    </div>

                    {progress && (
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {progress.status === 'pushing' && (
                          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                        )}
                        {progress.status === 'success' && (
                          <span className="text-green-400">✓</span>
                        )}
                        {progress.status === 'failed' && (
                          <span className="text-red-400" title={progress.message}>✕</span>
                        )}
                        <span className={`text-xs ${
                          progress.status === 'success' ? 'text-green-400' :
                          progress.status === 'failed' ? 'text-red-400' :
                          'text-blue-400'
                        }`}>
                          {progress.status === 'pushing' ? 'Pushing...' :
                           progress.status === 'success' ? 'Success' :
                           'Failed'}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Sync Tab */}
      {tab === 'sync' && (
        <div className="space-y-4">
          <div className="bg-dark-card border border-dark-border rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-200 mb-2">Sync All Published Products</h2>
            <p className="text-sm text-gray-400 mb-4">
              Sends all products published on Etsy to DovShop in one bulk request.
              Products are auto-categorized by style and room based on their tags.
            </p>

            <button
              onClick={async () => {
                setSyncing(true);
                setSyncResult(null);
                setError(null);
                try {
                  const result = await syncAllToDovShop();
                  setSyncResult(result);
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Sync failed');
                } finally {
                  setSyncing(false);
                }
              }}
              disabled={syncing || !status?.connected}
              className="px-6 py-3 bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {syncing ? 'Syncing...' : 'Sync Now'}
            </button>

            {syncing && (
              <div className="mt-4">
                <div className="w-full h-2 bg-dark-bg rounded-full overflow-hidden">
                  <div className="h-full bg-accent rounded-full animate-pulse" style={{ width: '100%' }} />
                </div>
                <p className="text-xs text-gray-500 mt-2">Sending products to DovShop...</p>
              </div>
            )}

            {syncResult && (
              <div className="mt-4 bg-dark-bg rounded-lg p-4 space-y-2">
                <div className="flex gap-6 text-sm">
                  <span className="text-gray-400">Total: <strong className="text-gray-200">{syncResult.total}</strong></span>
                  <span className="text-green-400">Created: <strong>{syncResult.created}</strong></span>
                  <span className="text-blue-400">Updated: <strong>{syncResult.updated}</strong></span>
                  {syncResult.errors.length > 0 && (
                    <span className="text-red-400">Errors: <strong>{syncResult.errors.length}</strong></span>
                  )}
                </div>
                <p className="text-sm text-gray-500">{syncResult.message}</p>

                {syncResult.errors.length > 0 && (
                  <div className="mt-2 space-y-1">
                    <p className="text-xs text-red-400 font-medium">Errors:</p>
                    {syncResult.errors.map((e, i) => (
                      <p key={i} className="text-xs text-red-400/70">
                        {e.printify_id}: {e.error}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
