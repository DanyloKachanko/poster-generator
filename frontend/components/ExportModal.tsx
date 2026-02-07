'use client';

import { useState, useEffect } from 'react';
import {
  getExportSizes,
  startExport,
  getExportDownloadUrl,
  ExportSizesResponse,
  ImageInfo,
} from '@/lib/api';

interface ExportModalProps {
  image: ImageInfo;
  onClose: () => void;
}

export default function ExportModal({ image, onClose }: ExportModalProps) {
  const [sizes, setSizes] = useState<ExportSizesResponse>({});
  const [selectedSizes, setSelectedSizes] = useState<Set<string>>(new Set());
  const [isExporting, setIsExporting] = useState(false);
  const [progress, setProgress] = useState<string>('');
  const [exportedFiles, setExportedFiles] = useState<Record<string, string> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generationName, setGenerationName] = useState('');

  useEffect(() => {
    getExportSizes()
      .then((data) => {
        setSizes(data);
        // Pre-select high priority sizes that don't need upscaling
        const safe = Object.entries(data)
          .filter(([, s]) => s.priority >= 4 && !s.needs_upscale)
          .map(([k]) => k);
        setSelectedSizes(new Set(safe));
      })
      .catch(console.error);

    // Generate a default name from image ID
    setGenerationName(`poster_${image.id.slice(0, 8)}`);
  }, [image.id]);

  const toggleSize = (key: string) => {
    setSelectedSizes((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelectedSizes(new Set(Object.keys(sizes)));
  };

  const selectNone = () => {
    setSelectedSizes(new Set());
  };

  const handleExport = async () => {
    if (selectedSizes.size === 0) return;

    setIsExporting(true);
    setError(null);
    setProgress('Starting export...');

    try {
      const result = await startExport(
        image.id,
        generationName,
        Array.from(selectedSizes)
      );
      setExportedFiles(result.files);
      setProgress('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const sizeEntries = Object.entries(sizes).sort(
    ([, a], [, b]) => b.priority - a.priority
  );

  return (
    <div
      className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-dark-card border border-dark-border rounded-xl w-full max-w-lg max-h-[90vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-dark-border">
          <h2 className="text-lg font-semibold text-gray-100">
            Export for Printify
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 text-xl"
          >
            &times;
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Preview */}
          <div className="flex gap-4">
            <img
              src={image.url}
              alt="Preview"
              className="w-20 h-24 object-cover rounded-lg"
            />
            <div className="flex-1">
              <label className="text-sm text-gray-400 block mb-1">
                Export name
              </label>
              <input
                type="text"
                value={generationName}
                onChange={(e) => setGenerationName(e.target.value)}
                disabled={isExporting || !!exportedFiles}
                className="w-full px-3 py-1.5 bg-dark-bg border border-dark-border rounded-lg text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50 disabled:opacity-50"
              />
            </div>
          </div>

          {/* Size selection */}
          {!exportedFiles && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-300">
                  Sizes ({selectedSizes.size} selected)
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={selectAll}
                    className="text-xs text-accent hover:text-accent-light"
                  >
                    All
                  </button>
                  <span className="text-xs text-gray-600">|</span>
                  <button
                    onClick={selectNone}
                    className="text-xs text-accent hover:text-accent-light"
                  >
                    None
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                {sizeEntries.map(([key, size]) => (
                  <label
                    key={key}
                    className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition-colors ${
                      selectedSizes.has(key)
                        ? 'border-accent/40 bg-accent/5'
                        : 'border-dark-border hover:border-dark-hover bg-dark-bg'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedSizes.has(key)}
                      onChange={() => toggleSize(key)}
                      disabled={isExporting}
                      className="accent-accent"
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-200">
                          {size.label}
                        </span>
                        {size.priority >= 4 && !size.needs_upscale && (
                          <span className="text-xs px-1.5 py-0.5 bg-accent/20 text-accent rounded">
                            popular
                          </span>
                        )}
                        {size.needs_upscale && (
                          <span className="text-xs px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">
                            low res
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">
                        {size.width}x{size.height}px (300 DPI)
                      </span>
                    </div>
                  </label>
                ))}
              </div>
            </>
          )}

          {/* Progress */}
          {isExporting && (
            <div className="flex items-center gap-3 p-3 bg-dark-bg rounded-lg">
              <div className="animate-spin w-5 h-5 border-2 border-accent border-t-transparent rounded-full" />
              <span className="text-sm text-gray-300">{progress}</span>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Results */}
          {exportedFiles && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-green-400">
                Export complete! {Object.keys(exportedFiles).length} files ready.
              </p>
              <div className="space-y-1.5">
                {Object.entries(exportedFiles).map(([sizeKey]) => {
                  const size = sizes[sizeKey];
                  return (
                    <div
                      key={sizeKey}
                      className="flex items-center justify-between p-2 bg-dark-bg rounded-lg"
                    >
                      <span className="text-sm text-gray-300">
                        {size?.label || sizeKey}
                      </span>
                      <a
                        href={getExportDownloadUrl(generationName, sizeKey)}
                        download
                        className="text-xs px-3 py-1 bg-accent text-dark-bg rounded font-medium hover:bg-accent-hover transition-colors"
                      >
                        Download
                      </a>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-dark-border flex justify-end gap-3">
          {!exportedFiles ? (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleExport}
                disabled={isExporting || selectedSizes.size === 0}
                className="px-4 py-2 text-sm bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isExporting ? 'Exporting...' : `Export ${selectedSizes.size} sizes`}
              </button>
            </>
          ) : (
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover transition-colors"
            >
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
