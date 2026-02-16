'use client';

import { Suspense, useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import StyleSelector from '@/components/StyleSelector';
import PresetSelector from '@/components/PresetSelector';
import ModelSelector from '@/components/ModelSelector';
import SizeSelector from '@/components/SizeSelector';
import NegativePromptInput from '@/components/NegativePromptInput';
import PromptInput from '@/components/PromptInput';
import GenerateButton from '@/components/GenerateButton';
import ImageGallery from '@/components/ImageGallery';
import {
  getStyles,
  getModels,
  getSizes,
  getDefaults,
  getPreset,
  startGeneration,
  pollForCompletion,
  StylesResponse,
  ModelsResponse,
  SizesResponse,
  DefaultsResponse,
  ImageInfo,
  PosterPreset,
} from '@/lib/api';

export default function Home() {
  return (
    <Suspense>
      <HomeContent />
    </Suspense>
  );
}

function HomeContent() {
  const searchParams = useSearchParams();
  const [styles, setStyles] = useState<StylesResponse>({});
  const [models, setModels] = useState<ModelsResponse>({});
  const [sizes, setSizes] = useState<SizesResponse>({});
  const [defaults, setDefaults] = useState<DefaultsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedStyle, setSelectedStyle] = useState<string | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>('phoenix');
  const [selectedSize, setSelectedSize] = useState<string | null>('poster_4_5');
  const [negativePrompt, setNegativePrompt] = useState<string>('');
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');
  const [loadedPreset, setLoadedPreset] = useState<PosterPreset | null>(null);
  const [numImages, setNumImages] = useState(1);
  const [ultra, setUltra] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [images, setImages] = useState<ImageInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    Promise.all([getStyles(), getModels(), getSizes(), getDefaults()])
      .then(([stylesData, modelsData, sizesData, defaultsData]) => {
        setStyles(stylesData);
        setModels(modelsData);
        setSizes(sizesData);
        setDefaults(defaultsData);
        setSelectedModel(defaultsData.model);
        setSelectedSize(defaultsData.size);
        setNegativePrompt(defaultsData.negative_prompt);
      })
      .catch((err) => {
        console.error('Failed to load data:', err);
        setError('Failed to load data. Is the backend running?');
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  // Load preset from URL query param (?preset=preset_id)
  useEffect(() => {
    const presetId = searchParams.get('preset');
    if (!presetId) return;

    getPreset(presetId)
      .then((preset) => {
        setIsCustomMode(true);
        setCustomPrompt(preset.prompt);
        setLoadedPreset(preset);
        if (preset.negative_prompt) {
          setNegativePrompt(preset.negative_prompt);
        }
        // Clear style/preset selection since we're in custom mode
        setSelectedStyle(null);
        setSelectedPreset(null);
        // Clean up URL without reload
        window.history.replaceState({}, '', '/');
      })
      .catch((err) => {
        console.error('Failed to load preset:', err);
      });
  }, [searchParams]);

  const handleStyleSelect = (styleKey: string) => {
    setSelectedStyle(styleKey);
    setSelectedPreset(null);
  };

  const handlePresetSelect = (presetKey: string) => {
    setSelectedPreset(presetKey);
  };

  const getCurrentPresetPrompt = (): string | null => {
    if (!selectedStyle || !selectedPreset) return null;
    return styles[selectedStyle]?.presets[selectedPreset]?.prompt || null;
  };

  const getActivePrompt = (): string => {
    if (isCustomMode) return customPrompt;
    return getCurrentPresetPrompt() || '';
  };

  const canGenerate = (): boolean => {
    const prompt = getActivePrompt();
    return prompt.trim().length > 0 && !isGenerating;
  };

  const handleGenerate = async () => {
    const prompt = getActivePrompt();
    if (!prompt.trim()) return;

    setIsGenerating(true);
    setError(null);
    setImages([]);

    try {
      const { generation_id } = await startGeneration(
        prompt,
        numImages,
        selectedModel,
        selectedSize,
        negativePrompt || null,
        ultra
      );

      const result = await pollForCompletion(generation_id);

      if (result.status === 'COMPLETE') {
        setImages(result.images);
      } else if (result.status === 'FAILED') {
        setError('Generation failed. Please try again.');
      }
      // Refresh credits in header
      window.dispatchEvent(new Event('credits-refresh'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsGenerating(false);
    }
  };

  const currentPresets = selectedStyle ? styles[selectedStyle]?.presets : null;

  return (
    <main className="p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Top row: Model + Size + Images count */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <ModelSelector
            models={models}
            selectedModel={selectedModel}
            onModelSelect={setSelectedModel}
            disabled={isGenerating}
            loading={isLoading}
          />
          <SizeSelector
            sizes={sizes}
            selectedSize={selectedSize}
            onSizeSelect={setSelectedSize}
            disabled={isGenerating}
            loading={isLoading}
          />
          <div className="space-y-2">
            <GenerateButton
              onClick={handleGenerate}
              disabled={!canGenerate()}
              isGenerating={isGenerating}
              numImages={numImages}
              onNumImagesChange={setNumImages}
            />
            {models[selectedModel || '']?.ultra && (
              <label className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-border cursor-pointer hover:border-accent/40 transition-colors">
                <input
                  type="checkbox"
                  checked={ultra}
                  onChange={(e) => setUltra(e.target.checked)}
                  disabled={isGenerating}
                  className="accent-accent"
                />
                <span className="text-xs text-gray-300">Ultra (~5MP, more credits)</span>
              </label>
            )}
          </div>
        </div>

        <div className="flex flex-col lg:flex-row gap-4">
          {/* Left: Style & Preset selection */}
          <div className="lg:w-72 space-y-4">
            <StyleSelector
              styles={styles}
              selectedStyle={selectedStyle}
              onStyleSelect={handleStyleSelect}
              loading={isLoading}
            />
            <PresetSelector
              presets={currentPresets}
              selectedPreset={selectedPreset}
              onPresetSelect={handlePresetSelect}
            />
          </div>

          {/* Center: Prompt area */}
          <div className="lg:w-80 space-y-4">
            {loadedPreset && (
              <div className="flex items-center gap-2 px-3 py-2 bg-accent/10 border border-accent/20 rounded-lg">
                <span className="text-xs text-accent font-medium">Preset:</span>
                <span className="text-xs text-gray-200 truncate">{loadedPreset.name}</span>
                <button
                  onClick={() => setLoadedPreset(null)}
                  className="ml-auto text-gray-500 hover:text-gray-300 text-xs"
                >
                  &#10005;
                </button>
              </div>
            )}
            <PromptInput
              presetPrompt={getCurrentPresetPrompt()}
              customPrompt={customPrompt}
              isCustomMode={isCustomMode}
              onCustomPromptChange={setCustomPrompt}
              onModeToggle={setIsCustomMode}
            />
            <NegativePromptInput
              negativePrompt={negativePrompt}
              defaultNegativePrompt={defaults?.negative_prompt || ''}
              onChange={setNegativePrompt}
              disabled={isGenerating}
            />
          </div>

          {/* Right: Results */}
          <div className="flex-1">
            <ImageGallery
              images={images}
              isLoading={isGenerating}
              error={error}
              preset={loadedPreset}
            />
          </div>
        </div>
      </div>
    </main>
  );
}
