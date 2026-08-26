import React, { useRef, useState, useEffect } from 'react';
import { KeychainConfig } from '../types';
import { Sliders, Type, Box, Move, Upload, RotateCcw, Info, Heart, Shield, RectangleHorizontal, Download, Hexagon, Square, Loader2, Layers } from 'lucide-react';
import { TEMPLATES } from '../src/templates';
import { api, API_BASE } from '../src/api';
import { TTFLoader } from 'three/addons/loaders/TTFLoader.js';
import { SVGLoader } from 'three/addons/loaders/SVGLoader.js';
import { FileCode } from 'lucide-react';
import * as THREE from 'three';
import JSZip from 'jszip';

interface ControlsProps {
  config: KeychainConfig;
  onChange: (newConfig: KeychainConfig) => void;
  onExport: (format: 'stl') => void;
  fonts: { name: string; url: string }[];
  userRole: string;
  isExpired?: boolean;
}

export const Controls: React.FC<ControlsProps> = ({ config, onChange, onExport, fonts, userRole, isExpired }) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const svgInputRef = useRef<HTMLInputElement>(null);
  const [isProcessingFont, setIsProcessingFont] = useState(false);
  const [detectedColors, setDetectedColors] = useState<string[]>([]);
  const [mode, setMode] = useState<'standard' | 'pro' | 'ultra'>('standard');
  const isDemo = userRole === 'user' || userRole === 'guest' || isExpired;

  // Server Templates & Fonts
  const [serverTemplates, setServerTemplates] = useState<string[]>([]);
  const [serverFonts, setServerFonts] = useState<string[]>([]);

  // Fetch templates and fonts on mount and on window focus (to sync with Admin Panel changes)
  const fetchData = () => {
    api.templates.list().then(res => {
      if (res.success) setServerTemplates(res.templates);
    }).catch(console.error);

    api.fonts.list().then(res => {
      if (res.success) setServerFonts(res.fonts);
    }).catch(console.error);
  };

  useEffect(() => {
    // Always fetch fonts
    api.fonts.list().then(res => {
      if (res.success) setServerFonts(res.fonts);
    }).catch(console.error);

    // Fetch templates only for pro/ultra
    if (mode === 'ultra' || mode === 'pro') {
      api.templates.list().then(res => {
        if (res.success) setServerTemplates(res.templates);
      }).catch(console.error);

      const onFocus = () => fetchData(); // Recalls everything
      window.addEventListener('focus', onFocus);
      return () => window.removeEventListener('focus', onFocus);
    }

    // Also add focus listener for standard mode just for fonts?
    const onFocusFonts = () => {
      api.fonts.list().then(res => {
        if (res.success) setServerFonts(res.fonts);
      }).catch(console.error);
    };
    if (mode === 'standard') {
      window.addEventListener('focus', onFocusFonts);
      return () => window.removeEventListener('focus', onFocusFonts);
    }
  }, [mode]);

  const handleServerTemplateChange = async (filename: string) => {
    if (!filename) return;
    try {
      const res = await fetch(`${API_BASE.replace('/php_server', '')}/templates/${filename}`);
      const text = await res.text();
      onChange({
        ...config,
        baseShape: 'template',
        templateContent: text,
        svgMaxDimension: 50 // Default
      });
    } catch (e) { console.error(e); }
  };

  const loadCloudFont = async (filename: string) => {
    setIsProcessingFont(true);
    try {
      const response = await fetch(`${API_BASE}/fonts.php?action=get&filename=${filename}&t=${Date.now()}`);
      if (!response.ok) throw new Error('Failed to download font');

      const arrayBuffer = await response.arrayBuffer();
      const loader = new TTFLoader();
      const fontData = loader.parse(arrayBuffer);
      const blob = new Blob([JSON.stringify(fontData)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);

      onChange({ ...config, fontUrl: url });
    } catch (err) {
      console.error("Cloud Font Error:", err);
      alert("Failed to load cloud font");
    } finally {
      setIsProcessingFont(false);
    }
  };

  // Custom Font Logic
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsProcessingFont(true);
    try {
      let arrayBuffer: ArrayBuffer | null = null;
      if (file.name.toLowerCase().endsWith('.zip')) {
        const zip = new JSZip();
        const contents = await zip.loadAsync(file);
        const fontFile = (Object.values(contents.files) as any[]).find((f: any) =>
          !f.dir && (f.name.toLowerCase().endsWith('.ttf') || f.name.toLowerCase().endsWith('.otf'))
        );
        if (fontFile) arrayBuffer = await (fontFile as any).async('arraybuffer');
      } else {
        arrayBuffer = await file.arrayBuffer();
      }
      if (!arrayBuffer) throw new Error("Could not read file data");
      const loader = new TTFLoader();
      const fontData = loader.parse(arrayBuffer);
      const blob = new Blob([JSON.stringify(fontData)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      onChange({ ...config, fontUrl: url });
    } catch (err) {
      console.error("Font Error:", err);
    } finally {
      setIsProcessingFont(false);
      if (event.target) event.target.value = '';
    }
  };

  const handleSVGUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result as string;
        onChange({
          ...config,
          baseShape: 'template',
          templateContent: content,
          svgMaxDimension: 50 // Reset to reasonable default
        });
      };
      reader.readAsText(file);
      event.target.value = '';
    }
  };

  // Color Detection Effect
  React.useEffect(() => {
    if (config.baseShape === 'template' && config.templateContent) {
      try {
        const loader = new SVGLoader();
        const data = loader.parse(config.templateContent);
        const colorMap: Record<string, number> = {};
        data.paths.forEach((path: any) => {
          let c = config.color;
          if (path.color) c = '#' + path.color.getHexString();

          const shapes = path.toShapes(true);
          shapes.forEach((s: THREE.Shape) => {
            const area = THREE.ShapeUtils.area(s.getPoints());
            colorMap[c] = (colorMap[c] || 0) + Math.abs(area);
          });
        });
        const colors = Object.keys(colorMap);
        setDetectedColors(colors);
        if (!config.baseLayerColor || !colors.includes(config.baseLayerColor)) {
          let maxArea = 0;
          let bestColor = colors[0];
          colors.forEach(c => {
            if (colorMap[c] > maxArea) {
              maxArea = colorMap[c];
              bestColor = c;
            }
          });
          // Auto-select best base
          if (bestColor) {
            const newBase = bestColor;
            // Initialize default layer config based on new base
            const newLayerConfig: any = {};
            colors.forEach(c => {
              const isBase = c === newBase;
              // Base: -Thickness to 0. Rest: 0 to Thickness.
              // We use config.thickness as default depth/offset magnitude
              newLayerConfig[c] = {
                depth: config.thickness,
                offset: isBase ? -config.thickness : 0
              };
            });
            onChange({ ...config, baseLayerColor: newBase, layerConfig: newLayerConfig });
            return; // Stop here to avoid double update
          }
        } else {
          // If base exists but layerConfig missing, init it
          if (!config.layerConfig) {
            const newLayerConfig: any = {};
            colors.forEach(c => {
              const isBase = c === config.baseLayerColor;
              newLayerConfig[c] = {
                depth: config.thickness,
                offset: isBase ? -config.thickness : 0
              };
            });
            onChange({ ...config, layerConfig: newLayerConfig });
          }
        }
      } catch (e) { console.error("Error parsing colors", e); }
    }
  }, [config.templateContent, config.baseShape, config.baseLayerColor]); // Added baseLayerColor dependency to re-init if user changes base




  const currentFontPreset = fonts.find(f => f.url === config.fontUrl);
  const isCustomUpload = config.fontUrl.startsWith('blob:') && !currentFontPreset;

  // Determine the selected value for the dropdown
  let selectValue = '';
  if (currentFontPreset) {
    selectValue = currentFontPreset.url;
  } else if (isCustomUpload) {
    // If it's a blob URL, we can't directly match it to a cloud font filename.
    // For simplicity, if it's a blob and not a preset, we'll show "Custom Upload"
    // The user will re-select if they want a cloud font.
    selectValue = "custom";
  } else {
    // Fallback for initial load or if config.fontUrl is not a blob and not a preset (e.g., default)
    selectValue = config.fontUrl;
  }

  return (
    <div className={`
      relative h-full flex flex-col gap-4 p-4 overflow-y-auto custom-scrollbar 
      ${mode === 'ultra' ? 'bg-black/90' : 'bg-zinc-900/90'} 
      backdrop-blur-xl border-r border-white/5 transition-colors duration-500
    `}>
      {/* Header */}
      <div>
        <h2 className="text-2xl font-black text-lime-400 mb-1 tracking-tighter uppercase">KEYGEN 3D</h2>
        <p className="text-zinc-500 text-xs font-mono">DESIGN & PRINT SYSTEM v2.0</p>
      </div>

      {/* Mode Switcher */}
      <div className="flex bg-black p-1 rounded-xl border border-zinc-800 shadow-[inset_0_2px_4px_rgba(0,0,0,0.5)]">
        {(['standard', 'pro', 'ultra'] as const).map((m) => (
          <button
            key={m}
            onClick={() => {
              setMode(m);
              if (m === 'pro') {
                onChange({ ...config, baseShape: 'template' });
              }
            }}
            className={`flex-1 py-2 text-[10px] font-black uppercase tracking-[0.2em] rounded-lg transition-all duration-300 ${mode === m ? 'bg-lime-400 text-black shadow-[0_0_15px_rgba(163,230,53,0.6)]' : 'text-zinc-600 hover:text-lime-400/50'}`}
          >
            {m}
          </button>
        ))}
      </div>

      {/* 1. TEXT CONFIGURATION CARD */}
      <div className="bg-zinc-900/50 p-3 rounded-xl border border-zinc-800 space-y-4">
        <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block mb-2">Text Settings</span>

        {/* Text Input */}
        <div className="space-y-1">
          <label className="text-[10px] text-zinc-500 uppercase tracking-wide">Content</label>
          <div className="relative">
            <input
              type="text"
              maxLength={15}
              value={config.text}
              onChange={(e) => onChange({ ...config, text: e.target.value })}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-lime-500 outline-none font-mono text-sm"
              placeholder="MY NAME"
            />
            <span className="absolute right-2 top-2 text-[10px] text-zinc-600 font-mono">{config.text.length}/15</span>
          </div>
        </div>

        {/* Font Selection */}
        <div className="space-y-1">
          <label className="text-[10px] text-zinc-500 uppercase tracking-wide">Font Style</label>
          <div className="flex gap-2">
            <div className="relative group flex-grow">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                {isProcessingFont ? <Loader2 className="w-4 h-4 text-lime-400 animate-spin" /> : <Type className="w-4 h-4 text-zinc-400 group-hover:text-lime-400 transition-colors" />}
              </div>
              <select
                value={selectValue}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === 'custom') {
                    fileInputRef.current?.click();
                  } else if (val.startsWith('cloud:')) {
                    const filename = val.replace('cloud:', '');
                    loadCloudFont(filename);
                  } else {
                    onChange({ ...config, fontUrl: val });
                  }
                }}
                disabled={isProcessingFont}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-lime-500 outline-none font-mono text-xs appearance-none pl-9"
              >
                <optgroup label="Standard Fonts">
                  {fonts.map((font) => <option key={font.name} value={font.url}>{font.name}</option>)}
                </optgroup>

                {serverFonts.length > 0 && (
                  <optgroup label="Cloud Fonts">
                    {serverFonts.map(f => {
                      const displayName = f.replace('_hidden_', '').replace(/\.(ttf|otf)$/i, '').replace(/_/g, ' ');
                      return <option key={f} value={`cloud:${f}`}>{displayName}</option>;
                    })}
                  </optgroup>
                )}

                <option value="custom">Upload Custom (.ttf)...</option>
              </select>
            </div>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="bg-zinc-800 border border-zinc-700 hover:border-lime-500/50 rounded-lg px-2 text-lime-400 hover:bg-zinc-700 transition-colors"
              title="Upload Custom Font"
            >
              <Upload className="w-4 h-4" />
            </button>
            <input type="file" accept=".ttf,.otf,.zip" ref={fileInputRef} className="hidden" onChange={handleFileUpload} />
          </div>
        </div>

        {/* Font Dimensions (Size/Width/Spacing) */}
        <div className="grid grid-cols-1 gap-3 pt-2 border-t border-zinc-800/50">
          {/* Font Size */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Size</span><span>{config.fontSize}mm</span></div>
            <input type="range" min={4} max={30} step={0.5} value={config.fontSize} onChange={(e) => onChange({ ...config, fontSize: Number(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
          </div>

          {/* Font Width */}
          {(mode === 'standard' || mode === 'ultra') && (
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Width</span><span>{(config.fontScaleX * 100).toFixed(0)}%</span></div>
              <input type="range" min="0.5" max="2" step="0.05" value={config.fontScaleX} onChange={(e) => onChange({ ...config, fontScaleX: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
            </div>
          )}

          {/* Letter Spacing */}
          {(mode === 'standard' || mode === 'ultra') && (
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Spacing</span><span>{config.letterSpacing.toFixed(1)}mm</span></div>
              <input type="range" min="-2" max="10" step="0.1" value={config.letterSpacing} onChange={(e) => onChange({ ...config, letterSpacing: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
            </div>
          )}

          {/* Text Thickness (Depth) */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Thickness</span><span>{config.textDepth.toFixed(1)}mm</span></div>
            <input type="range" min="0.2" max="5" step="0.2" value={config.textDepth} onChange={(e) => onChange({ ...config, textDepth: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
          </div>
        </div>

        {/* Text Color Picker */}
        <div className="space-y-2 pt-2 border-t border-zinc-800/50">
          <label className="text-[10px] text-zinc-500 uppercase tracking-wide">Text Color</label>
          <div className="flex flex-wrap gap-2">
            {['#000000', '#ffffff', '#fbbf24', '#880000', '#a3e635'].map(c => (
              <button
                key={c}
                onClick={() => onChange({ ...config, textColor: c })}
                className={`w-5 h-5 rounded-full border-2 ${config.textColor === c ? 'border-lime-400 scale-110 shadow-[0_0_8px_rgba(163,230,53,0.8)]' : 'border-zinc-800 opacity-70 hover:opacity-100'} transition-all`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
        </div>


        {/* Outline Settings (Active for Template, Outline & Capsule Base) */}
        {(config.baseShape === 'outline' || config.baseShape === 'template' || config.baseShape === 'capsule') && (mode === 'ultra' || mode === 'standard' || mode === 'pro') && (
          <div className="pt-2 border-t border-zinc-800/50 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">Outline</span>
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-[10px] text-zinc-500 uppercase">{config.addSecondOutline ? 'ON' : 'OFF'}</span>
                <input type="checkbox" checked={config.addSecondOutline} onChange={(e) => onChange({ ...config, addSecondOutline: e.target.checked })} className="toggle-checkbox h-4 w-4 accent-lime-400 rounded bg-zinc-800 border-zinc-600" />
              </label>
            </div>

            {config.addSecondOutline && (
              <div className="space-y-3 animate-in fade-in slide-in-from-top-1">
                <div className="space-y-1">
                  <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Width</span><span>{config.secondOutlineSize.toFixed(2)}mm</span></div>
                  <input type="range" min="0.1" max={Math.max(0.1, config.outlineSize - 0.2)} step="0.05" value={config.secondOutlineSize} onChange={(e) => onChange({ ...config, secondOutlineSize: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Height</span><span>{config.secondOutlineDepth.toFixed(1)}mm</span></div>
                  <input type="range" min="0.4" max="1" step="0.1" value={config.secondOutlineDepth} onChange={(e) => onChange({ ...config, secondOutlineDepth: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Softness</span><span>{config.secondOutlineEdgeRoundness.toFixed(1)}mm</span></div>
                  <input type="range" min="0" max="3" step="0.1" value={config.secondOutlineEdgeRoundness} onChange={(e) => onChange({ ...config, secondOutlineEdgeRoundness: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 2. BASE SETTINGS CARD */}
      <div className="bg-zinc-900/50 p-3 rounded-xl border border-zinc-800 space-y-4">
        <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block mb-2">Base Settings</span>

        {/* Shape Selector (Standard/Ultra Only) */}
        {mode !== 'pro' && (
          <div className="space-y-1">
            <label className="text-[10px] text-zinc-500 uppercase tracking-wide">Shape Strategy</label>
            <div className="grid grid-cols-2 gap-2">
              {['outline', 'capsule'].map(shape => (
                <button
                  key={shape}
                  onClick={() => onChange({ ...config, baseShape: shape as any })}
                  className={`flex flex-col items-center justify-center p-2 rounded-lg border transition-all ${config.baseShape === shape ? 'bg-lime-400 border-lime-400 text-black' : 'bg-black border-zinc-800 text-zinc-500 hover:border-zinc-600'}`}
                >
                  <div className="flex items-center gap-2">
                    {shape === 'outline' ? <Hexagon size={14} /> : <RectangleHorizontal size={14} />}
                    <span className="text-[10px] font-bold uppercase">{shape}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Pro Mode: Forced Template Shape Display */}
        {mode === 'pro' && (
          <div className="space-y-1">
            <label className="text-[10px] text-zinc-500 uppercase tracking-wide">Shape Strategy</label>
            <div className="flex items-center gap-2 p-2 bg-zinc-900/80 border border-zinc-700 rounded-lg text-lime-400">
              <Layers size={14} />
              <span className="text-[10px] font-bold uppercase">Template Base</span>
            </div>
          </div>
        )}

        {/* Outline Specific: Size/Roundness */}
        {config.baseShape === 'outline' && (
          <div className="space-y-3 pt-2 border-t border-zinc-800/50">
            {/* Outline Size (XY) */}
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Contour Width</span><span>{config.outlineSize.toFixed(1)}mm</span></div>
              <input type="range" min="0.1" max="5" step="0.1" value={config.outlineSize} onChange={(e) => onChange({ ...config, outlineSize: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
            </div>

            {/* Z Smoothness (Base Roundness) */}
            {(mode === 'standard' || mode === 'ultra') && (
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Smoothness</span><span>{config.baseRoundness}</span></div>
                <input type="range" min="0" max="32" step="1" value={config.baseRoundness} onChange={(e) => onChange({ ...config, baseRoundness: parseInt(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
              </div>
            )}
          </div>
        )}

        {/* Capsule Specific: Border & Width */}
        {config.baseShape === 'capsule' && (
          <div className="space-y-2 mt-2">
            <div className="flex items-center justify-between p-2 bg-zinc-900 rounded border border-zinc-800">
              <span className="text-[10px] font-bold text-lime-400 uppercase">Add Border</span>
              <input type="checkbox" checked={config.addBorder} onChange={(e) => onChange({ ...config, addBorder: e.target.checked })} className="toggle-checkbox h-4 w-4 accent-lime-400 rounded bg-zinc-800 border-zinc-600" />
            </div>

            {/* Base Width (Capsule) */}
            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Base Width</span><span>{config.baseWidth.toFixed(0)}mm</span></div>
              <input type="range" min="30" max="150" step="1" value={config.baseWidth} onChange={(e) => onChange({ ...config, baseWidth: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
            </div>
          </div>
        )}

        {/* General: Thickness & Edge Roundness */}
        <div className="space-y-2 pt-2 border-t border-zinc-800/50">
          {/* Base Thickness */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Thickness</span><span>{config.thickness.toFixed(1)}mm</span></div>
            <input type="range" min="1" max={config.baseShape === 'template' ? "4" : "5"} step="0.2" value={config.thickness} onChange={(e) => onChange({ ...config, thickness: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
          </div>

          {/* Top Edge Radius */}
          {(mode === 'standard' || mode === 'ultra') && (
            <div className="space-y-1">
              <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Edge Radius (Bevel)</span><span>{config.edgeRoundness.toFixed(1)}mm</span></div>
              <input type="range" min="0" max="3" step="0.1" value={config.edgeRoundness} onChange={(e) => onChange({ ...config, edgeRoundness: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
            </div>
          )}
        </div>

        {/* Base Color Picker */}
        <div className="space-y-2 pt-2 border-t border-zinc-800/50">
          <label className="text-[10px] text-zinc-500 uppercase tracking-wide">Base Color</label>
          <div className="flex flex-wrap gap-2">
            {['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#a855f7', '#ec4899', '#ffffff', '#000000'].map(c => (
              <button
                key={c}
                onClick={() => onChange({ ...config, color: c })}
                className={`w-5 h-5 rounded-full border-2 ${config.color === c ? 'border-lime-400 scale-110 shadow-[0_0_8px_rgba(163,230,53,0.8)]' : 'border-zinc-800 opacity-70 hover:opacity-100'} transition-all`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* 3. TEMPLATE CONFIGURATION CARD */}
      {
        (mode === 'pro' || mode === 'ultra') && (
          <div className="bg-zinc-900/50 p-3 rounded-xl border border-zinc-800 space-y-4 animate-in fade-in">
            <label className="text-xs font-bold text-slate-300 uppercase tracking-wider block mb-2">Template Config</label>
            <div className="flex gap-2">
              <select
                className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-white focus:ring-2 focus:ring-lime-500 outline-none font-mono text-sm"
                value={config.templateName || ''}
                onChange={async (e) => {
                  const selectedName = e.target.value;
                  if (!selectedName) return;

                  // Check Local
                  const local = TEMPLATES.find(t => t.name === selectedName);
                  if (local) {
                    onChange({
                      ...config,
                      baseShape: 'template',
                      templateName: selectedName,
                      templateContent: local.svg,
                      svgMaxDimension: 50
                    });
                    return;
                  }

                  // Check Remote
                  if (serverTemplates.includes(selectedName)) {
                    try {
                      // Use PHP script to fetch to ensure CORS headers are present
                      // Add timestamp to bypass browser cache
                      const res = await fetch(`${API_BASE}/templates.php?action=get&filename=${selectedName}&t=${Date.now()}`);
                      if (!res.ok) throw new Error('Failed to load');
                      const text = await res.text();

                      // Basic validation check
                      if (!text.trim().startsWith('<svg') && !text.includes('<svg')) {
                        alert("Error: Loaded content is not a valid SVG.\nContent: " + text.substring(0, 100));
                        return;
                      }

                      console.log("Fetched SVG:", text.substring(0, 100)); // Debug log

                      onChange({
                        ...config,
                        baseShape: 'template',
                        templateName: selectedName,
                        templateContent: text,
                        svgMaxDimension: 50
                      });
                    } catch (err) {
                      console.error(err);
                      alert("Failed to load template");
                    }
                  }
                }}
              >
                <option value="">Select Template...</option>
                {TEMPLATES.length > 0 && (
                  <optgroup label="System">
                    {TEMPLATES.map(t => (
                      <option key={t.name} value={t.name}>{t.name}</option>
                    ))}
                  </optgroup>
                )}
                {serverTemplates.length > 0 && (
                  <optgroup label="Cloud">
                    {serverTemplates.map(t => (
                      <option key={t} value={t}>{t.replace('.svg', '').replace(/_/g, ' ')}</option>
                    ))}
                  </optgroup>
                )}
              </select>

              {/* Contextual Refresh for Cloud */}
              <button
                onClick={() => {
                  api.templates.list().then(res => {
                    if (res.success) setServerTemplates(res.templates);
                    alert("List updated!");
                  });
                }}
                className="bg-zinc-800 text-lime-400 p-2 rounded-lg"
                title="Refresh List"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
              {mode === 'ultra' && (
                <>
                  <button onClick={() => svgInputRef.current?.click()} className="p-2 rounded-lg border border-dashed border-zinc-600 hover:text-lime-400">
                    <Upload size={20} />
                  </button>
                  <input
                    type="file"
                    accept=".svg"
                    ref={svgInputRef}
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files?.[0]) {
                        const file = e.target.files[0];
                        const reader = new FileReader();
                        reader.onload = (ev) => {
                          const content = ev.target?.result as string;
                          onChange({
                            ...config,
                            baseShape: 'template',
                            templateName: 'custom',
                            templateContent: content,
                            svgMaxDimension: 50
                          });
                        };
                        reader.readAsText(file);
                      }
                    }}
                  />
                </>
              )}
            </div>

            {/* Base Layer Selector */}
            {config.baseShape === 'template' && detectedColors.length > 1 && (
              <div className="space-y-2 pt-2 border-t border-zinc-800">
                <label className="text-[10px] font-bold text-lime-400/80 uppercase">Base Layer</label>
                <div className="flex flex-wrap gap-2">
                  {detectedColors.map(c => (
                    <button
                      key={c}
                      onClick={() => onChange({ ...config, baseLayerColor: c })}
                      className={`w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all ${config.baseLayerColor === c ? 'border-lime-400 scale-110' : 'border-zinc-700'}`}
                      style={{ backgroundColor: c }}
                      title={c}
                    >
                      {config.baseLayerColor === c && <div className="w-2 h-2 rounded-full bg-white animate-pulse" />}
                    </button>
                  ))}
                </div>
                <p className="text-[10px] text-zinc-500">Selected color acts as base (-2mm), others sit on top (+2mm).</p>
              </div>
            )}

            {/* Detailed Layer Settings (ULTRA ONLY) */}
            {config.baseShape === 'template' && config.layerConfig && detectedColors.length > 0 && (mode === 'ultra' || mode === 'pro') && (
              <div className="space-y-2 pt-2 border-t border-zinc-800">
                <label className="text-[10px] font-bold text-lime-400/80 uppercase">Layer Settings</label>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-1 scrollbar-thin scrollbar-thumb-zinc-700">
                  {detectedColors.map(c => {
                    const conf = config.layerConfig?.[c] || { depth: config.thickness, offset: 0 };
                    return (
                      <div key={c} className="flex items-center gap-2 bg-zinc-900/50 p-1 rounded border border-zinc-800">
                        <div className="w-4 h-4 rounded-full border border-zinc-600 flex-shrink-0" style={{ backgroundColor: c }} title={c} />

                        <div className="flex-1">
                          <div className="space-y-1">
                            <div className="flex justify-between text-[10px] text-zinc-500 uppercase">
                              <span>Height</span>
                              <span>{conf.depth.toFixed(1)}mm</span>
                            </div>
                            <input
                              type="range"
                              min="0.5"
                              max="20"
                              step="0.5"
                              value={conf.depth}
                              onChange={(e) => {
                                const newVal = parseFloat(e.target.value);
                                // Auto-calc offset: If Base => -Height, Else 0
                                const isBase = c === config.baseLayerColor;
                                const newOffset = isBase ? -newVal : 0;

                                const newConf = { ...config.layerConfig, [c]: { depth: newVal, offset: newOffset } };
                                onChange({ ...config, layerConfig: newConf });
                              }}
                              className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-lime-400"
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}


            {/* SVG/Text Adjustments */}
            {config.baseShape === 'template' && (
              <div className="space-y-3 pt-2">
                {[
                  { l: 'Size', k: 'svgMaxDimension', min: 10, max: 200 },
                  { l: 'Offset X', k: 'textOffsetX', min: -50, max: 50 },
                  { l: 'Offset Y', k: 'textOffsetY', min: -50, max: 50 },
                  { l: 'Start Z (Text)', k: 'textOffsetZ', min: -10, max: 10 }
                ].map(opt => (
                  <div key={opt.k} className="space-y-1">
                    <div className="flex justify-between text-[10px] text-lime-400/70"><span>{opt.l}</span><span>{(config as any)[opt.k]}mm</span></div>
                    <input type="range" min={opt.min} max={opt.max} value={(config as any)[opt.k]} onChange={e => onChange({ ...config, [opt.k]: Number(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-lime-400" />
                  </div>
                ))}

              </div>
            )}
          </div>
        )
      }



      {/* 5. RING SETTINGS CARD */}
      {
        (mode === 'pro' || mode === 'ultra' || mode === 'standard') && (
          <div className="bg-zinc-900/50 p-3 rounded-xl border border-zinc-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Ring Settings</span>
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-[10px] text-zinc-500 uppercase">{config.showRing ? 'ON' : 'OFF'}</span>
                <input
                  type="checkbox"
                  checked={config.showRing !== false}
                  onChange={(e) => onChange({ ...config, showRing: e.target.checked })}
                  className="toggle-checkbox h-4 w-4 accent-lime-400 rounded bg-zinc-800 border-zinc-600"
                />
              </label>
            </div>

            {config.showRing !== false && (
              <div className="space-y-4 animate-in fade-in slide-in-from-top-1">
                <div className="space-y-1">
                  <div className="flex justify-between text-[10px] text-zinc-500 uppercase"><span>Overlap</span><span>{config.ringOverlap.toFixed(1)}mm</span></div>
                  <input type="range" min="-5" max="6" step="0.1" value={config.ringOverlap} onChange={(e) => onChange({ ...config, ringOverlap: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
                </div>

                <div className="space-y-1">
                  <div className="flex justify-between text-[10px] text-zinc-500 uppercase">
                    <span>{(config.baseShape === 'template' || config.baseShape === 'outline') ? "Position" : "Height"}</span>
                    <span>{(config.baseShape === 'template' || config.baseShape === 'outline') ? `${((config.ringPosition || 0) * 100).toFixed(0)}%` : `${config.ringOffsetY > 0 ? '+' : ''}${config.ringOffsetY.toFixed(1)} mm`}</span>
                  </div>
                  {(config.baseShape === 'template' || config.baseShape === 'outline') ? (
                    <input type="range" min="0" max="1" step="0.01" value={typeof config.ringPosition !== 'undefined' ? config.ringPosition : 0} onChange={(e) => onChange({ ...config, ringPosition: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
                  ) : (
                    <input type="range" min="-10" max="10" step="1" value={config.ringOffsetY} onChange={(e) => onChange({ ...config, ringOffsetY: parseFloat(e.target.value) })} className="w-full h-1 bg-zinc-800 rounded-lg accent-lime-400 appearance-none cursor-pointer" />
                  )}
                </div>
              </div>
            )}
          </div>
        )
      }

      {/* 6. EXPORT ACTIONS CARD */}
      <div className="bg-zinc-900/50 p-3 rounded-xl border border-zinc-800 space-y-3 mt-auto">
        <span className="text-xs font-bold text-slate-300 uppercase tracking-wider block mb-2">Export</span>
        <button
          onClick={() => {
            if (isDemo) {
              alert("Export is disabled in Demo Mode. Contact admin for full access.");
              return;
            }
            onExport('stl');
          }}
          className={`w-full flex items-center justify-center gap-2 font-black py-4 rounded-xl shadow-lg transition-all transform uppercase tracking-[0.2em] ${isDemo
            ? 'bg-zinc-800 text-zinc-600 cursor-not-allowed border border-zinc-700'
            : 'bg-lime-400 hover:bg-lime-300 text-black shadow-[0_0_20px_rgba(163,230,53,0.3)] active:scale-[0.98]'
            }`}
          title={isDemo ? "Disabled in Demo Mode" : "Export STL"}
        >
          <Download className="w-5 h-5" />
          Export STL
        </button>
        <p className="text-center text-[10px] text-zinc-500 font-mono uppercase tracking-widest">
          Ready for slicer (STL)
        </p>
      </div>
    </div >
  );
};