'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { getApiUrl, importEtsyCsv, ImportCsvResult } from '@/lib/api';
import { authFetch } from '@/lib/auth';

interface AuditStatus {
  status: string;
  total: number;
  done: number;
  good: number;
  low: number;
  no_image: number;
}

export default function ImportExportPage() {
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [result, setResult] = useState<ImportCsvResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Image audit
  const [audit, setAudit] = useState<AuditStatus | null>(null);
  const [auditPolling, setAuditPolling] = useState(false);

  const pollAudit = useCallback(async () => {
    try {
      const res = await authFetch(`${getApiUrl()}/etsy/image-audit-status`);
      if (!res.ok) return;
      const data: AuditStatus = await res.json();
      setAudit(data);
      if (data.status === 'running') {
        setAuditPolling(true);
      } else {
        setAuditPolling(false);
      }
    } catch { /* ignore */ }
  }, []);

  // Load audit status on mount
  useEffect(() => { pollAudit(); }, [pollAudit]);

  // Poll while running
  useEffect(() => {
    if (!auditPolling) return;
    const id = setInterval(pollAudit, 3000);
    return () => clearInterval(id);
  }, [auditPolling, pollAudit]);

  const handleExport = async () => {
    setExporting(true);
    setError(null);
    try {
      const res = await authFetch(`${getApiUrl()}/etsy/export-csv`);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'etsy_listings.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  const handleImport = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setImporting(true);
    setError(null);
    setResult(null);
    try {
      const data = await importEtsyCsv(file);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed');
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const startAudit = async () => {
    setError(null);
    try {
      const res = await authFetch(`${getApiUrl()}/etsy/image-audit`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to start audit');
      const data = await res.json();
      if (data.started) {
        setAudit({ status: 'running', total: data.total, done: 0, good: 0, low: 0, no_image: 0 });
        setAuditPolling(true);
      } else {
        pollAudit();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Audit failed');
    }
  };

  const downloadAuditCsv = async () => {
    try {
      const res = await authFetch(`${getApiUrl()}/etsy/image-audit-csv`);
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'etsy_image_audit.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed');
    }
  };

  const auditPercent = audit && audit.total > 0 ? Math.round((audit.done / audit.total) * 100) : 0;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <h1 className="text-2xl font-bold text-gray-100">Import / Export Listings</h1>

      {/* Export Section */}
      <div className="bg-dark-card border border-dark-border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-100 mb-2">Export to CSV</h2>
        <p className="text-sm text-gray-400 mb-4">
          Download all active Etsy listings as CSV. Includes a tag_issues column flagging any tags
          that violate Etsy rules (over 20 chars, duplicates, special characters).
        </p>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 disabled:opacity-50 transition-colors"
        >
          {exporting ? 'Exporting...' : 'Export Listings CSV'}
        </button>
      </div>

      {/* Import Section */}
      <div className="bg-dark-card border border-dark-border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-100 mb-2">Import from CSV</h2>
        <p className="text-sm text-gray-400 mb-4">
          Upload a CSV to update listings. Tags are auto-validated before sending to Etsy:
          truncated to 20 chars, duplicates removed, special characters stripped, max 13 tags kept.
        </p>
        <div className="flex items-center gap-4">
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="text-sm text-gray-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-dark-hover file:text-gray-200 file:cursor-pointer hover:file:bg-dark-border"
          />
          <button
            onClick={handleImport}
            disabled={importing}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 disabled:opacity-50 transition-colors"
          >
            {importing ? 'Importing...' : 'Import & Update'}
          </button>
        </div>

        {importing && (
          <div className="mt-4">
            <div className="w-full bg-dark-hover rounded-full h-2">
              <div className="bg-accent h-2 rounded-full animate-pulse" style={{ width: '100%' }} />
            </div>
            <p className="text-sm text-gray-400 mt-2">Validating tags & updating listings on Etsy...</p>
          </div>
        )}
      </div>

      {/* Image Quality Audit */}
      <div className="bg-dark-card border border-dark-border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-100 mb-2">Image Quality Audit</h2>
        <p className="text-sm text-gray-400 mb-4">
          Check primary image resolution for all listings. Good = 2400x3000+ (300 DPI at 8x10).
          Runs in background — results downloadable as CSV.
        </p>

        <div className="flex items-center gap-3">
          <button
            onClick={startAudit}
            disabled={audit?.status === 'running'}
            className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent/80 disabled:opacity-50 transition-colors"
          >
            {audit?.status === 'running' ? 'Auditing...' : 'Start Audit'}
          </button>
          {audit?.status === 'completed' && (
            <button
              onClick={downloadAuditCsv}
              className="px-4 py-2 bg-dark-hover text-gray-200 rounded-lg hover:bg-dark-border transition-colors"
            >
              Download Audit CSV
            </button>
          )}
        </div>

        {/* Progress */}
        {audit?.status === 'running' && (
          <div className="mt-4">
            <div className="flex justify-between text-sm text-gray-400 mb-1">
              <span>Checking images...</span>
              <span>{audit.done}/{audit.total} ({auditPercent}%)</span>
            </div>
            <div className="w-full bg-dark-hover rounded-full h-2">
              <div
                className="bg-accent h-2 rounded-full transition-all duration-500"
                style={{ width: `${auditPercent}%` }}
              />
            </div>
          </div>
        )}

        {/* Completed Summary */}
        {audit?.status === 'completed' && (
          <div className="mt-4 flex gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-100">{audit.total}</div>
              <div className="text-xs text-gray-500">Total</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-400">{audit.good}</div>
              <div className="text-xs text-gray-500">Good</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-400">{audit.low}</div>
              <div className="text-xs text-gray-500">Low Res</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-500">{audit.no_image}</div>
              <div className="text-xs text-gray-500">No Image</div>
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-4">
          {error}
        </div>
      )}

      {/* Import Results */}
      {result && (
        <div className="bg-dark-card border border-dark-border rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-100">Import Results</h2>

          <div className="flex gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-100">{result.total}</div>
              <div className="text-xs text-gray-500">Total Rows</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-400">{result.updated}</div>
              <div className="text-xs text-gray-500">Updated</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-400">{result.errors}</div>
              <div className="text-xs text-gray-500">Errors</div>
            </div>
          </div>

          {/* Tag Validation Summary */}
          {(result.tags_truncated > 0 || result.duplicates_removed > 0) && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
              <h3 className="text-sm font-medium text-yellow-400 mb-1">Tag Validation</h3>
              <p className="text-sm text-gray-400">
                {result.tags_truncated > 0 && <span>{result.tags_truncated} tags were truncated to 20 chars. </span>}
                {result.duplicates_removed > 0 && <span>{result.duplicates_removed} duplicate tags removed.</span>}
              </p>
            </div>
          )}

          {/* Errors List */}
          {result.results.some(r => r.status === 'error') && (
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-red-400">Errors:</h3>
              {result.results
                .filter(r => r.status === 'error')
                .map((r, i) => (
                  <div key={i} className="text-sm text-gray-400">
                    Row {r.row} (listing {r.listing_id}): {r.error}
                  </div>
                ))}
            </div>
          )}

          {/* Tag Fixes Details */}
          {result.results.some(r => r.tag_fixes?.length) && (
            <details className="text-sm">
              <summary className="text-yellow-400 cursor-pointer hover:text-yellow-300">
                Show tag fix details ({result.results.filter(r => r.tag_fixes?.length).length} listings affected)
              </summary>
              <div className="mt-2 space-y-1 text-gray-500 max-h-60 overflow-y-auto">
                {result.results
                  .filter(r => r.tag_fixes?.length)
                  .map((r, i) => (
                    <div key={i}>
                      <span className="text-gray-400">Row {r.row}:</span>{' '}
                      {r.tag_fixes!.join(', ')}
                    </div>
                  ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
