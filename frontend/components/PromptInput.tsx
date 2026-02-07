'use client';

interface PromptInputProps {
  presetPrompt: string | null;
  customPrompt: string;
  isCustomMode: boolean;
  onCustomPromptChange: (prompt: string) => void;
  onModeToggle: (isCustom: boolean) => void;
}

export default function PromptInput({
  presetPrompt,
  customPrompt,
  isCustomMode,
  onCustomPromptChange,
  onModeToggle,
}: PromptInputProps) {
  return (
    <div className="bg-dark-card rounded-lg border border-dark-border p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-medium text-gray-300">Prompt</h2>
        <label className="flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={isCustomMode}
            onChange={(e) => onModeToggle(e.target.checked)}
            className="mr-2 accent-accent"
          />
          <span className="text-sm text-gray-400">Custom prompt</span>
        </label>
      </div>

      {isCustomMode ? (
        <textarea
          value={customPrompt}
          onChange={(e) => onCustomPromptChange(e.target.value)}
          placeholder="Enter your custom prompt..."
          className="w-full h-32 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-200 placeholder-gray-500 resize-none focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent"
        />
      ) : (
        <div className="w-full h-32 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-400 overflow-auto">
          {presetPrompt || 'Select a style and preset to see the prompt'}
        </div>
      )}
    </div>
  );
}
