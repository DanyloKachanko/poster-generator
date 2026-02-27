import { authFetch } from './auth';

// API URL: prefer NEXT_PUBLIC_API_URL env var, fall back to current hostname
export function getApiUrl(): string {
  if (typeof window !== 'undefined') {
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl) return envUrl;
    // Dev fallback: use current hostname with backend port 8001
    return `http://${window.location.hostname}:8001`;
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
}

// Use authFetch for all API calls (adds Bearer token, handles 401)
const apiFetch = authFetch;

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
  ultra?: boolean;
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
  const response = await apiFetch(`${getApiUrl()}/styles`);
  if (!response.ok) {
    throw new Error('Failed to fetch styles');
  }
  return response.json();
}

export async function getModels(): Promise<ModelsResponse> {
  const response = await apiFetch(`${getApiUrl()}/models`);
  if (!response.ok) {
    throw new Error('Failed to fetch models');
  }
  return response.json();
}

export async function getSizes(): Promise<SizesResponse> {
  const response = await apiFetch(`${getApiUrl()}/sizes`);
  if (!response.ok) {
    throw new Error('Failed to fetch sizes');
  }
  return response.json();
}

export async function getDefaults(): Promise<DefaultsResponse> {
  const response = await apiFetch(`${getApiUrl()}/defaults`);
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
  negativePrompt: string | null = null,
  ultra: boolean = false
): Promise<GenerateResponse> {
  const response = await apiFetch(`${getApiUrl()}/generate`, {
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
      ultra,
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
  const response = await apiFetch(`${getApiUrl()}/generation/${generationId}`);
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
  archived: boolean = false,
  excludeStyle?: string
): Promise<HistoryResponse> {
  const params = new URLSearchParams();
  params.set('limit', limit.toString());
  params.set('offset', offset.toString());
  if (status) params.set('status', status);
  if (style) params.set('style', style);
  if (excludeStyle) params.set('exclude_style', excludeStyle);
  if (archived) params.set('archived', 'true');

  const response = await apiFetch(`${getApiUrl()}/history?${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch history');
  }
  return response.json();
}

export async function archiveGeneration(generationId: string): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/history/${generationId}/archive`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to archive');
  }
}

export async function restoreGeneration(generationId: string): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/history/${generationId}/restore`, {
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
  const response = await apiFetch(`${getApiUrl()}/export/sizes`);
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
  const response = await apiFetch(`${getApiUrl()}/export`, {
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
  const response = await apiFetch(`${getApiUrl()}/export/${generationName}/status`);
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
  const response = await apiFetch(`${getApiUrl()}/generate-listing`, {
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
  const response = await apiFetch(`${getApiUrl()}/regenerate-title`, {
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
  const response = await apiFetch(`${getApiUrl()}/regenerate-description`, {
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
  const response = await apiFetch(`${getApiUrl()}/regenerate-tags`, {
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
  const response = await apiFetch(`${getApiUrl()}/pricing?strategy=${strategy}`);
  if (!response.ok) {
    throw new Error('Failed to fetch pricing');
  }
  return response.json();
}

export async function getCredits(): Promise<CreditsResponse> {
  const response = await apiFetch(`${getApiUrl()}/credits`);
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
  const response = await apiFetch(`${getApiUrl()}/printify/status`);
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
  const response = await apiFetch(`${getApiUrl()}/printify/products?${params}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch products' }));
    throw new Error(error.detail || 'Failed to fetch products');
  }
  return response.json();
}

export async function getPrintifyProduct(productId: string): Promise<PrintifyProduct> {
  const response = await apiFetch(`${getApiUrl()}/printify/products/${productId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch product');
  }
  return response.json();
}

export async function publishPrintifyProduct(productId: string): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/printify/products/${productId}/publish`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to publish' }));
    throw new Error(error.detail || 'Failed to publish');
  }
}

export async function unpublishPrintifyProduct(productId: string): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/printify/products/${productId}/unpublish`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to unpublish' }));
    throw new Error(error.detail || 'Failed to unpublish');
  }
}

export async function deletePrintifyProduct(productId: string): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/printify/products/${productId}`, {
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
  const response = await apiFetch(`${getApiUrl()}/printify/products/${productId}`, {
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
  // Pre-generated listing data (skips AI re-generation on backend)
  listing_title?: string;
  listing_tags?: string[];
  listing_description?: string;
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
  request: CreateFullProductRequest,
  onStep?: (step: string) => void,
): Promise<CreateFullProductResponse> {
  // Start background task
  const startResp = await apiFetch(`${getApiUrl()}/create-full-product`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!startResp.ok) {
    const error = await startResp.json().catch(() => ({ detail: 'Failed to create product' }));
    throw new Error(error.detail || 'Failed to create product');
  }
  const { task_id } = await startResp.json();

  // Poll for completion
  while (true) {
    await new Promise((r) => setTimeout(r, 1500));
    const statusResp = await apiFetch(
      `${getApiUrl()}/create-full-product/status/${task_id}`
    );
    if (!statusResp.ok) {
      throw new Error('Failed to check product creation status');
    }
    const status = await statusResp.json();

    if (onStep && status.step) {
      onStep(status.step);
    }

    if (status.status === 'completed') {
      return status.result as CreateFullProductResponse;
    }
    if (status.status === 'failed') {
      throw new Error(status.error || 'Product creation failed');
    }
  }
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
  total_products: number;
  live_products: number;
  draft_products: number;
  deleted_products: number;
  products_with_views: number;
  products_no_views: number;
  avg_views: number;
  avg_favorites: number;
  fav_rate: number;
  best_performer: string | null;
  best_performer_views: number;
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
  const response = await apiFetch(`${getApiUrl()}/analytics`);
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
  const response = await apiFetch(`${getApiUrl()}/analytics`, {
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
  const response = await apiFetch(`${getApiUrl()}/analytics/${productId}/history`);
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
  const response = await apiFetch(`${getApiUrl()}/etsy/status`);
  if (!response.ok) {
    throw new Error('Failed to fetch Etsy status');
  }
  return response.json();
}

export async function getEtsyAuthUrl(): Promise<{ url: string }> {
  const response = await apiFetch(`${getApiUrl()}/etsy/auth-url`);
  if (!response.ok) {
    throw new Error('Failed to get Etsy auth URL');
  }
  return response.json();
}

export async function syncEtsyAnalytics(): Promise<EtsySyncResult> {
  const response = await apiFetch(`${getApiUrl()}/etsy/sync`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Sync failed' }));
    throw new Error(error.detail || 'Sync failed');
  }
  return response.json();
}

export async function disconnectEtsy(): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/etsy/disconnect`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to disconnect Etsy');
  }
}

// === Etsy Listing Management ===

export interface EtsyListingImage {
  listing_image_id: number;
  url_570xN: string;
  url_fullxfull: string;
  rank: number;
}

export interface EtsyListing {
  listing_id: number;
  title: string;
  description: string;
  tags: string[];
  materials: string[];
  state: string;
  views: number;
  num_favorers: number;
  price: { amount: number; divisor: number; currency_code: string };
  url: string;
  images?: EtsyListingImage[];
  creation_timestamp: number;
  last_modified_timestamp: number;
  who_made: string;
  when_made: string;
  is_supply: boolean;
  shop_section_id: number | null;
  shipping_profile_id: number | null;
  should_auto_renew: boolean;
  taxonomy_id: number | null;
}

export interface EtsyListingsResponse {
  listings: EtsyListing[];
  count: number;
  shop_id: string;
}

export interface UpdateEtsyListingPayload {
  title?: string;
  tags?: string[];
  description?: string;
  materials?: string[];
  who_made?: string;
  when_made?: string;
  is_supply?: boolean;
  shop_section_id?: number;
  shipping_profile_id?: number;
  should_auto_renew?: boolean;
  primary_color?: string;
  secondary_color?: string;
}

export const ETSY_COLORS = [
  'Beige', 'Black', 'Blue', 'Bronze', 'Brown', 'Clear', 'Copper', 'Gold',
  'Gray', 'Green', 'Orange', 'Pink', 'Purple', 'Rainbow', 'Red',
  'Rose gold', 'Silver', 'White', 'Yellow',
] as const;

export interface EtsyShopSection {
  shop_section_id: number;
  title: string;
  rank: number;
  active_listing_count: number;
}

export interface EtsyShippingProfile {
  shipping_profile_id: number;
  title: string;
  min_processing_days: number;
  max_processing_days: number;
}

export async function getEtsyShopSections(): Promise<{ results: EtsyShopSection[] }> {
  const response = await apiFetch(`${getApiUrl()}/etsy/shop-sections`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch sections' }));
    throw new Error(error.detail || 'Failed to fetch sections');
  }
  return response.json();
}

export async function getEtsyShippingProfiles(): Promise<{ results: EtsyShippingProfile[] }> {
  const response = await apiFetch(`${getApiUrl()}/etsy/shipping-profiles`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch profiles' }));
    throw new Error(error.detail || 'Failed to fetch profiles');
  }
  return response.json();
}

export interface BulkSeoResult {
  total: number;
  updated: number;
  failed: number;
  results: {
    listing_id: string;
    status: 'updated' | 'error';
    old_title?: string;
    new_title?: string;
    new_tags?: string[];
    error?: string;
  }[];
}

export async function getEtsyListings(): Promise<EtsyListingsResponse> {
  const response = await apiFetch(`${getApiUrl()}/etsy/listings`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch Etsy listings' }));
    throw new Error(error.detail || 'Failed to fetch Etsy listings');
  }
  return response.json();
}

export async function updateEtsyListing(
  listingId: string,
  payload: UpdateEtsyListingPayload
): Promise<EtsyListing> {
  const response = await apiFetch(`${getApiUrl()}/etsy/listings/${listingId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update listing' }));
    throw new Error(error.detail || 'Failed to update listing');
  }
  return response.json();
}

export async function getEtsyListingProperties(
  listingId: string
): Promise<{ colors: { primary_color: string | null; secondary_color: string | null } }> {
  const response = await apiFetch(`${getApiUrl()}/etsy/listings/${listingId}/properties`);
  if (!response.ok) return { colors: { primary_color: null, secondary_color: null } };
  return response.json();
}

export async function updateEtsyImagesAltTexts(
  listingId: string,
  altTexts: string[]
): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/etsy/listings/${listingId}/images/alt-texts`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alt_texts: altTexts }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update alt texts' }));
    throw new Error(error.detail || 'Failed to update alt texts');
  }
}

// === Etsy Listing Image Management ===

export async function getEtsyListingImages(
  listingId: string
): Promise<{ count: number; results: EtsyListingImage[] }> {
  const response = await apiFetch(`${getApiUrl()}/etsy/listings/${listingId}/images`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch images' }));
    throw new Error(error.detail || 'Failed to fetch images');
  }
  return response.json();
}

export async function uploadEtsyListingImage(
  listingId: string,
  file: File,
  rank?: number
): Promise<EtsyListingImage> {
  const formData = new FormData();
  formData.append('image', file);
  if (rank !== undefined) {
    formData.append('rank', String(rank));
  }
  const response = await apiFetch(`${getApiUrl()}/etsy/listings/${listingId}/images`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to upload image' }));
    throw new Error(error.detail || 'Failed to upload image');
  }
  return response.json();
}

export async function deleteEtsyListingImage(
  listingId: string,
  imageId: string
): Promise<void> {
  const response = await fetch(
    `${getApiUrl()}/etsy/listings/${listingId}/images/${imageId}`,
    { method: 'DELETE' }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete image' }));
    throw new Error(error.detail || 'Failed to delete image');
  }
}

export async function setEtsyListingImagePrimary(
  listingId: string,
  imageId: string
): Promise<EtsyListingImage> {
  const response = await fetch(
    `${getApiUrl()}/etsy/listings/${listingId}/images/${imageId}/set-primary`,
    { method: 'POST' }
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to set primary image' }));
    throw new Error(error.detail || 'Failed to set primary image');
  }
  return response.json();
}

export async function bulkRegenerateSeo(listingIds: string[]): Promise<BulkSeoResult> {
  const response = await apiFetch(`${getApiUrl()}/etsy/listings/bulk-seo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ listing_ids: listingIds }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Bulk SEO update failed' }));
    throw new Error(error.detail || 'Bulk SEO update failed');
  }
  return response.json();
}

export interface SeoSuggestion {
  title: string;
  tags: string[];
  description: string;
  tags_string: string;
  superstar_keyword: string;
}

export async function suggestSeo(
  title: string,
  tags: string[],
  description: string
): Promise<SeoSuggestion> {
  const response = await apiFetch(`${getApiUrl()}/etsy/listings/suggest-seo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, tags, description }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'SEO suggestion failed' }));
    throw new Error(error.detail || 'SEO suggestion failed');
  }
  return response.json();
}

// === Printify Mockups ===

export interface MockupImage {
  src: string;
  is_default: boolean;
  position: string;
  variant_ids: number[];
  size: string;
  camera_label: string;
}

export interface MockupProduct {
  printify_id: string;
  title: string;
  etsy_listing_id: string | null;
  etsy_url: string | null;
  images: MockupImage[];
}

export async function getMockups(): Promise<MockupProduct[]> {
  const response = await apiFetch(`${getApiUrl()}/printify/mockups`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch mockups' }));
    throw new Error(error.detail || 'Failed to fetch mockups');
  }
  return response.json();
}

// === AI Fill (vision-based SEO generation) ===

export interface AIFillRequest {
  image_url: string;
  current_title?: string;
  niche?: string;
  enabled_sizes?: string[];
}

export interface AIFillResponse {
  title: string;
  tags: string[];
  description: string;
  superstar_keyword: string;
  materials: string[];
  primary_color: string;
  secondary_color: string;
  alt_texts: string[];
  validation_errors: string[];
  is_valid: boolean;
}

export async function aiFillListing(request: AIFillRequest): Promise<AIFillResponse> {
  const response = await apiFetch(`${getApiUrl()}/etsy/listings/ai-fill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'AI Fill failed' }));
    throw new Error(error.detail || 'AI Fill failed');
  }
  return response.json();
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
  const response = await apiFetch(`${getApiUrl()}/presets/${presetId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch preset');
  }
  return response.json();
}

export async function getPresets(category?: string): Promise<PresetsResponse> {
  const params = category ? `?category=${category}` : '';
  const response = await apiFetch(`${getApiUrl()}/presets${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch presets');
  }
  return response.json();
}

export async function getTrendingPresets(limit: number = 10): Promise<{ presets: PosterPreset[] }> {
  const response = await apiFetch(`${getApiUrl()}/presets/trending?limit=${limit}`);
  if (!response.ok) {
    throw new Error('Failed to fetch trending presets');
  }
  return response.json();
}

export async function getCategories(): Promise<Record<string, PresetCategory>> {
  const response = await apiFetch(`${getApiUrl()}/categories`);
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
  const response = await apiFetch(`${getApiUrl()}/providers`);
  if (!response.ok) {
    throw new Error('Failed to fetch providers');
  }
  return response.json();
}

export async function compareProviders(size: string = '18x24'): Promise<{ size: string; providers: ProviderComparison[] }> {
  const response = await apiFetch(`${getApiUrl()}/providers/compare?size=${size}`);
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
  conversion_rate: number;
  trends_7d: {
    views: number;
    orders: number;
    revenue: number;
  };
  daily_views: { date: string; views: number }[];
  top_products: {
    printify_product_id: string;
    total_views: number;
    total_favorites: number;
    total_orders: number;
    total_revenue_cents: number;
  }[];
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await apiFetch(`${getApiUrl()}/dashboard/stats`);
  if (!response.ok) {
    throw new Error('Failed to fetch dashboard stats');
  }
  return response.json();
}

// === Product Manager ===

export interface ProductManagerItem {
  printify_product_id: string;
  title: string;
  thumbnail: string | null;
  status: string;
  min_price: number;
  max_price: number;
  etsy_url: string | null;
  etsy_listing_id: string | null;
  total_views: number;
  total_favorites: number;
  total_orders: number;
  total_revenue_cents: number;
  etsy_title: string;
  etsy_tags: string[];
  etsy_description: string;
  etsy_materials: string[];
  created_at: string;
}

export interface ProductManagerResponse {
  products: ProductManagerItem[];
}

export async function getProductManagerData(): Promise<ProductManagerResponse> {
  const response = await apiFetch(`${getApiUrl()}/products/manager`);
  if (!response.ok) {
    throw new Error('Failed to fetch product manager data');
  }
  return response.json();
}

export async function syncEtsyOrders(): Promise<{ synced: number; date: string }> {
  const response = await apiFetch(`${getApiUrl()}/etsy/sync-orders`, { method: 'POST' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Order sync failed' }));
    throw new Error(error.detail || 'Order sync failed');
  }
  return response.json();
}

export async function republishPrintifyProduct(productId: string): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/printify/products/${productId}/republish`, {
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
  const response = await apiFetch(`${getApiUrl()}/library/categories`);
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
  const response = await apiFetch(`${getApiUrl()}/library/prompts${qs}`);
  if (!response.ok) {
    throw new Error('Failed to fetch library prompts');
  }
  return response.json();
}

export async function getLibraryPrompt(promptId: string): Promise<LibraryPrompt> {
  const response = await apiFetch(`${getApiUrl()}/library/prompts/${promptId}`);
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
  const response = await apiFetch(`${getApiUrl()}/batch/generate`, {
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
  const response = await apiFetch(`${getApiUrl()}/batch/${batchId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch batch status');
  }
  return response.json();
}

export async function cancelBatch(batchId: string): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/batch/${batchId}/cancel`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to cancel batch' }));
    throw new Error(error.detail || 'Failed to cancel batch');
  }
}

export async function listBatches(): Promise<{ batches: BatchStatus[] }> {
  const response = await apiFetch(`${getApiUrl()}/batch`);
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
  const response = await apiFetch(`${getApiUrl()}/pipeline/auto-product`, {
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
  const response = await apiFetch(`${getApiUrl()}/dpi/analyze?${params}`);
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
  const response = await apiFetch(`${getApiUrl()}/printify/fix-existing-products?dry_run=${dryRun}`, {
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
  preferred_primary_camera: string;
  default_shipping_profile_id: number | null;
  default_shop_section_id: number | null;
  updated_at: string | null;
}

export async function getScheduleQueue(status?: string): Promise<ScheduledProduct[]> {
  const params = status ? `?status=${status}` : '';
  const response = await apiFetch(`${getApiUrl()}/schedule/queue${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch schedule queue');
  }
  return response.json();
}

export async function getScheduleStats(): Promise<ScheduleStats> {
  const response = await apiFetch(`${getApiUrl()}/schedule/stats`);
  if (!response.ok) {
    throw new Error('Failed to fetch schedule stats');
  }
  return response.json();
}

export async function getScheduleSettings(): Promise<ScheduleSettings> {
  const response = await apiFetch(`${getApiUrl()}/schedule/settings`);
  if (!response.ok) {
    throw new Error('Failed to fetch schedule settings');
  }
  return response.json();
}

export async function updateScheduleSettings(settings: {
  publish_times: string[];
  timezone?: string;
  enabled?: boolean;
  preferred_primary_camera?: string;
  default_shipping_profile_id?: number | null;
  default_shop_section_id?: number | null;
}): Promise<ScheduleSettings> {
  const response = await apiFetch(`${getApiUrl()}/schedule/settings`, {
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
  const response = await apiFetch(`${getApiUrl()}/schedule/publish-now/${productId}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to publish' }));
    throw new Error(error.detail || 'Failed to publish');
  }
}

export async function addToSchedule(printifyProductId: string, title: string, scheduledPublishAt?: string): Promise<ScheduledProduct> {
  const body: Record<string, string> = { printify_product_id: printifyProductId, title };
  if (scheduledPublishAt) body.scheduled_publish_at = scheduledPublishAt;
  const response = await apiFetch(`${getApiUrl()}/schedule/add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to add to schedule' }));
    throw new Error(error.detail || 'Failed to add to schedule');
  }
  return response.json();
}

export async function removeFromSchedule(productId: string): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/schedule/${productId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to remove from schedule' }));
    throw new Error(error.detail || 'Failed to remove from schedule');
  }
}

// === Batch scheduling + retry ===

export async function addToScheduleBatch(productIds: string[]): Promise<{
  scheduled: number;
  failed: number;
  results: Array<{ printify_product_id: string; title?: string; scheduled_publish_at?: string; error?: string }>;
}> {
  const response = await apiFetch(`${getApiUrl()}/schedule/add-batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_ids: productIds }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to batch schedule' }));
    throw new Error(error.detail || 'Failed to batch schedule');
  }
  return response.json();
}

export async function retrySchedule(productId: string): Promise<{
  printify_product_id: string;
  status: string;
  scheduled_publish_at: string;
}> {
  const response = await apiFetch(`${getApiUrl()}/schedule/retry/${productId}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to retry' }));
    throw new Error(error.detail || 'Failed to retry');
  }
  return response.json();
}

// === Products (local DB) ===

export interface SourceImage {
  id: number;
  generation_id: string;
  url: string;
  mockup_url: string | null;
  mockup_status: string | null;
}

export interface TrackedProduct {
  id: number;
  printify_product_id: string;
  etsy_listing_id: string | null;
  title: string;
  description: string | null;
  tags: string[] | null;
  image_url: string | null;
  pricing_strategy: string;
  enabled_sizes: string[] | null;
  status: string;
  etsy_metadata: Record<string, unknown>;
  dovshop_product_id: string | null;
  source_image_id: number | null;
  source_image?: SourceImage;
  created_at: string;
  updated_at: string;
}

export async function getTrackedProducts(status?: string, limit: number = 50, offset: number = 0): Promise<{
  items: TrackedProduct[];
  total: number;
  limit: number;
  offset: number;
}> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  params.set('limit', String(limit));
  params.set('offset', String(offset));
  const response = await apiFetch(`${getApiUrl()}/products?${params}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch products' }));
    throw new Error(error.detail || 'Failed to fetch products');
  }
  return response.json();
}

export async function getTrackedProduct(printifyProductId: string): Promise<TrackedProduct> {
  const response = await apiFetch(`${getApiUrl()}/products/${printifyProductId}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Product not found' }));
    throw new Error(error.detail || 'Product not found');
  }
  return response.json();
}

// === Product mockups ===

export interface ProductMockup {
  src: string;
  is_default: boolean;
  position: string;
  variant_ids: number[];
  camera_label: string;
  size: string;
}

export async function getProductMockups(printifyProductId: string): Promise<{
  printify_product_id: string;
  title: string;
  mockups: ProductMockup[];
}> {
  const response = await apiFetch(`${getApiUrl()}/products/${printifyProductId}/mockups`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch mockups' }));
    throw new Error(error.detail || 'Failed to fetch mockups');
  }
  return response.json();
}

export async function setProductPrimaryMockup(printifyProductId: string, mockupUrl: string): Promise<{
  ok: boolean;
  etsy_listing_id: string;
  image_id: number;
}> {
  const response = await apiFetch(`${getApiUrl()}/products/${printifyProductId}/set-primary-mockup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mockup_url: mockupUrl }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to set primary mockup' }));
    throw new Error(error.detail || 'Failed to set primary mockup');
  }
  return response.json();
}

export async function uploadProductMockup(printifyProductId: string, file: File, rank?: number): Promise<{
  ok: boolean;
  etsy_listing_id: string;
  image_id: number;
  rank: number | null;
}> {
  const formData = new FormData();
  formData.append('image', file);
  if (rank !== undefined) formData.append('rank', String(rank));
  const response = await apiFetch(`${getApiUrl()}/products/${printifyProductId}/upload-mockup`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to upload mockup' }));
    throw new Error(error.detail || 'Failed to upload mockup');
  }
  return response.json();
}

export async function setPreferredMockup(printifyProductId: string, mockupUrl: string | null): Promise<{
  printify_product_id: string;
  preferred_mockup_url: string | null;
}> {
  const response = await apiFetch(`${getApiUrl()}/products/${printifyProductId}/preferred-mockup`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mockup_url: mockupUrl }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to set preferred mockup' }));
    throw new Error(error.detail || 'Failed to set preferred mockup');
  }
  return response.json();
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
  const response = await apiFetch(`${getApiUrl()}/calendar/upcoming?days=${days}`);
  if (!response.ok) {
    throw new Error('Failed to fetch calendar events');
  }
  return response.json();
}

export async function getCalendarEvent(eventId: string): Promise<SeasonalEvent> {
  const response = await apiFetch(`${getApiUrl()}/calendar/events/${eventId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch calendar event');
  }
  return response.json();
}

export async function getCalendarEventPresets(eventId: string): Promise<{ presets: CalendarEventPreset[] }> {
  const response = await apiFetch(`${getApiUrl()}/calendar/events/${eventId}/presets`);
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
  const response = await apiFetch(`${getApiUrl()}/calendar/events/${eventId}/track`, {
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

// === Custom Mockup Generator ===

export interface MockupScene {
  name: string;
}

export interface MockupRatio {
  name: string;
}

export interface MockupModel {
  name: string;
  description: string;
}

export interface MockupStyle {
  name: string;
  description: string;
}

export interface MockupScenesResponse {
  scenes: Record<string, MockupScene>;
  ratios: Record<string, MockupRatio>;
  models: Record<string, MockupModel>;
  styles: Record<string, MockupStyle>;
}

export async function getMockupScenes(): Promise<MockupScenesResponse> {
  const response = await apiFetch(`${getApiUrl()}/mockups/scenes`);
  if (!response.ok) {
    throw new Error('Failed to fetch mockup scenes');
  }
  return response.json();
}

export async function generateMockupScene(
  sceneType: string,
  ratio: string = '4:5',
  customPrompt?: string,
  numImages: number = 2,
  modelId?: string,
  style?: string
): Promise<{ generation_id: string; status: string; scene_type: string; ratio: string; width: number; height: number }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/generate-scene`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scene_type: sceneType,
      ratio,
      custom_prompt: customPrompt || undefined,
      num_images: numImages,
      model_id: modelId || undefined,
      style: style || undefined,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Scene generation failed' }));
    throw new Error(error.detail || 'Scene generation failed');
  }
  return response.json();
}

// --- Mockup Templates ---

export interface MockupTemplate {
  id: number;
  name: string;
  scene_url: string;
  scene_width: number;
  scene_height: number;
  corners: number[][]; // [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
  is_active?: boolean;
  blend_mode?: string; // "normal" | "multiply"
  created_at: string;
}

export async function getMockupTemplates(): Promise<MockupTemplate[]> {
  const response = await apiFetch(`${getApiUrl()}/mockups/templates`);
  if (!response.ok) throw new Error('Failed to fetch templates');
  return response.json();
}

export async function saveMockupTemplate(
  name: string,
  sceneUrl: string,
  sceneWidth: number,
  sceneHeight: number,
  corners: number[][],
  blendMode: string = 'normal'
): Promise<MockupTemplate> {
  const response = await apiFetch(`${getApiUrl()}/mockups/templates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      scene_url: sceneUrl,
      scene_width: sceneWidth,
      scene_height: sceneHeight,
      corners,
      blend_mode: blendMode,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to save template' }));
    throw new Error(error.detail || 'Failed to save template');
  }
  return response.json();
}

export async function deleteMockupTemplate(id: number): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/mockups/templates/${id}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('Failed to delete template');
}

export async function updateMockupTemplate(
  id: number,
  name: string,
  sceneUrl: string,
  sceneWidth: number,
  sceneHeight: number,
  corners: number[][],
  blendMode: string = 'normal'
): Promise<MockupTemplate> {
  const response = await apiFetch(`${getApiUrl()}/mockups/templates/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      scene_url: sceneUrl,
      scene_width: sceneWidth,
      scene_height: sceneHeight,
      corners,
      blend_mode: blendMode,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update template' }));
    throw new Error(error.detail || 'Failed to update template');
  }
  return response.json();
}

export async function uploadMockupTemplate(
  file: File,
  name: string,
  sceneWidth: number,
  sceneHeight: number,
  corners: number[][]
): Promise<MockupTemplate> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name);
  formData.append('scene_width', sceneWidth.toString());
  formData.append('scene_height', sceneHeight.toString());
  formData.append('corners', JSON.stringify(corners));

  const response = await apiFetch(`${getApiUrl()}/mockups/templates/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to upload template' }));
    throw new Error(error.detail || 'Failed to upload template');
  }
  return response.json();
}

export async function composeMockup(
  templateId: number,
  posterUrl: string,
  fillMode: 'stretch' | 'fit' | 'fill' = 'fill',
  colorGrade: string = 'none'
): Promise<Blob> {
  const response = await apiFetch(`${getApiUrl()}/mockups/compose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      template_id: templateId,
      poster_url: posterUrl,
      fill_mode: fillMode,
      color_grade: colorGrade,
    }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Composition failed' }));
    throw new Error(error.detail || 'Composition failed');
  }
  return response.blob();
}

export interface DefaultTemplateResponse {
  default_template_id: number | null;
  template: MockupTemplate | null;
}

export async function getDefaultMockupTemplate(): Promise<DefaultTemplateResponse> {
  const response = await apiFetch(`${getApiUrl()}/mockups/settings/default-template`);
  if (!response.ok) throw new Error('Failed to get default template');
  return response.json();
}

export async function setDefaultMockupTemplate(templateId: number): Promise<{ success: boolean; message: string }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/settings/default-template/${templateId}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to set default template' }));
    throw new Error(error.detail || 'Failed to set default template');
  }
  return response.json();
}

// === Active Templates ===

export async function getActiveMockupTemplates(): Promise<{ active_templates: MockupTemplate[]; count: number }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/settings/active-templates`);
  if (!response.ok) throw new Error('Failed to fetch active templates');
  return response.json();
}

export async function toggleTemplateActive(templateId: number): Promise<{ template_id: number; is_active: boolean }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/templates/${templateId}/toggle-active`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to toggle template');
  return response.json();
}

export interface ComposeAllResult {
  previews: { template_id: number; preview_url: string }[];
  poster_url: string;
}

export async function composeAllMockups(posterUrl: string, fillMode: string = 'fill'): Promise<ComposeAllResult> {
  const response = await apiFetch(`${getApiUrl()}/mockups/compose-all`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ poster_url: posterUrl, fill_mode: fillMode }),
  });
  if (!response.ok) throw new Error('Failed to compose all mockups');
  return response.json();
}

// === Mockup Packs ===

export interface MockupPack {
  id: number;
  name: string;
  template_count: number;
  color_grade: string;
  templates?: MockupTemplate[];
  created_at: string;
}

export async function getMockupPacks(): Promise<{ packs: MockupPack[] }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/packs`);
  if (!response.ok) throw new Error('Failed to fetch packs');
  return response.json();
}

export async function getMockupPack(packId: number): Promise<MockupPack> {
  const response = await apiFetch(`${getApiUrl()}/mockups/packs/${packId}`);
  if (!response.ok) throw new Error('Failed to fetch pack');
  return response.json();
}

export async function createMockupPack(name: string, templateIds: number[] = [], colorGrade: string = 'none'): Promise<MockupPack> {
  const response = await apiFetch(`${getApiUrl()}/mockups/packs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, template_ids: templateIds, color_grade: colorGrade }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create pack' }));
    throw new Error(error.detail || 'Failed to create pack');
  }
  return response.json();
}

export async function updateMockupPack(packId: number, name: string, templateIds: number[], colorGrade: string = 'none'): Promise<MockupPack> {
  const response = await apiFetch(`${getApiUrl()}/mockups/packs/${packId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, template_ids: templateIds, color_grade: colorGrade }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update pack' }));
    throw new Error(error.detail || 'Failed to update pack');
  }
  return response.json();
}

export async function getColorGrades(): Promise<{ grades: { id: string; name: string }[] }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/color-grades`);
  if (!response.ok) throw new Error('Failed to fetch color grades');
  return response.json();
}

export async function deleteMockupPack(packId: number): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/mockups/packs/${packId}`, { method: 'DELETE' });
  if (!response.ok) throw new Error('Failed to delete pack');
}

export async function composeByPack(posterUrl: string, packId: number, fillMode: string = 'fill'): Promise<ComposeAllResult & { pack_id: number }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/compose-by-pack`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ poster_url: posterUrl, pack_id: packId, fill_mode: fillMode }),
  });
  if (!response.ok) throw new Error('Failed to compose by pack');
  return response.json();
}

export async function reapplyApprovedMockups(packId?: number): Promise<{ started: boolean; total: number; message: string }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/workflow/reapply-approved`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(packId ? { pack_id: packId } : {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Reapply failed' }));
    throw new Error(error.detail || 'Reapply failed');
  }
  return response.json();
}

export async function getReapplyStatus(): Promise<{ running: boolean; total: number; done: number; ok: number; errors: string[] }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/workflow/reapply-status`);
  if (!response.ok) throw new Error('Failed to get status');
  return response.json();
}

export async function reapplyProductMockups(printifyProductId: string, packId?: number): Promise<{ success: boolean; mockups_composed: number; etsy_upload: Record<string, unknown> }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/workflow/reapply-product/${printifyProductId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(packId ? { pack_id: packId } : {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Reapply failed' }));
    throw new Error(error.detail || 'Reapply failed');
  }
  return response.json();
}

// === Competitor Intelligence ===

export interface CompetitorShop {
  id: number;
  etsy_shop_id: string;
  shop_name: string;
  shop_url: string;
  icon_url: string | null;
  total_listings: number;
  rating: number;
  total_reviews: number;
  country: string | null;
  is_active: number;
  created_at: string;
  updated_at: string;
}

export interface CompetitorSearchResult {
  shop_id: string;
  shop_name: string;
  icon_url: string | null;
  rating: number;
  total_reviews: number;
  listing_count: number;
  already_tracked: boolean;
}

export interface CompetitorListing {
  id: number;
  competitor_id: number;
  etsy_listing_id: string;
  title: string;
  description: string;
  tags: string[];
  price_cents: number;
  currency: string;
  views: number;
  favorites: number;
  image_url: string | null;
  created_at: string;
  synced_at: string;
}

export interface CompetitorDetail extends CompetitorShop {
  listings_count: number;
  top_tags: string[];
  last_snapshot_date: string | null;
}

export interface CompetitorSyncResult {
  synced: number;
  total_listings: number;
  date: string;
}

export async function searchCompetitorShops(keywords: string): Promise<CompetitorSearchResult[]> {
  const response = await apiFetch(`${getApiUrl()}/competitors/search?keywords=${encodeURIComponent(keywords)}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Search failed' }));
    throw new Error(error.detail || 'Search failed');
  }
  const data = await response.json();
  return data.shops;
}

export async function getCompetitors(): Promise<{ competitors: CompetitorShop[]; count: number }> {
  const response = await apiFetch(`${getApiUrl()}/competitors`);
  if (!response.ok) {
    throw new Error('Failed to fetch competitors');
  }
  return response.json();
}

export async function getCompetitor(id: number): Promise<CompetitorDetail> {
  const response = await apiFetch(`${getApiUrl()}/competitors/${id}`);
  if (!response.ok) {
    throw new Error('Failed to fetch competitor');
  }
  return response.json();
}

export async function addCompetitor(etsyShopId: string): Promise<CompetitorShop> {
  const response = await apiFetch(`${getApiUrl()}/competitors`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ etsy_shop_id: etsyShopId }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to add competitor' }));
    throw new Error(error.detail || 'Failed to add competitor');
  }
  return response.json();
}

export async function deleteCompetitor(id: number): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/competitors/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete competitor' }));
    throw new Error(error.detail || 'Failed to delete competitor');
  }
}

export async function syncCompetitor(id: number): Promise<CompetitorSyncResult> {
  const response = await apiFetch(`${getApiUrl()}/competitors/${id}/sync`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Sync failed' }));
    throw new Error(error.detail || 'Sync failed');
  }
  return response.json();
}

// === Custom Presets types and functions ===

export interface CustomPresetSummary {
  id: string;
  name: string;
  model: string;
  prompt_count: number;
  generated_count: number;
  settings: Record<string, unknown>;
}

export interface CustomPresetPrompt {
  id: string;
  name?: string;
  prompt: string;
  type?: 'single' | 'diptych';
  generation_id: string | null;
  images: { id: string; url: string }[];
}

export interface CustomPreset {
  name: string;
  model: string;
  suffix: string;
  negative_prompt: string;
  settings: Record<string, unknown>;
  prompts: CustomPresetPrompt[];
}

export interface PresetJobStatus {
  job_id: string;
  preset_id: string;
  status: string;
  total: number;
  completed: number;
  failed: number;
  current_prompt_id: string | null;
  items: Record<string, {
    prompt_id: string;
    prompt_name: string;
    status: string;
    generation_id: string | null;
    images: { id: string; url: string }[];
    error: string | null;
  }>;
}

export async function getCustomPresets(): Promise<{ presets: CustomPresetSummary[] }> {
  const response = await apiFetch(`${getApiUrl()}/custom-presets`);
  if (!response.ok) throw new Error('Failed to fetch custom presets');
  return response.json();
}

export async function getCustomPreset(presetId: string): Promise<CustomPreset> {
  const response = await apiFetch(`${getApiUrl()}/custom-presets/${presetId}`);
  if (!response.ok) throw new Error('Failed to fetch custom preset');
  return response.json();
}

export async function uploadCustomPreset(file: File): Promise<{ preset_id: string; name: string }> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiFetch(`${getApiUrl()}/custom-presets/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(error.detail || 'Upload failed');
  }
  return response.json();
}

export async function deleteCustomPreset(presetId: string): Promise<void> {
  const response = await apiFetch(`${getApiUrl()}/custom-presets/${presetId}`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to delete preset');
}

export async function generatePresetPrompt(
  presetId: string,
  promptId: string
): Promise<{ generation_id: string; prompt_id: string; status: string; images: { id: string; url: string }[] }> {
  const response = await apiFetch(`${getApiUrl()}/custom-presets/${presetId}/generate/${promptId}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Generation failed' }));
    throw new Error(error.detail || 'Generation failed');
  }
  return response.json();
}

export async function generateAllPresetPrompts(presetId: string): Promise<{ job_id: string }> {
  const response = await apiFetch(`${getApiUrl()}/custom-presets/${presetId}/generate-all`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Batch start failed' }));
    throw new Error(error.detail || 'Batch start failed');
  }
  return response.json();
}

export async function getPresetJobStatus(jobId: string): Promise<PresetJobStatus> {
  const response = await apiFetch(`${getApiUrl()}/custom-presets/jobs/${jobId}`);
  if (!response.ok) throw new Error('Failed to fetch job status');
  return response.json();
}

export async function getCompetitorListings(
  id: number,
  sortBy: string = 'favorites',
  sortDir: string = 'desc',
  limit: number = 50,
  offset: number = 0
): Promise<{ listings: CompetitorListing[]; total: number }> {
  const params = new URLSearchParams({
    sort_by: sortBy,
    sort_dir: sortDir,
    limit: limit.toString(),
    offset: offset.toString(),
  });
  const response = await apiFetch(`${getApiUrl()}/competitors/${id}/listings?${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch competitor listings');
  }
  return response.json();
}

// === DovShop Integration types and functions ===

export interface DovShopStatus {
  configured: boolean;
  connected: boolean;
  info?: Record<string, unknown>;
  error?: string;
  message?: string;
}

export interface DovShopProduct {
  id: string;
  title: string;
  description?: string;
  price: number;
  image_url: string;
  images?: string[];
  tags?: string[];
  created_at: string;
  slug?: string;
  etsy_url?: string;
  printify_id?: string;
  style?: string;
  featured?: boolean;
  collection?: { id: number; name: string; slug: string } | null;
  categories?: string[];
}

export interface DovShopCollection {
  id: string;
  name: string;
  description: string;
  cover_url?: string;
  product_count?: number;
  created_at?: string;
}

export interface PushProductToDovShopRequest {
  printify_product_id: string;
  title?: string;
  description?: string;
  price?: number;
  tags?: string[];
}

export interface PushProductToDovShopResponse {
  success: boolean;
  dovshop_product_id?: string;
  dovshop_product?: DovShopProduct;
  message: string;
}

export interface CreateDovShopCollectionRequest {
  name: string;
  description?: string;
  cover_url?: string;
}

export async function getDovShopStatus(): Promise<DovShopStatus> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/status`);
  if (!response.ok) {
    throw new Error('Failed to get DovShop status');
  }
  return response.json();
}

export async function getDovShopProducts(): Promise<{ products: DovShopProduct[] }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/products`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch DovShop products' }));
    throw new Error(error.detail || 'Failed to fetch DovShop products');
  }
  return response.json();
}

export async function pushProductToDovShop(data: PushProductToDovShopRequest): Promise<PushProductToDovShopResponse> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/push`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to push product to DovShop' }));
    throw new Error(error.detail || 'Failed to push product to DovShop');
  }
  return response.json();
}

export async function deleteDovShopProduct(productId: string): Promise<{ success: boolean; message: string }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/products/${productId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete product from DovShop' }));
    throw new Error(error.detail || 'Failed to delete product from DovShop');
  }
  return response.json();
}

export async function getDovShopCollections(): Promise<{ collections: DovShopCollection[] }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/collections`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch DovShop collections' }));
    throw new Error(error.detail || 'Failed to fetch DovShop collections');
  }
  return response.json();
}

export async function createDovShopCollection(data: CreateDovShopCollectionRequest): Promise<{ success: boolean; collection: DovShopCollection; message: string }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/collections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create DovShop collection' }));
    throw new Error(error.detail || 'Failed to create DovShop collection');
  }
  return response.json();
}

export async function deleteDovShopCollection(collectionId: string): Promise<{ success: boolean; message: string }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/collections/${collectionId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to delete DovShop collection' }));
    throw new Error(error.detail || 'Failed to delete DovShop collection');
  }
  return response.json();
}

// --- DovShop Sync ---

export interface DovShopSyncResponse {
  total: number;
  created: number;
  updated: number;
  errors: { printify_id: string; error: string }[];
  message: string;
}

export async function syncAllToDovShop(): Promise<DovShopSyncResponse> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/sync`, { method: 'POST' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Sync failed' }));
    throw new Error(error.detail || 'Sync failed');
  }
  return response.json();
}

// --- DovShop AI ---

export interface DovShopEnrichResult {
  categories: string[];
  collection_name: string | null;
  seo_description: string;
  featured: boolean;
}

export interface DovShopStrategyResult {
  new_collections: { name: string; description: string; poster_ids: number[] }[];
  feature_recommendations: { id: number; title: string; reason: string }[];
  category_gaps: { slug: string; suggestion: string }[];
  seo_improvements: { id: number; title: string; suggested_desc: string }[];
  summary: string;
}

export interface DovShopStrategyHistoryItem {
  id: number;
  result: DovShopStrategyResult;
  product_count: number;
  created_at: string;
}

export async function getDovShopAIEnrich(printifyProductId: string): Promise<DovShopEnrichResult> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/ai-enrich`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ printify_product_id: printifyProductId }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'AI enrichment failed' }));
    throw new Error(error.detail || 'AI enrichment failed');
  }
  return response.json();
}

export async function getDovShopAIStrategy(): Promise<DovShopStrategyResult> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/ai-strategy`, { method: 'POST' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Strategy analysis failed' }));
    throw new Error(error.detail || 'Strategy analysis failed');
  }
  return response.json();
}

export async function getDovShopStrategyLatest(): Promise<DovShopStrategyHistoryItem | null> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/ai-strategy/latest`);
  if (!response.ok) return null;
  const data = await response.json();
  return data.item || null;
}

export async function getDovShopStrategyHistory(limit: number = 20): Promise<DovShopStrategyHistoryItem[]> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/ai-strategy/history?limit=${limit}`);
  if (!response.ok) return [];
  const data = await response.json();
  return data.items || [];
}

export async function applyDovShopCollection(data: { name: string; description?: string; poster_ids?: number[] }): Promise<{ success: boolean; collection_id: number; assigned: number }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/apply-collection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error('Failed to apply collection');
  return response.json();
}

export async function applyDovShopFeature(posterId: number, featured: boolean): Promise<{ success: boolean }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/apply-feature`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ poster_id: posterId, featured }),
  });
  if (!response.ok) throw new Error('Failed to apply feature');
  return response.json();
}

export async function applyDovShopSeo(posterId: number, description: string): Promise<{ success: boolean }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/apply-seo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ poster_id: posterId, description }),
  });
  if (!response.ok) throw new Error('Failed to apply SEO');
  return response.json();
}

// === DovShop Mockup Management ===

export interface DovShopMockup {
  id: number;
  template_id: number;
  rank: number;
  is_included: boolean;
  dovshop_included: boolean;
  dovshop_primary: boolean;
  thumbnail_url: string;
}

export async function getProductMockupsForDovShop(printifyProductId: string): Promise<{ mockups: DovShopMockup[]; printify_product_id: string }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/product-mockups/${printifyProductId}`);
  if (!response.ok) throw new Error('Failed to fetch product mockups');
  return response.json();
}

export async function setDovShopPrimary(mockupId: number): Promise<{ mockup_id: number; dovshop_primary: boolean }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/workflow/set-dovshop-primary/${mockupId}`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to set primary mockup');
  return response.json();
}

export async function toggleDovShopMockup(mockupId: number, included: boolean): Promise<{ mockup_id: number; dovshop_included: boolean }> {
  const response = await apiFetch(`${getApiUrl()}/mockups/workflow/toggle-dovshop-mockup/${mockupId}?dovshop_included=${included}`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to toggle mockup');
  return response.json();
}

export async function updateDovShopProductImages(printifyProductId: string): Promise<{ success: boolean; image_count: number }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/update-product-images/${printifyProductId}`, {
    method: 'POST',
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to update images' }));
    throw new Error(error.detail || 'Failed to update images');
  }
  return response.json();
}

export async function assignPackPattern(startOffset: number = 0): Promise<{ total: number; updated: number }> {
  const response = await apiFetch(`${getApiUrl()}/dovshop/assign-pack-pattern`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_offset: startOffset }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to assign pattern' }));
    throw new Error(error.detail || 'Failed to assign pattern');
  }
  return response.json();
}


// === Strategy ===

export interface StrategyPlan {
  id: number;
  name: string;
  status: 'draft' | 'executing' | 'completed';
  total_items: number;
  done_items: number;
  created_at: string;
  updated_at: string;
}

export interface StrategyItem {
  id: number;
  plan_id: number;
  prompt: string;
  description: string;
  style: string;
  preset: string;
  model_id: string;
  size_id: string;
  title_hint: string;
  status: 'planned' | 'generating' | 'generated' | 'product_created' | 'skipped';
  generation_id: string | null;
  printify_product_id: string | null;
  sort_order: number;
  created_at: string;
}

export interface StrategyPlanDetail extends StrategyPlan {
  items: StrategyItem[];
}

export interface StrategyCoverage {
  total_combinations: number;
  covered: number;
  products: number;
  coverage_percent: number;
}

export interface ExecutionStatus {
  status: string;
  step: number;
  total: number;
  completed: number;
  current_item: number | null;
  current_title: string | null;
  errors: Array<{ item_id: number; error: string }>;
}

export async function getStrategyPlans(): Promise<StrategyPlan[]> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans`);
  if (!resp.ok) throw new Error('Failed to fetch plans');
  return resp.json();
}

export async function getStrategyPlan(planId: number): Promise<StrategyPlanDetail> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans/${planId}`);
  if (!resp.ok) throw new Error('Failed to fetch plan');
  return resp.json();
}

export async function createStrategyPlan(name: string): Promise<StrategyPlan> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!resp.ok) throw new Error('Failed to create plan');
  return resp.json();
}

export async function deleteStrategyPlan(planId: number): Promise<void> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans/${planId}`, { method: 'DELETE' });
  if (!resp.ok) throw new Error('Failed to delete plan');
}

export async function generateStrategyPlan(name: string, count: number = 15): Promise<StrategyPlanDetail> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/generate-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, count }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'AI generation failed' }));
    throw new Error(err.detail || 'AI generation failed');
  }
  return resp.json();
}

export async function updateStrategyItem(
  itemId: number,
  data: Partial<Pick<StrategyItem, 'prompt' | 'description' | 'style' | 'preset' | 'model_id' | 'size_id' | 'title_hint' | 'sort_order' | 'status'>>,
): Promise<StrategyItem> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/items/${itemId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error('Failed to update item');
  return resp.json();
}

export async function deleteStrategyItem(itemId: number): Promise<void> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/items/${itemId}`, { method: 'DELETE' });
  if (!resp.ok) throw new Error('Failed to delete item');
}

export async function executeStrategyPlan(planId: number): Promise<{ task_id: string; total_items: number }> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/plans/${planId}/execute`, { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Execution failed' }));
    throw new Error(err.detail || 'Execution failed');
  }
  return resp.json();
}

export async function getExecutionStatus(taskId: string): Promise<ExecutionStatus> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/execute/status/${taskId}`);
  if (!resp.ok) throw new Error('Failed to check status');
  return resp.json();
}

export async function getStrategyCoverage(): Promise<StrategyCoverage> {
  const resp = await apiFetch(`${getApiUrl()}/strategy/coverage`);
  if (!resp.ok) throw new Error('Failed to fetch coverage');
  return resp.json();
}

// --- Source image linking ---

export interface UnlinkedImage {
  id: number;
  generation_id: string;
  url: string;
  prompt: string;
  style: string;
  created_at: string;
}

export async function getUnlinkedImages(limit: number = 50, offset: number = 0): Promise<{ items: UnlinkedImage[]; total: number }> {
  const response = await apiFetch(`${getApiUrl()}/generated-images/unlinked?limit=${limit}&offset=${offset}`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch images' }));
    throw new Error(error.detail || 'Failed to fetch images');
  }
  return response.json();
}

export async function linkSourceImage(printifyProductId: string, imageId: number): Promise<{ success: boolean }> {
  const response = await apiFetch(`${getApiUrl()}/products/${printifyProductId}/link-image`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image_id: imageId }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to link image' }));
    throw new Error(error.detail || 'Failed to link image');
  }
  return response.json();
}

export async function syncProductsFromPrintify(): Promise<{ total: number; imported: number; skipped: number }> {
  const response = await apiFetch(`${getApiUrl()}/products/sync`, { method: 'POST' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Sync failed' }));
    throw new Error(error.detail || 'Sync failed');
  }
  return response.json();
}

// === SEO V2: Autocomplete Validation ===

export interface AutocompleteTagResult {
  tag: string;
  found: boolean;
  position: number | null;
  suggestions: string[];
}

export interface ValidateTagsResponse {
  total: number;
  found: number;
  not_found: number;
  results: AutocompleteTagResult[];
  score: number;
}

export async function validateTags(tags: string[]): Promise<ValidateTagsResponse> {
  const response = await apiFetch(`${getApiUrl()}/seo/validate-tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Validation failed' }));
    throw new Error(error.detail || 'Validation failed');
  }
  return response.json();
}

export async function getSeoAutocomplete(query: string): Promise<{ query: string; suggestions: string[] }> {
  const response = await apiFetch(`${getApiUrl()}/seo/autocomplete?q=${encodeURIComponent(query)}`);
  if (!response.ok) throw new Error('Autocomplete failed');
  return response.json();
}

// === SEO V2.1: Etsy Search Volume Validation ===

export interface EtsyTagResult {
  tag: string;
  found: boolean;
  total_results: number;
  demand: 'high' | 'medium' | 'low' | 'dead' | 'error';
  source: 'etsy';
}

export interface ValidateTagsEtsyResponse {
  total: number;
  found: number;
  not_found: number;
  results: EtsyTagResult[];
  score: number;
  source: 'etsy';
}

export async function validateTagsEtsy(tags: string[]): Promise<ValidateTagsEtsyResponse> {
  const response = await apiFetch(`${getApiUrl()}/seo/validate-tags-etsy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Etsy validation failed' }));
    throw new Error(error.detail || 'Etsy validation failed');
  }
  return response.json();
}
