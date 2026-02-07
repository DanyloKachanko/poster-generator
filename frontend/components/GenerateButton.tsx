'use client';

interface GenerateButtonProps {
  onClick: () => void;
  disabled: boolean;
  isGenerating: boolean;
  numImages: number;
  onNumImagesChange: (num: number) => void;
}

export default function GenerateButton({
  onClick,
  disabled,
  isGenerating,
  numImages,
  onNumImagesChange,
}: GenerateButtonProps) {
  return (
    <div className="bg-dark-card rounded-lg border border-dark-border p-4 space-y-4">
      <div>
        <h2 className="text-sm font-medium text-gray-300 mb-3">Settings</h2>
        <div className="space-y-3">
          <div>
            <label className="text-sm text-gray-400 block mb-2">
              Number of images
            </label>
            <div className="flex gap-2">
              {[1, 2].map((num) => (
                <button
                  key={num}
                  onClick={() => onNumImagesChange(num)}
                  disabled={isGenerating}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                    numImages === num
                      ? 'bg-accent text-dark-bg'
                      : 'bg-dark-hover text-gray-300 hover:bg-dark-border'
                  } ${isGenerating ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {num}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <button
        onClick={onClick}
        disabled={disabled || isGenerating}
        className={`w-full py-4 rounded-lg font-medium text-lg transition-colors ${
          disabled || isGenerating
            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
            : 'bg-accent hover:bg-accent-hover text-dark-bg'
        }`}
      >
        {isGenerating ? (
          <span className="flex items-center justify-center gap-2">
            <svg
              className="animate-spin h-5 w-5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            Generating...
          </span>
        ) : (
          'Generate'
        )}
      </button>
    </div>
  );
}
