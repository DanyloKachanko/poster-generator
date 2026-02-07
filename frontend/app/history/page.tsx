'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import ExportModal from '@/components/ExportModal';
import ListingPanel from '@/components/ListingPanel';
import {
  getHistory,
  getStyles,
  getCredits,
  archiveGeneration,
  restoreGeneration,
  HistoryItem,
  HistoryResponse,
  StylesResponse,
  CreditsResponse,
  ImageInfo,
} from '@/lib/api';

export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [styles, setStyles] = useState<StylesResponse>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStyle, setSelectedStyle] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [showArchived, setShowArchived] = useState(false);
  const [page, setPage] = useState(0);
  const [detailItem, setDetailItem] = useState<HistoryItem | null>(null);
  const [detailImageIndex, setDetailImageIndex] = useState(0);
  const [exportImage, setExportImage] = useState<ImageInfo | null>(null);
  const [listingItem, setListingItem] = useState<HistoryItem | null>(null);
  const [listingImageUrl, setListingImageUrl] = useState<string>('');
  const [credits, setCredits] = useState<CreditsResponse | null>(null);
  const limit = 12;

  useEffect(() => {
    getStyles().then(setStyles).catch(console.error);
    getCredits().then(setCredits).catch(console.error);
  }, []);

  const loadHistory = () => {
    setIsLoading(true);
    setError(null);
    getHistory(
      limit,
      page * limit,
      selectedStatus || undefined,
      selectedStyle || undefined,
      showArchived
    )
      .then(setHistory)
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadHistory();
  }, [page, selectedStyle, selectedStatus, showArchived]);

  const handleArchive = async (generationId: string) => {
    try {
      await archiveGeneration(generationId);
      setDetailItem(null);
      loadHistory();
    } catch (err) {
      console.error('Archive failed:', err);
    }
  };

  const handleRestore = async (generationId: string) => {
    try {
      await restoreGeneration(generationId);
      setDetailItem(null);
      loadHistory();
    } catch (err) {
      console.error('Restore failed:', err);
    }
  };

  const handleDownload = async (url: string, id: string) => {
    try {
      const response = await fetch(url);
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `poster-${id}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const openDetail = (item: HistoryItem, imageIndex: number = 0) => {
    setDetailItem(item);
    setDetailImageIndex(imageIndex);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <main className="p-4 md:p-6">
      <div className="max-w-7xl mx-auto">
        {/* Tabs + Filters */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className="flex bg-dark-card rounded-lg border border-dark-border p-0.5">
              <button
                onClick={() => {
                  setShowArchived(false);
                  setPage(0);
                }}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  !showArchived
                    ? 'bg-accent/15 text-accent'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                All ({history?.total || 0})
              </button>
              <button
                onClick={() => {
                  setShowArchived(true);
                  setPage(0);
                }}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  showArchived
                    ? 'bg-accent/15 text-accent'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                Archive
              </button>
            </div>
            {credits && credits.total_credits_used > 0 && (
              <span className="text-xs text-gray-500">
                {credits.total_credits_used.toLocaleString()} tokens spent
              </span>
            )}
          </div>
          <div className="flex gap-3">
            <select
              value={selectedStyle}
              onChange={(e) => {
                setSelectedStyle(e.target.value);
                setPage(0);
              }}
              className="px-3 py-1.5 bg-dark-card border border-dark-border rounded-lg text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
            >
              <option value="">All Styles</option>
              {Object.entries(styles).map(([key, style]) => (
                <option key={key} value={key}>
                  {style.name}
                </option>
              ))}
            </select>

            <select
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value);
                setPage(0);
              }}
              className="px-3 py-1.5 bg-dark-card border border-dark-border rounded-lg text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-accent/50"
            >
              <option value="">All Status</option>
              <option value="COMPLETE">Complete</option>
              <option value="PENDING">Pending</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {[...Array(8)].map((_, i) => (
              <div
                key={i}
                className="aspect-[4/5] bg-dark-card rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-400">{error}</p>
          </div>
        ) : history?.items.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-500 mb-4">
              {showArchived
                ? 'No archived posters'
                : 'No posters generated yet'}
            </p>
            {!showArchived && (
              <Link
                href="/"
                className="inline-block px-4 py-2 bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover transition-colors"
              >
                Generate your first poster
              </Link>
            )}
          </div>
        ) : (
          <>
            {/* Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {history?.items.map((item) => (
                <HistoryCard
                  key={item.generation_id}
                  item={item}
                  formatDate={formatDate}
                  onOpenDetail={openDetail}
                  onArchive={handleArchive}
                  onRestore={handleRestore}
                  isArchived={showArchived}
                />
              ))}
            </div>

            {/* Pagination */}
            {history && history.total > limit && (
              <div className="flex items-center justify-center gap-4 mt-8">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="px-4 py-2 bg-dark-card border border-dark-border rounded-lg text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-dark-hover transition-colors"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-400">
                  {page + 1} / {Math.ceil(history.total / limit)}
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!history.has_more}
                  className="px-4 py-2 bg-dark-card border border-dark-border rounded-lg text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-dark-hover transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Detail Modal */}
      {detailItem && detailItem.status === 'COMPLETE' && detailItem.images.length > 0 && (
        <DetailModal
          item={detailItem}
          imageIndex={detailImageIndex}
          onImageIndexChange={setDetailImageIndex}
          onClose={() => setDetailItem(null)}
          onDownload={handleDownload}
          onExport={(img) => setExportImage(img)}
          onListing={(item, imageUrl) => { setListingItem(item); setListingImageUrl(imageUrl); setDetailItem(null); }}
          onArchive={handleArchive}
          onRestore={handleRestore}
          isArchived={showArchived}
          formatDate={formatDate}
        />
      )}

      {/* Export Modal */}
      {exportImage && (
        <ExportModal
          image={exportImage}
          onClose={() => setExportImage(null)}
        />
      )}

      {/* Listing Generator Modal */}
      {listingItem && (
        <ListingPanel
          style={listingItem.style || 'abstract'}
          preset={listingItem.preset || 'general'}
          imageDescription={listingItem.prompt}
          imageUrl={listingImageUrl}
          onClose={() => setListingItem(null)}
        />
      )}
    </main>
  );
}

function DetailModal({
  item,
  imageIndex,
  onImageIndexChange,
  onClose,
  onDownload,
  onExport,
  onListing,
  onArchive,
  onRestore,
  isArchived,
  formatDate,
}: {
  item: HistoryItem;
  imageIndex: number;
  onImageIndexChange: (idx: number) => void;
  onClose: () => void;
  onDownload: (url: string, id: string) => void;
  onExport: (img: ImageInfo) => void;
  onListing: (item: HistoryItem, imageUrl: string) => void;
  onArchive: (id: string) => void;
  onRestore: (id: string) => void;
  isArchived: boolean;
  formatDate: (date: string) => string;
}) {
  const currentImage = item.images[imageIndex];

  return (
    <div
      className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-dark-card border border-dark-border rounded-xl max-w-4xl w-full max-h-[90vh] overflow-auto flex flex-col md:flex-row"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Left: Image */}
        <div className="md:w-3/5 bg-dark-bg flex items-center justify-center relative min-h-[300px]">
          <img
            src={currentImage.url}
            alt="Poster"
            className="max-w-full max-h-[70vh] object-contain"
          />
          {/* Image navigation */}
          {item.images.length > 1 && (
            <>
              <button
                onClick={() => onImageIndexChange((imageIndex - 1 + item.images.length) % item.images.length)}
                className="absolute left-2 top-1/2 -translate-y-1/2 p-2 bg-black/60 hover:bg-black/80 rounded-full text-white"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
                </svg>
              </button>
              <button
                onClick={() => onImageIndexChange((imageIndex + 1) % item.images.length)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-black/60 hover:bg-black/80 rounded-full text-white"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                </svg>
              </button>
              <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
                {item.images.map((_, idx) => (
                  <button
                    key={idx}
                    onClick={() => onImageIndexChange(idx)}
                    className={`w-2 h-2 rounded-full transition-colors ${
                      idx === imageIndex ? 'bg-accent' : 'bg-white/40 hover:bg-white/60'
                    }`}
                  />
                ))}
              </div>
            </>
          )}
        </div>

        {/* Right: Info & Actions */}
        <div className="md:w-2/5 p-5 flex flex-col">
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-3 right-3 text-gray-400 hover:text-gray-200 text-xl md:static md:self-end md:mb-2"
          >
            &times;
          </button>

          {/* Prompt */}
          <div className="mb-4">
            <h3 className="text-xs font-medium text-gray-500 uppercase mb-1">Prompt</h3>
            <p className="text-sm text-gray-200 leading-relaxed">{item.prompt}</p>
          </div>

          {/* Details */}
          <div className="grid grid-cols-2 gap-3 mb-4 text-xs">
            <div>
              <span className="text-gray-500">Size</span>
              <p className="text-gray-300">{item.width}x{item.height}</p>
            </div>
            <div>
              <span className="text-gray-500">Date</span>
              <p className="text-gray-300">{formatDate(item.created_at)}</p>
            </div>
            {item.style && (
              <div>
                <span className="text-gray-500">Style</span>
                <p className="text-accent">{item.style}</p>
              </div>
            )}
            {item.api_credit_cost > 0 && (
              <div>
                <span className="text-gray-500">Cost</span>
                <p className="text-gray-300">{item.api_credit_cost} tokens</p>
              </div>
            )}
            {item.images.length > 1 && (
              <div>
                <span className="text-gray-500">Images</span>
                <p className="text-gray-300">{imageIndex + 1} / {item.images.length}</p>
              </div>
            )}
          </div>

          {/* Multiple images thumbnails */}
          {item.images.length > 1 && (
            <div className="flex gap-1.5 mb-4 flex-wrap">
              {item.images.map((img, idx) => (
                <img
                  key={img.id}
                  src={img.url}
                  alt={`Image ${idx + 1}`}
                  className={`w-12 h-12 object-cover rounded cursor-pointer transition-all ${
                    idx === imageIndex
                      ? 'ring-2 ring-accent opacity-100'
                      : 'opacity-60 hover:opacity-80'
                  }`}
                  onClick={() => onImageIndexChange(idx)}
                />
              ))}
            </div>
          )}

          {/* Spacer */}
          <div className="flex-1" />

          {/* Action buttons */}
          <div className="space-y-2 mt-4">
            <button
              onClick={() => onDownload(currentImage.url, currentImage.id)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-dark-bg border border-dark-border rounded-lg text-gray-200 hover:bg-dark-hover transition-colors text-sm"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              Download Original
            </button>

            <button
              onClick={() => {
                onExport(currentImage);
                onClose();
              }}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-accent text-dark-bg rounded-lg font-medium hover:bg-accent-hover transition-colors text-sm"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
              </svg>
              Export for Printify
            </button>

            <button
              onClick={() => onListing(item, currentImage.url)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-green-500/10 border border-green-500/30 text-green-400 rounded-lg hover:bg-green-500/20 transition-colors text-sm"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Create Product
            </button>

            <button
              onClick={() =>
                isArchived
                  ? onRestore(item.generation_id)
                  : onArchive(item.generation_id)
              }
              className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm transition-colors ${
                isArchived
                  ? 'bg-green-500/10 border border-green-500/30 text-green-400 hover:bg-green-500/20'
                  : 'bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20'
              }`}
            >
              {isArchived ? (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 15 3 9m0 0 6-6M3 9h12a6 6 0 0 1 0 12h-3" />
                  </svg>
                  Restore
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5m8.25 3v6.75m0 0-3-3m3 3 3-3M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125Z" />
                  </svg>
                  Archive
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function HistoryCard({
  item,
  formatDate,
  onOpenDetail,
  onArchive,
  onRestore,
  isArchived,
}: {
  item: HistoryItem;
  formatDate: (date: string) => string;
  onOpenDetail: (item: HistoryItem, imageIndex?: number) => void;
  onArchive: (id: string) => void;
  onRestore: (id: string) => void;
  isArchived: boolean;
}) {
  const mainImage = item.images[0];

  return (
    <div className="bg-dark-card rounded-lg border border-dark-border overflow-hidden">
      {/* Image */}
      <div
        className="aspect-[4/5] bg-dark-bg relative cursor-pointer"
        onClick={() => {
          if (item.status === 'COMPLETE' && mainImage) {
            onOpenDetail(item, 0);
          }
        }}
      >
        {item.status === 'COMPLETE' && mainImage ? (
          <>
            <img
              src={mainImage.url}
              alt={item.prompt.slice(0, 50)}
              className="w-full h-full object-cover"
            />
            {item.images.length > 1 && (
              <div className="absolute bottom-2 right-2 px-2 py-1 bg-black/70 text-white text-xs rounded">
                +{item.images.length - 1} more
              </div>
            )}
          </>
        ) : item.status === 'PENDING' ? (
          <div className="w-full h-full flex items-center justify-center">
            <div className="animate-spin w-8 h-8 border-2 border-accent border-t-transparent rounded-full" />
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center text-red-400 text-sm">
            Failed
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3">
        <p className="text-sm text-gray-300 line-clamp-2" title={item.prompt}>
          {item.prompt.length > 60
            ? item.prompt.slice(0, 60) + '...'
            : item.prompt}
        </p>
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-500">
            {formatDate(item.created_at)}
          </span>
          <span className="text-xs text-gray-500">
            {item.width}x{item.height}
          </span>
        </div>
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-2">
            {item.api_credit_cost > 0 && (
              <span className="text-xs px-2 py-0.5 bg-dark-bg text-gray-400 rounded">
                {item.api_credit_cost} tokens
              </span>
            )}
            {item.style && (
              <span className="text-xs px-2 py-0.5 bg-accent/20 text-accent rounded">
                {item.style}
              </span>
            )}
          </div>
          {/* Archive/Restore button - always visible */}
          {item.status === 'COMPLETE' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                isArchived
                  ? onRestore(item.generation_id)
                  : onArchive(item.generation_id);
              }}
              className={`p-1.5 rounded-lg transition-colors ${
                isArchived
                  ? 'text-green-400 hover:bg-green-500/10'
                  : 'text-gray-500 hover:text-red-400 hover:bg-red-500/10'
              }`}
              title={isArchived ? 'Restore' : 'Archive'}
            >
              {isArchived ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 15 3 9m0 0 6-6M3 9h12a6 6 0 0 1 0 12h-3" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5m8.25 3v6.75m0 0-3-3m3 3 3-3M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125Z" />
                </svg>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Multiple images preview */}
      {item.images.length > 1 && (
        <div className="px-3 pb-3 flex gap-1">
          {item.images.slice(0, 4).map((img, idx) => (
            <img
              key={img.id}
              src={img.url}
              alt={`Image ${idx + 1}`}
              className="w-10 h-10 object-cover rounded cursor-pointer hover:opacity-80 transition-opacity"
              onClick={() => onOpenDetail(item, idx)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
