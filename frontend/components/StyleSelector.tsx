'use client';

import { StyleCategory } from '@/lib/api';

interface StyleSelectorProps {
  styles: Record<string, StyleCategory>;
  selectedStyle: string | null;
  onStyleSelect: (styleKey: string) => void;
  loading?: boolean;
}

export default function StyleSelector({
  styles,
  selectedStyle,
  onStyleSelect,
  loading = false,
}: StyleSelectorProps) {
  const styleKeys = Object.keys(styles);

  return (
    <div className="bg-dark-card rounded-lg border border-dark-border p-4">
      <h2 className="text-sm font-medium text-gray-300 mb-3">Style</h2>
      {loading ? (
        <div className="text-sm text-gray-500 animate-pulse">Loading styles...</div>
      ) : styleKeys.length === 0 ? (
        <div className="text-sm text-red-400">Failed to load styles</div>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          {styleKeys.map((key) => (
            <button
              key={key}
              onClick={() => onStyleSelect(key)}
              className={`px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                selectedStyle === key
                  ? 'bg-accent text-dark-bg'
                  : 'bg-dark-hover text-gray-300 hover:bg-dark-border'
              }`}
            >
              {styles[key].name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
