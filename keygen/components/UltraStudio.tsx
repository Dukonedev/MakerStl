import React, { useState, useRef } from 'react';
import { UltraScene } from './UltraScene';
import { UltraControls } from './UltraControls';
import { Loader2 } from 'lucide-react';
import * as THREE from 'three';

export interface ColorLayer {
    id: string;
    color: string;
    extrusionHeight: number;
    isVisible: boolean;
    isSolid: boolean; // Treats layer as base (no holes)
    paths: any[]; // SVG Paths
    groupId?: string;
    scale?: number;
    offset?: { x: number, y: number };
    zOffset?: number; // New: Vertical Shift
    locked?: boolean;
    processedShapes?: THREE.Shape[];
    originalColor?: string; // For Reset functionality
}

import { api } from '../src/api';

interface UltraStudioProps {
    user?: any;
    onUserUpdate?: (user: any) => void;
}

export const UltraStudio: React.FC<UltraStudioProps> = ({ user, onUserUpdate }) => {
    const [layers, setLayers] = useState<ColorLayer[]>([]);
    const [loading, setLoading] = useState(false);
    const [sceneCenter, setSceneCenter] = useState<{ x: number, y: number }>({ x: 0, y: 0 });
    const [sceneScale, setSceneScale] = useState(0.05);
    const [baseDimensions, setBaseDimensions] = useState<{ width: number, height: number }>({ width: 0, height: 0 });
    const [projectName, setProjectName] = useState("Project");

    // Scene Ref for Export
    const sceneRef = useRef<any>(null);

    const handleUpdateLayer = (id: string, updates: Partial<ColorLayer>) => {
        setLayers(prev => prev.map(l => l.id === id ? { ...l, ...updates } : l));
    };

    const handleExport = async (format: '3mf' | 'stl' | 'obj') => {
        if (sceneRef.current) {
            setLoading(true);
            try {
                const fileName = `KeyGen3D_${projectName}`;
                if (format === '3mf') {
                    await sceneRef.current.export3MF(fileName);
                } else if (format === 'obj') {
                    await sceneRef.current.exportOBJ(fileName);
                } else {
                    await sceneRef.current.exportSTL(fileName);
                }

                // Track download
                if (user && user.id) {
                    try {
                        const response = await api.stats.track(user.id);
                        if (response.success && onUserUpdate && response.download_count !== undefined) {
                            // Fix: stats.php returns 'download_count', not a full 'user' object.
                            // We must construct the updated user state manually to avoid passing undefined (which triggers logout).
                            onUserUpdate({ ...user, download_count: response.download_count });
                        }
                    } catch (err) {
                        console.error("Tracking Error:", err);
                    }
                }
            } catch (error) {
                console.error("Export Failed:", error);
                alert("Export Failed. Please check console for details.");
            } finally {
                setLoading(false);
            }
        }
    };


    const handleResetView = () => {
        if (sceneRef.current) {
            sceneRef.current.resetView();
        }
    };

    return (
        <div className="w-full max-w-7xl h-[90vh] grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Panel: 3D Scene */}
            <div className="lg:col-span-1 relative h-[40vh] lg:h-auto rounded-3xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)] border border-zinc-900 bg-black group">
                {/* Header / HUD */}
                <div className="absolute top-6 left-6 flex items-center gap-3 z-10">
                    <div className="bg-black/40 backdrop-blur-md border border-purple-500/20 px-3 py-1 rounded text-[10px] font-mono text-purple-400 uppercase tracking-widest flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></div>
                        ULTRA STUDIO
                    </div>
                </div>

                <UltraScene ref={sceneRef} layers={layers} center={sceneCenter} scale={sceneScale} />

                <div className="absolute bottom-4 left-4 right-4 z-10 flex flex-col gap-2">
                    <div className="bg-black/60 backdrop-blur-md border border-zinc-800 rounded-xl p-3 text-[10px] font-mono text-zinc-400">
                        <div className="uppercase tracking-widest text-zinc-500 mb-2 border-b border-zinc-700/50 pb-1">Extrusion Coordinates (Z-Axis)</div>
                        <div className="space-y-1">
                            {layers.map((layer, index) => {
                                const startZ = (layer.zOffset || 0);
                                const endZ = startZ + layer.extrusionHeight;
                                const isBase = layer.isSolid;
                                // Use a more distinct name logic
                                const name = isBase ? 'Template Base' : `Logo Layer ${index + 1}`;

                                return (
                                    <div key={layer.id} className="flex justify-between items-center text-[10px]">
                                        <div className="flex items-center gap-2">
                                            {/* Color Indicator */}
                                            <div className="w-2 h-2 rounded-full border border-white/20" style={{ backgroundColor: layer.color }}></div>
                                            <span className={`uppercase font-bold ${isBase ? 'text-zinc-300' : 'text-lime-400'}`}>
                                                {name}
                                            </span>
                                        </div>
                                        <span className="font-mono text-zinc-500">
                                            <span className="text-zinc-400">Z:</span> {startZ.toFixed(2)} <span className="text-zinc-600">to</span> {endZ.toFixed(2)}
                                        </span>
                                    </div>
                                );
                            })}
                            {layers.length === 0 && <span className="italic opacity-50">No layers loaded</span>}
                        </div>
                    </div>
                    <div className="text-zinc-600 text-[10px] font-mono uppercase tracking-[0.2em] select-none opacity-50 text-center">
                        Click & Drag to rotate • Scroll to zoom
                    </div>
                </div>
            </div>

            {/* Right Panel: Controls */}
            <div className="h-full flex flex-col gap-6 overflow-hidden">
                <div className="flex-grow overflow-y-auto pr-2 custom-scrollbar">
                    <UltraControls
                        layers={layers}
                        setLayers={setLayers}
                        onUpdateLayer={handleUpdateLayer}
                        loading={loading}
                        setLoading={setLoading}
                        onExport={handleExport}
                        onResetView={handleResetView}
                        sceneCenter={sceneCenter}
                        setSceneCenter={setSceneCenter}
                        sceneScale={sceneScale}
                        setSceneScale={setSceneScale}
                        baseDimensions={baseDimensions}
                        setBaseDimensions={setBaseDimensions}
                        setProjectName={setProjectName}
                    />
                </div>
            </div>
        </div>
    );
};
