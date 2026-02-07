'use client';

import { SizesResponse } from '@/lib/api';

interface SizeSelectorProps {
  sizes: SizesResponse;
  selectedSize: string | null;
  onSizeSelect: (size: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

export default function SizeSelector({
  sizes,
  selectedSize,
  onSizeSelect,
  disabled = false,
  loading = false,
}: SizeSelectorProps) {
  const sizeEntries = Object.entries(sizes);

  if (loading) {
    return (
      <div className="bg-dark-card rounded-lg border border-dark-border p-4">
        <label className="text-sm font-medium text-gray-300 block mb-3">Poster Size</label>
        <div className="h-10 bg-dark-bg rounded-lg animate-pulse" />
      </div>
    );
  }

  return (
    <div className="bg-dark-card rounded-lg border border-dark-border p-4">
      <label className="text-sm font-medium text-gray-300 block mb-3">Poster Size</label>
      <select
        value={selectedSize || ''}
        onChange={(e) => onSizeSelect(e.target.value)}
        disabled={disabled}
        className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {sizeEntries.map(([key, size]) => (
          <option key={key} value={key}>
            {size.name} ({size.width}x{size.height}) - {size.description}
          </option>
        ))}
      </select>
    </div>
  );
}
