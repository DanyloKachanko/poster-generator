'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  getMockupScenes,
  generateMockupScene,
  pollForCompletion,
  getHistory,
  getMockupTemplates,
  saveMockupTemplate,
  updateMockupTemplate,
  uploadMockupTemplate,
  deleteMockupTemplate,
  composeMockup,
  toggleTemplateActive,
  getMockupPacks,
  getMockupPack,
  createMockupPack,
  updateMockupPack,
  deleteMockupPack,
  getColorGrades,
  HistoryItem,
  MockupScene,
  MockupRatio,
  MockupModel,
  MockupStyle,
  MockupTemplate,
  MockupPack,
} from '@/lib/api';

type Corner = [number, number]; // [x, y] in virtual coords
type Mode = 'templates' | 'generate' | 'define' | 'compose' | 'upload' | 'edit' | 'packs';

interface SceneImage {
  url: string;
  width: number;
  height: number;
}

export default function MockupGeneratorPage() {
  const [mode, setMode] = useState<Mode>('templates');

  // Templates
  const [templates, setTemplates] = useState<MockupTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [activeTemplateIds, setActiveTemplateIds] = useState<Set<number>>(new Set());

  // Scene generation
  const [scenes, setScenes] = useState<Record<string, MockupScene>>({});
  const [ratios, setRatios] = useState<Record<string, MockupRatio>>({});
  const [models, setModels] = useState<Record<string, { name: string; description: string }>>({});
  const [styles, setStyles] = useState<Record<string, { name: string; description: string }>>({});
  const [selectedScene, setSelectedScene] = useState('living_room');
  const [selectedRatio, setSelectedRatio] = useState('4:5');
  const [selectedModel, setSelectedModel] = useState('vision_xl');
  const [selectedStyle, setSelectedStyle] = useState('stock_photo');
  const [customPrompt, setCustomPrompt] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedScenes, setGeneratedScenes] = useState<SceneImage[]>([]);

  // Corner definition
  const [defineScene, setDefineScene] = useState<SceneImage | null>(null);
  const [corners, setCorners] = useState<Corner[]>([]);
  const [templateName, setTemplateName] = useState('');
  const [savingTemplate, setSavingTemplate] = useState(false);
  const imgRef = useRef<HTMLDivElement>(null);

  // Compose
  const [activeTemplate, setActiveTemplate] = useState<MockupTemplate | null>(null);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [activePoster, setActivePoster] = useState<string | null>(null);
  const [isComposing, setIsComposing] = useState(false);
  const [composedUrl, setComposedUrl] = useState<string | null>(null);
  const [fillMode, setFillMode] = useState<'stretch' | 'fit' | 'fill'>('fill');
  const [composeColorGrade, setComposeColorGrade] = useState('none');

  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState('');
  const [uploadJSON, setUploadJSON] = useState('{\n  "corners": [\n    [0, 0],\n    [1024, 0],\n    [1024, 1280],\n    [0, 1280]\n  ],\n  "image_size": [1024, 1280],\n  "blend_alpha": 1.0,\n  "feather_radius": 3\n}');
  const [isUploading, setIsUploading] = useState(false);

  // Edit state
  const [editingTemplate, setEditingTemplate] = useState<MockupTemplate | null>(null);
  const [editJSON, setEditJSON] = useState('');
  const [editCorners, setEditCorners] = useState<Corner[]>([]);
  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const zoomRef = useRef(1);
  const panXRef = useRef(0);
  const panYRef = useRef(0);
  const [draggedCorner, setDraggedCorner] = useState<number | null>(null);
  const [selectedCorner, setSelectedCorner] = useState<number>(-1);
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState<{x: number; y: number; px: number; py: number} | null>(null);
  const [spaceHeld, setSpaceHeld] = useState(false);
  const editImgRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  // Define mode drag support
  const [defineDraggedCorner, setDefineDraggedCorner] = useState<number | null>(null);

  // Edit live preview + name + blend mode
  const [editPreviewPoster, setEditPreviewPoster] = useState<string | null>(null);
  const [editNameValue, setEditNameValue] = useState('');
  const [editBlendMode, setEditBlendMode] = useState<string>('normal');

  // Packs
  const [packs, setPacks] = useState<MockupPack[]>([]);
  const [loadingPacks, setLoadingPacks] = useState(false);
  const [editingPack, setEditingPack] = useState<MockupPack | null>(null);
  const [packName, setPackName] = useState('');
  const [packTemplateIds, setPackTemplateIds] = useState<Set<number>>(new Set());
  const [packColorGrade, setPackColorGrade] = useState('none');
  const [colorGrades, setColorGrades] = useState<{ id: string; name: string }[]>([]);
  const [savingPack, setSavingPack] = useState(false);

  // Load templates + scenes + history on mount
  useEffect(() => {
    loadTemplates();
    getMockupScenes()
      .then((data) => {
        setScenes(data.scenes);
        setRatios(data.ratios);
        setModels(data.models || {});
        setStyles(data.styles || {});
      })
      .catch(() => {});
    getColorGrades()
      .then((data) => setColorGrades(data.grades))
      .catch(() => {});
    getHistory(50, 0, 'COMPLETE', undefined, false, 'mockup')
      .then((data) => setHistoryItems(data.items.filter((i) => i.images.length > 0)))
      .catch(() => {})
      .finally(() => setLoadingHistory(false));
  }, []);

  const loadTemplates = async () => {
    setLoadingTemplates(true);
    try {
      const t = await getMockupTemplates();
      setTemplates(t);
      // Load active template IDs
      const activeIds = new Set<number>(
        t.filter((tmpl) => tmpl.is_active).map((tmpl) => tmpl.id)
      );
      setActiveTemplateIds(activeIds);
    } catch {}
    setLoadingTemplates(false);
  };

  const handleToggleActive = async (id: number) => {
    try {
      const result = await toggleTemplateActive(id);
      setActiveTemplateIds((prev: Set<number>) => {
        const next = new Set(prev);
        if (result.is_active) {
          next.add(id);
        } else {
          next.delete(id);
        }
        return next;
      });
      // Also update the templates array
      setTemplates((prev: MockupTemplate[]) =>
        prev.map((t: MockupTemplate) => (t.id === id ? { ...t, is_active: result.is_active } : t))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle template');
    }
  };

  // Generate scene
  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      const result = await generateMockupScene(
        selectedScene,
        selectedRatio,
        useCustom ? customPrompt : undefined,
        2,
        selectedModel,
        selectedStyle
      );
      const final = await pollForCompletion(result.generation_id, undefined, 3000, 120000);
      if (final.status === 'COMPLETE' && final.images.length > 0) {
        const newScenes = final.images.map((img) => ({
          url: img.url,
          width: result.width,
          height: result.height,
        }));
        setGeneratedScenes((prev) => [...newScenes, ...prev]);
        setSuccessMsg(`Generated ${final.images.length} scene(s)`);
        setTimeout(() => setSuccessMsg(null), 3000);
      } else {
        setError('Generation failed or returned no images');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setIsGenerating(false);
    }
  };

  // Click on scene image to place corner
  const handleCornerClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!defineScene || defineDraggedCorner !== null) return;
    if (corners.length >= 4) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * defineScene.width;
    const y = ((e.clientY - rect.top) / rect.height) * defineScene.height;
    setCorners((prev) => [...prev, [Math.round(x), Math.round(y)]]);
  };

  // Define mode: drag existing corners
  const handleDefineCornerMouseDown = (e: React.MouseEvent, idx: number) => {
    e.stopPropagation();
    e.preventDefault();
    setDefineDraggedCorner(idx);
  };

  const handleDefineMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (defineDraggedCorner === null || !defineScene) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * defineScene.width);
    const y = Math.round(((e.clientY - rect.top) / rect.height) * defineScene.height);
    const clamped: Corner = [
      Math.max(0, Math.min(defineScene.width, x)),
      Math.max(0, Math.min(defineScene.height, y)),
    ];
    setCorners((prev) => {
      const next = [...prev];
      next[defineDraggedCorner] = clamped;
      return next;
    });
  };

  const handleDefineMouseUp = () => {
    setDefineDraggedCorner(null);
  };

  // Save template
  const handleSaveTemplate = async () => {
    if (!defineScene || corners.length !== 4 || !templateName.trim()) return;
    setSavingTemplate(true);
    setError(null);
    try {
      await saveMockupTemplate(
        templateName.trim(),
        defineScene.url,
        defineScene.width,
        defineScene.height,
        corners
      );
      setSuccessMsg('Template saved!');
      setTimeout(() => setSuccessMsg(null), 3000);
      setCorners([]);
      setTemplateName('');
      setDefineScene(null);
      await loadTemplates();
      setMode('templates');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSavingTemplate(false);
    }
  };

  // Compose mockup
  const handleCompose = async () => {
    if (!activeTemplate || !activePoster) return;
    setIsComposing(true);
    setError(null);
    setComposedUrl(null);
    try {
      const blob = await composeMockup(activeTemplate.id, activePoster, fillMode, composeColorGrade);
      const url = URL.createObjectURL(blob);
      setComposedUrl(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Composition failed');
    } finally {
      setIsComposing(false);
    }
  };

  // Download composed image
  const handleDownload = () => {
    if (!composedUrl) return;
    const a = document.createElement('a');
    a.href = composedUrl;
    a.download = `mockup-${activeTemplate?.id}-${Date.now()}.png`;
    a.click();
  };

  // Delete template
  const handleDeleteTemplate = async (id: number) => {
    try {
      await deleteMockupTemplate(id);
      await loadTemplates();
    } catch {}
  };

  const handleUpload = async () => {
    if (!uploadFile || !uploadName.trim()) {
      setError('Please provide a file and name');
      return;
    }

    setIsUploading(true);
    setError(null);
    try {
      const config = JSON.parse(uploadJSON);

      // Support both formats: {width, height} and {image_size: [w, h]}
      let width, height;
      if (config.image_size && Array.isArray(config.image_size)) {
        [width, height] = config.image_size;
      } else {
        width = config.width || 1024;
        height = config.height || 1280;
      }

      await uploadMockupTemplate(
        uploadFile,
        uploadName,
        width,
        height,
        config.corners
      );
      setSuccessMsg('Template uploaded successfully!');
      setTimeout(() => setSuccessMsg(null), 3000);
      setUploadFile(null);
      setUploadName('');
      await loadTemplates();
      setMode('templates');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleEdit = (template: MockupTemplate) => {
    setEditingTemplate(template);
    setEditCorners(template.corners.map(c => [c[0], c[1]] as Corner));
    setEditNameValue(template.name);
    setEditBlendMode(template.blend_mode || 'normal');
    // Use app-compatible format: image_size array + blend_alpha/feather_radius
    setEditJSON(JSON.stringify({
      corners: template.corners,
      image_size: [template.scene_width, template.scene_height],
      blend_alpha: 1.0,
      feather_radius: 3
    }, null, 2));
    setZoom(1);
    setPanX(0);
    setPanY(0);
    setSelectedCorner(-1);
    setDraggedCorner(null);
    setIsPanning(false);
    setMode('edit');
    // Fit view after render
    setTimeout(() => fitEditView(), 100);
  };

  const fitEditView = () => {
    if (!canvasRef.current || !editingTemplate) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const cw = rect.width;
    const ch = rect.height;
    if (cw < 10 || ch < 10) return;
    const newZoom = Math.min(cw / editingTemplate.scene_width, ch / editingTemplate.scene_height) * 0.92;
    setZoom(newZoom);
    setPanX((cw - editingTemplate.scene_width * newZoom) / 2);
    setPanY((ch - editingTemplate.scene_height * newZoom) / 2);
  };

  // Coordinate transforms: natural image coords ↔ canvas coords
  const natToCanvas = (nx: number, ny: number): [number, number] => {
    return [nx * zoom + panX, ny * zoom + panY];
  };

  const canvasToNat = (cx: number, cy: number): [number, number] => {
    return [(cx - panX) / zoom, (cy - panY) / zoom];
  };

  // Keep refs in sync with state so native listeners read fresh values
  useEffect(() => { zoomRef.current = zoom; }, [zoom]);
  useEffect(() => { panXRef.current = panX; }, [panX]);
  useEffect(() => { panYRef.current = panY; }, [panY]);

  // Native wheel listener (passive: false to allow preventDefault)
  useEffect(() => {
    const el = canvasRef.current;
    if (!el || mode !== 'edit' || !editingTemplate) return;

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const rect = el.getBoundingClientRect();
      const cursorX = e.clientX - rect.left;
      const cursorY = e.clientY - rect.top;

      const z = zoomRef.current;
      const px = panXRef.current;
      const py = panYRef.current;

      // Natural coords at cursor
      const natX = (cursorX - px) / z;
      const natY = (cursorY - py) / z;

      // Zoom factor per scroll tick
      const delta = e.deltaY > 0 ? 0.92 : 1.08;
      const newZoom = Math.max(0.05, Math.min(20, z * delta));

      // Keep point under cursor stable
      const newPanX = cursorX - natX * newZoom;
      const newPanY = cursorY - natY * newZoom;

      zoomRef.current = newZoom;
      panXRef.current = newPanX;
      panYRef.current = newPanY;
      setZoom(newZoom);
      setPanX(newPanX);
      setPanY(newPanY);
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [mode, editingTemplate]);

  // Handle keyboard events
  useEffect(() => {
    if (mode !== 'edit' || !editingTemplate) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Space key for panning
      if (e.code === 'Space' && !spaceHeld) {
        e.preventDefault();
        setSpaceHeld(true);
        return;
      }

      // F key - fit view
      if (e.code === 'KeyF') {
        e.preventDefault();
        fitEditView();
        return;
      }

      // Number keys 1-4 to select corners
      if (['Digit1', 'Digit2', 'Digit3', 'Digit4'].includes(e.code)) {
        e.preventDefault();
        const idx = parseInt(e.code.slice(-1)) - 1;
        setSelectedCorner(idx);
        return;
      }

      // Arrow keys to move selected corner
      if (selectedCorner >= 0 && selectedCorner < 4) {
        const step = e.shiftKey ? 5 : 1;
        let dx = 0, dy = 0;

        if (e.code === 'ArrowLeft') { dx = -step; e.preventDefault(); }
        else if (e.code === 'ArrowRight') { dx = step; e.preventDefault(); }
        else if (e.code === 'ArrowUp') { dy = -step; e.preventDefault(); }
        else if (e.code === 'ArrowDown') { dy = step; e.preventDefault(); }

        if (dx !== 0 || dy !== 0) {
          const newCorners = [...editCorners];
          newCorners[selectedCorner] = [
            Math.max(0, Math.min(editingTemplate.scene_width, newCorners[selectedCorner][0] + dx)),
            Math.max(0, Math.min(editingTemplate.scene_height, newCorners[selectedCorner][1] + dy))
          ];
          setEditCorners(newCorners);

          // Update JSON in app-compatible format
          try {
            const config = JSON.parse(editJSON);
            config.corners = newCorners;
            setEditJSON(JSON.stringify(config, null, 2));
          } catch {}
        }
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        e.preventDefault();
        setSpaceHeld(false);
        setIsPanning(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [mode, editingTemplate, selectedCorner, editCorners, editJSON, zoom, panX, panY, spaceHeld]);

  // Mouse handlers for canvas
  const handleCanvasMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!canvasRef.current) return;

    // Middle click or Space+click for panning
    if (e.button === 1 || (e.button === 0 && spaceHeld)) {
      e.preventDefault();
      setIsPanning(true);
      setPanStart({ x: e.clientX, y: e.clientY, px: panX, py: panY });
      return;
    }
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isPanning && panStart) {
      const dx = e.clientX - panStart.x;
      const dy = e.clientY - panStart.y;
      setPanX(panStart.px + dx);
      setPanY(panStart.py + dy);
    }
  };

  const handleCanvasMouseUp = () => {
    setIsPanning(false);
    setPanStart(null);
  };

  const handleSaveEdit = async () => {
    if (!editingTemplate) return;

    try {
      const config = JSON.parse(editJSON);

      // Support both formats: {width, height} and {image_size: [w, h]}
      let width, height;
      if (config.image_size && Array.isArray(config.image_size)) {
        [width, height] = config.image_size;
      } else {
        width = config.width || editingTemplate.scene_width;
        height = config.height || editingTemplate.scene_height;
      }

      await updateMockupTemplate(
        editingTemplate.id,
        editNameValue || editingTemplate.name,
        editingTemplate.scene_url,
        width,
        height,
        config.corners,
        editBlendMode
      );
      setSuccessMsg('Template updated!');
      setTimeout(() => setSuccessMsg(null), 3000);
      setEditingTemplate(null);
      await loadTemplates();
      setMode('templates');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed');
    }
  };

  const handleCornerMouseDown = (e: React.MouseEvent, cornerIndex: number) => {
    e.stopPropagation();
    setDraggedCorner(cornerIndex);
    setSelectedCorner(cornerIndex);
  };

  const handleCornerDrag = (e: React.MouseEvent<HTMLDivElement>) => {
    if (draggedCorner === null || !editingTemplate || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const canvasX = e.clientX - rect.left;
    const canvasY = e.clientY - rect.top;

    // Convert canvas coords to natural image coords
    const [natX, natY] = canvasToNat(canvasX, canvasY);

    // Clamp to image bounds
    const clampedX = Math.max(0, Math.min(editingTemplate.scene_width, Math.round(natX)));
    const clampedY = Math.max(0, Math.min(editingTemplate.scene_height, Math.round(natY)));

    const newCorners = [...editCorners];
    newCorners[draggedCorner] = [clampedX, clampedY];
    setEditCorners(newCorners);

    // Update JSON in app-compatible format
    try {
      const config = JSON.parse(editJSON);
      config.corners = newCorners;
      setEditJSON(JSON.stringify(config, null, 2));
    } catch {}
  };

  const handleCornerMouseUp = () => {
    setDraggedCorner(null);
  };

  const handleDownloadTemplate = async (template: MockupTemplate) => {
    try {
      const a = document.createElement('a');
      a.href = template.scene_url;
      a.download = `mockup-${template.name.replace(/\s+/g, '-').toLowerCase()}.png`;
      a.click();
    } catch (err) {
      setError('Failed to download template');
    }
  };

  const cornerLabels = ['TL (top-left)', 'TR (top-right)', 'BR (bottom-right)', 'BL (bottom-left)'];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Custom Mockup Generator</h1>
          <p className="text-sm text-gray-500 mt-1">
            Create reusable templates, then instantly compose mockups
          </p>
        </div>
        <Link
          href="/mockups"
          className="px-4 py-2 bg-dark-card border border-dark-border rounded-lg text-sm text-gray-300 hover:bg-dark-hover transition-colors"
        >
          Printify Mockups
        </Link>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}
      {successMsg && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 text-green-400 text-sm">
          {successMsg}
        </div>
      )}

      {/* Mode tabs */}
      <div className="flex gap-2">
        {[
          { key: 'templates' as Mode, label: 'My Templates' },
          { key: 'packs' as Mode, label: 'Packs' },
          { key: 'upload' as Mode, label: 'Upload Mockup' },
          { key: 'generate' as Mode, label: 'Generate Scene' },
          { key: 'compose' as Mode, label: 'Compose Mockup' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setMode(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              mode === tab.key
                ? 'bg-accent text-dark-bg'
                : 'bg-dark-card border border-dark-border text-gray-400 hover:text-gray-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ========== MY TEMPLATES ========== */}
      {mode === 'templates' && (
        <div className="space-y-4">
          {!loadingTemplates && templates.length > 0 && (
            <div className={`text-sm px-3 py-2 rounded-lg ${
              activeTemplateIds.size >= 4
                ? 'bg-green-500/10 text-green-400'
                : activeTemplateIds.size > 0
                ? 'bg-yellow-500/10 text-yellow-400'
                : 'bg-red-500/10 text-red-400'
            }`}>
              {activeTemplateIds.size} active template{activeTemplateIds.size !== 1 ? 's' : ''}
              {' — '}
              {activeTemplateIds.size + 1} image{activeTemplateIds.size + 1 !== 1 ? 's' : ''} per Etsy listing
              {activeTemplateIds.size < 4 && ' (recommended: 4+ for 5 images minimum)'}
            </div>
          )}
          {loadingTemplates ? (
            <div className="text-sm text-gray-500 py-8 text-center">Loading templates...</div>
          ) : templates.length === 0 ? (
            <div className="bg-dark-card border border-dark-border rounded-lg p-8 text-center space-y-3">
              <p className="text-gray-400">No templates yet</p>
              <p className="text-xs text-gray-600">
                Generate a room scene, then define the poster area to create a reusable template
              </p>
              <button
                onClick={() => setMode('generate')}
                className="px-4 py-2 bg-accent text-dark-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
              >
                Generate First Scene
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {templates.map((t) => (
                <div
                  key={t.id}
                  className="bg-dark-card border border-dark-border rounded-lg overflow-hidden group"
                >
                  <div className="relative">
                    <img
                      src={t.scene_url}
                      alt={t.name}
                      className="w-full object-cover"
                      style={{ aspectRatio: `${t.scene_width} / ${t.scene_height}` }}
                    />
                    {/* Draw corner markers */}
                    <svg
                      className="absolute inset-0 w-full h-full pointer-events-none"
                      viewBox={`0 0 ${t.scene_width} ${t.scene_height}`}
                    >
                      <polygon
                        points={t.corners.map((c) => `${c[0]},${c[1]}`).join(' ')}
                        fill="rgba(232,197,71,0.15)"
                        stroke="rgba(232,197,71,0.8)"
                        strokeWidth="3"
                      />
                    </svg>
                  </div>
                  <div className="p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-200 truncate flex items-center gap-1">
                        {t.name}
                        {t.blend_mode === 'multiply' && (
                          <span className="text-[9px] px-1 py-0.5 bg-purple-500/20 text-purple-400 rounded">M</span>
                        )}
                      </span>
                      <button
                        onClick={() => handleToggleActive(t.id)}
                        className={`relative w-9 h-5 rounded-full transition-colors ${
                          activeTemplateIds.has(t.id) ? 'bg-accent' : 'bg-dark-border'
                        }`}
                        title={activeTemplateIds.has(t.id) ? 'Active — click to deactivate' : 'Inactive — click to activate'}
                      >
                        <span
                          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                            activeTemplateIds.has(t.id) ? 'translate-x-4' : 'translate-x-0'
                          }`}
                        />
                      </button>
                    </div>
                    <div className="flex gap-1 flex-wrap">
                      <button
                        onClick={() => {
                          setActiveTemplate(t);
                          setActivePoster(null);
                          setComposedUrl(null);
                          setMode('compose');
                        }}
                        className="px-2 py-1 bg-accent/20 text-accent rounded text-xs hover:bg-accent/30 transition-colors"
                      >
                        Use
                      </button>
                      <button
                        onClick={() => handleEdit(t)}
                        className="px-2 py-1 bg-blue-500/10 text-blue-400 rounded text-xs hover:bg-blue-500/20 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDownloadTemplate(t)}
                        className="px-2 py-1 bg-green-500/10 text-green-400 rounded text-xs hover:bg-green-500/20 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        ↓
                      </button>
                      <button
                        onClick={() => handleDeleteTemplate(t.id)}
                        className="px-2 py-1 bg-red-500/10 text-red-400 rounded text-xs hover:bg-red-500/20 transition-colors opacity-0 group-hover:opacity-100"
                      >
                        Del
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========== GENERATE SCENE ========== */}
      {mode === 'generate' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-4">
              <h2 className="text-sm font-medium text-gray-200">1. Generate Room Scene</h2>

              <div className="grid grid-cols-3 gap-2">
                {Object.entries(scenes).map(([key, scene]) => (
                  <button
                    key={key}
                    onClick={() => {
                      setSelectedScene(key);
                      setUseCustom(false);
                    }}
                    className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                      selectedScene === key && !useCustom
                        ? 'bg-accent text-dark-bg'
                        : 'bg-dark-bg border border-dark-border text-gray-400 hover:text-gray-200'
                    }`}
                  >
                    {scene.name}
                  </button>
                ))}
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-2 block">AI Model (Style)</label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-100 focus:outline-none focus:border-accent"
                >
                  {Object.entries(models).map(([key, model]) => (
                    <option key={key} value={key}>
                      {model.name} — {model.description}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-2 block">Style</label>
                <select
                  value={selectedStyle}
                  onChange={(e) => setSelectedStyle(e.target.value)}
                  className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-100 focus:outline-none focus:border-accent"
                >
                  {Object.entries(styles).map(([key, style]) => (
                    <option key={key} value={key}>
                      {style.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-2 block">Poster Ratio</label>
                <div className="flex gap-2">
                  {Object.entries(ratios).map(([key, ratio]) => (
                    <button
                      key={key}
                      onClick={() => setSelectedRatio(key)}
                      className={`flex-1 px-2 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        selectedRatio === key
                          ? 'bg-accent/20 text-accent border border-accent/40'
                          : 'bg-dark-bg border border-dark-border text-gray-400 hover:text-gray-200'
                      }`}
                    >
                      {ratio.name}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="flex items-center gap-2 text-xs text-gray-400 mb-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={useCustom}
                    onChange={(e) => setUseCustom(e.target.checked)}
                    className="rounded border-dark-border"
                  />
                  Custom prompt
                </label>
                {useCustom && (
                  <textarea
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    placeholder="A modern studio with a white blank vertical poster in a frame on the wall..."
                    rows={3}
                    className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-accent resize-none"
                  />
                )}
              </div>

              <button
                onClick={handleGenerate}
                disabled={isGenerating || (useCustom && !customPrompt.trim())}
                className="w-full px-4 py-2.5 bg-accent text-dark-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
              >
                {isGenerating ? 'Generating scene...' : 'Generate Scene'}
              </button>
            </div>
          </div>

          {/* Generated scenes */}
          <div className="space-y-4">
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <h2 className="text-sm font-medium text-gray-200">
                2. Click a scene to define poster zone
              </h2>
              {generatedScenes.length === 0 ? (
                <div
                  className="bg-dark-bg border border-dark-border rounded-lg flex items-center justify-center text-gray-600 text-sm"
                  style={{ aspectRatio: '4 / 5' }}
                >
                  Generate a scene to get started
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3">
                  {generatedScenes.map((scene, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setDefineScene(scene);
                        setCorners([]);
                        setTemplateName('');
                        setMode('define');
                      }}
                      className="relative rounded-lg overflow-hidden border-2 border-transparent hover:border-accent transition-colors"
                    >
                      <img
                        src={scene.url}
                        alt={`Scene ${i + 1}`}
                        className="w-full object-cover"
                        style={{ aspectRatio: `${scene.width} / ${scene.height}` }}
                      />
                      <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 to-transparent p-2">
                        <span className="text-xs text-white">Click to define poster zone</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========== DEFINE CORNERS ========== */}
      {mode === 'define' && defineScene && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <h2 className="text-sm font-medium text-gray-200">
                Click 4 corners of the poster area (TL → TR → BR → BL)
              </h2>
              <div
                ref={imgRef}
                className="relative rounded-lg overflow-hidden"
                onClick={handleCornerClick}
                onMouseMove={handleDefineMouseMove}
                onMouseUp={handleDefineMouseUp}
                onMouseLeave={handleDefineMouseUp}
                style={{
                  aspectRatio: `${defineScene.width} / ${defineScene.height}`,
                  cursor: defineDraggedCorner !== null ? 'grabbing' : corners.length >= 4 ? 'default' : 'crosshair',
                }}
              >
                <img
                  src={defineScene.url}
                  alt="Scene"
                  className="w-full h-full object-cover"
                  draggable={false}
                />
                {/* SVG overlay for corners and polygon */}
                <svg
                  className="absolute inset-0 w-full h-full pointer-events-none"
                  viewBox={`0 0 ${defineScene.width} ${defineScene.height}`}
                >
                  {corners.length >= 2 && (
                    <polyline
                      points={corners.map((c) => `${c[0]},${c[1]}`).join(' ')}
                      fill="none"
                      stroke="rgba(232,197,71,0.8)"
                      strokeWidth="3"
                      strokeDasharray={corners.length < 4 ? '8,4' : undefined}
                    />
                  )}
                  {corners.length === 4 && (
                    <polygon
                      points={corners.map((c) => `${c[0]},${c[1]}`).join(' ')}
                      fill="rgba(232,197,71,0.15)"
                      stroke="rgba(232,197,71,0.8)"
                      strokeWidth="3"
                    />
                  )}
                  {corners.map((c, i) => (
                    <g key={i} style={{ pointerEvents: 'all' }}>
                      <circle
                        cx={c[0]} cy={c[1]} r="12"
                        fill={defineDraggedCorner === i ? 'rgba(232,197,71,1)' : 'rgba(232,197,71,0.9)'}
                        stroke="white" strokeWidth="2"
                        onMouseDown={(e: React.MouseEvent) => handleDefineCornerMouseDown(e, i)}
                        style={{ cursor: 'grab' }}
                      />
                      <text
                        x={c[0]}
                        y={c[1] - 18}
                        textAnchor="middle"
                        fill="white"
                        fontSize="18"
                        fontWeight="bold"
                        style={{ pointerEvents: 'none' }}
                      >
                        {i + 1}
                      </text>
                    </g>
                  ))}
                </svg>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <h2 className="text-sm font-medium text-gray-200">Corner Points</h2>
              <div className="space-y-2">
                {[0, 1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className={`flex items-center gap-2 text-xs ${
                      corners[i] ? 'text-accent' : 'text-gray-600'
                    }`}
                  >
                    <div
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                        corners[i] ? 'bg-accent text-dark-bg' : 'bg-dark-bg border border-dark-border'
                      }`}
                    >
                      {i + 1}
                    </div>
                    <span>{cornerLabels[i]}</span>
                    {corners[i] && (
                      <span className="text-gray-500 ml-auto">
                        ({corners[i][0]}, {corners[i][1]})
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {corners.length > 0 && corners.length < 4 && (
                <div className="flex gap-3">
                  <button
                    onClick={() => setCorners((prev: Corner[]) => prev.slice(0, -1))}
                    className="text-xs text-yellow-400 hover:text-yellow-300"
                  >
                    Undo last
                  </button>
                  <button
                    onClick={() => setCorners([])}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Reset all
                  </button>
                </div>
              )}

              {corners.length === 4 && (
                <>
                  <input
                    type="text"
                    value={templateName}
                    onChange={(e) => setTemplateName(e.target.value)}
                    placeholder="Template name (e.g. Living Room 1)"
                    className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-accent"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => setCorners([])}
                      className="flex-1 px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-xs text-gray-400 hover:text-gray-200 transition-colors"
                    >
                      Reset
                    </button>
                    <button
                      onClick={handleSaveTemplate}
                      disabled={savingTemplate || !templateName.trim()}
                      className="flex-1 px-3 py-2 bg-accent text-dark-bg rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
                    >
                      {savingTemplate ? 'Saving...' : 'Save Template'}
                    </button>
                  </div>
                </>
              )}
            </div>

            <button
              onClick={() => setMode('generate')}
              className="w-full px-3 py-2 bg-dark-card border border-dark-border rounded-lg text-xs text-gray-400 hover:text-gray-200 transition-colors"
            >
              Back to scenes
            </button>
          </div>
        </div>
      )}

      {/* ========== COMPOSE MOCKUP ========== */}
      {mode === 'compose' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: template picker + poster picker */}
          <div className="space-y-4">
            {/* Template selection */}
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <h2 className="text-sm font-medium text-gray-200">1. Select Template</h2>
              {templates.length === 0 ? (
                <p className="text-xs text-gray-500">
                  No templates yet.{' '}
                  <button onClick={() => setMode('generate')} className="text-accent hover:underline">
                    Create one
                  </button>
                </p>
              ) : (
                <div className="grid grid-cols-3 gap-2">
                  {templates.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => {
                        setActiveTemplate(t);
                        setComposedUrl(null);
                      }}
                      className={`relative rounded-lg overflow-hidden border-2 transition-colors ${
                        activeTemplate?.id === t.id
                          ? 'border-accent'
                          : 'border-transparent hover:border-dark-border'
                      }`}
                    >
                      <img
                        src={t.scene_url}
                        alt={t.name}
                        className="w-full object-cover"
                        style={{ aspectRatio: `${t.scene_width} / ${t.scene_height}` }}
                      />
                      <svg
                        className="absolute inset-0 w-full h-full pointer-events-none"
                        viewBox={`0 0 ${t.scene_width} ${t.scene_height}`}
                      >
                        <polygon
                          points={t.corners.map((c) => `${c[0]},${c[1]}`).join(' ')}
                          fill="rgba(232,197,71,0.1)"
                          stroke="rgba(232,197,71,0.5)"
                          strokeWidth="2"
                        />
                      </svg>
                      {activeTemplate?.id === t.id && (
                        <div className="absolute top-1 right-1 w-4 h-4 bg-accent rounded-full flex items-center justify-center">
                          <svg
                            className="w-3 h-3 text-dark-bg"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={3}
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Poster selection */}
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <h2 className="text-sm font-medium text-gray-200">2. Select Poster</h2>
              {loadingHistory ? (
                <div className="text-xs text-gray-500 py-4 text-center">Loading posters...</div>
              ) : historyItems.length === 0 ? (
                <div className="text-xs text-gray-500 py-4 text-center">No posters found</div>
              ) : (
                <div className="grid grid-cols-5 gap-2 max-h-64 overflow-y-auto">
                  {historyItems.flatMap((item) =>
                    item.images.map((img) => (
                      <button
                        key={img.id}
                        onClick={() => {
                          setActivePoster(img.url);
                          setComposedUrl(null);
                        }}
                        className={`relative rounded-lg overflow-hidden border-2 transition-colors ${
                          activePoster === img.url
                            ? 'border-accent'
                            : 'border-transparent hover:border-dark-border'
                        }`}
                      >
                        <img src={img.url} alt="" className="w-full aspect-[4/5] object-cover" />
                        {activePoster === img.url && (
                          <div className="absolute top-1 right-1 w-4 h-4 bg-accent rounded-full flex items-center justify-center">
                            <svg
                              className="w-3 h-3 text-dark-bg"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={3}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M5 13l4 4L19 7"
                              />
                            </svg>
                          </div>
                        )}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Fill Mode Selector */}
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <h3 className="text-sm font-medium text-gray-200">Compose Mode</h3>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => setFillMode('stretch')}
                  className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                    fillMode === 'stretch'
                      ? 'bg-accent text-dark-bg'
                      : 'bg-dark-bg border border-dark-border text-gray-400 hover:text-gray-200 hover:border-accent/40'
                  }`}
                >
                  <div className="font-semibold mb-0.5">↔️ Stretch</div>
                  <div className="text-[10px] opacity-75">May distort</div>
                </button>
                <button
                  onClick={() => setFillMode('fit')}
                  className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                    fillMode === 'fit'
                      ? 'bg-accent text-dark-bg'
                      : 'bg-dark-bg border border-dark-border text-gray-400 hover:text-gray-200 hover:border-accent/40'
                  }`}
                >
                  <div className="font-semibold mb-0.5">🖼️ Fit</div>
                  <div className="text-[10px] opacity-75">Add white mat</div>
                </button>
                <button
                  onClick={() => setFillMode('fill')}
                  className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                    fillMode === 'fill'
                      ? 'bg-accent text-dark-bg'
                      : 'bg-dark-bg border border-dark-border text-gray-400 hover:text-gray-200 hover:border-accent/40'
                  }`}
                >
                  <div className="font-semibold mb-0.5">✂️ Fill</div>
                  <div className="text-[10px] opacity-75">Crop edges</div>
                </button>
              </div>
            </div>

            {/* Color Grade */}
            {colorGrades.length > 0 && (
              <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
                <h3 className="text-sm font-medium text-gray-200">Color Grade</h3>
                <div className="flex flex-wrap gap-2">
                  {colorGrades.map((g) => (
                    <button
                      key={g.id}
                      onClick={() => {
                        setComposeColorGrade(g.id);
                        setComposedUrl(null);
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        composeColorGrade === g.id
                          ? 'bg-purple-500/30 border border-purple-500/50 text-purple-300'
                          : 'bg-dark-bg border border-dark-border text-gray-400 hover:text-gray-200 hover:border-purple-500/30'
                      }`}
                    >
                      {g.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Compose button */}
            {activeTemplate && activePoster && (
              <button
                onClick={handleCompose}
                disabled={isComposing}
                className="w-full px-4 py-3 bg-accent text-dark-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
              >
                {isComposing ? 'Composing...' : 'Create Mockup'}
              </button>
            )}
          </div>

          {/* Right: Preview */}
          <div className="space-y-4">
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-gray-200">3. Result</h2>
                {composedUrl && (
                  <button
                    onClick={handleDownload}
                    className="px-4 py-1.5 bg-accent text-dark-bg rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors"
                  >
                    Download PNG
                  </button>
                )}
              </div>

              {isComposing ? (
                <div
                  className="bg-dark-bg border border-dark-border rounded-lg flex items-center justify-center text-gray-500 text-sm"
                  style={{
                    aspectRatio: activeTemplate
                      ? `${activeTemplate.scene_width} / ${activeTemplate.scene_height}`
                      : '4 / 5',
                  }}
                >
                  Composing with perspective transform...
                </div>
              ) : composedUrl ? (
                <img
                  src={composedUrl}
                  alt="Composed mockup"
                  className="w-full rounded-lg"
                  style={{
                    aspectRatio: activeTemplate
                      ? `${activeTemplate.scene_width} / ${activeTemplate.scene_height}`
                      : undefined,
                  }}
                />
              ) : activeTemplate ? (
                <div className="relative">
                  <img
                    src={activeTemplate.scene_url}
                    alt="Template preview"
                    className="w-full rounded-lg opacity-60"
                    style={{
                      aspectRatio: `${activeTemplate.scene_width} / ${activeTemplate.scene_height}`,
                    }}
                  />
                  <svg
                    className="absolute inset-0 w-full h-full pointer-events-none"
                    viewBox={`0 0 ${activeTemplate.scene_width} ${activeTemplate.scene_height}`}
                  >
                    <polygon
                      points={activeTemplate.corners.map((c) => `${c[0]},${c[1]}`).join(' ')}
                      fill="rgba(232,197,71,0.2)"
                      stroke="rgba(232,197,71,0.8)"
                      strokeWidth="3"
                      strokeDasharray="8,4"
                    />
                    <text
                      x={activeTemplate.corners.reduce((s, c) => s + c[0], 0) / 4}
                      y={activeTemplate.corners.reduce((s, c) => s + c[1], 0) / 4}
                      textAnchor="middle"
                      fill="rgba(232,197,71,0.8)"
                      fontSize="24"
                      fontWeight="bold"
                    >
                      Poster goes here
                    </text>
                  </svg>
                </div>
              ) : (
                <div
                  className="bg-dark-bg border border-dark-border rounded-lg flex items-center justify-center text-gray-600 text-sm"
                  style={{ aspectRatio: '4 / 5' }}
                >
                  Select a template and poster
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========== UPLOAD MOCKUP ========== */}
      {mode === 'upload' && (
        <div className="max-w-2xl mx-auto space-y-4">
          <div className="bg-dark-card border border-dark-border rounded-lg p-6 space-y-4">
            <h2 className="text-lg font-medium text-gray-200">Upload Custom Mockup</h2>

            <div>
              <label className="text-sm text-gray-400 mb-2 block">1. Upload Image</label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-100 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:bg-accent file:text-dark-bg hover:file:bg-accent-hover"
              />
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-2 block">2. Template Name</label>
              <input
                type="text"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                placeholder="My Custom Mockup"
                className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-100 focus:outline-none focus:border-accent"
              />
            </div>

            <div>
              <label className="text-sm text-gray-400 mb-2 block">3. Configuration JSON</label>
              <textarea
                value={uploadJSON}
                onChange={(e) => setUploadJSON(e.target.value)}
                rows={14}
                className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-xs font-mono text-gray-100 focus:outline-none focus:border-accent resize-none"
              />
              <p className="text-xs text-gray-600 mt-1">
                Supports both formats: <code className="text-accent">image_size: [w, h]</code> or <code className="text-accent">width/height</code> separately. Copy-paste from your app!
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setMode('templates')}
                className="flex-1 px-4 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={isUploading || !uploadFile || !uploadName.trim()}
                className="flex-1 px-4 py-2 bg-accent text-dark-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
              >
                {isUploading ? 'Uploading...' : 'Upload Template'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========== EDIT TEMPLATE ========== */}
      {/* ========== PACKS ========== */}
      {mode === 'packs' && (() => {
        const loadPacks = async () => {
          setLoadingPacks(true);
          try {
            const data = await getMockupPacks();
            setPacks(data.packs);
          } catch {} finally {
            setLoadingPacks(false);
          }
        };

        const handleSavePack = async () => {
          if (!packName.trim()) return;
          setSavingPack(true);
          setError(null);
          try {
            const ids = Array.from(packTemplateIds) as number[];
            if (editingPack) {
              const result = await updateMockupPack(editingPack.id, packName.trim(), ids, packColorGrade);
              const affected = (result as any).affected_products || 0;
              if (affected > 0) {
                setSuccessMsg(`Pack updated! Reapplying to ${affected} product${affected !== 1 ? 's' : ''} in background...`);
              } else {
                setSuccessMsg('Pack updated!');
              }
            } else {
              await createMockupPack(packName.trim(), ids, packColorGrade);
              setSuccessMsg('Pack created!');
            }
            setTimeout(() => setSuccessMsg(null), 6000);
            setEditingPack(null);
            setPackName('');
            setPackTemplateIds(new Set());
            setPackColorGrade('none');
            loadPacks();
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save pack');
          } finally {
            setSavingPack(false);
          }
        };

        const handleDeletePack = async (packId: number) => {
          if (!confirm('Delete this pack? Templates will not be affected.')) return;
          try {
            await deleteMockupPack(packId);
            loadPacks();
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to delete pack');
          }
        };

        const startEditPack = async (pack: MockupPack) => {
          setEditingPack(pack);
          setPackName(pack.name);
          setPackColorGrade(pack.color_grade || 'none');
          try {
            const data = await getMockupPack(pack.id);
            setPackTemplateIds(new Set((data.templates || []).map((t: MockupTemplate) => t.id)));
          } catch {
            setPackTemplateIds(new Set());
          }
        };

        // Auto-load packs on tab open
        if (packs.length === 0 && !loadingPacks) {
          loadPacks();
        }

        const isEditing = editingPack !== null || packName.trim().length > 0;

        return (
          <div className="space-y-4">
            {/* Create / Edit form */}
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-medium text-gray-200">
                  {editingPack ? `Edit Pack: ${editingPack.name}` : 'Create New Pack'}
                </h2>
                {editingPack && (
                  <button
                    onClick={() => { setEditingPack(null); setPackName(''); setPackTemplateIds(new Set()); setPackColorGrade('none'); }}
                    className="text-xs text-gray-500 hover:text-gray-300"
                  >
                    Cancel Edit
                  </button>
                )}
              </div>

              <input
                type="text"
                value={packName}
                onChange={(e) => setPackName(e.target.value)}
                placeholder="Pack name (e.g., Living Room, Office...)"
                className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-100 focus:outline-none focus:border-accent"
              />

              {/* Template picker */}
              <div>
                <label className="text-xs text-gray-500 mb-2 block">
                  Select templates ({packTemplateIds.size} selected)
                </label>
                {templates.length === 0 ? (
                  <p className="text-xs text-gray-600">No templates yet. Create some first.</p>
                ) : (
                  <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 max-h-48 overflow-y-auto">
                    {templates.map((t) => {
                      const selected = packTemplateIds.has(t.id);
                      return (
                        <button
                          key={t.id}
                          onClick={() => {
                            setPackTemplateIds((prev: Set<number>) => {
                              const next = new Set(prev);
                              if (next.has(t.id)) next.delete(t.id);
                              else next.add(t.id);
                              return next;
                            });
                          }}
                          className={`relative rounded-lg overflow-hidden border-2 transition-colors ${
                            selected ? 'border-accent' : 'border-transparent hover:border-dark-border'
                          }`}
                        >
                          <img src={t.scene_url} alt={t.name} className="w-full aspect-[4/5] object-cover" />
                          {selected && (
                            <div className="absolute top-1 right-1 w-5 h-5 bg-accent rounded-full flex items-center justify-center">
                              <span className="text-dark-bg text-xs font-bold">
                                {Array.from(packTemplateIds).indexOf(t.id) + 1}
                              </span>
                            </div>
                          )}
                          <div className="absolute bottom-0 inset-x-0 bg-black/60 px-1 py-0.5">
                            <span className="text-[9px] text-white leading-tight line-clamp-1">{t.name}</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Color grade selector */}
              {colorGrades.length > 0 && (
                <div>
                  <label className="text-xs text-gray-500 mb-2 block">Color Grade</label>
                  <div className="flex gap-2 flex-wrap">
                    {colorGrades.map((g) => (
                      <button
                        key={g.id}
                        onClick={() => setPackColorGrade(g.id)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                          packColorGrade === g.id
                            ? 'bg-accent text-dark-bg'
                            : 'bg-dark-bg border border-dark-border text-gray-400 hover:text-gray-200'
                        }`}
                      >
                        {g.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <button
                onClick={handleSavePack}
                disabled={!packName.trim() || packTemplateIds.size === 0 || savingPack}
                className="px-4 py-2 bg-accent text-dark-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50"
              >
                {savingPack ? 'Saving...' : editingPack ? 'Update Pack' : 'Create Pack'}
              </button>
            </div>

            {/* Existing packs */}
            {loadingPacks ? (
              <div className="text-center text-gray-500 py-8">Loading packs...</div>
            ) : packs.length === 0 && !isEditing ? (
              <div className="text-center text-gray-600 py-8">No packs yet. Create one above.</div>
            ) : (
              <div className="space-y-3">
                {packs.map((pack: MockupPack) => (
                  <div
                    key={pack.id}
                    className={`bg-dark-card border rounded-lg p-4 ${
                      editingPack?.id === pack.id ? 'border-accent/50' : 'border-dark-border'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium text-gray-200">{pack.name}</h3>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-accent/15 text-accent">
                          {pack.template_count} templates
                        </span>
                        {pack.color_grade && pack.color_grade !== 'none' && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/15 text-purple-400">
                            {colorGrades.find((g) => g.id === pack.color_grade)?.name || pack.color_grade}
                          </span>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => startEditPack(pack)}
                          className="text-xs text-gray-400 hover:text-accent transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleDeletePack(pack.id)}
                          className="text-xs text-gray-400 hover:text-red-400 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })()}

      {mode === 'edit' && editingTemplate && (
        <div className="max-w-7xl mx-auto space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Interactive Canvas */}
            <div className="lg:col-span-2 bg-dark-card border border-dark-border rounded-lg p-2 flex flex-col">
              {/* Canvas with zoom/pan */}
              <div
                ref={canvasRef}
                className="relative w-full rounded-lg overflow-hidden flex-1"
                style={{
                  minHeight: 'calc(100vh - 12rem)',
                  cursor: spaceHeld || isPanning ? 'grab' : draggedCorner !== null ? 'grabbing' : 'crosshair',
                  backgroundImage: 'linear-gradient(45deg, #1a1a2e 25%, transparent 25%), linear-gradient(-45deg, #1a1a2e 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #1a1a2e 75%), linear-gradient(-45deg, transparent 75%, #1a1a2e 75%)',
                  backgroundSize: '20px 20px',
                  backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0',
                  backgroundColor: '#141422',
                }}
                onMouseDown={handleCanvasMouseDown}
                onMouseMove={(e) => {
                  handleCanvasMouseMove(e);
                  if (draggedCorner !== null) handleCornerDrag(e);
                }}
                onMouseUp={() => {
                  handleCanvasMouseUp();
                  handleCornerMouseUp();
                }}
                onMouseLeave={() => {
                  handleCanvasMouseUp();
                  handleCornerMouseUp();
                }}
                onContextMenu={(e) => e.preventDefault()}
              >
                {/* Image transformed by zoom/pan */}
                <img
                  src={editingTemplate.scene_url}
                  alt={editingTemplate.name}
                  className="absolute block"
                  draggable={false}
                  style={{
                    left: panX,
                    top: panY,
                    width: editingTemplate.scene_width * zoom,
                    height: editingTemplate.scene_height * zoom,
                    maxWidth: 'none',
                    maxHeight: 'none',
                    pointerEvents: 'none',
                    userSelect: 'none',
                    filter: 'drop-shadow(0 4px 24px rgba(0,0,0,0.5))',
                  }}
                />

                {/* Live poster preview overlay (clipped to polygon) */}
                {editPreviewPoster && editCorners.length === 4 && editingTemplate && (() => {
                  const sw = editingTemplate.scene_width;
                  const sh = editingTemplate.scene_height;
                  const clipPoints = editCorners
                    .map((c: Corner) => `${(c[0] / sw) * 100}% ${(c[1] / sh) * 100}%`)
                    .join(', ');
                  const xs = editCorners.map((c: Corner) => c[0]);
                  const ys = editCorners.map((c: Corner) => c[1]);
                  const bx = Math.min(...xs), by = Math.min(...ys);
                  const bw = Math.max(...xs) - bx, bh = Math.max(...ys) - by;
                  if (bw < 10 || bh < 10) return null;
                  return (
                    <div
                      style={{
                        position: 'absolute',
                        left: panX,
                        top: panY,
                        width: sw * zoom,
                        height: sh * zoom,
                        maxWidth: 'none',
                        maxHeight: 'none',
                        clipPath: `polygon(${clipPoints})`,
                        pointerEvents: 'none',
                      }}
                    >
                      <img
                        src={editPreviewPoster}
                        alt=""
                        draggable={false}
                        style={{
                          position: 'absolute',
                          left: `${(bx / sw) * 100}%`,
                          top: `${(by / sh) * 100}%`,
                          width: `${(bw / sw) * 100}%`,
                          height: `${(bh / sh) * 100}%`,
                          objectFit: 'cover',
                          maxWidth: 'none',
                          maxHeight: 'none',
                          opacity: 0.85,
                        }}
                      />
                    </div>
                  );
                })()}

                {/* SVG overlay for corner markers in canvas coords */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none">
                  {/* Image boundary guide */}
                  {(() => {
                    const [x0, y0] = natToCanvas(0, 0);
                    const [x1, y1] = natToCanvas(editingTemplate.scene_width, editingTemplate.scene_height);
                    return (
                      <rect
                        x={x0} y={y0} width={x1 - x0} height={y1 - y0}
                        fill="none"
                        stroke="rgba(255,255,255,0.12)"
                        strokeWidth="1"
                        strokeDasharray="6,4"
                      />
                    );
                  })()}

                  {/* Polygon */}
                  {editCorners.length === 4 && (
                    <polygon
                      points={editCorners
                        .map((c) => {
                          const [cx, cy] = natToCanvas(c[0], c[1]);
                          return `${cx},${cy}`;
                        })
                        .join(' ')}
                      fill={editPreviewPoster ? 'none' : 'rgba(232,197,71,0.15)'}
                      stroke="rgba(232,197,71,0.8)"
                      strokeWidth="2"
                    />
                  )}

                  {/* Edge dimension labels */}
                  {editCorners.length === 4 && (() => {
                    const topW = Math.round(Math.abs(editCorners[1][0] - editCorners[0][0]));
                    const leftH = Math.round(Math.abs(editCorners[3][1] - editCorners[0][1]));
                    const [tlx, tly] = natToCanvas(editCorners[0][0], editCorners[0][1]);
                    const [trx, try_] = natToCanvas(editCorners[1][0], editCorners[1][1]);
                    const [blx, bly] = natToCanvas(editCorners[3][0], editCorners[3][1]);
                    return (
                      <>
                        <text
                          x={(tlx + trx) / 2} y={Math.min(tly, try_) - 8}
                          textAnchor="middle" fill="rgba(232,197,71,0.6)" fontSize="10"
                          style={{ pointerEvents: 'none', userSelect: 'none' }}
                        >{topW}px</text>
                        <text
                          x={Math.min(tlx, blx) - 8} y={(tly + bly) / 2}
                          textAnchor="end" fill="rgba(232,197,71,0.6)" fontSize="10"
                          dominantBaseline="middle"
                          style={{ pointerEvents: 'none', userSelect: 'none' }}
                        >{leftH}px</text>
                      </>
                    );
                  })()}

                  {/* Corner markers — fixed screen-space size */}
                  {editCorners.map((corner, i) => {
                    const [cx, cy] = natToCanvas(corner[0], corner[1]);
                    const isSelected = selectedCorner === i;
                    const isDragging = draggedCorner === i;

                    return (
                      <g key={i} style={{ pointerEvents: 'all' }}>
                        {/* Invisible hit area (larger) */}
                        <circle
                          cx={cx} cy={cy} r={16}
                          fill="transparent"
                          onMouseDown={(e) => handleCornerMouseDown(e, i)}
                          style={{ cursor: 'grab' }}
                        />

                        {/* Outer glow for selected */}
                        {isSelected && (
                          <circle
                            cx={cx} cy={cy} r={11}
                            fill="none"
                            stroke="rgba(232,197,71,0.4)"
                            strokeWidth="2"
                            style={{ pointerEvents: 'none' }}
                          />
                        )}

                        {/* Main circle */}
                        <circle
                          cx={cx} cy={cy} r={7}
                          fill={isDragging ? 'rgba(232,197,71,1)' : isSelected ? 'rgba(232,197,71,0.95)' : 'rgba(232,197,71,0.85)'}
                          stroke="white"
                          strokeWidth={isSelected ? 2.5 : 1.5}
                          style={{ pointerEvents: 'none' }}
                        />

                        {/* Corner number */}
                        <text
                          x={cx} y={cy - 16}
                          textAnchor="middle" fill="white" fontSize="11" fontWeight="bold"
                          style={{ pointerEvents: 'none', userSelect: 'none' }}
                        >
                          {i + 1}
                        </text>

                        {/* Coordinates */}
                        <text
                          x={cx} y={cy + 22}
                          textAnchor="middle" fill="rgba(232,197,71,0.9)" fontSize="10" fontWeight="bold"
                          style={{ pointerEvents: 'none', userSelect: 'none' }}
                        >
                          ({corner[0]}, {corner[1]})
                        </text>
                      </g>
                    );
                  })}
                </svg>

                {/* Floating zoom toolbar */}
                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-dark-card/90 backdrop-blur border border-dark-border rounded-lg px-2 py-1.5 shadow-lg" style={{ pointerEvents: 'all' }}>
                  <button
                    onClick={() => {
                      const newZoom = Math.max(0.05, zoom * 0.8);
                      setPanX(panX + (zoom - newZoom) * editingTemplate.scene_width / 2);
                      setPanY(panY + (zoom - newZoom) * editingTemplate.scene_height / 2);
                      setZoom(newZoom);
                    }}
                    className="w-6 h-6 flex items-center justify-center text-gray-400 hover:text-white rounded hover:bg-dark-hover transition-colors text-sm font-bold"
                  >-</button>
                  <span className="text-xs text-gray-300 font-mono w-12 text-center select-none">
                    {Math.round(zoom * 100)}%
                  </span>
                  <button
                    onClick={() => {
                      const newZoom = Math.min(20, zoom * 1.25);
                      setPanX(panX + (zoom - newZoom) * editingTemplate.scene_width / 2);
                      setPanY(panY + (zoom - newZoom) * editingTemplate.scene_height / 2);
                      setZoom(newZoom);
                    }}
                    className="w-6 h-6 flex items-center justify-center text-gray-400 hover:text-white rounded hover:bg-dark-hover transition-colors text-sm font-bold"
                  >+</button>
                  <div className="w-px h-4 bg-dark-border mx-1" />
                  <button
                    onClick={fitEditView}
                    className="px-2 py-0.5 text-xs text-gray-400 hover:text-white rounded hover:bg-dark-hover transition-colors"
                  >Fit</button>
                  <button
                    onClick={() => {
                      if (!canvasRef.current) return;
                      const rect = canvasRef.current.getBoundingClientRect();
                      setPanX((rect.width - editingTemplate.scene_width) / 2);
                      setPanY((rect.height - editingTemplate.scene_height) / 2);
                      setZoom(1);
                    }}
                    className="px-2 py-0.5 text-xs text-gray-400 hover:text-white rounded hover:bg-dark-hover transition-colors"
                  >100%</button>
                  {selectedCorner >= 0 && (
                    <>
                      <div className="w-px h-4 bg-dark-border mx-1" />
                      <span className="text-xs text-accent select-none">Corner {selectedCorner + 1}</span>
                    </>
                  )}
                </div>
              </div>

              <div className="text-[10px] text-gray-600 px-2 py-1 flex items-center gap-4">
                <span>Scroll: zoom</span>
                <span>Space+drag: pan</span>
                <span>Drag corners</span>
                <span>Arrows: ±1px (Shift ±5)</span>
                <span>1-4: select corner</span>
                <span>F: fit</span>
              </div>
            </div>

            {/* JSON Editor + Controls */}
            <div className="bg-dark-card border border-dark-border rounded-lg p-4 space-y-3">
              <h2 className="text-sm font-medium text-gray-200">Configuration</h2>

              {/* Template name */}
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Template Name</label>
                <input
                  type="text"
                  value={editNameValue}
                  onChange={(e) => setEditNameValue(e.target.value)}
                  className="w-full px-3 py-1.5 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-100 focus:outline-none focus:border-accent"
                />
              </div>

              {/* Blend mode */}
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Blend Mode</label>
                <div className="flex gap-2">
                  {['normal', 'multiply'].map((m) => (
                    <button
                      key={m}
                      onClick={() => setEditBlendMode(m)}
                      className={`flex-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        editBlendMode === m
                          ? 'bg-accent text-dark-bg'
                          : 'bg-dark-bg border border-dark-border text-gray-400 hover:text-gray-200'
                      }`}
                    >
                      {m.charAt(0).toUpperCase() + m.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Corner coordinates */}
              <div className="space-y-2">
                {cornerLabels.map((label, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedCorner(i)}
                    className={`w-full flex items-center gap-2 text-xs p-2 rounded transition-colors ${
                      selectedCorner === i
                        ? 'bg-accent/20 border border-accent/40'
                        : 'bg-dark-bg border border-transparent hover:border-dark-border'
                    }`}
                  >
                    <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      selectedCorner === i ? 'bg-accent text-dark-bg' : 'bg-dark-border text-gray-400'
                    }`}>
                      {i + 1}
                    </span>
                    <span className={`flex-1 text-left ${selectedCorner === i ? 'text-gray-200' : 'text-gray-500'}`}>
                      {label}
                    </span>
                    <span className={`font-mono ${selectedCorner === i ? 'text-accent' : 'text-gray-600'}`}>
                      ({editCorners[i]?.[0] || 0}, {editCorners[i]?.[1] || 0})
                    </span>
                  </button>
                ))}
              </div>

              <div className="border-t border-dark-border pt-3">
                <label className="text-xs text-gray-500 mb-2 block">Raw JSON</label>
                <textarea
                  value={editJSON}
                  onChange={(e) => {
                    setEditJSON(e.target.value);
                    try {
                      const config = JSON.parse(e.target.value);
                      if (config.corners && config.corners.length === 4) {
                        setEditCorners(config.corners);
                      }
                    } catch {}
                  }}
                  rows={12}
                  className="w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-lg text-xs font-mono text-gray-100 focus:outline-none focus:border-accent resize-none"
                />
              </div>

              {/* Live preview poster selector */}
              <div className="border-t border-dark-border pt-3">
                <label className="text-xs text-gray-500 mb-2 block">
                  Live Preview {editPreviewPoster ? '(click to remove)' : '— select a poster'}
                </label>
                {editPreviewPoster ? (
                  <div className="flex items-center gap-2">
                    <img
                      src={editPreviewPoster}
                      alt=""
                      className="w-10 h-14 object-cover rounded border border-accent/40"
                    />
                    <button
                      onClick={() => setEditPreviewPoster(null)}
                      className="text-xs text-red-400 hover:text-red-300"
                    >
                      Clear
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-5 gap-1 max-h-32 overflow-y-auto">
                    {historyItems.flatMap((item: HistoryItem) =>
                      item.images.map((img) => (
                        <button
                          key={img.id}
                          onClick={() => setEditPreviewPoster(img.url)}
                          className="rounded overflow-hidden border border-transparent hover:border-accent transition-colors"
                        >
                          <img src={img.url} alt="" className="w-full aspect-[4/5] object-cover" />
                        </button>
                      ))
                    )}
                    {historyItems.length === 0 && (
                      <span className="col-span-5 text-[10px] text-gray-600">No posters in history</span>
                    )}
                  </div>
                )}
              </div>

              <div className="flex gap-3 pt-3">
                <button
                  onClick={() => {
                    setEditingTemplate(null);
                    setEditPreviewPoster(null);
                    setMode('templates');
                  }}
                  className="flex-1 px-4 py-2 bg-dark-bg border border-dark-border rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveEdit}
                  className="flex-1 px-4 py-2 bg-accent text-dark-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
                >
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
