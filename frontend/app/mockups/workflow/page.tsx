'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { getApiUrl, reapplyApprovedMockups, getReapplyStatus } from '@/lib/api';

interface WorkflowPoster {
  id: number;
  url: string;
  generation_id: string;
  prompt: string | null;
  created_at: string;
  mockup_url: string | null;
  mockup_status: string;
}

interface DeclinedPoster {
  id: number;
  url: string;
  generation_id: string;
  prompt: string | null;
  created_at: string;
  mockup_status: string;
  product_id: number | null;
}

interface MockupPreview {
  template_id: number;
  preview_url: string;
  is_included: boolean;
}

interface ActiveTemplateInfo {
  id: number;
  name: string;
  scene_url: string;
}

type Tab = 'pending' | 'declined';

export default function MockupWorkflowPage() {
  const [tab, setTab] = useState<Tab>('pending');
  const [posters, setPosters] = useState<WorkflowPoster[]>([]);
  const [declinedPosters, setDeclinedPosters] = useState<DeclinedPoster[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTemplates, setActiveTemplates] = useState<ActiveTemplateInfo[]>([]);
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  // Multi-mockup previews: posterId -> array of previews
  const [mockupPreviews, setMockupPreviews] = useState<Record<number, MockupPreview[]>>({});
  const [loadingPreviews, setLoadingPreviews] = useState<Set<number>>(new Set());
  const [batchProgress, setBatchProgress] = useState<{ total: number; done: number } | null>(null);
  // Which mockup is shown as main preview per poster
  const [selectedPreviewIdx, setSelectedPreviewIdx] = useState<Record<number, number>>({});
  // Excluded template IDs per poster (toggled off)
  const [excludedTemplates, setExcludedTemplates] = useState<Record<number, Set<number>>>({});
  // Packs
  const [packs, setPacks] = useState<{ id: number; name: string; template_count: number }[]>([]);
  const [globalPackId, setGlobalPackId] = useState<number | null>(null);
  const [posterPackId, setPosterPackId] = useState<Record<number, number | null>>({});
  const [reapplying, setReapplying] = useState(false);
  const [reapplyResult, setReapplyResult] = useState<{ total: number; uploaded: number } | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Load active templates
      const activeRes = await fetch(`${getApiUrl()}/mockups/settings/active-templates`);
      if (!activeRes.ok) throw new Error('Failed to load active templates');
      const activeData = await activeRes.json();
      setActiveTemplates(activeData.active_templates || []);

      // Load packs + default pack
      try {
        const [packsRes, defaultPackRes] = await Promise.all([
          fetch(`${getApiUrl()}/mockups/packs`),
          fetch(`${getApiUrl()}/mockups/settings/default-pack`),
        ]);
        if (packsRes.ok) {
          const packsData = await packsRes.json();
          setPacks(packsData.packs || []);
        }
        if (defaultPackRes.ok) {
          const defaultData = await defaultPackRes.json();
          if (defaultData.default_pack_id) {
            setGlobalPackId(defaultData.default_pack_id);
          }
        }
      } catch {}

      if (!activeData.active_templates?.length && packs.length === 0) {
        setError('No active mockup templates or packs. Please configure templates first.');
        setLoading(false);
        return;
      }

      // Load pending posters + declined in parallel
      const [postersRes, declinedRes] = await Promise.all([
        fetch(`${getApiUrl()}/mockups/workflow/posters?status=pending`),
        fetch(`${getApiUrl()}/mockups/workflow/declined`),
      ]);
      if (!postersRes.ok) throw new Error('Failed to load posters');
      const postersData = await postersRes.json();
      const loadedPosters: WorkflowPoster[] = postersData.posters || [];
      setPosters(loadedPosters);

      if (declinedRes.ok) {
        const declinedData = await declinedRes.json();
        setDeclinedPosters(declinedData.posters || []);
      }

      // Auto-compose all mockups for each poster
      if (loadedPosters.length > 0) {
        loadedPosters.forEach((poster: WorkflowPoster) => {
          composeAllPreviews(poster.id, poster.url);
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const composeAllPreviews = async (posterId: number, posterUrl: string, packId?: number | null) => {
    setLoadingPreviews((prev) => new Set(prev).add(posterId));
    try {
      const effectivePackId = packId ?? posterPackId[posterId] ?? globalPackId;
      const endpoint = effectivePackId
        ? `${getApiUrl()}/mockups/compose-by-pack`
        : `${getApiUrl()}/mockups/compose-all`;
      const bodyObj = effectivePackId
        ? { poster_url: posterUrl, pack_id: effectivePackId, fill_mode: 'fill' }
        : { poster_url: posterUrl, fill_mode: 'fill' };
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyObj),
      });
      if (!res.ok) throw new Error('Failed to compose mockups');
      const data = await res.json();
      const previews: MockupPreview[] = (data.previews || []).map((p: { template_id: number; preview_url: string }) => ({
        ...p,
        is_included: true,
      }));
      setMockupPreviews((prev) => ({ ...prev, [posterId]: previews }));
    } catch (err) {
      console.error(`Failed to compose previews for poster ${posterId}:`, err);
    } finally {
      setLoadingPreviews((prev) => {
        const next = new Set(prev);
        next.delete(posterId);
        return next;
      });
    }
  };

  const toggleMockupInclusion = (posterId: number, templateId: number) => {
    setExcludedTemplates((prev) => {
      const current = prev[posterId] || new Set<number>();
      const next = new Set(current);
      if (next.has(templateId)) {
        next.delete(templateId);
      } else {
        next.add(templateId);
      }
      return { ...prev, [posterId]: next };
    });
  };

  const getIncludedCount = (posterId: number) => {
    const previews = mockupPreviews[posterId] || [];
    const excluded = excludedTemplates[posterId] || new Set<number>();
    const includedMockups = previews.filter((p) => !excluded.has(p.template_id)).length;
    return includedMockups + 1; // +1 for original poster
  };

  const getExcludedIds = (posterId: number): number[] => {
    const excluded = excludedTemplates[posterId];
    return excluded ? Array.from(excluded) : [];
  };

  const handleApprove = async (posterId: number) => {
    setProcessingIds((prev) => new Set(prev).add(posterId));
    setError(null);
    try {
      const excluded = getExcludedIds(posterId);
      const effectivePackId = posterPackId[posterId] ?? globalPackId;
      const approveBody: Record<string, unknown> = { excluded_template_ids: excluded };
      if (effectivePackId) approveBody.pack_id = effectivePackId;
      const res = await fetch(`${getApiUrl()}/mockups/workflow/approve/${posterId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(approveBody),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Approval failed' }));
        throw new Error(errData.detail || 'Approval failed');
      }
      const result = await res.json();
      const etsyResult = result.etsy_upload;
      if (etsyResult?.success) {
        setSuccessMsg(`Approved & uploaded ${etsyResult.images_uploaded} images to Etsy (listing ${etsyResult.listing_id})`);
      } else if (etsyResult?.reason === 'scheduled') {
        setSuccessMsg(`Approved ${result.mockups_composed} mockups! Will auto-upload when published.`);
      } else if (etsyResult?.reason === 'no_product') {
        setSuccessMsg(`Approved ${result.mockups_composed} mockups! No product linked.`);
      } else if (etsyResult) {
        setSuccessMsg(`Approved, but Etsy upload failed: ${etsyResult.error || etsyResult.reason || 'unknown'}`);
      } else {
        setSuccessMsg('Poster approved!');
      }
      setTimeout(() => setSuccessMsg(null), 5000);
      setPosters((prev) => prev.filter((p) => p.id !== posterId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval failed');
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(posterId);
        return next;
      });
    }
  };

  const handleDecline = async (posterId: number) => {
    setProcessingIds((prev) => new Set(prev).add(posterId));
    setError(null);
    try {
      const res = await fetch(`${getApiUrl()}/mockups/workflow/decline/${posterId}`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Decline failed' }));
        throw new Error(errData.detail || 'Decline failed');
      }
      setSuccessMsg('Poster marked as needs attention.');
      setTimeout(() => setSuccessMsg(null), 3000);
      setPosters((prev) => prev.filter((p) => p.id !== posterId));
      const declined = posters.find((p) => p.id === posterId);
      if (declined) {
        setDeclinedPosters((prev) => [{ ...declined, mockup_status: 'needs_attention', product_id: null }, ...prev]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Decline failed');
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(posterId);
        return next;
      });
    }
  };

  const handleRetry = async (posterId: number) => {
    setProcessingIds((prev) => new Set(prev).add(posterId));
    setError(null);
    try {
      const res = await fetch(`${getApiUrl()}/mockups/workflow/retry/${posterId}`, {
        method: 'POST',
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Retry failed' }));
        throw new Error(errData.detail || 'Retry failed');
      }
      setSuccessMsg('Poster moved back to pending.');
      setTimeout(() => setSuccessMsg(null), 3000);
      const retried = declinedPosters.find((p) => p.id === posterId);
      setDeclinedPosters((prev) => prev.filter((p) => p.id !== posterId));
      if (retried) {
        const asPending: WorkflowPoster = {
          ...retried,
          mockup_url: null,
          mockup_status: 'pending',
        };
        setPosters((prev) => [asPending, ...prev]);
        composeAllPreviews(retried.id, retried.url);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retry failed');
    } finally {
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(posterId);
        return next;
      });
    }
  };

  const handleRetryAll = async () => {
    setError(null);
    try {
      const res = await fetch(`${getApiUrl()}/mockups/workflow/retry-all-declined`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Retry all failed');
      const result = await res.json();
      setSuccessMsg(`${result.retried} posters moved back to pending.`);
      setTimeout(() => setSuccessMsg(null), 5000);
      await loadData();
      setTab('pending');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retry all failed');
    }
  };

  const handleApproveAll = async () => {
    const readyIds = posters
      .filter((p) => mockupPreviews[p.id]?.length && !loadingPreviews.has(p.id))
      .map((p) => p.id);
    if (readyIds.length === 0) return;

    setBatchProgress({ total: readyIds.length, done: 0 });
    setError(null);
    let approved = 0;
    let etsyOk = 0;
    let errors = 0;

    for (const id of readyIds) {
      setProcessingIds((prev) => new Set(prev).add(id));
      try {
        const excluded = getExcludedIds(id);
        const effectivePackId = posterPackId[id] ?? globalPackId;
        const approveBody: Record<string, unknown> = { excluded_template_ids: excluded };
        if (effectivePackId) approveBody.pack_id = effectivePackId;
        const res = await fetch(`${getApiUrl()}/mockups/workflow/approve/${id}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(approveBody),
        });
        if (res.ok) {
          const result = await res.json();
          approved++;
          if (result.etsy_upload?.success) etsyOk++;
          setPosters((prev) => prev.filter((p) => p.id !== id));
        } else {
          errors++;
        }
      } catch {
        errors++;
      }
      setProcessingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      setBatchProgress({ total: readyIds.length, done: approved + errors });
    }

    setBatchProgress(null);
    setSuccessMsg(`Batch done: ${approved} approved, ${etsyOk} uploaded to Etsy${errors > 0 ? `, ${errors} failed` : ''}`);
    setTimeout(() => setSuccessMsg(null), 8000);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Mockup Workflow</h1>
          <p className="text-sm text-gray-500 mt-1">
            Review and approve posters — each gets {activeTemplates.length} mockup{activeTemplates.length !== 1 ? 's' : ''} + original ({activeTemplates.length + 1} images)
          </p>
        </div>
        <div className="flex gap-2">
          {tab === 'pending' && posters.length > 0 && (
            <button
              onClick={handleApproveAll}
              disabled={!!batchProgress || posters.every((p) => loadingPreviews.has(p.id))}
              className="px-4 py-2 bg-green-500/10 text-green-400 rounded-lg text-sm font-medium hover:bg-green-500/20 transition-colors disabled:opacity-50"
            >
              {batchProgress
                ? `Approving ${batchProgress.done}/${batchProgress.total}...`
                : `Approve All (${posters.filter((p) => mockupPreviews[p.id]?.length).length})`}
            </button>
          )}
          {tab === 'declined' && declinedPosters.length > 0 && (
            <button
              onClick={handleRetryAll}
              className="px-4 py-2 bg-yellow-500/10 text-yellow-400 rounded-lg text-sm font-medium hover:bg-yellow-500/20 transition-colors"
            >
              Retry All ({declinedPosters.length})
            </button>
          )}
          <Link
            href="/mockups/generate"
            className="px-4 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors"
          >
            Templates
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-dark-card border border-dark-border rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab('pending')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            tab === 'pending'
              ? 'bg-accent/15 text-accent'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Pending {posters.length > 0 && `(${posters.length})`}
        </button>
        <button
          onClick={() => setTab('declined')}
          className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
            tab === 'declined'
              ? 'bg-accent/15 text-accent'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          Declined {declinedPosters.length > 0 && `(${declinedPosters.length})`}
        </button>
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
      {batchProgress && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-300">Batch approving...</span>
            <span className="text-accent">{batchProgress.done}/{batchProgress.total}</span>
          </div>
          <div className="w-full bg-dark-border rounded-full h-2">
            <div
              className="bg-accent h-2 rounded-full transition-all"
              style={{ width: `${(batchProgress.done / batchProgress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Active templates summary */}
      {activeTemplates.length > 0 && (
        <div className="flex gap-2 items-center overflow-x-auto pb-1">
          <span className="text-xs text-gray-500 flex-shrink-0">Active templates:</span>
          {activeTemplates.map((t) => (
            <div key={t.id} className="flex-shrink-0 flex items-center gap-1.5 px-2 py-1 bg-dark-card border border-dark-border rounded text-xs text-gray-300">
              <img src={t.scene_url} alt="" className="w-5 h-6 object-cover rounded" />
              {t.name}
            </div>
          ))}
        </div>
      )}

      {/* Pack selector */}
      {packs.length > 0 && (
        <div className="flex gap-2 items-center overflow-x-auto pb-1">
          <span className="text-xs text-gray-500 flex-shrink-0">Pack:</span>
          <button
            onClick={() => {
              setGlobalPackId(null);
              // Re-compose all posters with active templates
              posters.forEach((p) => composeAllPreviews(p.id, p.url, null));
            }}
            className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              globalPackId === null
                ? 'bg-accent text-dark-bg'
                : 'bg-dark-card border border-dark-border text-gray-400 hover:text-gray-200'
            }`}
          >
            Active Templates
          </button>
          {packs.map((pack) => (
            <div key={pack.id} className="flex-shrink-0 flex items-center gap-0.5">
              <button
                onClick={() => {
                  setGlobalPackId(pack.id);
                  posters.forEach((p) => composeAllPreviews(p.id, p.url, pack.id));
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  globalPackId === pack.id
                    ? 'bg-accent text-dark-bg'
                    : 'bg-dark-card border border-dark-border text-gray-400 hover:text-gray-200'
                }`}
              >
                {pack.name} ({pack.template_count})
              </button>
              {globalPackId === pack.id && (
                <button
                  onClick={async () => {
                    try {
                      await fetch(`${getApiUrl()}/mockups/settings/default-pack/${pack.id}`, { method: 'POST' });
                      setSuccessMsg(`"${pack.name}" set as default pack for new products`);
                      setTimeout(() => setSuccessMsg(null), 4000);
                    } catch {}
                  }}
                  className="px-1.5 py-1 text-[10px] text-accent hover:text-accent-hover transition-colors"
                  title="Set as default for all new products"
                >
                  Set Default
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pending tab */}
      {tab === 'pending' && (
        <>
          {loading ? (
            <div className="text-center py-12 text-gray-500">Loading posters...</div>
          ) : posters.length === 0 ? (
            <div className="bg-dark-card border border-dark-border rounded-lg p-8 text-center space-y-4">
              <p className="text-gray-400">No pending posters</p>
              <p className="text-xs text-gray-600">
                All posters have been reviewed. New generations will appear here automatically.
              </p>

              {/* Reapply pack to all approved products */}
              <div className="border-t border-dark-border pt-4 space-y-3">
                <p className="text-sm text-gray-300 font-medium">Reapply mockups to all approved products</p>
                <p className="text-xs text-gray-500">
                  Re-compose all mockups with the selected pack and upload to Etsy.
                  This replaces existing mockup images on all listings.
                </p>
                {globalPackId ? (
                  <button
                    onClick={async () => {
                      setReapplying(true);
                      setReapplyResult(null);
                      setError(null);
                      try {
                        const result = await reapplyApprovedMockups(globalPackId);
                        if (!result.started) {
                          setError(result.message || 'Could not start');
                          setReapplying(false);
                          return;
                        }
                        // Poll for progress
                        const poll = setInterval(async () => {
                          try {
                            const status = await getReapplyStatus();
                            setReapplyResult({ total: status.total, uploaded: status.ok });
                            if (!status.running) {
                              clearInterval(poll);
                              setReapplying(false);
                              setSuccessMsg(`Done: ${status.ok}/${status.total} products updated`);
                              setTimeout(() => setSuccessMsg(null), 8000);
                            }
                          } catch {
                            clearInterval(poll);
                            setReapplying(false);
                          }
                        }, 3000);
                      } catch (err) {
                        setError(err instanceof Error ? err.message : 'Reapply failed');
                        setReapplying(false);
                      }
                    }}
                    disabled={reapplying}
                    className="px-6 py-2.5 bg-accent text-dark-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
                  >
                    {reapplying ? 'Reapplying...' : `Reapply Pack "${packs.find(p => p.id === globalPackId)?.name}" to All`}
                  </button>
                ) : (
                  <p className="text-xs text-yellow-500">Select a pack above first</p>
                )}
                {reapplying && reapplyResult && (
                  <div className="space-y-1">
                    <div className="w-full bg-dark-border rounded-full h-2">
                      <div
                        className="bg-accent h-2 rounded-full transition-all"
                        style={{ width: `${reapplyResult.total > 0 ? (reapplyResult.uploaded / reapplyResult.total) * 100 : 0}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-400">
                      {reapplyResult.uploaded}/{reapplyResult.total} products processed...
                    </p>
                  </div>
                )}
                {!reapplying && reapplyResult && (
                  <p className="text-sm text-green-400">
                    Done: {reapplyResult.uploaded}/{reapplyResult.total} products updated
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-gray-400">
                {posters.length} poster{posters.length !== 1 ? 's' : ''} pending review
              </p>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {posters.map((poster) => {
                  const isProcessing = processingIds.has(poster.id);
                  const isLoadingPreview = loadingPreviews.has(poster.id);
                  const previews = mockupPreviews[poster.id] || [];
                  const excluded = excludedTemplates[poster.id] || new Set<number>();
                  const selIdx = selectedPreviewIdx[poster.id] ?? -1; // -1 = original
                  const mainSrc = selIdx >= 0 && previews[selIdx]
                    ? previews[selIdx].preview_url
                    : (previews.length > 0 ? previews[0].preview_url : poster.url);
                  const includedCount = getIncludedCount(poster.id);

                  return (
                    <div
                      key={poster.id}
                      className="bg-dark-card border border-dark-border rounded-lg overflow-hidden"
                    >
                      {/* Main preview */}
                      <div className="relative">
                        {isLoadingPreview ? (
                          <div className="w-full aspect-[4/5] bg-dark-bg flex items-center justify-center">
                            <div className="text-center space-y-2">
                              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto"></div>
                              <p className="text-xs text-gray-500">Composing {activeTemplates.length} mockups...</p>
                            </div>
                          </div>
                        ) : (
                          <img
                            src={mainSrc}
                            alt="Preview"
                            className="w-full object-contain bg-dark-bg"
                          />
                        )}
                        {/* Image count badge */}
                        {previews.length > 0 && (
                          <span className="absolute top-2 right-2 bg-accent/80 text-dark-bg px-2 py-0.5 rounded text-xs font-medium">
                            {includedCount} images
                          </span>
                        )}
                        {isProcessing && (
                          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                            <div className="text-white text-sm">Processing...</div>
                          </div>
                        )}
                      </div>

                      {/* Thumbnail strip */}
                      {previews.length > 0 && (
                        <div className="flex gap-1 overflow-x-auto p-2 bg-dark-bg/50">
                          {/* Original poster thumbnail */}
                          <div
                            onClick={() => setSelectedPreviewIdx((prev) => ({ ...prev, [poster.id]: -1 }))}
                            className={`relative flex-shrink-0 w-12 h-15 cursor-pointer rounded border-2 transition-colors ${
                              selIdx === -1 ? 'border-green-500' : 'border-dark-border'
                            }`}
                          >
                            <img src={poster.url} alt="Original" className="w-12 h-15 object-cover rounded" />
                            <span className="absolute bottom-0 left-0 right-0 bg-green-500/80 text-[7px] text-center text-white leading-tight">
                              Original
                            </span>
                          </div>

                          {/* Mockup thumbnails */}
                          {previews.map((preview, idx) => {
                            const isExcluded = excluded.has(preview.template_id);
                            return (
                              <div
                                key={preview.template_id}
                                className={`relative flex-shrink-0 w-12 h-15 cursor-pointer rounded border-2 transition-all ${
                                  isExcluded
                                    ? 'border-dark-border opacity-30'
                                    : selIdx === idx
                                    ? 'border-accent'
                                    : 'border-dark-border'
                                }`}
                              >
                                <img
                                  src={preview.preview_url}
                                  alt={`Mockup ${idx + 1}`}
                                  className="w-12 h-15 object-cover rounded"
                                  onClick={() => setSelectedPreviewIdx((prev) => ({ ...prev, [poster.id]: idx }))}
                                />
                                {/* Toggle button */}
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleMockupInclusion(poster.id, preview.template_id);
                                  }}
                                  className={`absolute top-0 right-0 w-4 h-4 rounded-bl text-[8px] font-bold leading-none flex items-center justify-center ${
                                    isExcluded
                                      ? 'bg-red-500/80 text-white'
                                      : 'bg-accent/80 text-dark-bg'
                                  }`}
                                >
                                  {isExcluded ? '—' : '✓'}
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      <div className="p-3 space-y-2">
                        {poster.prompt && (
                          <p className="text-xs text-gray-500 line-clamp-2">{poster.prompt}</p>
                        )}

                        {/* Per-poster pack override */}
                        {packs.length > 0 && (
                          <select
                            value={posterPackId[poster.id] ?? globalPackId ?? ''}
                            onChange={(e) => {
                              const val = e.target.value ? Number(e.target.value) : null;
                              setPosterPackId((prev) => ({ ...prev, [poster.id]: val }));
                              composeAllPreviews(poster.id, poster.url, val);
                            }}
                            className="w-full px-2 py-1 bg-dark-bg border border-dark-border rounded text-xs text-gray-300 focus:outline-none focus:border-accent"
                          >
                            <option value="">Active Templates</option>
                            {packs.map((pack) => (
                              <option key={pack.id} value={pack.id}>{pack.name} ({pack.template_count})</option>
                            ))}
                          </select>
                        )}

                        <div className="grid grid-cols-2 gap-2">
                          <button
                            onClick={() => handleApprove(poster.id)}
                            disabled={isProcessing || isLoadingPreview}
                            className="px-3 py-2 bg-green-500/10 text-green-400 rounded-lg text-sm font-medium hover:bg-green-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Approve ({includedCount})
                          </button>
                          <button
                            onClick={() => handleDecline(poster.id)}
                            disabled={isProcessing || isLoadingPreview}
                            className="px-3 py-2 bg-red-500/10 text-red-400 rounded-lg text-sm font-medium hover:bg-red-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Decline
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}

      {/* Declined tab */}
      {tab === 'declined' && (
        <>
          {declinedPosters.length === 0 ? (
            <div className="bg-dark-card border border-dark-border rounded-lg p-8 text-center space-y-3">
              <p className="text-gray-400">No declined posters</p>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-gray-400">
                {declinedPosters.length} declined poster{declinedPosters.length !== 1 ? 's' : ''}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {declinedPosters.map((poster) => {
                  const isProcessing = processingIds.has(poster.id);
                  return (
                    <div
                      key={poster.id}
                      className="bg-dark-card border border-dark-border rounded-lg overflow-hidden opacity-75 hover:opacity-100 transition-opacity"
                    >
                      <div className="relative">
                        <img
                          src={poster.url}
                          alt="Declined Poster"
                          className="w-full aspect-[4/5] object-cover"
                        />
                        <span className="absolute top-2 right-2 px-2 py-0.5 rounded text-[10px] font-medium bg-red-500/20 text-red-400">
                          {poster.mockup_status === 'declined' ? 'Declined' : 'Needs Attention'}
                        </span>
                        {isProcessing && (
                          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                            <div className="text-white text-sm">Processing...</div>
                          </div>
                        )}
                      </div>
                      <div className="p-3 space-y-2">
                        {poster.prompt && (
                          <p className="text-xs text-gray-500 line-clamp-2">{poster.prompt}</p>
                        )}
                        <button
                          onClick={() => handleRetry(poster.id)}
                          disabled={isProcessing}
                          className="w-full px-3 py-2 bg-yellow-500/10 text-yellow-400 rounded-lg text-sm font-medium hover:bg-yellow-500/20 transition-colors disabled:opacity-50"
                        >
                          Retry
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
