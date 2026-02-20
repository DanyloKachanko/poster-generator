'use client';

import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import {
  getStrategyPlans,
  getStrategyPlan,
  createStrategyPlan,
  deleteStrategyPlan,
  generateStrategyPlan,
  updateStrategyItem,
  deleteStrategyItem,
  executeStrategyPlan,
  getExecutionStatus,
  getStrategyCoverage,
  StrategyPlan,
  StrategyPlanDetail,
  StrategyItem,
  StrategyCoverage,
  ExecutionStatus,
} from '@/lib/api';

export default function StrategyPage() {
  return (
    <Suspense
      fallback={
        <main className="p-4 md:p-6">
          <div className="max-w-7xl mx-auto flex items-center justify-center p-12">
            <div className="animate-spin h-8 w-8 border-2 border-accent border-t-transparent rounded-full" />
          </div>
        </main>
      }
    >
      <StrategyPageInner />
    </Suspense>
  );
}

// --- Status helpers ---

const statusBorderColor: Record<StrategyItem['status'], string> = {
  planned: 'border-l-gray-600',
  generating: 'border-l-yellow-500',
  generated: 'border-l-blue-500',
  product_created: 'border-l-green-500',
  skipped: 'border-l-gray-700 opacity-50',
};

const statusBadgeClass: Record<StrategyItem['status'], string> = {
  planned: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
  generating: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  generated: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  product_created: 'bg-green-500/15 text-green-400 border-green-500/30',
  skipped: 'bg-gray-500/10 text-gray-600 border-gray-600/30',
};

const planStatusBadge: Record<StrategyPlan['status'], string> = {
  draft: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
  executing: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  completed: 'bg-green-500/15 text-green-400 border-green-500/30',
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function StrategyPageInner() {
  // --- State ---
  const [plans, setPlans] = useState<StrategyPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<StrategyPlanDetail | null>(null);
  const [coverage, setCoverage] = useState<StrategyCoverage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // AI Generate dialog
  const [showGenerateDialog, setShowGenerateDialog] = useState(false);
  const [generateName, setGenerateName] = useState('AI Plan');
  const [generateCount, setGenerateCount] = useState(15);
  const [isGenerating, setIsGenerating] = useState(false);

  // Edit item dialog
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingItem, setEditingItem] = useState<StrategyItem | null>(null);
  const [editForm, setEditForm] = useState({ title_hint: '', prompt: '', style: '', preset: '' });

  // Execution
  const [executionTaskId, setExecutionTaskId] = useState<string | null>(null);
  const [executionStatus, setExecutionStatus] = useState<ExecutionStatus | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Action loading
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [deletingPlanId, setDeletingPlanId] = useState<number | null>(null);

  // --- Data loading ---

  const loadPlans = useCallback(async () => {
    try {
      const [plansData, coverageData] = await Promise.all([
        getStrategyPlans(),
        getStrategyCoverage(),
      ]);
      setPlans(plansData);
      setCoverage(coverageData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    }
  }, []);

  const loadPlanDetail = useCallback(async (planId: number) => {
    try {
      const detail = await getStrategyPlan(planId);
      setSelectedPlan(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load plan');
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadPlans().finally(() => setLoading(false));
  }, [loadPlans]);

  // --- Execution polling ---

  const startPolling = useCallback(
    (taskId: string) => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const status = await getExecutionStatus(taskId);
          setExecutionStatus(status);
          if (status.status === 'completed' || status.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setExecutionTaskId(null);
            // Refresh plan detail and plans list
            if (selectedPlan) {
              await loadPlanDetail(selectedPlan.id);
            }
            await loadPlans();
          }
        } catch (err) {
          console.error('Poll error:', err);
        }
      }, 2000);
    },
    [selectedPlan, loadPlanDetail, loadPlans],
  );

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // --- Handlers ---

  const handleSelectPlan = async (plan: StrategyPlan) => {
    setError(null);
    setLoading(true);
    try {
      const detail = await getStrategyPlan(plan.id);
      setSelectedPlan(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load plan');
    } finally {
      setLoading(false);
    }
  };

  const handleBackToPlans = () => {
    setSelectedPlan(null);
    setExecutionTaskId(null);
    setExecutionStatus(null);
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    loadPlans();
  };

  const handleCreatePlan = async () => {
    const name = prompt('Plan name:', 'New Plan');
    if (!name?.trim()) return;
    setError(null);
    try {
      const plan = await createStrategyPlan(name.trim());
      await loadPlans();
      const detail = await getStrategyPlan(plan.id);
      setSelectedPlan(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create plan');
    }
  };

  const handleDeletePlan = async (planId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this plan and all its items?')) return;
    setDeletingPlanId(planId);
    try {
      await deleteStrategyPlan(planId);
      await loadPlans();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete plan');
    } finally {
      setDeletingPlanId(null);
    }
  };

  const handleGenerate = async () => {
    if (!generateName.trim()) return;
    setIsGenerating(true);
    setError(null);
    try {
      const newPlan = await generateStrategyPlan(generateName.trim(), generateCount);
      setShowGenerateDialog(false);
      setGenerateName('AI Plan');
      setGenerateCount(15);
      await loadPlans();
      setSelectedPlan(newPlan);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'AI generation failed');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleExecute = async () => {
    if (!selectedPlan) return;
    setError(null);
    try {
      const result = await executeStrategyPlan(selectedPlan.id);
      setExecutionTaskId(result.task_id);
      setExecutionStatus({
        status: 'running',
        step: 0,
        total: result.total_items,
        completed: 0,
        current_item: null,
        current_title: null,
        errors: [],
      });
      startPolling(result.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start execution');
    }
  };

  const handleEditItem = (item: StrategyItem) => {
    setEditingItem(item);
    setEditForm({
      title_hint: item.title_hint || '',
      prompt: item.prompt || '',
      style: item.style || '',
      preset: item.preset || '',
    });
    setShowEditDialog(true);
  };

  const handleSaveEdit = async () => {
    if (!editingItem || !selectedPlan) return;
    setActionLoading(`edit-${editingItem.id}`);
    try {
      await updateStrategyItem(editingItem.id, editForm);
      await loadPlanDetail(selectedPlan.id);
      setShowEditDialog(false);
      setEditingItem(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update item');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSkipItem = async (item: StrategyItem) => {
    if (!selectedPlan) return;
    setActionLoading(`skip-${item.id}`);
    try {
      await updateStrategyItem(item.id, { status: 'skipped' });
      await loadPlanDetail(selectedPlan.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to skip item');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteItem = async (item: StrategyItem) => {
    if (!selectedPlan) return;
    if (!confirm('Delete this item?')) return;
    setActionLoading(`delete-${item.id}`);
    try {
      await deleteStrategyItem(item.id);
      await loadPlanDetail(selectedPlan.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete item');
    } finally {
      setActionLoading(null);
    }
  };

  // --- Derived ---

  const plannedCount = selectedPlan?.items.filter((i) => i.status === 'planned').length ?? 0;
  const isExecuting = !!executionTaskId;

  // --- Render ---

  if (loading && !selectedPlan && plans.length === 0) {
    return (
      <main className="p-4 md:p-6">
        <div className="max-w-7xl mx-auto flex items-center justify-center p-12">
          <div className="animate-spin h-8 w-8 border-2 border-accent border-t-transparent rounded-full" />
        </div>
      </main>
    );
  }

  return (
    <main className="p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Error banner */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 mb-6 text-red-400 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-300 ml-4"
            >
              &#10005;
            </button>
          </div>
        )}

        {/* === PLAN LIST VIEW === */}
        {!selectedPlan && (
          <>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl font-bold text-gray-100">Strategy Plans</h1>
                <p className="text-sm text-gray-500 mt-1">
                  Plan and execute poster generation strategies
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCreatePlan}
                  className="px-4 py-2 rounded-lg text-sm font-medium bg-dark-card border border-dark-border text-gray-300 hover:text-gray-100 hover:border-dark-hover transition-colors"
                >
                  + New Plan
                </button>
                <button
                  onClick={() => setShowGenerateDialog(true)}
                  className="px-4 py-2 rounded-lg text-sm font-medium bg-accent/15 text-accent border border-accent/30 hover:bg-accent/25 transition-colors"
                >
                  AI Generate
                </button>
              </div>
            </div>

            {/* Plan cards */}
            {plans.length === 0 && !loading && (
              <div className="text-center py-20">
                <div className="text-5xl mb-4 opacity-30">&#128203;</div>
                <h2 className="text-lg font-medium text-gray-400 mb-2">No strategy plans yet</h2>
                <p className="text-gray-600 mb-6">
                  Use AI Generate to create your first strategy plan.
                </p>
              </div>
            )}

            <div className="space-y-3">
              {plans.map((plan) => (
                <div
                  key={plan.id}
                  onClick={() => handleSelectPlan(plan)}
                  className="bg-dark-card border border-dark-border rounded-lg px-5 py-4 cursor-pointer hover:border-accent/30 transition-colors group"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      <h3 className="text-sm font-semibold text-gray-100 truncate group-hover:text-accent transition-colors">
                        {plan.name}
                      </h3>
                      <span
                        className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full border flex-shrink-0 ${planStatusBadge[plan.status]}`}
                      >
                        {plan.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 flex-shrink-0">
                      <div className="text-sm text-gray-400">
                        <span className="text-gray-200 font-medium">{plan.done_items}</span>
                        <span className="text-gray-600"> / </span>
                        <span>{plan.total_items}</span>
                        <span className="text-gray-600 ml-1">items</span>
                      </div>
                      <span className="text-xs text-gray-600">{formatDate(plan.created_at)}</span>
                      <button
                        onClick={(e) => handleDeletePlan(plan.id, e)}
                        disabled={deletingPlanId === plan.id}
                        className="px-2 py-1 rounded text-xs text-red-400/60 hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                      >
                        {deletingPlanId === plan.id ? '...' : 'Delete'}
                      </button>
                    </div>
                  </div>
                  {/* Progress bar */}
                  {plan.total_items > 0 && (
                    <div className="mt-3 w-full h-1.5 bg-dark-bg rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent/60 rounded-full transition-all duration-300"
                        style={{
                          width: `${Math.round((plan.done_items / plan.total_items) * 100)}%`,
                        }}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Coverage bar */}
            {coverage && (
              <div className="mt-8 bg-dark-card border border-dark-border rounded-lg px-5 py-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-300">Style/Preset Coverage</span>
                  <span className="text-sm text-gray-400">
                    {coverage.covered}
                    <span className="text-gray-600"> / </span>
                    {coverage.total_combinations} combos
                    <span className="text-gray-600 ml-1">
                      ({coverage.coverage_percent}%)
                    </span>
                  </span>
                </div>
                <div className="w-full h-2 bg-dark-bg rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent rounded-full transition-all duration-500"
                    style={{ width: `${coverage.coverage_percent}%` }}
                  />
                </div>
                <div className="mt-1.5 text-xs text-gray-600">
                  {coverage.products} products across {coverage.covered} unique style/preset
                  combinations
                </div>
              </div>
            )}
          </>
        )}

        {/* === PLAN DETAIL VIEW === */}
        {selectedPlan && (
          <>
            {/* Back + header */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-4">
                <button
                  onClick={handleBackToPlans}
                  className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
                >
                  &larr; Back to Plans
                </button>
                <h1 className="text-2xl font-bold text-gray-100">{selectedPlan.name}</h1>
                <span
                  className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full border ${planStatusBadge[selectedPlan.status]}`}
                >
                  {selectedPlan.status}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleExecute}
                  disabled={plannedCount === 0 || isExecuting}
                  className="px-4 py-2 rounded-lg text-sm font-medium bg-accent text-dark-bg hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isExecuting ? 'Executing...' : `Execute All Planned (${plannedCount})`}
                </button>
              </div>
            </div>

            {/* Execution progress */}
            {executionStatus && (executionTaskId || executionStatus.status === 'completed' || executionStatus.status === 'failed') && (
              <div className="bg-dark-card border border-dark-border rounded-lg p-4 mb-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-200">
                    {executionStatus.status === 'completed'
                      ? 'Execution Complete'
                      : executionStatus.status === 'failed'
                        ? 'Execution Failed'
                        : `Executing... Step ${executionStatus.step} of ${executionStatus.total}`}
                  </span>
                  <span className="text-sm text-gray-400">
                    {executionStatus.total > 0
                      ? Math.round((executionStatus.completed / executionStatus.total) * 100)
                      : 0}
                    %
                  </span>
                </div>
                <div className="w-full h-2 bg-dark-bg rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      executionStatus.status === 'failed' ? 'bg-red-500' : 'bg-accent'
                    }`}
                    style={{
                      width: `${
                        executionStatus.total > 0
                          ? Math.round((executionStatus.completed / executionStatus.total) * 100)
                          : 0
                      }%`,
                    }}
                  />
                </div>
                <div className="flex items-center justify-between mt-2">
                  <div className="flex gap-3 text-xs">
                    <span className="text-green-400">{executionStatus.completed} done</span>
                    {executionStatus.errors.length > 0 && (
                      <span className="text-red-400">{executionStatus.errors.length} errors</span>
                    )}
                  </div>
                  {executionStatus.current_title && executionTaskId && (
                    <span className="text-xs text-gray-500 truncate max-w-xs">
                      Current: {executionStatus.current_title}
                    </span>
                  )}
                </div>
                {/* Error details */}
                {executionStatus.errors.length > 0 && (
                  <div className="mt-3 space-y-1">
                    {executionStatus.errors.map((err, i) => (
                      <div
                        key={i}
                        className="text-xs text-red-400/80 bg-red-500/5 px-3 py-1.5 rounded"
                      >
                        Item #{err.item_id}: {err.error}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Items grid */}
            {selectedPlan.items.length === 0 ? (
              <div className="text-center py-16">
                <div className="text-4xl mb-3 opacity-30">&#128466;</div>
                <p className="text-gray-500">This plan has no items yet.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {selectedPlan.items
                  .sort((a, b) => a.sort_order - b.sort_order)
                  .map((item) => (
                    <div
                      key={item.id}
                      className={`bg-dark-card border border-dark-border rounded-lg p-4 border-l-4 ${statusBorderColor[item.status]}`}
                    >
                      {/* Title hint */}
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <h3 className="text-sm font-semibold text-gray-100 truncate flex-1">
                          {item.title_hint || 'Untitled'}
                        </h3>
                        <span
                          className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full border flex-shrink-0 ${statusBadgeClass[item.status]}`}
                        >
                          {item.status.replace('_', ' ')}
                        </span>
                      </div>

                      {/* Style/preset pills */}
                      <div className="flex flex-wrap gap-1.5 mb-2">
                        {item.style && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20">
                            {item.style}
                          </span>
                        )}
                        {item.preset && (
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                            {item.preset}
                          </span>
                        )}
                      </div>

                      {/* Prompt */}
                      {item.prompt && (
                        <p className="text-xs text-gray-300 line-clamp-2 mb-1.5">{item.prompt}</p>
                      )}

                      {/* Description */}
                      {item.description && (
                        <p className="text-xs text-gray-500 italic truncate mb-3">
                          {item.description}
                        </p>
                      )}

                      {/* Action buttons (only for planned items) */}
                      {item.status === 'planned' && (
                        <div className="flex items-center gap-2 pt-2 border-t border-dark-border">
                          <button
                            onClick={() => handleEditItem(item)}
                            className="px-2.5 py-1 rounded text-[11px] font-medium bg-dark-hover text-gray-300 hover:text-gray-100 transition-colors"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleSkipItem(item)}
                            disabled={actionLoading === `skip-${item.id}`}
                            className="px-2.5 py-1 rounded text-[11px] font-medium bg-dark-hover text-gray-400 hover:text-yellow-400 transition-colors disabled:opacity-50"
                          >
                            {actionLoading === `skip-${item.id}` ? '...' : 'Skip'}
                          </button>
                          <button
                            onClick={() => handleDeleteItem(item)}
                            disabled={actionLoading === `delete-${item.id}`}
                            className="px-2.5 py-1 rounded text-[11px] font-medium bg-dark-hover text-gray-400 hover:text-red-400 transition-colors disabled:opacity-50 ml-auto"
                          >
                            {actionLoading === `delete-${item.id}` ? '...' : 'Delete'}
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            )}
          </>
        )}

        {/* === AI GENERATE DIALOG === */}
        {showGenerateDialog && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div className="bg-dark-card border border-dark-border rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl">
              <h2 className="text-lg font-semibold text-gray-100 mb-4">AI Generate Plan</h2>

              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Plan Name</label>
                  <input
                    type="text"
                    value={generateName}
                    onChange={(e) => setGenerateName(e.target.value)}
                    className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-accent/50"
                    placeholder="e.g. Winter Collection"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Number of Items</label>
                  <input
                    type="number"
                    value={generateCount}
                    onChange={(e) =>
                      setGenerateCount(Math.min(30, Math.max(5, Number(e.target.value))))
                    }
                    min={5}
                    max={30}
                    className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-accent/50"
                  />
                  <span className="text-[11px] text-gray-600 mt-1 block">
                    Between 5 and 30 items
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 mt-6">
                <button
                  onClick={() => {
                    setShowGenerateDialog(false);
                    setError(null);
                  }}
                  disabled={isGenerating}
                  className="px-4 py-2 rounded-lg bg-dark-bg border border-dark-border text-sm text-gray-400 hover:text-gray-300 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating || !generateName.trim()}
                  className="px-4 py-2 rounded-lg bg-accent text-dark-bg text-sm font-medium hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  {isGenerating && (
                    <div className="animate-spin h-4 w-4 border-2 border-dark-bg border-t-transparent rounded-full" />
                  )}
                  {isGenerating ? 'Generating...' : 'Generate'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* === EDIT ITEM DIALOG === */}
        {showEditDialog && editingItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
            <div className="bg-dark-card border border-dark-border rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl">
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Edit Item</h2>

              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Title Hint</label>
                  <input
                    type="text"
                    value={editForm.title_hint}
                    onChange={(e) => setEditForm({ ...editForm, title_hint: e.target.value })}
                    className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-accent/50"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Prompt</label>
                  <textarea
                    value={editForm.prompt}
                    onChange={(e) => setEditForm({ ...editForm, prompt: e.target.value })}
                    rows={4}
                    className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-accent/50 resize-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Style</label>
                    <input
                      type="text"
                      value={editForm.style}
                      onChange={(e) => setEditForm({ ...editForm, style: e.target.value })}
                      className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-accent/50"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Preset</label>
                    <input
                      type="text"
                      value={editForm.preset}
                      onChange={(e) => setEditForm({ ...editForm, preset: e.target.value })}
                      className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-accent/50"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 mt-6">
                <button
                  onClick={() => {
                    setShowEditDialog(false);
                    setEditingItem(null);
                  }}
                  className="px-4 py-2 rounded-lg bg-dark-bg border border-dark-border text-sm text-gray-400 hover:text-gray-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  disabled={actionLoading === `edit-${editingItem.id}`}
                  className="px-4 py-2 rounded-lg bg-accent text-dark-bg text-sm font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors"
                >
                  {actionLoading === `edit-${editingItem.id}` ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
