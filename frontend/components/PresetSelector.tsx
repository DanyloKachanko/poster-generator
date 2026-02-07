'use client';

import { StylePreset } from '@/lib/api';

interface PresetSelectorProps {
  presets: Record<string, StylePreset> | null;
  selectedPreset: string | null;
  onPresetSelect: (presetKey: string) => void;
}

export default function PresetSelector({
  presets,
  selectedPreset,
  onPresetSelect,
}: PresetSelectorProps) {
  if (!presets) {
    return (
      <div className="bg-dark-card rounded-lg border border-dark-border p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-3">Preset</h2>
        <p className="text-sm text-gray-500">Select a style first</p>
      </div>
    );
  }

  const presetKeys = Object.keys(presets);

  return (
    <div className="bg-dark-card rounded-lg border border-dark-border p-4">
      <h2 className="text-sm font-medium text-gray-300 mb-3">Preset</h2>
      <div className="space-y-2">
        {presetKeys.map((key) => (
          <button
            key={key}
            onClick={() => onPresetSelect(key)}
            className={`w-full px-4 py-2 rounded-lg text-sm text-left transition-colors ${
              selectedPreset === key
                ? 'bg-accent text-dark-bg'
                : 'bg-dark-hover text-gray-300 hover:bg-dark-border'
            }`}
          >
            {presets[key].name}
          </button>
        ))}
      </div>
    </div>
  );
}
