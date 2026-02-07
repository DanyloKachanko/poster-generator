'use client';

import { ModelInfo } from '@/lib/api';

interface ModelSelectorProps {
  models: Record<string, ModelInfo>;
  selectedModel: string | null;
  onModelSelect: (modelKey: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

export default function ModelSelector({
  models,
  selectedModel,
  onModelSelect,
  disabled = false,
  loading = false,
}: ModelSelectorProps) {
  const modelEntries = Object.entries(models);

  if (loading) {
    return (
      <div className="bg-dark-card rounded-lg border border-dark-border p-4">
        <label className="text-sm font-medium text-gray-300 block mb-2">AI Model</label>
        <div className="h-10 bg-dark-bg rounded-lg animate-pulse" />
      </div>
    );
  }

  if (modelEntries.length === 0) {
    return (
      <div className="bg-dark-card rounded-lg border border-dark-border p-4">
        <label className="text-sm font-medium text-gray-300 block mb-2">AI Model</label>
        <div className="text-sm text-red-400">Failed to load models</div>
      </div>
    );
  }

  const selected = selectedModel ? models[selectedModel] : null;

  return (
    <div className="bg-dark-card rounded-lg border border-dark-border p-4">
      <label className="text-sm font-medium text-gray-300 block mb-2">AI Model</label>
      <select
        value={selectedModel || ''}
        onChange={(e) => onModelSelect(e.target.value)}
        disabled={disabled}
        className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {modelEntries.map(([key, model]) => (
          <option key={key} value={key}>
            {model.name}
          </option>
        ))}
      </select>
      {selected && (
        <p className="text-xs text-gray-500 mt-1.5">{selected.description}</p>
      )}
    </div>
  );
}
