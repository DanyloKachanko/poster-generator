'use client';

import { useState, useEffect } from 'react';
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
  getDovShopAIStrategy,
  getDovShopStrategyLatest,
  getDovShopStrategyHistory,
  applyDovShopCollection,
  applyDovShopFeature,
  applyDovShopSeo,
  getProductMockupsForDovShop,
  toggleDovShopMockup,
  setDovShopPrimary,
  updateDovShopProductImages,
  assignPackPattern,
  type DovShopStatus,
  type DovShopProduct,
  type DovShopCollection,
  type DovShopMockup,
  type TrackedProduct,
  type DovShopSyncResponse,
  type DovShopStrategyResult,
  type DovShopStrategyHistoryItem,
} from '@/lib/api';

type Tab = 'sync' | 'products' | 'collections' | 'push' | 'strategy';

export default function DovShopPage() {
  const [tab, setTab] = useState<Tab>('products');
  const [status, setStatus] = useState<DovShopStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Products tab
  const [products, setProducts] = useState<DovShopProduct[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [deletingProduct, setDeletingProduct] = useState<string | null>(null);

  // Collections tab
  const [collections, setCollections] = useState<DovShopCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [showCreateCollection, setShowCreateCollection] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [newCollectionDesc, setNewCollectionDesc] = useState('');
  const [creating, setCreating] = useState(false);

  // Push tab
  const [panelProducts, setPanelProducts] = useState<TrackedProduct[]>([]);
  const [panelProductsLoading, setPanelProductsLoading] = useState(false);
  const [selectedProducts, setSelectedProducts] = useState<Set<string>>(new Set());
  const [pushing, setPushing] = useState(false);
  const [pushProgress, setPushProgress] = useState<Record<string, { status: string; message?: string }>>({});

  // Sync tab
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<DovShopSyncResponse | null>(null);

  // Mockup selector (per-product)
  const [expandedMockups, setExpandedMockups] = useState<string | null>(null);
  const [productMockups, setProductMockups] = useState<DovShopMockup[]>([]);
  const [mockupsLoading, setMockupsLoading] = useState(false);
  const [savingMockups, setSavingMockups] = useState<string | null>(null);

  // Pack patterns (rotate primary mockup)
  const [packOffset, setPackOffset] = useState(0);
  const [applyingPattern, setApplyingPattern] = useState(false);
  const [patternResult, setPatternResult] = useState<{ total: number; updated: number } | null>(null);

  // Strategy tab
  const [strategy, setStrategy] = useState<DovShopStrategyResult | null>(null);
  const [strategyLoading, setStrategyLoading] = useState(false);
  const [applyingAction, setApplyingAction] = useState<string | null>(null);
  const [appliedActions, setAppliedActions] = useState<Set<string>>(new Set());
  const [strategyHistory, setStrategyHistory] = useState<DovShopStrategyHistoryItem[]>([]);
  const [strategyDate, setStrategyDate] = useState<string | null>(null);

  useEffect(() => { loadStatus(); }, []);

  useEffect(() => {
    if (tab === 'products') loadProducts();
    else if (tab === 'collections') loadCollections();
    else if (tab === 'push') loadPanelProducts();
    else if (tab === 'strategy') loadStrategyHistory();
  }, [tab]);

  const loadStrategyHistory = async () => {
    try {
      const items = await getDovShopStrategyHistory(20);
      setStrategyHistory(items);
      if (!strategy && items.length > 0) {
        setStrategy(items[0].result);
        setStrategyDate(items[0].created_at);
      }
    } catch {}
  };

  const loadStatus = async () => {
    try {
      const s = await getDovShopStatus();
      setStatus(s);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const loadProducts = async () => {
    setProductsLoading(true);
    try {
      const data = await getDovShopProducts();
      setProducts(data.products);
      setError(null);
    } catch (err) { setError((err as Error).message); }
    finally { setProductsLoading(false); }
  };

  const loadCollections = async () => {
    setCollectionsLoading(true);
    try {
      const data = await getDovShopCollections();
      setCollections(data.collections);
      setError(null);
    } catch (err) { setError((err as Error).message); }
    finally { setCollectionsLoading(false); }
  };

  const loadPanelProducts = async () => {
    setPanelProductsLoading(true);
    try {
      const data = await getTrackedProducts(undefined, 100);
      setPanelProducts(data.items);
      setError(null);
    } catch (err) { setError((err as Error).message); }
    finally { setPanelProductsLoading(false); }
  };

  const handleDeleteProduct = async (productId: string) => {
    if (!confirm('Delete this product from DovShop?')) return;
    setDeletingProduct(productId);
    try {
      await deleteDovShopProduct(productId);
      await loadProducts();
    } catch (err) { setError((err as Error).message); }
    finally { setDeletingProduct(null); }
  };

  const handleCreateCollection = async () => {
    if (!newCollectionName.trim()) return;
    setCreating(true);
    try {
      await createDovShopCollection({ name: newCollectionName, description: newCollectionDesc });
      setNewCollectionName(''); setNewCollectionDesc('');
      setShowCreateCollection(false);
      await loadCollections();
    } catch (err) { setError((err as Error).message); }
    finally { setCreating(false); }
  };

  const handleDeleteCollection = async (id: string) => {
    if (!confirm('Delete this collection?')) return;
    try { await deleteDovShopCollection(id); await loadCollections(); }
    catch (err) { setError((err as Error).message); }
  };

  // Push
  const unsyncedProducts = panelProducts.filter(p => !p.dovshop_product_id);
  const handleToggleProduct = (id: string) => {
    const s = new Set(selectedProducts);
    s.has(id) ? s.delete(id) : s.add(id);
    setSelectedProducts(s);
  };
  const handleSelectAll = () => {
    setSelectedProducts(
      selectedProducts.size === unsyncedProducts.length
        ? new Set()
        : new Set(unsyncedProducts.map(p => p.printify_product_id))
    );
  };
  const handlePushProducts = async () => {
    if (selectedProducts.size === 0) return;
    setPushing(true);
    const progress: Record<string, { status: string; message?: string }> = {};
    for (const pid of Array.from(selectedProducts)) {
      try {
        progress[pid] = { status: 'pushing' };
        setPushProgress({ ...progress });
        await pushProductToDovShop({ printify_product_id: pid });
        progress[pid] = { status: 'success' };
      } catch (err) {
        progress[pid] = { status: 'failed', message: (err as Error).message };
      }
      setPushProgress({ ...progress });
      await new Promise(r => setTimeout(r, 500));
    }
    setPushing(false);
    await loadProducts();
  };
  const completedCount = Object.values(pushProgress).filter(p => p.status !== 'pushing').length;
  const progressPercent = selectedProducts.size > 0 ? (completedCount / selectedProducts.size) * 100 : 0;

  // Strategy
  const handleRunStrategy = async () => {
    setStrategyLoading(true);
    setStrategy(null);
    setError(null);
    setAppliedActions(new Set());
    setStrategyDate(null);
    try {
      const result = await getDovShopAIStrategy();
      setStrategy(result);
      setStrategyDate(new Date().toISOString());
      await loadStrategyHistory();
    } catch (err) { setError((err as Error).message); }
    finally { setStrategyLoading(false); }
  };

  const handleSelectHistoryItem = (item: DovShopStrategyHistoryItem) => {
    setStrategy(item.result);
    setStrategyDate(item.created_at);
    setAppliedActions(new Set());
  };

  // Mockup selector handlers
  const handleExpandMockups = async (printifyId: string) => {
    if (expandedMockups === printifyId) {
      setExpandedMockups(null);
      setProductMockups([]);
      return;
    }
    setExpandedMockups(printifyId);
    setMockupsLoading(true);
    try {
      const data = await getProductMockupsForDovShop(printifyId);
      setProductMockups(data.mockups);
    } catch (err) { setError((err as Error).message); }
    finally { setMockupsLoading(false); }
  };

  const handleToggleDovShopMockup = async (mockupId: number, currentVal: boolean) => {
    try {
      await toggleDovShopMockup(mockupId, !currentVal);
      setProductMockups(prev => prev.map(m => m.id === mockupId ? { ...m, dovshop_included: !currentVal } : m));
    } catch (err) { setError((err as Error).message); }
  };

  const handleSetPrimary = async (mockupId: number) => {
    try {
      await setDovShopPrimary(mockupId);
      setProductMockups(prev => prev.map(m => ({ ...m, dovshop_primary: m.id === mockupId })));
    } catch (err) { setError((err as Error).message); }
  };

  const handleSaveMockupsToDovShop = async (printifyId: string) => {
    setSavingMockups(printifyId);
    try {
      await updateDovShopProductImages(printifyId);
    } catch (err) { setError((err as Error).message); }
    finally { setSavingMockups(null); }
  };

  const handleApplyPattern = async () => {
    setApplyingPattern(true);
    setPatternResult(null);
    try {
      const result = await assignPackPattern(packOffset);
      setPatternResult(result);
    } catch (err) { setError((err as Error).message); }
    finally { setApplyingPattern(false); }
  };

  const handleApplyCollection = async (name: string, description: string, posterIds: number[]) => {
    const key = `coll-${name}`;
    setApplyingAction(key);
    try {
      await applyDovShopCollection({ name, description, poster_ids: posterIds });
      setAppliedActions(prev => new Set(prev).add(key));
      await loadCollections();
    } catch (err) { setError((err as Error).message); }
    finally { setApplyingAction(null); }
  };

  const handleApplyFeature = async (posterId: number) => {
    const key = `feat-${posterId}`;
    setApplyingAction(key);
    try {
      await applyDovShopFeature(posterId, true);
      setAppliedActions(prev => new Set(prev).add(key));
    } catch (err) { setError((err as Error).message); }
    finally { setApplyingAction(null); }
  };

  const handleApplySeo = async (posterId: number, desc: string) => {
    const key = `seo-${posterId}`;
    setApplyingAction(key);
    try {
      await applyDovShopSeo(posterId, desc);
      setAppliedActions(prev => new Set(prev).add(key));
    } catch (err) { setError((err as Error).message); }
    finally { setApplyingAction(null); }
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen"><div className="text-gray-400">Loading DovShop...</div></div>;
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'products', label: 'Products' },
    { key: 'collections', label: 'Collections' },
    { key: 'push', label: 'Push New' },
    { key: 'sync', label: 'Sync All' },
    { key: 'strategy', label: 'AI Strategy' },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Header + Stats */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">DovShop</h1>
          <p className="text-sm text-gray-400 mt-1">AI-managed product catalog at dovshop.org</p>
        </div>
        <div className="flex items-center gap-4">
          {status?.connected ? (
            <div className="flex items-center gap-4 text-sm">
              <span className="text-gray-400">{products.length} products</span>
              <span className="text-gray-400">{collections.length} collections</span>
              <span className="flex items-center gap-1.5 text-green-400">
                <span className="w-2 h-2 rounded-full bg-green-400"></span>
                Connected
              </span>
            </div>
          ) : (
            <span className="flex items-center gap-1.5 text-yellow-400 text-sm">
              <span className="w-2 h-2 rounded-full bg-yellow-400"></span>
              {status?.message || 'Not connected'}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">x</button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-dark-border">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 font-medium transition-colors ${
              tab === t.key ? 'border-b-2 border-accent text-accent -mb-px' : 'text-gray-400 hover:text-gray-200'
            }`}>{t.label}</button>
        ))}
      </div>

      {/* === Products Tab === */}
      {tab === 'products' && (
        <div className="space-y-4">
          {/* Rotate Primary Mockup */}
          <div className="bg-dark-card border border-dark-border rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-200 mb-1">Rotate Primary Mockup</h3>
            <p className="text-xs text-gray-500 mb-3">Cycle through mockups so each product has a different hero image on the storefront</p>
            <div className="flex items-end gap-3 flex-wrap">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Start offset</label>
                <input type="number" min={0} max={20} value={packOffset} onChange={e => setPackOffset(Number(e.target.value))}
                  className="w-16 px-2 py-1.5 bg-dark-bg border border-dark-border rounded text-sm text-gray-200 focus:outline-none focus:border-accent" />
              </div>
              <button onClick={handleApplyPattern} disabled={applyingPattern}
                className="px-4 py-1.5 bg-accent/15 hover:bg-accent/25 border border-accent/30 rounded text-accent text-sm font-medium disabled:opacity-50">
                {applyingPattern ? 'Applying...' : 'Rotate Primaries'}
              </button>
              {patternResult && (
                <span className="text-xs text-gray-400">
                  {patternResult.updated}/{patternResult.total} products updated
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-200">Products on DovShop ({products.length})</h2>
            <button onClick={loadProducts} disabled={productsLoading}
              className="px-4 py-2 bg-dark-card hover:bg-dark-hover border border-dark-border rounded-lg text-gray-300 text-sm font-medium transition-colors disabled:opacity-50">
              {productsLoading ? 'Loading...' : 'Refresh'}
            </button>
          </div>

          {productsLoading ? (
            <div className="text-center py-12 text-gray-400">Loading products...</div>
          ) : products.length === 0 ? (
            <div className="text-center py-12 text-gray-400">No products on DovShop yet.</div>
          ) : (
            <div className="space-y-2">
              {products.map(p => (
                <div key={p.id} className="bg-dark-card border border-dark-border rounded-lg overflow-hidden">
                  <div className="flex items-center gap-4 p-3 hover:bg-dark-hover transition-colors">
                    <div className="w-12 h-12 rounded bg-dark-bg overflow-hidden flex-shrink-0">
                      {p.image_url && <img src={p.image_url} alt={p.title} className="w-full h-full object-cover" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium text-gray-200 truncate">{p.title}</h3>
                        {p.featured && <span className="text-xs text-yellow-400 bg-yellow-500/10 px-1.5 py-0.5 rounded">featured</span>}
                      </div>
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        {p.categories?.map(c => (
                          <span key={c} className="text-xs text-blue-400/80 bg-blue-500/10 px-1.5 py-0.5 rounded">{c}</span>
                        ))}
                        {p.collection && (
                          <span className="text-xs text-purple-400/80 bg-purple-500/10 px-1.5 py-0.5 rounded">{p.collection.name}</span>
                        )}
                        {p.price > 0 && <span className="text-xs text-gray-500">${p.price.toFixed(0)}+</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {p.printify_id && (
                        <button onClick={() => handleExpandMockups(p.printify_id!)}
                          className={`px-2 py-1 text-xs border rounded transition-colors ${expandedMockups === p.printify_id ? 'text-accent bg-accent/10 border-accent/30' : 'text-gray-400 border-dark-border hover:text-gray-200'}`}>
                          Mockups
                        </button>
                      )}
                      {p.slug && (
                        <a href={`https://dovshop.org/poster/${p.slug}`} target="_blank" rel="noopener noreferrer"
                          className="px-2 py-1 text-xs text-accent hover:text-accent/80 border border-accent/30 rounded">Site</a>
                      )}
                      {p.etsy_url && (
                        <a href={p.etsy_url} target="_blank" rel="noopener noreferrer"
                          className="px-2 py-1 text-xs text-orange-400 hover:text-orange-300 border border-orange-500/30 rounded">Etsy</a>
                      )}
                      <button onClick={() => handleDeleteProduct(p.id)} disabled={deletingProduct === p.id}
                        className="px-2 py-1 text-xs text-red-400 hover:text-red-300 border border-red-500/30 rounded disabled:opacity-50">
                        {deletingProduct === p.id ? '...' : 'Del'}
                      </button>
                    </div>
                  </div>

                  {/* Mockup selector panel */}
                  {expandedMockups === p.printify_id && (
                    <div className="border-t border-dark-border p-3 bg-dark-bg/50">
                      {mockupsLoading ? (
                        <div className="text-sm text-gray-400 py-2">Loading mockups...</div>
                      ) : productMockups.length === 0 ? (
                        <div className="text-sm text-gray-500 py-2">No mockups for this product.</div>
                      ) : (
                        <>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-gray-400">
                              {productMockups.filter(m => m.dovshop_included).length}/{productMockups.length} mockups selected for DovShop
                            </span>
                            <button onClick={() => handleSaveMockupsToDovShop(p.printify_id!)}
                              disabled={savingMockups === p.printify_id}
                              className="px-3 py-1 bg-accent/15 hover:bg-accent/25 border border-accent/30 rounded text-accent text-xs font-medium disabled:opacity-50">
                              {savingMockups === p.printify_id ? 'Saving...' : 'Save to DovShop'}
                            </button>
                          </div>
                          <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
                            {productMockups.map(m => (
                              <div key={m.id} className={`relative aspect-[4/5] rounded overflow-hidden border-2 transition-colors ${m.dovshop_primary ? 'border-yellow-400' : m.dovshop_included ? 'border-green-500' : 'border-dark-border opacity-50'}`}>
                                <button onClick={() => handleToggleDovShopMockup(m.id, m.dovshop_included)}
                                  className="w-full h-full">
                                  <img src={m.thumbnail_url} alt={`Mockup ${m.id}`} className="w-full h-full object-cover" />
                                  {!m.dovshop_included && <div className="absolute inset-0 bg-black/30" />}
                                </button>
                                {m.dovshop_included && (
                                  <div className="absolute top-1 right-1 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
                                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                                  </div>
                                )}
                                {m.dovshop_included && (
                                  <button onClick={() => handleSetPrimary(m.id)}
                                    title={m.dovshop_primary ? 'Primary image' : 'Set as primary'}
                                    className={`absolute top-1 left-1 w-5 h-5 rounded-full flex items-center justify-center transition-colors ${m.dovshop_primary ? 'bg-yellow-400 text-black' : 'bg-black/50 text-gray-300 hover:bg-yellow-400/80 hover:text-black'}`}>
                                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* === Collections Tab === */}
      {tab === 'collections' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-200">Collections ({collections.length})</h2>
            <button onClick={() => setShowCreateCollection(!showCreateCollection)}
              className="px-4 py-2 bg-accent/15 hover:bg-accent/25 border border-accent/30 rounded-lg text-accent text-sm font-medium transition-colors">
              {showCreateCollection ? 'Cancel' : '+ New'}
            </button>
          </div>

          {showCreateCollection && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <input type="text" value={newCollectionName} onChange={e => setNewCollectionName(e.target.value)}
                placeholder="Collection name" className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-200 text-sm focus:outline-none focus:border-accent" />
              <textarea value={newCollectionDesc} onChange={e => setNewCollectionDesc(e.target.value)}
                placeholder="Description (optional)" rows={2}
                className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-200 text-sm focus:outline-none focus:border-accent resize-none" />
              <button onClick={handleCreateCollection} disabled={creating || !newCollectionName.trim()}
                className="px-4 py-2 bg-accent hover:bg-accent/80 rounded-lg text-white text-sm font-medium disabled:opacity-50">
                {creating ? 'Creating...' : 'Create'}
              </button>
            </div>
          )}

          {collectionsLoading ? (
            <div className="text-center py-12 text-gray-400">Loading...</div>
          ) : collections.length === 0 ? (
            <div className="text-center py-12 text-gray-400">No collections yet.</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {collections.map(c => (
                <div key={c.id} className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
                  {c.cover_url && (
                    <div className="aspect-square rounded-lg overflow-hidden bg-dark-bg">
                      <img src={c.cover_url} alt={c.name} className="w-full h-full object-cover" />
                    </div>
                  )}
                  <div>
                    <h3 className="font-medium text-gray-100 text-sm">{c.name}</h3>
                    {c.description && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{c.description}</p>}
                    <p className="text-xs text-gray-500 mt-2">{c.product_count || 0} products</p>
                  </div>
                  <button onClick={() => handleDeleteCollection(c.id)}
                    className="w-full px-3 py-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded text-red-400 text-xs font-medium transition-colors">
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* === Push Tab === */}
      {tab === 'push' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-200">Push to DovShop</h2>
            <div className="flex gap-2">
              <button onClick={handleSelectAll} disabled={unsyncedProducts.length === 0}
                className="px-4 py-2 bg-dark-card hover:bg-dark-hover border border-dark-border rounded-lg text-gray-300 text-sm font-medium disabled:opacity-50">
                {selectedProducts.size === unsyncedProducts.length && unsyncedProducts.length > 0 ? 'Deselect All' : `Select All (${unsyncedProducts.length})`}
              </button>
              <button onClick={handlePushProducts} disabled={pushing || selectedProducts.size === 0}
                className="px-4 py-2 bg-accent hover:bg-accent/80 rounded-lg text-white text-sm font-medium disabled:opacity-50">
                {pushing ? `Pushing ${completedCount}/${selectedProducts.size}` : `Push (${selectedProducts.size})`}
              </button>
            </div>
          </div>

          {pushing && (
            <div className="bg-dark-card border border-dark-border rounded-lg p-4">
              <div className="w-full h-2 bg-dark-bg rounded-full overflow-hidden">
                <div className="h-full bg-accent rounded-full transition-all duration-300" style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
          )}

          {panelProductsLoading ? (
            <div className="text-center py-12 text-gray-400">Loading...</div>
          ) : panelProducts.length === 0 ? (
            <div className="text-center py-12 text-gray-400">No products yet.</div>
          ) : (
            <div className="space-y-2">
              {panelProducts.map(product => {
                const progress = pushProgress[product.printify_product_id];
                const isSelected = selectedProducts.has(product.printify_product_id);
                const synced = !!product.dovshop_product_id;
                return (
                  <div key={product.printify_product_id}
                    className={`flex items-center gap-4 p-3 bg-dark-card border rounded-lg hover:bg-dark-hover transition-colors ${synced ? 'border-green-500/30' : 'border-dark-border'}`}>
                    <input type="checkbox" checked={isSelected} onChange={() => handleToggleProduct(product.printify_product_id)}
                      disabled={pushing || synced} className="w-4 h-4 rounded border-gray-600 bg-dark-bg text-accent" />
                    {product.image_url && (
                      <div className="w-12 h-12 rounded bg-dark-bg overflow-hidden flex-shrink-0">
                        <img src={product.image_url} alt={product.title} className="w-full h-full object-cover" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-gray-200 truncate">{product.title}</h3>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">{product.status}</span>
                        {synced && <span className="text-xs text-green-400/80 bg-green-500/10 px-1.5 py-0.5 rounded">on DovShop</span>}
                      </div>
                    </div>
                    {progress && (
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {progress.status === 'pushing' && <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />}
                        {progress.status === 'success' && <span className="text-green-400 text-sm">Done</span>}
                        {progress.status === 'failed' && <span className="text-red-400 text-xs" title={progress.message}>Failed</span>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* === Sync Tab === */}
      {tab === 'sync' && (
        <div className="space-y-4">
          <div className="bg-dark-card border border-dark-border rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-200 mb-2">Sync All Published Products</h2>
            <p className="text-sm text-gray-400 mb-4">
              Bulk sync all Etsy-published products to DovShop with auto-categorization.
            </p>
            <button onClick={async () => {
              setSyncing(true); setSyncResult(null); setError(null);
              try { setSyncResult(await syncAllToDovShop()); }
              catch (err) { setError(err instanceof Error ? err.message : 'Sync failed'); }
              finally { setSyncing(false); }
            }} disabled={syncing || !status?.connected}
              className="px-6 py-3 bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover transition-colors disabled:opacity-50">
              {syncing ? 'Syncing...' : 'Sync Now'}
            </button>

            {syncing && (
              <div className="mt-4">
                <div className="w-full h-2 bg-dark-bg rounded-full overflow-hidden">
                  <div className="h-full bg-accent rounded-full animate-pulse" style={{ width: '100%' }} />
                </div>
              </div>
            )}

            {syncResult && (
              <div className="mt-4 bg-dark-bg rounded-lg p-4 space-y-2">
                <div className="flex gap-6 text-sm">
                  <span className="text-gray-400">Total: <strong className="text-gray-200">{syncResult.total}</strong></span>
                  <span className="text-green-400">Created: <strong>{syncResult.created}</strong></span>
                  <span className="text-blue-400">Updated: <strong>{syncResult.updated}</strong></span>
                  {syncResult.errors.length > 0 && <span className="text-red-400">Errors: <strong>{syncResult.errors.length}</strong></span>}
                </div>
                {syncResult.errors.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {syncResult.errors.map((e, i) => <p key={i} className="text-xs text-red-400/70">{e.printify_id}: {e.error}</p>)}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* === AI Strategy Tab === */}
      {tab === 'strategy' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-medium text-gray-200">AI Strategy</h2>
              <p className="text-sm text-gray-400">Claude analyzes your DovShop catalog and suggests SEO improvements</p>
            </div>
            <button onClick={handleRunStrategy} disabled={strategyLoading || !status?.connected}
              className="px-6 py-3 bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover transition-colors disabled:opacity-50">
              {strategyLoading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-dark-bg border-t-transparent rounded-full animate-spin"></span>
                  Analyzing...
                </span>
              ) : 'Analyze Catalog'}
            </button>
          </div>

          {strategy && (
            <div className="space-y-6">
              {/* Summary */}
              <div className="bg-accent/5 border border-accent/20 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-accent">Summary</h3>
                  {strategyDate && (
                    <span className="text-xs text-gray-500">
                      {new Date(strategyDate).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-300">{strategy.summary}</p>
              </div>

              {/* New Collections */}
              {strategy.new_collections?.length > 0 && (
                <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
                  <h3 className="text-sm font-medium text-gray-200">Suggested Collections</h3>
                  {strategy.new_collections.map((c, i) => (
                    <div key={i} className="flex items-start justify-between gap-4 p-3 bg-dark-bg rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-200">{c.name}</p>
                        <p className="text-xs text-gray-400 mt-1">{c.description}</p>
                        <p className="text-xs text-gray-500 mt-1">{c.poster_ids?.length || 0} posters to assign</p>
                      </div>
                      {appliedActions.has(`coll-${c.name}`) ? (
                        <span className="px-3 py-1.5 text-green-400 text-xs font-medium">Created</span>
                      ) : (
                        <button onClick={() => handleApplyCollection(c.name, c.description, c.poster_ids)}
                          disabled={applyingAction === `coll-${c.name}`}
                          className="px-3 py-1.5 bg-accent/15 hover:bg-accent/25 border border-accent/30 rounded text-accent text-xs font-medium disabled:opacity-50">
                          {applyingAction === `coll-${c.name}` ? 'Creating...' : 'Create'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Feature Recommendations */}
              {strategy.feature_recommendations?.length > 0 && (
                <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
                  <h3 className="text-sm font-medium text-gray-200">Feature Recommendations</h3>
                  {strategy.feature_recommendations.map((r, i) => (
                    <div key={i} className="flex items-center justify-between gap-4 p-3 bg-dark-bg rounded-lg">
                      <div className="flex-1">
                        <p className="text-sm text-gray-200">{r.title}</p>
                        <p className="text-xs text-gray-400 mt-1">{r.reason}</p>
                      </div>
                      {appliedActions.has(`feat-${r.id}`) ? (
                        <span className="px-3 py-1.5 text-green-400 text-xs font-medium">Featured</span>
                      ) : (
                        <button onClick={() => handleApplyFeature(r.id)}
                          disabled={applyingAction === `feat-${r.id}`}
                          className="px-3 py-1.5 bg-yellow-500/15 hover:bg-yellow-500/25 border border-yellow-500/30 rounded text-yellow-400 text-xs font-medium disabled:opacity-50">
                          {applyingAction === `feat-${r.id}` ? '...' : 'Feature'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Category Gaps */}
              {strategy.category_gaps?.length > 0 && (
                <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
                  <h3 className="text-sm font-medium text-gray-200">Category Gaps</h3>
                  {strategy.category_gaps.map((g, i) => (
                    <div key={i} className="p-3 bg-dark-bg rounded-lg">
                      <span className="text-xs text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded mr-2">{g.slug}</span>
                      <span className="text-sm text-gray-300">{g.suggestion}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* SEO Improvements */}
              {strategy.seo_improvements?.length > 0 && (
                <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
                  <h3 className="text-sm font-medium text-gray-200">SEO Improvements</h3>
                  {strategy.seo_improvements.map((s, i) => (
                    <div key={i} className="p-3 bg-dark-bg rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-200">{s.title}</p>
                        {appliedActions.has(`seo-${s.id}`) ? (
                          <span className="px-3 py-1.5 text-green-400 text-xs font-medium">Applied</span>
                        ) : (
                          <button onClick={() => handleApplySeo(s.id, s.suggested_desc)}
                            disabled={applyingAction === `seo-${s.id}`}
                            className="px-3 py-1.5 bg-green-500/15 hover:bg-green-500/25 border border-green-500/30 rounded text-green-400 text-xs font-medium disabled:opacity-50">
                            {applyingAction === `seo-${s.id}` ? '...' : 'Apply'}
                          </button>
                        )}
                      </div>
                      <p className="text-xs text-gray-400">{s.suggested_desc}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* History selector */}
          {strategyHistory.length > 1 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-gray-500">History:</span>
              {strategyHistory.map(h => {
                const d = new Date(h.created_at);
                const label = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                const isActive = strategyDate === h.created_at;
                return (
                  <button key={h.id} onClick={() => handleSelectHistoryItem(h)}
                    className={`px-2 py-1 rounded text-xs transition-colors ${isActive ? 'bg-accent/20 text-accent border border-accent/30' : 'bg-dark-card text-gray-400 border border-dark-border hover:text-gray-200'}`}>
                    {label} ({h.product_count}p)
                  </button>
                );
              })}
            </div>
          )}

          {!strategy && !strategyLoading && (
            <div className="text-center py-16 text-gray-500">
              <p className="text-lg mb-2">Click "Analyze Catalog" to get AI recommendations</p>
              <p className="text-sm">Claude will analyze your products, collections, and categories to suggest improvements</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
