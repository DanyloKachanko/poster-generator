'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  ImageInfo,
  CustomPresetSummary,
  CustomPresetPrompt,
  CustomPreset,
  PresetJobStatus,
  getCustomPresets,
  getCustomPreset,
  uploadCustomPreset,
  deleteCustomPreset,
  generatePresetPrompt,
  generateAllPresetPrompts,
  getPresetJobStatus,
} from '@/lib/api';
import CreateProductModal from '@/components/CreateProductModal';

export default function CustomPresetsPanel() {
  const [view, setView] = useState<'list' | 'detail' | 'running'>('list');
  const [presets, setPresets] = useState<CustomPresetSummary[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [presetDetail, setPresetDetail] = useState<CustomPreset | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatingPromptId, setGeneratingPromptId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<PresetJobStatus | null>(null);
  const [createProductImage, setCreateProductImage] = useState<ImageInfo | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const pollRef = useRef<NodeJS.Timeout | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Auto-dismiss errors after 5 seconds
  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(timer);
  }, [error]);

  // Load presets on mount
  useEffect(() => {
    loadPresets();
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const loadPresets = async () => {
    setLoading(true);
    try {
      const data = await getCustomPresets();
      setPresets(data.presets);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load presets');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    if (!file.name.endsWith('.json')) {
      setError('Only JSON files are supported');
      return;
    }
    setUploading(true);
    setError(null);
    try {
      await uploadCustomPreset(file);
      await loadPresets();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file);
    // Reset so same file can be re-selected
    e.target.value = '';
  };

  const handleDeletePreset = async (presetId: string) => {
    if (!confirm('Delete this preset? This cannot be undone.')) return;
    try {
      await deleteCustomPreset(presetId);
      setPresets((prev) => prev.filter((p) => p.id !== presetId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete preset');
    }
  };

  const handleSelectPreset = async (presetId: string) => {
    setSelectedPresetId(presetId);
    setError(null);
    try {
      const detail = await getCustomPreset(presetId);
      setPresetDetail(detail);
      setView('detail');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preset details');
    }
  };

  const handleBackToList = async () => {
    setView('list');
    setSelectedPresetId(null);
    setPresetDetail(null);
    setGeneratingPromptId(null);
    // Refresh presets list (generated_count may have changed)
    await loadPresets();
  };

  const handleGenerateSingle = async (promptId: string) => {
    if (!selectedPresetId) return;
    setGeneratingPromptId(promptId);
    setError(null);
    try {
      const result = await generatePresetPrompt(selectedPresetId, promptId);
      // Update the prompt in presetDetail with the returned data
      setPresetDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          prompts: prev.prompts.map((p) =>
            p.id === promptId
              ? { ...p, generation_id: result.generation_id, images: result.images }
              : p
          ),
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setGeneratingPromptId(null);
    }
  };

  const pollJobStatus = useCallback(
    (id: string) => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const status = await getPresetJobStatus(id);
          setJobStatus(status);
          if (status.status === 'completed' || status.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            // Refresh preset detail and go back to detail view
            if (selectedPresetId) {
              try {
                const detail = await getCustomPreset(selectedPresetId);
                setPresetDetail(detail);
              } catch {
                // Ignore refresh error
              }
            }
            setView('detail');
          }
        } catch (err) {
          console.error('Poll error:', err);
        }
      }, 3000);
    },
    [selectedPresetId]
  );

  const handleGenerateAll = async () => {
    if (!selectedPresetId) return;
    setError(null);
    try {
      const result = await generateAllPresetPrompts(selectedPresetId);
      setJobId(result.job_id);
      setJobStatus(null);
      setView('running');
      pollJobStatus(result.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start batch generation');
    }
  };

  // Helper: get dimensions string from settings
  const getDimensionsString = (settings: Record<string, unknown>): string | null => {
    const w = settings.width as number | undefined;
    const h = settings.height as number | undefined;
    if (w && h) return `${w}\u00D7${h}`;
    return null;
  };

  // Check if all prompts already have generations
  const allPromptsGenerated =
    presetDetail?.prompts.every((p) => p.generation_id !== null) ?? false;

  // Compute job progress
  const jobProgress =
    jobStatus && jobStatus.total > 0
      ? Math.round(((jobStatus.completed + jobStatus.failed) / jobStatus.total) * 100)
      : 0;

  // ==================== RENDER ====================

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="animate-spin h-8 w-8 border-2 border-accent border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Error toast */}
      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400 flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-300 ml-4 shrink-0"
          >
            &#10005;
          </button>
        </div>
      )}

      {/* ==================== LIST VIEW ==================== */}
      {view === 'list' && (
        <>
          {/* Upload drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              dragOver
                ? 'border-accent bg-accent/5'
                : 'border-dark-border hover:border-gray-500 bg-dark-card'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              onChange={handleFileSelect}
              className="hidden"
            />
            {uploading ? (
              <div className="flex items-center justify-center gap-3">
                <div className="animate-spin w-5 h-5 border-2 border-accent border-t-transparent rounded-full" />
                <span className="text-sm text-gray-300">Uploading...</span>
              </div>
            ) : (
              <>
                <svg
                  className="w-8 h-8 text-gray-500 mx-auto mb-2"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"
                  />
                </svg>
                <p className="text-sm text-gray-400">
                  Drop JSON preset file here
                </p>
                <p className="text-xs text-gray-600 mt-1">or click to browse</p>
              </>
            )}
          </div>

          {/* Preset cards grid */}
          {presets.length === 0 ? (
            <div className="bg-dark-card border border-dark-border rounded-lg p-8 text-center text-gray-500 text-sm">
              No custom presets yet. Upload a JSON file to get started.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {presets.map((preset) => (
                <div
                  key={preset.id}
                  onClick={() => handleSelectPreset(preset.id)}
                  className="relative bg-dark-card border border-dark-border rounded-lg p-4 cursor-pointer hover:border-gray-600 transition-colors group"
                >
                  {/* Delete button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeletePreset(preset.id);
                    }}
                    className="absolute top-2 right-2 w-5 h-5 flex items-center justify-center rounded text-gray-600 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                    title="Delete preset"
                  >
                    <svg
                      className="w-3.5 h-3.5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>

                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-medium text-gray-200 truncate">
                      {preset.name}
                    </span>
                    <span className="text-xs px-1.5 py-0.5 bg-dark-bg rounded text-gray-500 shrink-0">
                      {preset.model}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>{preset.prompt_count} prompts</span>
                    <span className="text-gray-700">|</span>
                    <span
                      className={
                        preset.generated_count === preset.prompt_count
                          ? 'text-green-400'
                          : ''
                      }
                    >
                      {preset.generated_count}/{preset.prompt_count} generated
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ==================== DETAIL VIEW ==================== */}
      {view === 'detail' && presetDetail && selectedPresetId && (
        <>
          {/* Back button */}
          <button
            onClick={handleBackToList}
            className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back to presets
          </button>

          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <h2 className="text-lg font-bold text-gray-100 truncate">
                {presetDetail.name}
              </h2>
              <span className="text-xs px-2 py-0.5 bg-dark-bg rounded text-gray-500 shrink-0">
                {presetDetail.model}
              </span>
              {getDimensionsString(presetDetail.settings) && (
                <span className="text-xs text-gray-600 shrink-0">
                  {getDimensionsString(presetDetail.settings)}
                </span>
              )}
            </div>
            <button
              onClick={handleGenerateAll}
              disabled={allPromptsGenerated}
              className="px-4 py-2 bg-accent text-dark-bg rounded-lg font-medium text-sm hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              Generate All
            </button>
          </div>

          {/* Prompt list — grouped by type */}
          {(() => {
            const singles = presetDetail.prompts.filter((p) => (p.type || 'single') === 'single');
            const diptychs = presetDetail.prompts.filter((p) => p.type === 'diptych');
            const hasBothTypes = singles.length > 0 && diptychs.length > 0;

            const renderPromptRow = (prompt: typeof presetDetail.prompts[0]) => {
              const isGenerating = generatingPromptId === prompt.id;
              const hasGeneration = prompt.generation_id !== null;
              const hasImages = prompt.images.length > 0;
              const isDiptych = prompt.type === 'diptych';

              return (
                <div
                  key={prompt.id}
                  className="bg-dark-card border border-dark-border rounded-lg p-3"
                >
                  <div className="flex items-start gap-3">
                    {/* Status icon */}
                    <div className="w-5 h-5 flex items-center justify-center shrink-0 mt-0.5">
                      {isGenerating ? (
                        <div className="animate-spin w-4 h-4 border-2 border-accent border-t-transparent rounded-full" />
                      ) : hasGeneration ? (
                        <svg
                          className="w-5 h-5 text-green-400"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M5 13l4 4L19 7"
                          />
                        </svg>
                      ) : (
                        <div className="w-2 h-2 rounded-full bg-gray-600" />
                      )}
                    </div>

                    {/* Prompt info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-200 truncate">
                          {prompt.name || prompt.id}
                        </span>
                        {isDiptych && (
                          <span className="text-[10px] px-1.5 py-0.5 bg-purple-500/10 text-purple-400 border border-purple-500/20 rounded shrink-0">
                            2 posters
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                        {prompt.prompt}
                      </p>

                      {/* Image thumbnails */}
                      {hasImages && (
                        <div className={`grid gap-1.5 mt-2 ${isDiptych ? 'grid-cols-2' : 'grid-cols-4'}`}>
                          {prompt.images.map((img) => (
                            <div key={img.id} className="relative group/img">
                              <img
                                src={img.url}
                                alt=""
                                className={`w-full object-cover rounded ${isDiptych ? 'max-h-32' : 'max-h-20'}`}
                              />
                              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover/img:opacity-100 transition-opacity bg-black/40 rounded">
                                <button
                                  onClick={() =>
                                    setCreateProductImage({
                                      id: img.id,
                                      url: img.url,
                                    })
                                  }
                                  className="px-2 py-1 bg-green-600 hover:bg-green-500 text-white rounded text-[10px] font-medium"
                                >
                                  Create Product
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Generate button */}
                    <button
                      onClick={() => handleGenerateSingle(prompt.id)}
                      disabled={hasGeneration || isGenerating || generatingPromptId !== null}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors shrink-0 disabled:opacity-40 disabled:cursor-not-allowed border-accent/30 text-accent hover:bg-accent/10"
                    >
                      {isGenerating ? 'Generating...' : 'Generate'}
                    </button>
                  </div>
                </div>
              );
            };

            return (
              <>
                {singles.length > 0 && (
                  <div className="space-y-2">
                    {hasBothTypes && (
                      <h3 className="text-xs text-gray-500 uppercase tracking-wider font-medium pt-1">
                        Single Posters ({singles.length})
                      </h3>
                    )}
                    {singles.map(renderPromptRow)}
                  </div>
                )}
                {diptychs.length > 0 && (
                  <div className="space-y-2">
                    {hasBothTypes && (
                      <h3 className="text-xs text-purple-400/70 uppercase tracking-wider font-medium pt-3">
                        Diptych Pairs ({diptychs.length})
                      </h3>
                    )}
                    {diptychs.map(renderPromptRow)}
                  </div>
                )}
              </>
            );
          })()}
        </>
      )}

      {/* ==================== RUNNING VIEW ==================== */}
      {view === 'running' && (
        <div className="space-y-4">
          {/* Progress bar */}
          <div className="bg-dark-card rounded-lg border border-dark-border p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-200">
                Generating...{' '}
                {jobStatus
                  ? `${jobStatus.completed + jobStatus.failed}/${jobStatus.total}`
                  : 'Starting...'}
              </span>
              <span className="text-sm text-gray-400">{jobProgress}%</span>
            </div>
            <div className="w-full h-2 bg-dark-bg rounded-full overflow-hidden">
              <div
                className="h-full bg-accent rounded-full transition-all duration-500"
                style={{ width: `${jobProgress}%` }}
              />
            </div>
            {jobStatus && (
              <div className="flex items-center gap-3 mt-2 text-xs">
                <span className="text-green-400">{jobStatus.completed} done</span>
                {jobStatus.failed > 0 && (
                  <span className="text-red-400">{jobStatus.failed} failed</span>
                )}
              </div>
            )}
          </div>

          {/* Per-item status rows */}
          {jobStatus?.items && (
            <div className="space-y-2">
              {Object.values(jobStatus.items).map((item) => (
                <div
                  key={item.prompt_id}
                  className="flex items-center gap-3 p-3 bg-dark-card rounded-lg border border-dark-border"
                >
                  <div className="w-5 h-5 flex items-center justify-center shrink-0">
                    {item.status === 'pending' && (
                      <div className="w-2 h-2 rounded-full bg-gray-600" />
                    )}
                    {item.status === 'generating' && (
                      <div className="animate-spin w-4 h-4 border-2 border-accent border-t-transparent rounded-full" />
                    )}
                    {item.status === 'complete' && (
                      <svg
                        className="w-5 h-5 text-green-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    )}
                    {item.status === 'failed' && (
                      <svg
                        className="w-5 h-5 text-red-400"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12"
                        />
                      </svg>
                    )}
                    {item.status === 'skipped' && (
                      <span className="text-xs text-gray-500">-</span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-gray-200 truncate block">
                      {item.prompt_name || item.prompt_id}
                    </span>
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      item.status === 'complete'
                        ? 'bg-green-500/10 text-green-400'
                        : item.status === 'generating'
                        ? 'bg-accent/10 text-accent'
                        : item.status === 'failed'
                        ? 'bg-red-500/10 text-red-400'
                        : 'bg-dark-bg text-gray-500'
                    }`}
                  >
                    {item.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Create Product Modal */}
      {createProductImage && (
        <CreateProductModal
          image={createProductImage}
          preset={null}
          onClose={() => setCreateProductImage(null)}
          autoFill
        />
      )}
    </div>
  );
}
