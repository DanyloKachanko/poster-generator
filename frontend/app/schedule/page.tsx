'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  getScheduleQueue,
  getScheduleStats,
  getScheduleSettings,
  updateScheduleSettings,
  publishNow,
  removeFromSchedule,
  addToSchedule,
  addToScheduleBatch,
  retrySchedule,
  getMockups,
  MockupProduct,
  ScheduledProduct,
  ScheduleStats,
  ScheduleSettings,
} from '@/lib/api';

type TabFilter = 'pending' | 'published' | 'failed' | 'all';

function formatScheduleTime(isoString: string): string {
  try {
    const dt = new Date(isoString);
    return dt.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'America/New_York',
      timeZoneName: 'short',
    });
  } catch {
    return isoString;
  }
}

function formatRelative(isoString: string): string {
  try {
    const dt = new Date(isoString);
    const now = new Date();
    const diffMs = dt.getTime() - now.getTime();
    const diffHours = Math.round(diffMs / (1000 * 60 * 60));
    const diffMins = Math.round(diffMs / (1000 * 60));

    if (diffMins < 0) return 'overdue';
    if (diffMins < 60) return `in ${diffMins}m`;
    if (diffHours < 24) return `in ${diffHours}h`;
    const diffDays = Math.round(diffHours / 24);
    return `in ${diffDays}d`;
  } catch {
    return '';
  }
}

export default function SchedulePage() {
  const [stats, setStats] = useState<ScheduleStats | null>(null);
  const [settings, setSettings] = useState<ScheduleSettings | null>(null);
  const [queue, setQueue] = useState<ScheduledProduct[]>([]);
  const [activeTab, setActiveTab] = useState<TabFilter>('pending');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Settings edit state
  const [showSettings, setShowSettings] = useState(false);
  const [editTimes, setEditTimes] = useState<string[]>([]);
  const [editEnabled, setEditEnabled] = useState(true);
  const [editPrimaryCamera, setEditPrimaryCamera] = useState('');
  const [editShippingProfileId, setEditShippingProfileId] = useState('');
  const [editShopSectionId, setEditShopSectionId] = useState('');
  const [newTime, setNewTime] = useState('');
  const [savingSettings, setSavingSettings] = useState(false);

  // Add product picker state
  const [showPicker, setShowPicker] = useState(false);
  const [pickerProducts, setPickerProducts] = useState<MockupProduct[]>([]);
  const [pickerLoading, setPickerLoading] = useState(false);
  const [addingProduct, setAddingProduct] = useState<string | null>(null);
  const [pickerDateTime, setPickerDateTime] = useState('');
  const [selectedBatch, setSelectedBatch] = useState<Set<string>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [statsData, settingsData, queueData] = await Promise.all([
        getScheduleStats(),
        getScheduleSettings(),
        getScheduleQueue(activeTab === 'all' ? undefined : activeTab),
      ]);
      setStats(statsData);
      setSettings(settingsData);
      setQueue(queueData);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load data';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Sync edit state when settings load
  useEffect(() => {
    if (settings) {
      setEditTimes(settings.publish_times || []);
      setEditEnabled(Boolean(settings.enabled));
      setEditPrimaryCamera(settings.preferred_primary_camera || '');
      setEditShippingProfileId(settings.default_shipping_profile_id ? String(settings.default_shipping_profile_id) : '');
      setEditShopSectionId(settings.default_shop_section_id ? String(settings.default_shop_section_id) : '');
    }
  }, [settings]);

  const handlePublishNow = async (productId: string) => {
    setActionLoading(productId);
    try {
      await publishNow(productId);
      await loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to publish';
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRemove = async (productId: string) => {
    setActionLoading(productId);
    try {
      await removeFromSchedule(productId);
      await loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to remove';
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetry = async (productId: string) => {
    setActionLoading(productId);
    try {
      await retrySchedule(productId);
      await loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to retry';
      setError(message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleOpenPicker = async () => {
    if (showPicker) {
      setShowPicker(false);
      return;
    }
    setShowPicker(true);
    setPickerLoading(true);
    try {
      const mockups = await getMockups();
      // Filter: only draft products (not on Etsy) that aren't already scheduled
      const scheduledIds = new Set(queue.map((q) => q.printify_product_id));
      const drafts = mockups.filter(
        (m) => !m.etsy_listing_id && !scheduledIds.has(m.printify_id)
      );
      setPickerProducts(drafts);
    } catch {
      setPickerProducts([]);
    } finally {
      setPickerLoading(false);
    }
  };

  const handleAddProduct = async (product: MockupProduct) => {
    setAddingProduct(product.printify_id);
    try {
      // Convert local datetime to ISO UTC if user picked a custom time
      let scheduledAt: string | undefined;
      if (pickerDateTime) {
        scheduledAt = new Date(pickerDateTime).toISOString();
      }
      await addToSchedule(product.printify_id, product.title, scheduledAt);
      setShowPicker(false);
      setPickerDateTime('');
      await loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to add';
      setError(message);
    } finally {
      setAddingProduct(null);
    }
  };

  const toggleBatchSelect = (id: string) => {
    setSelectedBatch((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBatchSchedule = async () => {
    if (selectedBatch.size === 0) return;
    setBatchLoading(true);
    try {
      await addToScheduleBatch(Array.from(selectedBatch));
      setShowPicker(false);
      setSelectedBatch(new Set());
      await loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to batch schedule';
      setError(message);
    } finally {
      setBatchLoading(false);
    }
  };

  const handleAddTime = () => {
    const trimmed = newTime.trim();
    if (!trimmed) return;
    // Validate HH:MM
    if (!/^\d{1,2}:\d{2}$/.test(trimmed)) {
      setError('Invalid time format. Use HH:MM');
      return;
    }
    const [h, m] = trimmed.split(':').map(Number);
    if (h < 0 || h > 23 || m < 0 || m > 59) {
      setError('Invalid time. Hours 0-23, minutes 0-59');
      return;
    }
    const formatted = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    if (editTimes.includes(formatted)) {
      setError('This time slot already exists');
      return;
    }
    setEditTimes((prev) => [...prev, formatted].sort());
    setNewTime('');
    setError(null);
  };

  const handleRemoveTime = (time: string) => {
    setEditTimes((prev) => prev.filter((t) => t !== time));
  };

  const handleSaveSettings = async () => {
    if (editTimes.length === 0) {
      setError('At least one publish time is required');
      return;
    }
    setSavingSettings(true);
    try {
      const result = await updateScheduleSettings({
        publish_times: editTimes,
        enabled: editEnabled,
        preferred_primary_camera: editPrimaryCamera,
        default_shipping_profile_id: editShippingProfileId ? Number(editShippingProfileId) : null,
        default_shop_section_id: editShopSectionId ? Number(editShopSectionId) : null,
      });
      setSettings(result);
      setError(null);
      setShowSettings(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save';
      setError(message);
    } finally {
      setSavingSettings(false);
    }
  };

  const tabs: { key: TabFilter; label: string }[] = [
    { key: 'pending', label: 'Pending' },
    { key: 'published', label: 'Published' },
    { key: 'failed', label: 'Failed' },
    { key: 'all', label: 'All' },
  ];

  const statusDot: Record<string, string> = {
    pending: 'bg-yellow-400',
    published: 'bg-green-400',
    failed: 'bg-red-400',
  };

  const statusBadge: Record<string, string> = {
    pending: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    published: 'bg-green-500/15 text-green-400 border-green-500/30',
    failed: 'bg-red-500/15 text-red-400 border-red-500/30',
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Publish Schedule</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage your Etsy publishing queue and timing
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleOpenPicker}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              showPicker
                ? 'bg-accent text-dark-bg'
                : 'bg-accent/15 text-accent border border-accent/30 hover:bg-accent/25'
            }`}
          >
            + Add Product
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="px-4 py-2 rounded-lg bg-dark-card border border-dark-border text-sm text-gray-300 hover:bg-dark-hover transition-colors"
          >
            Settings
          </button>
          <button
            onClick={loadData}
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
          <button
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-300 ml-4"
          >
            &#10005;
          </button>
        </div>
      )}

      {/* Product Picker */}
      {showPicker && (
        <div className="bg-dark-card border border-accent/30 rounded-lg p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-200">
              Select a draft product to schedule
            </h2>
            <button onClick={() => setShowPicker(false)} className="text-gray-500 hover:text-gray-300">
              &#10005;
            </button>
          </div>
          {/* Schedule time picker + batch controls */}
          <div className="flex items-center gap-3 mb-3">
            <label className="text-xs text-gray-400">Publish at:</label>
            <input
              type="datetime-local"
              value={pickerDateTime}
              onChange={(e) => setPickerDateTime(e.target.value)}
              className="px-2 py-1 rounded bg-dark-bg border border-dark-border text-sm text-gray-200 focus:outline-none focus:border-accent/50"
            />
            {pickerDateTime && (
              <button
                onClick={() => setPickerDateTime('')}
                className="text-xs text-gray-500 hover:text-gray-300"
              >
                Clear (use auto)
              </button>
            )}
            {!pickerDateTime && (
              <span className="text-[11px] text-gray-600">Auto: next available slot</span>
            )}
            {selectedBatch.size > 0 && (
              <button
                onClick={handleBatchSchedule}
                disabled={batchLoading}
                className="ml-auto px-4 py-1.5 rounded-lg bg-accent text-dark-bg text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {batchLoading ? 'Scheduling...' : `Schedule ${selectedBatch.size} Selected`}
              </button>
            )}
          </div>

          {pickerLoading ? (
            <div className="flex items-center gap-2 py-6 justify-center text-gray-500 text-sm">
              <div className="animate-spin h-5 w-5 border-2 border-accent border-t-transparent rounded-full" />
              Loading products...
            </div>
          ) : pickerProducts.length === 0 ? (
            <div className="py-6 text-center text-sm text-gray-600">
              No draft products available. All products are either on Etsy or already scheduled.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 max-h-80 overflow-y-auto">
              {pickerProducts.map((p) => {
                const thumb = p.images.find((i) => i.is_default)?.src || p.images[0]?.src;
                const isAdding = addingProduct === p.printify_id;
                const isSelected = selectedBatch.has(p.printify_id);
                return (
                  <div
                    key={p.printify_id}
                    className={`flex items-center gap-3 p-2 rounded-lg bg-dark-bg border transition-colors ${
                      isSelected ? 'border-accent/60 bg-accent/5' : 'border-dark-border hover:border-accent/40'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleBatchSelect(p.printify_id)}
                      className="flex-shrink-0 accent-[var(--accent)]"
                    />
                    {thumb && (
                      <img src={thumb} alt="" className="w-10 h-14 object-cover rounded flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-gray-200 truncate">{p.title}</div>
                      <div className="text-[10px] text-gray-600 mt-0.5">{p.images.length} mockups</div>
                    </div>
                    <button
                      onClick={() => handleAddProduct(p)}
                      disabled={isAdding}
                      className="px-2 py-1 rounded text-[10px] font-medium bg-accent/15 text-accent border border-accent/30 hover:bg-accent/25 transition-colors disabled:opacity-50 flex-shrink-0"
                    >
                      {isAdding ? '...' : 'Add'}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-dark-card border border-dark-border rounded-lg p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              Pending
            </div>
            <div className="text-2xl font-bold text-yellow-400">{stats.pending}</div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              Published (7d)
            </div>
            <div className="text-2xl font-bold text-green-400">
              {stats.published_last_7_days}
            </div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              Failed
            </div>
            <div className="text-2xl font-bold text-red-400">{stats.failed}</div>
          </div>
          <div className="bg-dark-card border border-dark-border rounded-lg p-4">
            <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
              Next Publish
            </div>
            <div className="text-lg font-bold text-gray-100">
              {stats.next_publish_at
                ? formatRelative(stats.next_publish_at)
                : 'None'}
            </div>
            {stats.next_publish_at && (
              <div className="text-xs text-gray-500 mt-0.5">
                {formatScheduleTime(stats.next_publish_at)}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Settings Panel */}
      {showSettings && settings && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-5 mb-6">
          <h2 className="text-lg font-semibold text-gray-100 mb-4">
            Schedule Configuration
          </h2>

          {/* Publish Times */}
          <div className="mb-4">
            <label className="text-sm text-gray-400 mb-2 block">
              Publish Time Slots (EST)
            </label>
            <div className="flex flex-wrap gap-2 mb-3">
              {editTimes.map((time) => (
                <span
                  key={time}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-accent/15 text-accent text-sm font-medium border border-accent/30"
                >
                  {time} EST
                  <button
                    onClick={() => handleRemoveTime(time)}
                    className="text-accent/60 hover:text-accent ml-0.5"
                  >
                    &#10005;
                  </button>
                </span>
              ))}
              {editTimes.length === 0 && (
                <span className="text-sm text-gray-600">No time slots configured</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newTime}
                onChange={(e) => setNewTime(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddTime()}
                placeholder="HH:MM (e.g. 10:00)"
                className="w-40 px-3 py-1.5 rounded-lg bg-dark-bg border border-dark-border text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-accent/50"
              />
              <button
                onClick={handleAddTime}
                className="px-3 py-1.5 rounded-lg bg-accent/15 text-accent text-sm font-medium border border-accent/30 hover:bg-accent/25 transition-colors"
              >
                Add
              </button>
            </div>
          </div>

          {/* Primary Mockup Image */}
          <div className="mb-4">
            <label className="text-sm text-gray-400 mb-2 block">
              Primary Image on Etsy (auto-set after publish)
            </label>
            <select
              value={editPrimaryCamera}
              onChange={(e) => setEditPrimaryCamera(e.target.value)}
              className="w-64 px-3 py-1.5 rounded-lg bg-dark-bg border border-dark-border text-sm text-gray-200 focus:outline-none focus:border-accent/50"
            >
              <option value="">Disabled (Printify default)</option>
              <option value="front">Front</option>
              <option value="front-2">Front 2</option>
              <option value="close-up">Close-up</option>
              <option value="context-1">Context 1 (lifestyle)</option>
              <option value="context-2">Context 2 (lifestyle)</option>
              <option value="context-3">Context 3 (lifestyle)</option>
              <option value="context-4">Context 4 (lifestyle)</option>
              <option value="context-5">Context 5 (lifestyle)</option>
            </select>
            {editPrimaryCamera && (
              <p className="text-[11px] text-gray-600 mt-1">
                After publishing, the selected mockup type will be uploaded as the 1st Etsy image
              </p>
            )}
          </div>

          {/* Etsy Defaults */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-sm text-gray-400 mb-2 block">
                Default Shipping Profile ID
              </label>
              <input
                type="text"
                value={editShippingProfileId}
                onChange={(e) => setEditShippingProfileId(e.target.value.replace(/\D/g, ''))}
                placeholder="e.g. 12345678"
                className="w-full px-3 py-1.5 rounded-lg bg-dark-bg border border-dark-border text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-accent/50"
              />
              <p className="text-[11px] text-gray-600 mt-1">
                Auto-applied to Etsy listings after publish
              </p>
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-2 block">
                Default Shop Section ID
              </label>
              <input
                type="text"
                value={editShopSectionId}
                onChange={(e) => setEditShopSectionId(e.target.value.replace(/\D/g, ''))}
                placeholder="e.g. 42000000"
                className="w-full px-3 py-1.5 rounded-lg bg-dark-bg border border-dark-border text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-accent/50"
              />
              <p className="text-[11px] text-gray-600 mt-1">
                Auto-applied to Etsy listings after publish
              </p>
            </div>
          </div>

          {/* Enabled Toggle */}
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => setEditEnabled(!editEnabled)}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                editEnabled ? 'bg-accent' : 'bg-gray-700'
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                  editEnabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
            <span className="text-sm text-gray-300">
              Schedule {editEnabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>

          {/* Save */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleSaveSettings}
              disabled={savingSettings}
              className="px-4 py-2 rounded-lg bg-accent text-dark-bg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {savingSettings ? 'Saving...' : 'Save Settings'}
            </button>
            <button
              onClick={() => {
                setShowSettings(false);
                if (settings) {
                  setEditTimes(settings.publish_times || []);
                  setEditEnabled(Boolean(settings.enabled));
                  setEditPrimaryCamera(settings.preferred_primary_camera || '');
                  setEditShippingProfileId(settings.default_shipping_profile_id ? String(settings.default_shipping_profile_id) : '');
                  setEditShopSectionId(settings.default_shop_section_id ? String(settings.default_shop_section_id) : '');
                }
              }}
              className="px-4 py-2 rounded-lg bg-dark-bg border border-dark-border text-sm text-gray-400 hover:text-gray-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Current Schedule Info (compact, when settings panel is closed) */}
      {!showSettings && settings && (
        <div className="flex items-center gap-3 mb-6 text-sm text-gray-500">
          <span className={`w-2 h-2 rounded-full ${settings.enabled ? 'bg-green-400' : 'bg-gray-600'}`} />
          <span>
            {settings.enabled ? 'Publishing at ' : 'Schedule paused '}
            {settings.publish_times?.join(', ')} EST
          </span>
          {settings.preferred_primary_camera && (
            <span className="px-2 py-0.5 rounded bg-orange-500/10 text-orange-400 text-xs border border-orange-500/20">
              Primary: {settings.preferred_primary_camera}
            </span>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-4 border-b border-dark-border pb-px">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.key
                ? 'text-accent border-accent'
                : 'text-gray-500 border-transparent hover:text-gray-300'
            }`}
          >
            {tab.label}
            {tab.key === 'pending' && stats && stats.pending > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 text-[10px] rounded-full bg-yellow-500/15 text-yellow-400">
                {stats.pending}
              </span>
            )}
            {tab.key === 'failed' && stats && stats.failed > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 text-[10px] rounded-full bg-red-500/15 text-red-400">
                {stats.failed}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Loading */}
      {isLoading && queue.length === 0 && (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && queue.length === 0 && (
        <div className="text-center py-20">
          <div className="text-5xl mb-4 opacity-30">&#128197;</div>
          <h2 className="text-lg font-medium text-gray-400 mb-2">
            {activeTab === 'all'
              ? 'No scheduled products'
              : `No ${activeTab} products`}
          </h2>
          <p className="text-gray-600">
            Products added via &ldquo;Publish to Etsy&rdquo; will appear here.
          </p>
        </div>
      )}

      {/* Queue List */}
      {queue.length > 0 && (
        <div className="space-y-2">
          {queue.map((item) => (
            <div
              key={item.id}
              className="bg-dark-card border border-dark-border rounded-lg px-4 py-3 flex items-center gap-4"
            >
              {/* Product image or status dot */}
              {item.image_url ? (
                <img
                  src={item.image_url}
                  alt={item.title}
                  className="w-12 h-16 object-cover rounded flex-shrink-0"
                />
              ) : (
                <div
                  className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                    statusDot[item.status] || 'bg-gray-500'
                  }`}
                />
              )}

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium text-gray-200 truncate">
                    {item.title}
                  </h3>
                  <span
                    className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full border flex-shrink-0 ${
                      statusBadge[item.status] || ''
                    }`}
                  >
                    {item.status}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                  <span>
                    Scheduled: {formatScheduleTime(item.scheduled_publish_at)}
                  </span>
                  {item.status === 'pending' && (
                    <span className="text-yellow-400/70">
                      {formatRelative(item.scheduled_publish_at)}
                    </span>
                  )}
                  {item.published_at && (
                    <span className="text-green-400/70">
                      Published: {formatScheduleTime(item.published_at)}
                    </span>
                  )}
                  {item.error_message && (
                    <span className="text-red-400/70 truncate max-w-xs" title={item.error_message}>
                      Error: {item.error_message}
                    </span>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {item.status === 'pending' && (
                  <>
                    <button
                      onClick={() => handlePublishNow(item.printify_product_id)}
                      disabled={actionLoading === item.printify_product_id}
                      className="px-3 py-1.5 rounded-md text-xs font-medium bg-accent/15 text-accent border border-accent/30 hover:bg-accent/25 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === item.printify_product_id
                        ? '...'
                        : 'Publish Now'}
                    </button>
                    <button
                      onClick={() => handleRemove(item.printify_product_id)}
                      disabled={actionLoading === item.printify_product_id}
                      className="px-3 py-1.5 rounded-md text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                    >
                      Remove
                    </button>
                  </>
                )}
                {item.status === 'failed' && (
                  <>
                    <button
                      onClick={() => handleRetry(item.printify_product_id)}
                      disabled={actionLoading === item.printify_product_id}
                      className="px-3 py-1.5 rounded-md text-xs font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/30 hover:bg-yellow-500/20 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === item.printify_product_id ? '...' : 'Retry'}
                    </button>
                    <button
                      onClick={() => handleRemove(item.printify_product_id)}
                      disabled={actionLoading === item.printify_product_id}
                      className="px-3 py-1.5 rounded-md text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                    >
                      Remove
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
