// API URL: prefer NEXT_PUBLIC_API_URL env var, fall back to current hostname
function getApiUrl(): string {
  if (typeof window !== 'undefined') {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl) return envUrl;
    // Dev fallback: use current hostname with backend port 8001
    return `http://${window.location.hostname}:8001`;
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
}

export interface StylePreset {
  name: string;
  prompt: string;
}

export interface StyleCategory {
  name: string;
  presets: Record<string, StylePreset>;
}

export type StylesResponse = Record<string, StyleCategory>;

export interface ModelInfo {
  id: string;
  name: string;
  description: string;
}

export type ModelsResponse = Record<string, ModelInfo>;

export interface SizeInfo {
  name: string;
  width: number;
  height: number;
  description: string;
}

export type SizesResponse = Record<string, SizeInfo>;

export interface DefaultsResponse {
  negative_prompt: string;
  model: string;
  size: string;
}

export interface GenerateResponse {
  generation_id: string;
  status: string;
}

export interface ImageInfo {
  id: string;
  url: string;
}

export interface GenerationStatusResponse {
  generation_id: string;
  status: string;
  images: ImageInfo[];
}

export async function getStyles(): Promise<StylesResponse> {
  const response = await fetch(`${getApiUrl()}/styles`);
  if (!response.ok) {
    throw new Error('Failed to fetch styles');
  }
  return response.json();
}

export async function getModels(): Promise<ModelsResponse> {
  const response = await fetch(`${getApiUrl()}/models`);
  if (!response.ok) {
    throw new Error('Failed to fetch models');
  }
  return response.json();
}

export async function getSizes(): Promise<SizesResponse> {
  const response = await fetch(`${getApiUrl()}/sizes`);
  if (!response.ok) {
    throw new Error('Failed to fetch sizes');
  }
  return response.json();
}

export async function getDefaults(): Promise<DefaultsResponse> {
  const response = await fetch(`${getApiUrl()}/defaults`);
  if (!response.ok) {
    throw new Error('Failed to fetch defaults');
  }
  return response.json();
}

export async function startGeneration(
  prompt: string,
  numImages: number,
  modelId: string | null = null,
  sizeId: string | null = null,
  negativePrompt: string | null = null
): Promise<GenerateResponse> {
  const response = await fetch(`${getApiUrl()}/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      prompt,
      num_images: numImages,
      model_id: modelId,
      size_id: sizeId,
      negative_prompt: negativePrompt,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to start generation');
  }

  return response.json();
}

export async function getGenerationStatus(
  generationId: string
): Promise<GenerationStatusResponse> {
  const response = await fetch(`${getApiUrl()}/generation/${generationId}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to get generation status');
  }
  return response.json();
}

export async function pollForCompletion(
  generationId: string,
  onStatusUpdate?: (status: string) => void,
  pollInterval: number = 2000,
  timeout: number = 60000
): Promise<GenerationStatusResponse> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeout) {
    const result = await getGenerationStatus(generationId);

    if (onStatusUpdate) {
      onStatusUpdate(result.status);
    }

    if (result.status === 'COMPLETE' || result.status === 'FAILED') {
      return result;
    }

    await new Promise((resolve) => setTimeout(resolve, pollInterval));
  }

  throw new Error('Generation timed out');
}

// History types and functions
export interface HistoryImage {
  url: string;
  id: string;
}

export interface HistoryItem {
  id: number;
  generation_id: string;
  prompt: string;
  negative_prompt: string | null;
  model_id: string;
  model_name: string | null;
  style: string | null;
  preset: string | null;
  width: number;
  height: number;
  num_images: number;
  status: string;
  api_credit_cost: number;
  created_at: string;
  completed_at: string | null;
  error_message: string | null;
  images: HistoryImage[];
}

export interface HistoryResponse {
  items: HistoryItem[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface TokenBalance {
  api_subscription_tokens: number;
  api_paid_tokens: number;
  api_total_tokens: number;
  subscription_tokens: number;
  paid_tokens: number;
  total_tokens: number;
  token_renewal_date: string | null;
  api_token_renewal_date: string | null;
}

export interface CreditsResponse {
  total_credits_used: number;
  total_generations: number;
  total_images: number;
  by_status: Record<string, number>;
  balance: TokenBalance | null;
}

export async function getHistory(
  limit: number = 20,
  offset: number = 0,
  status?: string,
  style?: string,
  archived: boolean = false
): Promise<HistoryResponse> {
  const params = new URLSearchParams();
  params.set('limit', limit.toString());
  params.set('offset', offset.toString());
  if (status) params.set('status', status);
  if (style) params.set('style', style);
  if (archived) params.set('archived', 'true');

  const response = await fetch(`${getApiUrl()}/history?${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch history');
  }
  return response.json();
}

export async function archiveGeneration(generationId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/history/${generationId}/archive`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to archive');
  }
}

export async function restoreGeneration(generationId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/history/${generationId}/restore`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to restore');
  }
}

// Export types and functions
export interface ExportSizeInfo {
  label: string;
  width: number;
  height: number;
  ratio: string;
  priority: number;
  needs_upscale?: boolean;
}

export type ExportSizesResponse = Record<string, ExportSizeInfo>;

export interface ExportResponse {
  status: string;
  files: Record<string, string>;
  count: number;
}

export async function getExportSizes(): Promise<ExportSizesResponse> {
  const response = await fetch(`${getApiUrl()}/export/sizes`);
  if (!response.ok) {
    throw new Error('Failed to fetch export sizes');
  }
  return response.json();
}

export async function startExport(
  generatedImageId: string,
  generationName: string,
  sizes?: string[]
): Promise<ExportResponse> {
  const response = await fetch(`${getApiUrl()}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      generated_image_id: generatedImageId,
      generation_name: generationName,
      sizes: sizes || null,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Export failed' }));
    throw new Error(error.detail || 'Export failed');
  }
  return response.json();
}

export async function getExportStatus(
  generationName: string
): Promise<Record<string, boolean>> {
  const response = await fetch(`${getApiUrl()}/export/${generationName}/status`);
  if (!response.ok) {
    throw new Error('Failed to get export status');
  }
  return response.json();
}

export function getExportDownloadUrl(generationName: string, size: string): string {
  return `${getApiUrl()}/export/${generationName}/${size}`;
}

// Listing generation types and functions
export interface PriceInfo {
  size: string;
  strategy: string;
  recommended_price: number;
  base_cost: number;
  shipping_included: number;
  etsy_fees: number;
  profit: number;
  margin_percent: number;
}

export interface ListingData {
  title: string;
  tags: string[];
  tags_string: string;
  description: string;
  pricing?: Record<string, PriceInfo>;
}

export interface ListingRequest {
  style: string;
  preset: string;
  description: string;
  custom_keywords?: string[];
}

export async function generateListing(request: ListingRequest): Promise<ListingData> {
  const response = await fetch(`${getApiUrl()}/generate-listing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to generate listing' }));
    throw new Error(error.detail || 'Failed to generate listing');
  }
  return response.json();
}

export async function regenerateTitle(
  style: string,
  preset: string,
  currentTitle: string
): Promise<string> {
  const response = await fetch(`${getApiUrl()}/regenerate-title`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      style,
      preset,
      current_title: currentTitle,
    }),
  });
  if (!response.ok) {
    throw new Error('Failed to regenerate title');
  }
  const data = await response.json();
  return data.title;
}

export async function regenerateDescription(
  style: string,
  preset: string,
  currentDescription: string,
  tone: string = 'warm'
): Promise<string> {
  const response = await fetch(`${getApiUrl()}/regenerate-description`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      style,
      preset,
      current_description: currentDescription,
      tone,
    }),
  });
  if (!response.ok) {
    throw new Error('Failed to regenerate description');
  }
  const data = await response.json();
  return data.description;
}

export async function regenerateTags(
  style: string,
  preset: string,
  currentTags: string[],
  title: string = ''
): Promise<string[]> {
  const response = await fetch(`${getApiUrl()}/regenerate-tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      style,
      preset,
      current_tags: currentTags,
      title,
    }),
  });
  if (!response.ok) {
    throw new Error('Failed to regenerate tags');
  }
  const data = await response.json();
  return data.tags;
}

export async function getPricing(strategy: string = 'standard'): Promise<Record<string, PriceInfo>> {
  const response = await fetch(`${getApiUrl()}/pricing?strategy=${strategy}`);
  if (!response.ok) {
    throw new Error('Failed to fetch pricing');
  }
  return response.json();
}

export async function getCredits(): Promise<CreditsResponse> {
  const response = await fetch(`${getApiUrl()}/credits`);
  if (!response.ok) {
    throw new Error('Failed to fetch credits');
  }
  return response.json();
}

// Printify types and functions
export interface PrintifyStatus {
  configured: boolean;
  connected: boolean;
  shops?: { id: number; title: string }[];
  error?: string;
}

export interface PrintifyVariant {
  id: number;
  title: string;
  price: number;
  is_enabled: boolean;
}

export interface PrintifyImage {
  src: string;
  variant_ids: number[];
  position: string;
  is_default: boolean;
}

export interface PrintifyExternal {
  id: string;
  handle: string;
  shipping_template_id?: string;
  type?: number;
}

export interface PrintifyProduct {
  id: string;
  title: string;
  description: string;
  tags: string[];
  images: PrintifyImage[];
  variants: PrintifyVariant[];
  created_at: string;
  updated_at: string;
  visible: boolean;
  is_locked: boolean;
  blueprint_id: number;
  print_provider_id: number;
  sales_channel_properties: unknown;
  external?: PrintifyExternal;
}

export interface PrintifyProductsResponse {
  current_page: number;
  data: PrintifyProduct[];
  last_page: number;
  total: number;
}

export async function getPrintifyStatus(): Promise<PrintifyStatus> {
  const response = await fetch(`${getApiUrl()}/printify/status`);
  if (!response.ok) {
    throw new Error('Failed to fetch Printify status');
  }
  return response.json();
}

export async function getPrintifyProducts(
  page: number = 1,
  limit: number = 20
): Promise<PrintifyProductsResponse> {
  const params = new URLSearchParams({ page: page.toString(), limit: limit.toString() });
  const response = await fetch(`${getApiUrl()}/printify/products?${params}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch products' }));
    throw new Error(error.detail || 'Failed to fetch products');
  }
  return response.json();
}

export async function getPrintifyProduct(productId: string): Promise<PrintifyProduct> {
  const response = await fetch(`${getApiUrl()}/printify/products/${productId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch product');
  }
  return response.json();
}

export async function publishPrintifyProduct(productId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/printify/products/${productId}/publish`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to publish' }));
    throw new Error(error.detail || 'Failed to publish');
  }
}

export async function unpublishPrintifyProduct(productId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/printify/products/${productId}/unpublish`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to unpublish' }));
    throw new Error(error.detail || 'Failed to unpublish');
  }
}

export async function deletePrintifyProduct(productId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/printify/products/${productId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete' }));
    throw new Error(error.detail || 'Failed to delete');
  }
}

export interface UpdateProductPayload {
  title?: string;
  description?: string;
  tags?: string[];
  variants?: { id: number; price: number; is_enabled: boolean }[];
}

export async function updatePrintifyProduct(
  productId: string,
  payload: UpdateProductPayload
): Promise<PrintifyProduct> {
  const response = await fetch(`${getApiUrl()}/printify/products/${productId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update product' }));
    throw new Error(error.detail || 'Failed to update product');
  }
  return response.json();
}

// Full product creation (listing + Printify + optional Etsy publish)
export interface CreateFullProductRequest {
  style: string;
  preset: string;
  description: string;
  image_url: string;
  pricing_strategy?: string;
  publish_to_etsy?: boolean;
}

export interface DpiSizeAnalysis {
  size_key: string;
  size_label: string;
  native_dpi: number;
  quality: 'ideal' | 'good' | 'acceptable' | 'needs_upscale';
  is_sellable: boolean;
  upscale_needed: boolean;
  upscale_factor: number;
  achievable_dpi: number;
  target_width: number;
  target_height: number;
}

export interface CreateFullProductResponse {
  printify_product_id: string;
  title: string;
  tags: string[];
  description: string;
  pricing: Record<string, PriceInfo>;
  status: string;
  published: boolean;
  dpi_analysis?: Record<string, DpiSizeAnalysis>;
  enabled_sizes?: string[];
  upscale_backend?: string;
}

export async function createFullProduct(
  request: CreateFullProductRequest
): Promise<CreateFullProductResponse> {
  const response = await fetch(`${getApiUrl()}/create-full-product`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create product' }));
    throw new Error(error.detail || 'Failed to create product');
  }
  return response.json();
}

// Analytics types and functions
export interface AnalyticsProduct {
  printify_product_id: string;
  title: string;
  thumbnail: string | null;
  status: string;
  min_price: number;
  max_price: number;
  etsy_url: string | null;
  total_views: number;
  total_favorites: number;
  total_orders: number;
  total_revenue_cents: number;
  latest_date: string | null;
}

export interface AnalyticsTotals {
  total_views: number;
  total_favorites: number;
  total_orders: number;
  total_revenue_cents: number;
}

export interface AnalyticsResponse {
  products: AnalyticsProduct[];
  totals: AnalyticsTotals;
}

export interface AnalyticsEntry {
  id: number;
  printify_product_id: string;
  date: string;
  views: number;
  favorites: number;
  orders: number;
  revenue_cents: number;
  notes: string | null;
  created_at: string;
}

export async function getAnalytics(): Promise<AnalyticsResponse> {
  const response = await fetch(`${getApiUrl()}/analytics`);
  if (!response.ok) {
    throw new Error('Failed to fetch analytics');
  }
  return response.json();
}

export async function saveAnalytics(entry: {
  printify_product_id: string;
  date: string;
  views?: number;
  favorites?: number;
  orders?: number;
  revenue_cents?: number;
  notes?: string;
}): Promise<void> {
  const response = await fetch(`${getApiUrl()}/analytics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  });
  if (!response.ok) {
    throw new Error('Failed to save analytics');
  }
}

export async function getProductAnalyticsHistory(
  productId: string
): Promise<{ entries: AnalyticsEntry[] }> {
  const response = await fetch(`${getApiUrl()}/analytics/${productId}/history`);
  if (!response.ok) {
    throw new Error('Failed to fetch product analytics history');
  }
  return response.json();
}

// Etsy integration types and functions
export interface EtsyStatus {
  configured: boolean;
  connected: boolean;
  shop_id?: string;
  error?: string;
}

export interface EtsySyncResult {
  synced: number;
  date: string;
  products: {
    printify_product_id: string;
    etsy_listing_id?: string;
    title?: string;
    views?: number;
    favorites?: number;
    error?: string;
  }[];
}

export async function getEtsyStatus(): Promise<EtsyStatus> {
  const response = await fetch(`${getApiUrl()}/etsy/status`);
  if (!response.ok) {
    throw new Error('Failed to fetch Etsy status');
  }
  return response.json();
}

export async function getEtsyAuthUrl(): Promise<{ url: string }> {
  const response = await fetch(`${getApiUrl()}/etsy/auth-url`);
  if (!response.ok) {
    throw new Error('Failed to get Etsy auth URL');
  }
  return response.json();
}

export async function syncEtsyAnalytics(): Promise<EtsySyncResult> {
  const response = await fetch(`${getApiUrl()}/etsy/sync`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Sync failed' }));
    throw new Error(error.detail || 'Sync failed');
  }
  return response.json();
}

export async function disconnectEtsy(): Promise<void> {
  const response = await fetch(`${getApiUrl()}/etsy/disconnect`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to disconnect Etsy');
  }
}

// Presets types and functions
export interface PosterPreset {
  id: string;
  name: string;
  category: string;
  prompt: string;
  negative_prompt: string;
  tags: string[];
  difficulty: string;
  trending_score: number;
}

export interface PresetCategory {
  name: string;
  icon: string;
  color: string;
}

export interface PresetsResponse {
  presets: PosterPreset[];
  categories: Record<string, PresetCategory>;
  used_preset_ids: string[];
}

export async function getPreset(presetId: string): Promise<PosterPreset> {
  const response = await fetch(`${getApiUrl()}/presets/${presetId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch preset');
  }
  return response.json();
}

export async function getPresets(category?: string): Promise<PresetsResponse> {
  const params = category ? `?category=${category}` : '';
  const response = await fetch(`${getApiUrl()}/presets${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch presets');
  }
  return response.json();
}

export async function getTrendingPresets(limit: number = 10): Promise<{ presets: PosterPreset[] }> {
  const response = await fetch(`${getApiUrl()}/presets/trending?limit=${limit}`);
  if (!response.ok) {
    throw new Error('Failed to fetch trending presets');
  }
  return response.json();
}

export async function getCategories(): Promise<Record<string, PresetCategory>> {
  const response = await fetch(`${getApiUrl()}/categories`);
  if (!response.ok) {
    throw new Error('Failed to fetch categories');
  }
  return response.json();
}

// POD Providers types and functions
export interface PODProvider {
  id: string;
  name: string;
  has_etsy_integration: boolean;
  has_api: boolean;
  quality_rating: number;
  poster_prices: Record<string, number>;
  shipping_us: Record<string, number>;
  paper_types: string[];
  finishes: string[];
  branding_options: string[];
  production_days: string;
  shipping_days_us: string;
  notes: string;
}

export interface ProviderRecommendation {
  provider: string;
  reason: string;
  tips: string[];
}

export interface ProvidersResponse {
  providers: PODProvider[];
  recommendations: Record<string, ProviderRecommendation>;
}

export interface ProviderComparison {
  provider: string;
  provider_id: string;
  base_cost: number;
  shipping: number;
  total: number;
  quality: number;
  production_days: string;
  has_etsy: boolean;
}

export async function getProviders(): Promise<ProvidersResponse> {
  const response = await fetch(`${getApiUrl()}/providers`);
  if (!response.ok) {
    throw new Error('Failed to fetch providers');
  }
  return response.json();
}

export async function compareProviders(size: string = '18x24'): Promise<{ size: string; providers: ProviderComparison[] }> {
  const response = await fetch(`${getApiUrl()}/providers/compare?size=${size}`);
  if (!response.ok) {
    throw new Error('Failed to compare providers');
  }
  return response.json();
}

// Dashboard types and functions
export interface DashboardStats {
  total_generated: number;
  total_images: number;
  total_credits_used: number;
  total_products: number;
  total_published: number;
  total_views: number;
  total_favorites: number;
  total_orders: number;
  total_revenue_cents: number;
  by_status: Record<string, number>;
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await fetch(`${getApiUrl()}/dashboard/stats`);
  if (!response.ok) {
    throw new Error('Failed to fetch dashboard stats');
  }
  return response.json();
}

export async function republishPrintifyProduct(productId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/printify/products/${productId}/republish`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to republish' }));
    throw new Error(error.detail || 'Failed to republish');
  }
}

// === Prompt Library types and functions ===

export interface LibraryCategory {
  id: string;
  display_name: string;
  icon: string;
  color: string;
  etsy_tags_base: string[];
  seasonality: string;
  demand_level: string;
  competition: string;
}

export interface LibraryPrompt {
  id: string;
  name: string;
  category: string;
  prompt: string;
  negative_prompt: string;
  tags_extra: string[];
  style_preset: string;
  difficulty: string;
  trending_score: number;
  variations: string[];
  full_tags?: string[];
  category_display?: string;
}

export async function getLibraryCategories(): Promise<{ categories: LibraryCategory[] }> {
  const response = await fetch(`${getApiUrl()}/library/categories`);
  if (!response.ok) {
    throw new Error('Failed to fetch library categories');
  }
  return response.json();
}

export async function getLibraryPrompts(
  category?: string,
  seasonality?: string
): Promise<{ prompts: LibraryPrompt[]; total: number }> {
  const params = new URLSearchParams();
  if (category) params.set('category', category);
  if (seasonality) params.set('seasonality', seasonality);
  const qs = params.toString() ? `?${params}` : '';
  const response = await fetch(`${getApiUrl()}/library/prompts${qs}`);
  if (!response.ok) {
    throw new Error('Failed to fetch library prompts');
  }
  return response.json();
}

export async function getLibraryPrompt(promptId: string): Promise<LibraryPrompt> {
  const response = await fetch(`${getApiUrl()}/library/prompts/${promptId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch library prompt');
  }
  return response.json();
}

// === Batch Generation types and functions ===

export interface BatchGenerateRequest {
  prompt_ids: string[];
  model_id?: string;
  size_id?: string;
  num_images_per_prompt?: number;
  use_variations?: boolean;
  variation_index?: number;
  delay_between?: number;
}

export interface BatchItemStatus {
  prompt_id: string;
  prompt_name: string;
  generation_id: string | null;
  status: string;
  images: { id: string; url: string }[];
  error: string | null;
}

export interface BatchStatus {
  batch_id: string;
  status: string;
  total: number;
  completed: number;
  failed: number;
  progress_percent: number;
  current_item: string | null;
  model_id: string;
  size_id: string;
  created_at: number;
  started_at: number | null;
  completed_at: number | null;
  items?: Record<string, BatchItemStatus>;
}

export async function startBatchGeneration(
  request: BatchGenerateRequest
): Promise<BatchStatus> {
  const response = await fetch(`${getApiUrl()}/batch/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to start batch' }));
    throw new Error(error.detail || 'Failed to start batch');
  }
  return response.json();
}

export async function getBatchStatus(batchId: string): Promise<BatchStatus> {
  const response = await fetch(`${getApiUrl()}/batch/${batchId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch batch status');
  }
  return response.json();
}

export async function cancelBatch(batchId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/batch/${batchId}/cancel`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to cancel batch' }));
    throw new Error(error.detail || 'Failed to cancel batch');
  }
}

export async function listBatches(): Promise<{ batches: BatchStatus[] }> {
  const response = await fetch(`${getApiUrl()}/batch`);
  if (!response.ok) {
    throw new Error('Failed to list batches');
  }
  return response.json();
}

// === Pipeline Auto-Product ===

export interface AutoProductRequest {
  prompt_id: string;
  model_id?: string;
  size_id?: string;
  pricing_strategy?: string;
  publish_to_etsy?: boolean;
  custom_title?: string;
  custom_tags?: string[];
}

export interface AutoProductResponse {
  printify_product_id: string;
  generation_id: string;
  title: string;
  tags: string[];
  description: string;
  image_url: string;
  pricing: Record<string, PriceInfo>;
  published: boolean;
  dpi_analysis?: Record<string, DpiSizeAnalysis>;
  enabled_sizes?: string[];
  upscale_backend?: string;
}

export async function autoCreateProduct(
  request: AutoProductRequest
): Promise<AutoProductResponse> {
  const response = await fetch(`${getApiUrl()}/pipeline/auto-product`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create product' }));
    throw new Error(error.detail || 'Failed to create product');
  }
  return response.json();
}

// === DPI Analysis ===

export interface DpiAnalyzeResponse {
  source: { width: number; height: number };
  sizes: Record<string, DpiSizeAnalysis>;
  groups: {
    original_ok: string[];
    upscale_needed: string[];
    skip: string[];
  };
  upscale_backend: string;
}

export async function analyzeDpi(
  width: number,
  height: number
): Promise<DpiAnalyzeResponse> {
  const params = new URLSearchParams({ width: width.toString(), height: height.toString() });
  const response = await fetch(`${getApiUrl()}/dpi/analyze?${params}`);
  if (!response.ok) {
    throw new Error('Failed to analyze DPI');
  }
  return response.json();
}

// === Fix Existing Products ===

export interface FixExistingResult {
  dry_run: boolean;
  fixed: { id: string; title: string; action: string; variants_to_disable?: number[]; variants_disabled?: number[] }[];
  skipped: { id: string; title: string; reason: string }[];
  total_fixed: number;
  total_skipped: number;
}

export async function fixExistingProducts(dryRun: boolean = true): Promise<FixExistingResult> {
  const response = await fetch(`${getApiUrl()}/printify/fix-existing-products?dry_run=${dryRun}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fix products' }));
    throw new Error(error.detail || 'Failed to fix products');
  }
  return response.json();
}

// === Schedule types and functions ===

export interface ScheduledProduct {
  id: number;
  printify_product_id: string;
  title: string;
  image_url: string | null;
  status: 'pending' | 'published' | 'failed';
  scheduled_publish_at: string;
  published_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface ScheduleStats {
  pending: number;
  next_publish_at: string | null;
  published_last_7_days: number;
  failed: number;
}

export interface ScheduleSettings {
  id: number;
  publish_times_json: string;
  publish_times: string[];
  timezone: string;
  enabled: number;
  updated_at: string | null;
}

export async function getScheduleQueue(status?: string): Promise<ScheduledProduct[]> {
  const params = status ? `?status=${status}` : '';
  const response = await fetch(`${getApiUrl()}/schedule/queue${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch schedule queue');
  }
  return response.json();
}

export async function getScheduleStats(): Promise<ScheduleStats> {
  const response = await fetch(`${getApiUrl()}/schedule/stats`);
  if (!response.ok) {
    throw new Error('Failed to fetch schedule stats');
  }
  return response.json();
}

export async function getScheduleSettings(): Promise<ScheduleSettings> {
  const response = await fetch(`${getApiUrl()}/schedule/settings`);
  if (!response.ok) {
    throw new Error('Failed to fetch schedule settings');
  }
  return response.json();
}

export async function updateScheduleSettings(settings: {
  publish_times: string[];
  timezone?: string;
  enabled?: boolean;
}): Promise<ScheduleSettings> {
  const response = await fetch(`${getApiUrl()}/schedule/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update settings' }));
    throw new Error(error.detail || 'Failed to update settings');
  }
  return response.json();
}

export async function publishNow(productId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/schedule/publish-now/${productId}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to publish' }));
    throw new Error(error.detail || 'Failed to publish');
  }
}

export async function removeFromSchedule(productId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/schedule/${productId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to remove from schedule' }));
    throw new Error(error.detail || 'Failed to remove from schedule');
  }
}

// === Seasonal Calendar types and functions ===

export interface SeasonalEvent {
  id: string;
  name: string;
  month: number;
  day: number;
  icon: string;
  color: string;
  lead_time_weeks: number;
  live_by_weeks: number;
  description: string;
  preset_categories: string[];
  preset_ids: string[];
  seasonal_tags: string[];
  priority: number;
  event_date: string;
  year: number;
  start_creating: string;
  must_be_live: string;
  status: 'past' | 'must_be_live' | 'creating' | 'soon' | 'upcoming';
  days_until: number;
  product_count: number;
  presets_used: number;
  presets_total: number;
}

export interface CalendarEventPreset {
  id: string;
  name: string;
  category: string;
  category_name: string;
  difficulty: string;
  trending_score: number;
  tags: string[];
  is_used: boolean;
}

export async function getCalendarEvents(days: number = 90): Promise<{ events: SeasonalEvent[] }> {
  const response = await fetch(`${getApiUrl()}/calendar/upcoming?days=${days}`);
  if (!response.ok) {
    throw new Error('Failed to fetch calendar events');
  }
  return response.json();
}

export async function getCalendarEvent(eventId: string): Promise<SeasonalEvent> {
  const response = await fetch(`${getApiUrl()}/calendar/events/${eventId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch calendar event');
  }
  return response.json();
}

export async function getCalendarEventPresets(eventId: string): Promise<{ presets: CalendarEventPreset[] }> {
  const response = await fetch(`${getApiUrl()}/calendar/events/${eventId}/presets`);
  if (!response.ok) {
    throw new Error('Failed to fetch event presets');
  }
  return response.json();
}

export async function trackCalendarProduct(
  eventId: string,
  printifyProductId: string,
  presetId?: string
): Promise<void> {
  const response = await fetch(`${getApiUrl()}/calendar/events/${eventId}/track`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      printify_product_id: printifyProductId,
      preset_id: presetId,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to track product' }));
    throw new Error(error.detail || 'Failed to track product');
  }
}
