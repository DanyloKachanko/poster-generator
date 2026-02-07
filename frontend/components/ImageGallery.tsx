'use client';

import { useState } from 'react';
import { ImageInfo, PosterPreset } from '@/lib/api';
import ExportModal from './ExportModal';
import CreateProductModal from './CreateProductModal';

interface ImageGalleryProps {
  images: ImageInfo[];
  isLoading: boolean;
  error: string | null;
  preset?: PosterPreset | null;
}

export default function ImageGallery({
  images,
  isLoading,
  error,
  preset,
}: ImageGalleryProps) {
  const [selectedImage, setSelectedImage] = useState<ImageInfo | null>(null);
  const [exportImage, setExportImage] = useState<ImageInfo | null>(null);
  const [createProductImage, setCreateProductImage] = useState<ImageInfo | null>(null);

  const handleDownload = async (image: ImageInfo) => {
    try {
      const response = await fetch(image.url);
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `poster-${image.id}.png`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  if (error) {
    return (
      <div className="bg-dark-card rounded-lg border border-dark-border p-8">
        <div className="text-center text-red-400">
          <p className="font-medium">Generation failed</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="bg-dark-card rounded-lg border border-dark-border p-8">
        <div className="flex flex-col items-center justify-center">
          <div className="animate-spin h-12 w-12 border-3 border-accent border-t-transparent rounded-full" />
          <p className="mt-4 text-gray-400">Generating your posters...</p>
        </div>
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="bg-dark-card rounded-lg border border-dark-border p-8">
        <div className="text-center text-gray-500">
          <p>No images yet</p>
          <p className="text-sm mt-1">
            Select a style and preset, then click Generate
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="bg-dark-card rounded-lg border border-dark-border p-4">
        <h2 className="text-sm font-medium text-gray-300 mb-3">
          Generated Images
        </h2>
        <div className="grid grid-cols-2 gap-4">
          {images.map((image) => (
            <div key={image.id} className="relative group">
              <img
                src={image.url}
                alt="Generated poster"
                className="w-full rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
                onClick={() => setSelectedImage(image)}
              />
              {/* Action buttons on hover */}
              <div className="absolute bottom-2 left-2 right-2 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => setCreateProductImage(image)}
                  className="bg-green-600 hover:bg-green-500 text-white px-2.5 py-1.5 rounded-lg text-xs font-medium"
                  title="Create product on Printify"
                >
                  Create Product
                </button>
                <button
                  onClick={() => setExportImage(image)}
                  className="bg-accent/90 hover:bg-accent text-dark-bg px-2.5 py-1.5 rounded-lg text-xs font-medium"
                  title="Export for Printify"
                >
                  Export
                </button>
                <button
                  onClick={() => handleDownload(image)}
                  className="bg-dark-card/90 hover:bg-dark-card p-1.5 rounded-lg border border-dark-border ml-auto"
                  title="Download original"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-4 w-4 text-gray-300"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                    />
                  </svg>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Lightbox */}
      {selectedImage && (
        <div
          className="fixed inset-0 bg-black/90 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedImage(null)}
        >
          <div className="relative max-w-4xl max-h-full">
            <img
              src={selectedImage.url}
              alt="Full size poster"
              className="max-w-full max-h-[90vh] object-contain rounded-lg"
            />
            <button
              onClick={() => setSelectedImage(null)}
              className="absolute top-2 right-2 bg-dark-card/90 hover:bg-dark-card p-2 rounded-full border border-dark-border"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-6 w-6 text-gray-300"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
            <div className="absolute bottom-4 right-4 flex gap-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setCreateProductImage(selectedImage);
                  setSelectedImage(null);
                }}
                className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg font-medium text-sm"
              >
                Create Product
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setExportImage(selectedImage);
                  setSelectedImage(null);
                }}
                className="bg-accent hover:bg-accent-hover text-dark-bg px-4 py-2 rounded-lg font-medium text-sm"
              >
                Export
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDownload(selectedImage);
                }}
                className="bg-dark-card/90 hover:bg-dark-card text-gray-300 px-4 py-2 rounded-lg border border-dark-border text-sm"
              >
                Download
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export Modal */}
      {exportImage && (
        <ExportModal
          image={exportImage}
          onClose={() => setExportImage(null)}
        />
      )}

      {/* Create Product Modal */}
      {createProductImage && (
        <CreateProductModal
          image={createProductImage}
          preset={preset || null}
          onClose={() => setCreateProductImage(null)}
        />
      )}
    </>
  );
}
