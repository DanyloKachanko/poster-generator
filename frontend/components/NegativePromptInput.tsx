'use client';

import { useState } from 'react';

const ChevronDownIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
  </svg>
);

const ChevronUpIcon = ({ className }: { className?: string }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
  </svg>
);

interface NegativePromptInputProps {
  negativePrompt: string;
  defaultNegativePrompt: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export default function NegativePromptInput({
  negativePrompt,
  defaultNegativePrompt,
  onChange,
  disabled = false,
}: NegativePromptInputProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const handleReset = () => {
    onChange(defaultNegativePrompt);
  };

  const isModified = negativePrompt !== defaultNegativePrompt;

  return (
    <div className="bg-dark-card rounded-lg border border-dark-border p-4 space-y-2">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between w-full text-sm font-medium text-gray-300 hover:text-gray-100 transition-colors"
      >
        <span className="flex items-center gap-2">
          Negative Prompt
          {isModified && (
            <span className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded">
              Modified
            </span>
          )}
        </span>
        {isExpanded ? (
          <ChevronUpIcon className="w-4 h-4" />
        ) : (
          <ChevronDownIcon className="w-4 h-4" />
        )}
      </button>

      {isExpanded && (
        <div className="space-y-2">
          <textarea
            value={negativePrompt}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            rows={3}
            placeholder="Things to avoid in the generated image..."
            className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-gray-100 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent resize-none disabled:opacity-50 disabled:cursor-not-allowed"
          />
          {isModified && (
            <button
              type="button"
              onClick={handleReset}
              disabled={disabled}
              className="text-xs text-accent hover:text-accent-light transition-colors disabled:opacity-50"
            >
              Reset to default
            </button>
          )}
          <p className="text-xs text-gray-500">
            Describe elements you want to exclude from the generated image.
          </p>
        </div>
      )}
    </div>
  );
}
