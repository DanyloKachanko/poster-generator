'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  getLibraryCategories,
  getLibraryPrompts,
  getModels,
  getSizes,
  startBatchGeneration,
  getBatchStatus,
  cancelBatch,
  LibraryCategory,
  LibraryPrompt,
  BatchStatus,
  BatchItemStatus,
  ModelsResponse,
  SizesResponse,
} from '@/lib/api';
import CreateProductModal from '@/components/CreateProductModal';
import { ImageInfo } from '@/lib/api';

type PageState = 'select' | 'running' | 'results';

export default function BatchPage() {
  const [pageState, setPageState] = useState<PageState>('select');
  const [categories, setCategories] = useState<LibraryCategory[]>([]);
  const [prompts, setPrompts] = useState<LibraryPrompt[]>([]);
  const [models, setModels] = useState<ModelsResponse>({});
  const [sizes, setSizes] = useState<SizesResponse>({});
  const [loading, setLoading] = useState(true);

  // Selection state
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedPromptIds, setSelectedPromptIds] = useState<Set<string>>(new Set());
  const [modelId, setModelId] = useState('phoenix');
  const [sizeId, setSizeId] = useState('poster_2_3');
  const [numImages, setNumImages] = useState(1);
  const [delay, setDelay] = useState(3);

  // Batch state
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchStatus, setBatchStatus] = useState<BatchStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Product creation
  const [createProductImage, setCreateProductImage] = useState<ImageInfo | null>(null);

  // Load initial data
  useEffect(() => {
    setLoading(true);
    Promise.all([
      getLibraryCategories(),
      getLibraryPrompts(),
      getModels(),
      getSizes(),
    ])
      .then(([catData, promptData, modelsData, sizesData]) => {
        setCategories(catData.categories);
        setPrompts(promptData.prompts);
        setModels(modelsData);
        setSizes(sizesData);
      })
      .catch((err) => {
        setError('Failed to load data. Is the backend running?');
        console.error(err);
      })
      .finally(() => setLoading(false));
  }, []);

  // Filter prompts by category
  const filteredPrompts = selectedCategory
    ? prompts.filter((p) => p.category === selectedCategory)
    : prompts;

  const togglePrompt = (id: string) => {
    setSelectedPromptIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelectedPromptIds(new Set(filteredPrompts.map((p) => p.id)));
  };

  const selectNone = () => {
    setSelectedPromptIds(new Set());
  };

  // Poll batch status
  const startPolling = useCallback((id: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await getBatchStatus(id);
        setBatchStatus(status);
        if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
          if (pollRef.current) clearInterval(pollRef.current);
          setPageState('results');
        }
      } catch (err) {
        console.error('Poll error:', err);
      }
    }, 3000);
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleStartBatch = async () => {
    if (selectedPromptIds.size === 0) return;
    setError(null);

    try {
      const result = await startBatchGeneration({
        prompt_ids: Array.from(selectedPromptIds),
        model_id: modelId,
        size_id: sizeId,
        num_images_per_prompt: numImages,
        delay_between: delay,
      });
      setBatchId(result.batch_id);
      setBatchStatus(result);
      setPageState('running');
      startPolling(result.batch_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start batch');
    }
  };

  const handleCancel = async () => {
    if (!batchId) return;
    try {
      await cancelBatch(batchId);
    } catch (err) {
      console.error('Cancel error:', err);
    }
  };

  const handleNewBatch = () => {
    setBatchId(null);
    setBatchStatus(null);
    setSelectedPromptIds(new Set());
    setPageState('select');
  };

  // Collect all generated images from batch results
  const getResultImages = (): { promptName: string; promptId: string; images: ImageInfo[] }[] => {
    if (!batchStatus?.items) return [];
    return Object.values(batchStatus.items)
      .filter((item: BatchItemStatus) => item.status === 'complete' && item.images.length > 0)
      .map((item: BatchItemStatus) => ({
        promptName: item.prompt_name,
        promptId: item.prompt_id,
        images: item.images.map((img) => ({ id: img.id, url: img.url })),
      }));
  };

  if (loading) {
    return (
      <main className="p-4 md:p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-center p-12">
            <div className="animate-spin h-8 w-8 border-2 border-accent border-t-transparent rounded-full" />
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-100">Batch Generation</h1>
            <p className="text-sm text-gray-500 mt-1">
              Generate multiple posters from the prompt library
            </p>
          </div>
          {pageState !== 'select' && (
            <button
              onClick={handleNewBatch}
              className="px-4 py-2 text-sm bg-dark-card border border-dark-border rounded-lg text-gray-300 hover:text-gray-100 hover:border-dark-hover transition-colors"
            >
              New Batch
            </button>
          )}
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
            {error}
          </div>
        )}

        {/* SELECT STATE */}
        {pageState === 'select' && (
          <div className="space-y-4">
            {/* Config row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Model</label>
                <select
                  value={modelId}
                  onChange={(e) => setModelId(e.target.value)}
                  className="w-full px-3 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-accent/50"
                >
                  {Object.entries(models).map(([key, model]) => (
                    <option key={key} value={key}>
                      {model.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Size</label>
                <select
                  value={sizeId}
                  onChange={(e) => setSizeId(e.target.value)}
                  className="w-full px-3 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-accent/50"
                >
                  {Object.entries(sizes).map(([key, size]) => (
                    <option key={key} value={key}>
                      {size.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Images per prompt</label>
                <select
                  value={numImages}
                  onChange={(e) => setNumImages(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-accent/50"
                >
                  <option value={1}>1</option>
                  <option value={2}>2</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Delay (sec)</label>
                <select
                  value={delay}
                  onChange={(e) => setDelay(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-accent/50"
                >
                  <option value={3}>3s</option>
                  <option value={5}>5s</option>
                  <option value={10}>10s</option>
                </select>
              </div>
            </div>

            {/* Category filter */}
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={() => setSelectedCategory(null)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  !selectedCategory
                    ? 'bg-accent/15 text-accent border border-accent/30'
                    : 'bg-dark-card border border-dark-border text-gray-400 hover:text-gray-200'
                }`}
              >
                All
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    selectedCategory === cat.id
                      ? 'bg-accent/15 text-accent border border-accent/30'
                      : 'bg-dark-card border border-dark-border text-gray-400 hover:text-gray-200'
                  }`}
                >
                  {cat.icon} {cat.display_name}
                </button>
              ))}
            </div>

            {/* Selection controls */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">
                {selectedPromptIds.size} of {filteredPrompts.length} selected
              </span>
              <div className="flex gap-2">
                <button onClick={selectAll} className="text-xs text-accent hover:text-accent/80">
                  Select All
                </button>
                <span className="text-xs text-gray-600">|</span>
                <button onClick={selectNone} className="text-xs text-accent hover:text-accent/80">
                  None
                </button>
              </div>
            </div>

            {/* Prompt grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredPrompts.map((prompt) => (
                <label
                  key={prompt.id}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedPromptIds.has(prompt.id)
                      ? 'border-accent/40 bg-accent/5'
                      : 'border-dark-border hover:border-dark-hover bg-dark-card'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedPromptIds.has(prompt.id)}
                    onChange={() => togglePrompt(prompt.id)}
                    className="mt-1 accent-accent"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-200 truncate">
                        {prompt.name}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 bg-dark-bg rounded text-gray-500 shrink-0">
                        {prompt.trending_score}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1 line-clamp-2">{prompt.prompt}</p>
                    {prompt.full_tags && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {prompt.full_tags.slice(0, 5).map((tag) => (
                          <span
                            key={tag}
                            className="text-[10px] px-1.5 py-0.5 bg-dark-bg rounded text-gray-600"
                          >
                            {tag}
                          </span>
                        ))}
                        {prompt.full_tags.length > 5 && (
                          <span className="text-[10px] text-gray-600">
                            +{prompt.full_tags.length - 5}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </label>
              ))}
            </div>

            {/* Start button */}
            <div className="flex justify-end pt-2">
              <button
                onClick={handleStartBatch}
                disabled={selectedPromptIds.size === 0}
                className="px-6 py-2.5 bg-accent text-dark-bg rounded-lg font-medium text-sm hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Generate {selectedPromptIds.size} Prompt{selectedPromptIds.size !== 1 ? 's' : ''}
              </button>
            </div>
          </div>
        )}

        {/* RUNNING STATE */}
        {pageState === 'running' && batchStatus && (
          <div className="space-y-4">
            {/* Progress bar */}
            <div className="bg-dark-card rounded-lg border border-dark-border p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-200">
                  Generating... {batchStatus.completed + batchStatus.failed}/{batchStatus.total}
                </span>
                <span className="text-sm text-gray-400">
                  {batchStatus.progress_percent}%
                </span>
              </div>
              <div className="w-full h-2 bg-dark-bg rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent rounded-full transition-all duration-500"
                  style={{ width: `${batchStatus.progress_percent}%` }}
                />
              </div>
              <div className="flex items-center justify-between mt-2">
                <div className="flex gap-3 text-xs">
                  <span className="text-green-400">{batchStatus.completed} done</span>
                  {batchStatus.failed > 0 && (
                    <span className="text-red-400">{batchStatus.failed} failed</span>
                  )}
                </div>
                <button
                  onClick={handleCancel}
                  className="text-xs text-red-400 hover:text-red-300 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>

            {/* Per-item status */}
            {batchStatus.items && (
              <div className="space-y-2">
                {Object.values(batchStatus.items).map((item: BatchItemStatus) => (
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
                        <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                      {item.status === 'failed' && (
                        <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
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
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      item.status === 'complete'
                        ? 'bg-green-500/10 text-green-400'
                        : item.status === 'generating'
                        ? 'bg-accent/10 text-accent'
                        : item.status === 'failed'
                        ? 'bg-red-500/10 text-red-400'
                        : 'bg-dark-bg text-gray-500'
                    }`}>
                      {item.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* RESULTS STATE */}
        {pageState === 'results' && batchStatus && (
          <div className="space-y-4">
            {/* Summary */}
            <div className="bg-dark-card rounded-lg border border-dark-border p-4">
              <div className="flex items-center gap-4">
                <div className={`text-sm font-medium ${
                  batchStatus.status === 'completed' ? 'text-green-400' :
                  batchStatus.status === 'cancelled' ? 'text-yellow-400' :
                  'text-red-400'
                }`}>
                  Batch {batchStatus.status}
                </div>
                <div className="flex gap-3 text-xs text-gray-400">
                  <span>{batchStatus.completed} completed</span>
                  {batchStatus.failed > 0 && (
                    <span className="text-red-400">{batchStatus.failed} failed</span>
                  )}
                </div>
              </div>
            </div>

            {/* Results grid */}
            {getResultImages().map((result) => (
              <div key={result.promptId} className="bg-dark-card rounded-lg border border-dark-border p-4">
                <h3 className="text-sm font-medium text-gray-200 mb-3">{result.promptName}</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {result.images.map((image) => (
                    <div key={image.id} className="relative group">
                      <img
                        src={image.url}
                        alt={result.promptName}
                        className="w-full rounded-lg"
                      />
                      <div className="absolute bottom-2 left-2 right-2 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => setCreateProductImage(image)}
                          className="bg-green-600 hover:bg-green-500 text-white px-2.5 py-1.5 rounded-lg text-xs font-medium"
                        >
                          Create Product
                        </button>
                        <a
                          href={image.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="bg-dark-card/90 hover:bg-dark-card p-1.5 rounded-lg border border-dark-border ml-auto"
                          title="Open in new tab"
                        >
                          <svg className="h-4 w-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {getResultImages().length === 0 && (
              <div className="bg-dark-card rounded-lg border border-dark-border p-8 text-center text-gray-500">
                No images were generated.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create Product Modal */}
      {createProductImage && (
        <CreateProductModal
          image={createProductImage}
          preset={null}
          onClose={() => setCreateProductImage(null)}
        />
      )}
    </main>
  );
}
