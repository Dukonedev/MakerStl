
import React, { useRef, useEffect } from 'react';
import { Upload, Eye, EyeOff, Download, Layers, Ruler, Square, SquareDashed, Focus, Move, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, ChevronUp, ChevronDown, Minus, Plus, Trash2 } from 'lucide-react';
import { ColorLayer } from './UltraStudio';
import { SVGLoader } from 'three/addons/loaders/SVGLoader.js';
import * as THREE from 'three';
import { api, API_BASE } from '../src/api';
import { FileCode, Smartphone } from 'lucide-react';
import { GadgetSpec } from '../src/gadgets';


interface UltraControlsProps {
    layers: ColorLayer[];
    setLayers: React.Dispatch<React.SetStateAction<ColorLayer[]>>;
    onUpdateLayer: (id: string, updates: Partial<ColorLayer>) => void;
    loading: boolean;
    setLoading: (l: boolean) => void;
    onExport: (format: '3mf' | 'stl' | 'obj') => void;
    setSceneCenter: (center: { x: number, y: number }) => void;
    sceneScale: number;
    setSceneScale: (scale: number) => void;
    baseDimensions: { width: number, height: number };
    setBaseDimensions: (dim: { width: number, height: number }) => void;
    sceneCenter: { x: number, y: number };
    onResetView?: () => void;
    setProjectName: (name: string) => void;
}

export const UltraControls: React.FC<UltraControlsProps> = ({
    layers, setLayers, onUpdateLayer, loading, setLoading, onExport,
    setSceneCenter, sceneScale, setSceneScale, baseDimensions, setBaseDimensions,
    onResetView, setProjectName, sceneCenter
}) => {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [statusText, setStatusText] = React.useState("Processing...");
    const [currentBaseShape, setCurrentBaseShape] = React.useState<'none' | 'rect' | 'rounded' | 'circle'>('none');
    const [nudgeStep, setNudgeStep] = React.useState(1.0);

    const [selectedGadgetId, setSelectedGadgetId] = React.useState<string>("");
    const [gadgetsList, setGadgetsList] = React.useState<GadgetSpec[]>([]);

    React.useEffect(() => {
        api.gadgets.list().then(res => {
            if (res.success && Array.isArray(res.gadgets)) {
                setGadgetsList(res.gadgets.filter((g: any) => !g.hidden));
            }
        }).catch(err => console.error("Failed to fetch gadgets", err));
    }, []);

    const [engravingDepth, setEngravingDepth] = React.useState(0.4);
    const logoInputRef = useRef<HTMLInputElement>(null);

    React.useEffect(() => {
        api.settings.getAll().then(res => {
            if (res.success && res.settings && res.settings.engraving_depth_mm) {
                setEngravingDepth(parseFloat(res.settings.engraving_depth_mm));
            }
        });
    }, []);

    const loadGadget = async (gadgetId: string) => {
        const gadget = gadgetsList.find(g => g.id === gadgetId);
        if (!gadget) return;

        setSelectedGadgetId(gadgetId);
        setLoading(true);
        setStatusText("Loading Gadget...");

        try {
            // Construct absolute URL
            // API_BASE is .../php_server. Gadgets are in .../gadgets (sibling to php_server dir, usually parent of API_BASE if API_BASE is full url?)
            // If API_BASE = https://site.com/context/php_server
            // We want https://site.com/context/gadgets/file.svg
            // Or if svgUrl is relative 'gadgets/file.svg' and stored in root context?
            // Let's assume API_BASE relates to the server root.
            // URL construction for ../gadgets/ storage
            const baseUrl = API_BASE.replace('/php_server', '');
            const url = gadget.svgUrl.startsWith('http') ? gadget.svgUrl : `${baseUrl}/${gadget.svgUrl}`;

            const res = await fetch(url);
            if (!res.ok) throw new Error("Failed to fetch SVG");
            const svgText = await res.text();

            const loader = new SVGLoader();
            const svgData = loader.parse(svgText);

            // Calculate Dimensions from SVG
            const xml = svgData.xml as unknown as SVGSVGElement;
            let w = 0, h = 0, centerX = 0, centerY = 0;

            if (xml.viewBox && xml.viewBox.baseVal) {
                w = xml.viewBox.baseVal.width;
                h = xml.viewBox.baseVal.height;
                centerX = xml.viewBox.baseVal.x + w / 2;
                centerY = xml.viewBox.baseVal.y + h / 2;
            } else {
                w = parseFloat(xml.getAttribute('width') || '0');
                h = parseFloat(xml.getAttribute('height') || '0');
                centerX = w / 2; centerY = h / 2;
            }

            if (w === 0 || h === 0) throw new Error("Invalid SVG dimensions");

            // Calculate Scale to match Physical Dimensions (mm)
            // Gadgets define a target physical width (widthMm)
            // SceneScale maps SVG Units -> World Units (mm)
            const physicalScale = gadget.widthMm / w;

            setSceneCenter({ x: centerX, y: centerY });
            setSceneScale(physicalScale);
            setBaseDimensions({ width: w, height: h });
            setProjectName(gadget.name.replace(/\s+/g, '_'));

            // Generate Single Layer for Gadget Base
            // We use the SVG paths as the 'Base'

            // Collect all paths
            const gadgetPaths = svgData.paths.map(p => ({
                color: new THREE.Color(gadget.defaultColor), // Force default color
                toShapes: (isCCW: boolean) => p.toShapes(isCCW)
            }));

            const gadgetLayer: ColorLayer = {
                id: `gadget-${gadget.id}`,
                color: gadget.defaultColor,
                extrusionHeight: gadget.baseExtrusionMm,
                isVisible: true,
                isSolid: false, // Respect holes in SVG
                paths: svgData.paths,
                locked: true
            };

            setLayers([gadgetLayer]);

        } catch (e) {
            console.error("Failed to load gadget", e);
            setStatusText("Error loading gadget");
        } finally {
            setLoading(false);
            setStatusText("Processing...");
        }
    };

    const handleAddLogo = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setLoading(true);
        setStatusText("Adding Decoration...");

        try {
            const text = await file.text();
            const loader = new SVGLoader();
            const svgData = loader.parse(text);

            // Group by Unique Color (Merge same-color paths)
            const colorGroups: Record<string, THREE.Shape[]> = {};
            const uniqueColors: string[] = []; // Preserve order of first appearance

            svgData.paths.forEach((path) => {
                let color = '000000';
                if (path.color && path.color.getHexString) {
                    color = path.color.getHexString();
                }

                if (!colorGroups[color]) {
                    colorGroups[color] = [];
                    uniqueColors.push(color);
                }

                const shapes = path.toShapes(false); // CW -> CCW (Solid) after Y-flip
                shapes.forEach(s => colorGroups[color].push(s));
            });

            // 1. Calculate Bounding Box of Entire SVG (Paths)
            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
            let hasPoints = false;

            svgData.paths.forEach(p => {
                p.subPaths.forEach(sub => {
                    sub.getPoints().forEach(pt => {
                        if (pt.x < minX) minX = pt.x;
                        if (pt.x > maxX) maxX = pt.x;
                        if (pt.y < minY) minY = pt.y;
                        if (pt.y > maxY) maxY = pt.y;
                        hasPoints = true;
                    });
                });
            });

            const contentCenterX = hasPoints ? (minX + maxX) / 2 : 0;
            const contentCenterY = hasPoints ? (minY + maxY) / 2 : 0;

            console.log(`[UltraControls] Auto-Centering Logo. Bounds: [${minX.toFixed(2)}, ${maxX.toFixed(2)}] x [${minY.toFixed(2)}, ${maxY.toFixed(2)}]. Center: ${contentCenterX.toFixed(2)}, ${contentCenterY.toFixed(2)}`);

            // 2. Generate Shapes with Translation Applied
            // We iterate paths, convert to shapes, then rebuild shapes shifted by -Center

            Object.keys(colorGroups).forEach(color => {
                colorGroups[color] = []; // Clear initial un-shifted shapes
            });

            svgData.paths.forEach((path) => {
                let color = '000000';
                if (path.color && path.color.getHexString) {
                    color = path.color.getHexString();
                }

                const shapes = path.toShapes(false); // CW -> CCW (Solid) after Y-flip

                shapes.forEach(originalShape => {
                    // OPTIMIZE: Filter out tiny noise (dust) - Area check
                    // SVG units are usually large, so 0.1 is very small.
                    const area = THREE.ShapeUtils.area(originalShape.getPoints());
                    if (Math.abs(area) < 0.5) return; // Skip tiny specks

                    // Shift Main Shape Points
                    const newPoints = originalShape.getPoints().map(p => new THREE.Vector2(p.x - contentCenterX, p.y - contentCenterY));
                    const newShape = new THREE.Shape(newPoints);
                    // Ensure closed
                    if (newShape.curves.length > 0) newShape.autoClose = true;

                    // Shift Holes
                    if (originalShape.holes && originalShape.holes.length > 0) {
                        originalShape.holes.forEach(h => {
                            const holePoints = h.getPoints();
                            if (Math.abs(THREE.ShapeUtils.area(holePoints)) < 0.1) return; // Skip tiny holes

                            const newHolePoints = holePoints.map(p => new THREE.Vector2(p.x - contentCenterX, p.y - contentCenterY));
                            const newHolePath = new THREE.Path(newHolePoints);
                            newShape.holes.push(newHolePath);
                        });
                    }

                    if (colorGroups[color]) {
                        colorGroups[color].push(newShape);
                    }
                });
            });

            // Intarsia Logic Restored (Intra-Logo):
            // We assume the first color is the "Backplate" of the Logo, and subsequent colors are inlays.
            // This logic cuts the subsequent shapes out of the first shape.
            // Since all logo layers move together, this static boolean is valid and necessary for the inlay look.
            if (uniqueColors.length > 1) {
                const baseColor = uniqueColors[0];
                const baseShapes = colorGroups[baseColor];
                const newIslands: THREE.Shape[] = [];

                for (let i = 1; i < uniqueColors.length; i++) {
                    const decoColor = uniqueColors[i];
                    const decoShapes = colorGroups[decoColor];

                    decoShapes.forEach(ds => {
                        // 1. Convert Decoration to Hole in Base (Reverse Winding)
                        const holePath = new THREE.Path(ds.getPoints().reverse());

                        // Apply hole to ALL base shapes (simplification for logo matching)
                        baseShapes.forEach(bs => {
                            bs.holes.push(holePath);
                        });

                        // 2. Preserve Base "Islands" inside Decoration Holes
                        if (ds.holes && ds.holes.length > 0) {
                            ds.holes.forEach(dh => {
                                // dh is a hole in deco. To make it a solid base island, reverse it.
                                const islandShape = new THREE.Shape(dh.getPoints().reverse());
                                newIslands.push(islandShape);
                            });
                        }
                    });
                }
                // Add recovered islands to base
                newIslands.forEach(island => baseShapes.push(island));
            }

            // Calculate overriding depth

            // Calculate overriding depth
            let activeDepth = engravingDepth;
            if (selectedGadgetId) {
                const gadget = gadgetsList.find(g => g.id === selectedGadgetId);
                if (gadget && gadget.engravingDepthMm) {
                    activeDepth = gadget.engravingDepthMm;
                }
            }

            const newLayers: ColorLayer[] = uniqueColors.map((color, index) => {
                return {
                    id: `logo-${Date.now()}-${index}`,
                    color: `#${color}`,
                    originalColor: `#${color}`, // Store original for reset
                    // Strict Extrusion matching Template Incision Depth.
                    // Minimal epsilon added only to prevent Z-fighting artifacts in the 3D viewer.
                    extrusionHeight: activeDepth,
                    isVisible: true,
                    isSolid: false,
                    paths: [], // Legacy
                    processedShapes: colorGroups[color],
                    groupId: 'decoration',
                    scale: 1,
                    offset: { x: 0, y: 0 },
                    zOffset: layers[0]?.extrusionHeight || 2.0 // Default: Sit ON TOP of Base
                };
            });

            setLayers([...layers, ...newLayers]);

        } catch (err) {
            console.error(err);
            setStatusText("Error Adding Logo");
        } finally {
            setLoading(false);
            setStatusText("Processing...");
        }
    };



    const generateBaseLayer = (shapeType: 'none' | 'rect' | 'rounded' | 'circle') => {
        setCurrentBaseShape(shapeType);

        // Remove existing base layer if it exists
        const contentLayers = layers.filter(l => l.id !== 'generated-base');

        if (shapeType === 'none') {
            setLayers(contentLayers);
            return;
        }

        // Generate new base shape
        const padding = 5; // 5mm padding (in SVG units, usually mm if scaled 1:1, but here units are arbitrary before scale)
        // Actually, sceneScale scales usage. baseDimensions are in "svg units".
        // If we want 5mm padding *visually*, we should maybe check units?
        // Assuming SVG units ~= mm for now or proportional.

        const w = baseDimensions.width + (padding * 2);
        const h = baseDimensions.height + (padding * 2);
        const shape = new THREE.Shape();

        // We must generate the shape in the *original SVG coordinate space*
        // so that SVGLayerMesh's centering logic (which subtracts sceneCenter)
        // properly aligns it with the rest of the layers.

        // sceneCenter = vb.x + width/2
        const contentLeft = sceneCenter.x - (baseDimensions.width / 2);
        const contentTop = sceneCenter.y - (baseDimensions.height / 2);

        const x = contentLeft - padding;
        const y = contentTop - padding;

        switch (shapeType) {
            case 'rect':
                shape.moveTo(x, y);
                shape.lineTo(x + w, y);
                shape.lineTo(x + w, y + h);
                shape.lineTo(x, y + h);
                shape.lineTo(x, y);
                break;
            case 'rounded':
                const r = Math.min(w, h) * 0.1; // 10% radius
                shape.moveTo(x + r, y);
                shape.lineTo(x + w - r, y);
                shape.quadraticCurveTo(x + w, y, x + w, y + r);
                shape.lineTo(x + w, y + h - r);
                shape.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
                shape.lineTo(x + r, y + h);
                shape.quadraticCurveTo(x, y + h, x, y + h - r);
                shape.lineTo(x, y + r);
                shape.quadraticCurveTo(x, y, x + r, y);
                break;
            case 'circle':
                // Circle needs center and radius.
                // Center in SVG coords = sceneCenter.
                // Radius = max dimension / 2
                const radius = Math.max(w, h) / 2;
                shape.absarc(sceneCenter.x, sceneCenter.y, radius, 0, Math.PI * 2, false);
                break;
        }

        const baseLayer: ColorLayer = {
            id: 'generated-base',
            color: '#ffffff', // Default White Base
            extrusionHeight: 2.0, // Base default thick
            isVisible: true,
            isSolid: true,
            paths: [{
                toShapes: () => [shape],
                color: new THREE.Color('#ffffff')
            }]
        };

        // Ensure base is first
        setLayers([baseLayer, ...contentLayers]);
    };


    // Derived display values (in "mm")
    // If sceneScale = 1, then display = base.
    const displayWidth = baseDimensions.width * sceneScale;
    const displayHeight = baseDimensions.height * sceneScale;

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        // sanitize name: remove extension
        const rawName = file.name.replace(/\.[^/.]+$/, "");
        setProjectName(rawName);

        setLoading(true);
        // setStatusText("Optimizing Geometry...");

        // Standard Studio-like behavior: Local Parse
        // Server optimization seems to interfere with color grouping/attributes on some SVGs
        setStatusText("Parsing Structure...");

        try {
            const reader = new FileReader();
            reader.onload = (e) => {
                const content = e.target?.result as string;
                if (content) {
                    parseSVG(content);
                }
                setLoading(false);
                setStatusText("Processing...");
            };
            reader.readAsText(file);
        } catch (e) {
            console.error("File load error", e);
            setLoading(false);
        }

        /* 
        // Server Optimization (Disabled to match Studio behavior)
        try {
            console.log("[UltraControls] Optimizing SVG on server...");
            const optimizedContent = await api.svg.optimize(file);
            console.log("[UltraControls] Optimization success.");
            setStatusText("Parsing Structure...");
            parseSVG(optimizedContent);
        } catch (e) {
            console.error("[UltraControls] Optimization failed, falling back to local:", e);
            setStatusText("Falling back to Local Parser...");
            const reader = new FileReader();
            reader.onload = (e) => {
                const content = e.target?.result as string;
                if (content) {
                    parseSVG(content);
                }
            };
            reader.readAsText(file);
        } finally {
            setLoading(false);
            setStatusText("Processing...");
        }
        */
    };

    const parseSVG = (content: string) => {
        const loader = new SVGLoader();
        const svgData = loader.parse(content);

        // Calculate Center from ViewBox or Dimensions
        let centerX = 0;
        let centerY = 0;
        let scale = 0.05;
        let w = 0, h = 0;

        const xml = svgData.xml as unknown as SVGSVGElement; // Type assertion
        if (xml) {
            if (xml.viewBox && xml.viewBox.baseVal) {
                const vb = xml.viewBox.baseVal;
                w = vb.width;
                h = vb.height;
                centerX = vb.x + w / 2;
                centerY = vb.y + h / 2;
            } else {
                // Fallback to width/height attributes if available
                w = parseFloat(xml.getAttribute('width') || '0');
                h = parseFloat(xml.getAttribute('height') || '0');
                if (w && h) {
                    centerX = w / 2;
                    centerY = h / 2;
                }
            }

            // Auto-Scale to fit ~80 units
            if (w > 0 && h > 0) {
                const maxDim = Math.max(w, h);
                scale = 80 / maxDim;
            }
        }

        console.log(`[UltraControls] Center: ${centerX}, ${centerY} | Scale: ${scale} | Base: ${w}x${h} `);
        setSceneCenter({ x: centerX, y: centerY });
        setSceneScale(scale);
        setBaseDimensions({ width: w, height: h });

        // Group paths by color
        const colorGroups: Record<string, any[]> = {};

        // Helper to normalize color
        const isWhite = (c: string) => c.toLowerCase() === 'ffffff' || c.toLowerCase() === 'white' || c === 'rgb(255,255,255)';

        let hasWhite = false;

        let skippedPaths = 0;
        const MIN_PATH_SIZE = 0.01; // Effectively disable filtering to match Studio precision

        svgData.paths.forEach((path) => {
            // Optimization: Filter out tiny paths (noise/artifacts)
            // Three.js paths don't have a direct bounding box, but we can check subpaths
            let isTooSmall = true;

            // Check if any subpath is large enough
            for (const sub of path.subPaths) {
                const points = sub.getPoints();
                if (points.length < 2) continue;

                let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
                points.forEach(p => {
                    if (p.x < minX) minX = p.x;
                    if (p.x > maxX) maxX = p.x;
                    if (p.y < minY) minY = p.y;
                    if (p.y > maxY) maxY = p.y;
                });

                if ((maxX - minX) > MIN_PATH_SIZE || (maxY - minY) > MIN_PATH_SIZE) {
                    isTooSmall = false;
                    break;
                }
            }

            if (isTooSmall) {
                skippedPaths++;
                return;
            }

            let color = '000000'; // Default black if missing
            if (path.color && path.color.getHexString) {
                color = path.color.getHexString();
            }

            if (isWhite(color)) hasWhite = true;

            if (!colorGroups[color]) {
                colorGroups[color] = [];
            }
            colorGroups[color].push(path);
        });

        console.log(`[UltraControls] Optimizing SVG: Removed ${skippedPaths} tiny artifact paths.`);

        // Calculate Areas for Auto-Base Detection
        const colorAreas: Record<string, number> = {};

        Object.keys(colorGroups).forEach(color => {
            let totalArea = 0;
            colorGroups[color].forEach(path => {
                const shapes = path.toShapes(true);
                shapes.forEach((s: THREE.Shape) => {
                    totalArea += Math.abs(THREE.ShapeUtils.area(s.getPoints()));
                });
            });
            colorAreas[color] = totalArea;
        });

        // Find Base Color (Largest Area)
        let maxArea = 0;
        let baseColor = '';
        Object.keys(colorAreas).forEach(c => {
            if (colorAreas[c] > maxArea) {
                maxArea = colorAreas[c];
                baseColor = c;
            }
        });

        // Create Layers
        const newLayers: ColorLayer[] = Object.keys(colorGroups).map((color, index) => {
            const isBase = color === baseColor;
            return {
                id: `layer-${index}-${color}`,
                color: `#${color}`,
                extrusionHeight: 2.0, // Standard height for all
                isVisible: true,
                isSolid: isBase, // Auto-detect base
                paths: colorGroups[color],
                // Manual offset undefined -> relies on isSolid logic in UltraScene
            };
        });
        setLayers(newLayers);
    };

    const handleWidthChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newWidth = parseFloat(e.target.value);
        if (!newWidth || baseDimensions.width === 0) return;

        // Calculate new scale to match this width
        const newScale = newWidth / baseDimensions.width;
        setSceneScale(newScale);
    };

    const handleHeightChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newHeight = parseFloat(e.target.value);
        if (!newHeight || baseDimensions.height === 0) return;

        const newScale = newHeight / baseDimensions.height;
        setSceneScale(newScale);
    };

    const handleUpdateDecoration = (updates: Partial<ColorLayer>) => {
        const newLayers = layers.map(l => {
            if (l.groupId === 'decoration') {
                return { ...l, ...updates };
            }
            return l;
        });
        setLayers(newLayers);
    };

    const decorationLayer = layers.find(l => l.groupId === 'decoration');

    const handleMoveDecoration = (dx: number, dy: number) => {
        setLayers((prevLayers: ColorLayer[]) => prevLayers.map((l: ColorLayer) => {
            if (l.groupId === 'decoration') {
                const currentX = l.offset?.x || 0;
                const currentY = l.offset?.y || 0;
                return { ...l, offset: { x: currentX + dx, y: currentY + dy } };
            }
            return l;
        }));
    };

    const setDecorationX = (x: number) => {
        setLayers((prevLayers: ColorLayer[]) => prevLayers.map((l: ColorLayer) => {
            if (l.groupId === 'decoration') {
                const currentY = l.offset?.y || 0;
                return { ...l, offset: { x, y: currentY } };
            }
            return l;
        }));
    };

    const setDecorationY = (y: number) => {
        setLayers((prevLayers: ColorLayer[]) => prevLayers.map((l: ColorLayer) => {
            if (l.groupId === 'decoration') {
                const currentX = l.offset?.x || 0;
                return { ...l, offset: { x: currentX, y } };
            }
            return l;
        }));
    };

    // Calculate Dynamic Limits
    // Use baseDimensions (SVG Units) because 'offset' is applied in SVG space before scaling
    const limitX = baseDimensions.width > 0 ? (baseDimensions.width / 2) : 500;
    const limitY = baseDimensions.height > 0 ? (baseDimensions.height / 2) : 500;

    // Keyboard Support for Moving Decoration
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Only capture if decoration layer exists in current layers
            // We can check efficiently if we have a decoration layer, but logic is inside handleMove now.
            // But we should check if we SHOULDcapture. Only if gadget is selected (which implies decoration support).
            if (!decorationLayer) return;

            // Only capture if not typing in an input
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

            const step = e.shiftKey ? 2.5 : 0.5; // Shift for faster movement
            let handled = false;

            switch (e.key) {
                case 'ArrowUp':
                    handleMoveDecoration(0, step);
                    handled = true;
                    break;
                case 'ArrowDown':
                    handleMoveDecoration(0, -step);
                    handled = true;
                    break;
                case 'ArrowLeft':
                    handleMoveDecoration(-step, 0);
                    handled = true;
                    break;
                case 'ArrowRight':
                    handleMoveDecoration(step, 0);
                    handled = true;
                    break;
            }

            if (handled) {
                e.preventDefault();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [decorationLayer, layers]); // Re-bind when layers change (to check existence/freshness)







    return (
        <div className="space-y-6 p-1">

            {/* 0. GADGET SELECTOR (New Section) */}
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm relative mb-6">
                <h3 className="text-zinc-500 font-mono text-[10px] uppercase tracking-widest mb-4 flex items-center gap-2">
                    <Smartphone size={16} />
                    Gadget Templates
                </h3>

                <div className="relative">
                    <select
                        value={selectedGadgetId}
                        onChange={(e) => loadGadget(e.target.value)}
                        className="w-full bg-black border border-zinc-700 rounded-lg p-3 text-xs text-zinc-300 uppercase focus:border-purple-500 focus:outline-none appearance-none"
                    >
                        <option value="">Select a Gadget...</option>
                        {gadgetsList.map(g => (
                            <option key={g.id} value={g.id}>{g.name} ({g.widthMm}x{g.heightMm}mm)</option>
                        ))}
                    </select>
                </div>

                {selectedGadgetId && (() => {
                    const g = gadgetsList.find(x => x.id === selectedGadgetId);
                    return g ? (
                        <div className="mt-4 text-[10px] text-zinc-500 font-mono space-y-1 bg-black/40 p-3 rounded border border-zinc-800/50">
                            <div className="flex justify-between"><span>Specs:</span> <span className="text-zinc-300">{g.widthMm}mm x {g.heightMm}mm</span></div>
                            <div className="flex justify-between"><span>Base Extrusion:</span> <span className="text-zinc-300">{g.baseExtrusionMm}mm</span></div>
                            <div className="pt-2 italic border-t border-zinc-800/50 mt-2">{g.description}</div>
                        </div>
                    ) : null;
                })()}
            </div>

            {/* Add Logo Section (Only when Gadget Selected) */}
            {selectedGadgetId && (
                <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm relative mb-6">
                    <h3 className="text-zinc-500 font-mono text-[10px] uppercase tracking-widest mb-4 flex items-center gap-2">
                        <FileCode size={16} />
                        Add Decoration / Logo
                    </h3>
                    <button
                        onClick={() => logoInputRef.current?.click()}
                        disabled={loading}
                        className="w-full border border-dashed border-zinc-700 hover:border-lime-500/50 hover:bg-lime-500/10 rounded-xl p-4 flex items-center justify-center gap-2 text-zinc-500 hover:text-lime-400 transition-all text-xs font-mono uppercase tracking-widest"
                    >
                        <Upload size={14} />
                        Upload SVG Logo
                    </button>
                    <input
                        type="file"
                        accept=".svg"
                        ref={logoInputRef}
                        className="hidden"
                        onChange={handleAddLogo}
                    />
                    <div className="mt-2 text-[9px] text-zinc-600 font-mono flex justify-between">
                        <span>Extrusion (Incisione): {engravingDepth}mm</span>
                        <span>(Configured in Admin)</span>
                    </div>
                </div>
            )}



            {/* Upload Section - Hidden if Gadget Selected ("Empty Template" Mode) */}
            {!selectedGadgetId && (
                <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm relative overflow-hidden">
                    <h3 className="text-zinc-500 font-mono text-[10px] uppercase tracking-widest mb-4 flex items-center gap-2">
                        <FileCode size={16} />
                        Custom Project (Empty Template)
                    </h3>

                    <button
                        onClick={() => fileInputRef.current?.click()}
                        className="w-full border border-dashed border-zinc-700 hover:border-purple-500/50 hover:bg-purple-500/10 rounded-xl p-8 flex flex-col items-center justify-center gap-3 text-zinc-500 hover:text-purple-400 transition-all group"
                    >
                        <div className="w-12 h-12 rounded-full bg-black border border-zinc-800 group-hover:border-purple-500/50 flex items-center justify-center transition-colors">
                            <Upload size={20} />
                        </div>
                        <span className="text-xs font-mono uppercase tracking-widest">Upload Custom Template (SVG)</span>
                        <span className="text-[9px] text-zinc-600">Start from scratch with your own design</span>
                    </button>

                    <input
                        type="file"
                        accept=".svg"
                        ref={fileInputRef}
                        className="hidden"
                        onChange={handleFileUpload}
                    />

                    {loading && (
                        <div className="absolute inset-0 bg-black/80 backdrop-blur-sm z-20 flex flex-col items-center justify-center text-center p-4">
                            <div className="w-8 h-8 rounded-full border-2 border-purple-500 border-t-transparent animate-spin mb-3"></div>
                            <p className="text-purple-400 font-mono text-xs uppercase tracking-widest animate-pulse">{statusText}</p>
                        </div>
                    )}
                </div>
            )}



            {/* Base Shape Selection - Hidden if Gadget Selected */}
            {layers.length > 0 && !selectedGadgetId && (
                <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm">
                    <h3 className="text-zinc-500 font-mono text-[10px] uppercase tracking-widest mb-4 flex items-center gap-2">
                        <Square className="w-4 h-4" />
                        Base Shape
                    </h3>
                    <div className="grid grid-cols-4 gap-2">
                        {(['none', 'rect', 'rounded', 'circle'] as const).map((shape) => (
                            <button
                                key={shape}
                                onClick={() => generateBaseLayer(shape)}
                                className={`flex flex-col items-center justify-center p-2 rounded-lg border transition-all ${currentBaseShape === shape
                                    ? 'bg-purple-500 border-purple-500 text-white shadow-[0_0_10px_rgba(168,85,247,0.3)]'
                                    : 'bg-black border-zinc-800 text-zinc-500 hover:border-purple-500/50 hover:text-purple-400'
                                    }`}
                            >
                                <span className="text-[10px] font-bold uppercase">{shape}</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Decoration Controls (Unified) */}
            {decorationLayer && (
                <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm">
                    <h3 className="text-zinc-500 font-mono text-[10px] uppercase tracking-widest mb-4 flex items-center gap-2">
                        <Move className="w-4 h-4" />
                        Logo / Decoration Controls
                    </h3>

                    <div className="space-y-4">
                        {/* Scale */}
                        <div className="space-y-1">
                            <div className="flex justify-between text-[10px] text-zinc-500 uppercase tracking-wider">
                                <span>Scale</span>
                                <span>{(decorationLayer.scale || 1).toFixed(2)}x</span>
                            </div>
                            <input
                                type="range"
                                min="-200.0"
                                max="200.0"
                                step="0.1"
                                value={decorationLayer.scale || 1}
                                onChange={(e) => handleUpdateDecoration({ scale: parseFloat(e.target.value) })}
                                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-lime-400"
                            />
                        </div>

                    </div>

                    {/* Position Sliders (X/Y) */}
                    <div className="space-y-4 pt-2 border-t border-white/5 mt-2">
                        {/* Position X */}
                        <div className="space-y-1">
                            <div className="flex justify-between text-[10px] text-zinc-500 uppercase tracking-wider">
                                <span>Position X (mm)</span>
                                <span>{(decorationLayer.offset?.x || 0).toFixed(1)}</span>
                            </div>
                            <input
                                type="range"
                                min={-limitX}
                                max={limitX}
                                step="0.5"
                                value={decorationLayer.offset?.x || 0}
                                onChange={(e) => setDecorationX(parseFloat(e.target.value))}
                                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-lime-400"
                            />
                        </div>

                        {/* Position Y */}
                        <div className="space-y-1">
                            <div className="flex justify-between text-[10px] text-zinc-500 uppercase tracking-wider">
                                <span>Position Y (mm)</span>
                                <span>{(decorationLayer.offset?.y || 0).toFixed(1)}</span>
                            </div>
                            <input
                                type="range"
                                min={-limitY}
                                max={limitY}
                                step="0.5"
                                value={decorationLayer.offset?.y || 0}
                                onChange={(e) => setDecorationY(parseFloat(e.target.value))}
                                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-lime-400"
                            />
                        </div>
                    </div>

                    <div className="pt-2 border-t border-zinc-800/50">
                        <button
                            onClick={() => {
                                // Remove all decoration layers
                                setLayers(layers.filter(l => l.groupId !== 'decoration'));
                            }}
                            className="w-full text-[10px] text-red-400 hover:text-red-300 uppercase tracking-widest py-2 hover:bg-red-500/10 rounded transition-colors"
                        >
                            Remove Decoration
                        </button>
                    </div>
                </div>
            )}

            {/* Dimensions Control - Hidden if Gadget Selected */}
            {layers.length > 0 && !selectedGadgetId && (
                <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm">
                    <h3 className="text-zinc-500 font-mono text-[10px] uppercase tracking-widest mb-4 flex items-center gap-2">
                        <Ruler className="w-4 h-4" />
                        Dimensions (mm)
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Width</label>
                            <input
                                type="number"
                                value={displayWidth.toFixed(2)}
                                onChange={handleWidthChange}
                                className="w-full bg-black/40 border border-zinc-800 rounded-lg p-2 text-sm text-zinc-300 focus:outline-none focus:border-purple-500"
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-[10px] text-zinc-500 uppercase tracking-wider">Height</label>
                            <input
                                type="number"
                                value={displayHeight.toFixed(2)}
                                onChange={handleHeightChange}
                                className="w-full bg-black/40 border border-zinc-800 rounded-lg p-2 text-sm text-zinc-300 focus:outline-none focus:border-purple-500"
                            />
                        </div>
                    </div>
                </div>
            )
            }

            {/* Layers List */}
            {
                layers.length > 0 && (
                    <div className="bg-zinc-900/40 border border-zinc-800 rounded-2xl p-6 backdrop-blur-sm">
                        <h3 className="text-zinc-500 font-mono text-[10px] uppercase tracking-widest mb-4 flex items-center gap-2">
                            <Layers className="w-4 h-4" />
                            Detected Colors ({layers.length})
                        </h3>

                        <div className="space-y-3">
                            {layers.map((layer) => (
                                <div key={layer.id} className="bg-black/40 border border-zinc-800 rounded-xl p-3 flex flex-col gap-3">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                            <div className="relative group/color">
                                                <div
                                                    className="w-6 h-6 rounded-full border border-white/10 shadow-sm cursor-pointer hover:scale-110 transition-transform"
                                                    style={{ backgroundColor: layer.color }}
                                                />
                                                <input
                                                    type="color"
                                                    value={layer.color}
                                                    onChange={(e) => onUpdateLayer(layer.id, { color: e.target.value })}
                                                    className="absolute inset-0 opacity-0 cursor-pointer"
                                                />
                                            </div>
                                            <div className="flex flex-col">
                                                <span className="font-mono text-xs text-zinc-400 uppercase">{layer.color}</span>
                                                {layer.originalColor && layer.color !== layer.originalColor && (
                                                    <button
                                                        onClick={() => onUpdateLayer(layer.id, { color: layer.originalColor })}
                                                        className="text-[9px] text-red-400 hover:text-red-300 underline uppercase"
                                                    >
                                                        Reset
                                                    </button>
                                                )}
                                            </div>
                                            {layer.groupId === 'decoration' && <span className="text-[9px] bg-lime-500/20 text-lime-400 px-1.5 rounded uppercase">Logo</span>}
                                        </div>
                                        <div className="flex items-center gap-1">
                                            {!layer.locked && (
                                                <button
                                                    onClick={() => onUpdateLayer(layer.id, { isSolid: !layer.isSolid })}
                                                    className={`p-1.5 rounded-lg transition-colors ${layer.isSolid ? 'text-purple-400 bg-purple-500/10 hover:text-purple-300' : 'text-zinc-700 hover:text-zinc-500'}`}
                                                    title={layer.isSolid ? "Solid Base (No Holes)" : "Standard (With Holes)"}
                                                >
                                                    {layer.isSolid ? <Square className="w-4 h-4 fill-current" /> : <SquareDashed className="w-4 h-4" />}
                                                </button>
                                            )}
                                            <button
                                                onClick={() => onUpdateLayer(layer.id, { isVisible: !layer.isVisible })}
                                                className={`p-1.5 rounded-lg transition-colors ${layer.isVisible ? 'text-zinc-400 hover:text-white' : 'text-zinc-700 hover:text-zinc-500'}`}
                                            >
                                                {layer.isVisible ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                                            </button>
                                            <button
                                                onClick={() => setLayers(prev => prev.filter(l => l.id !== layer.id))}
                                                className="p-1.5 rounded-lg text-zinc-700 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                                                title="Delete Layer"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>

                                    </div>

                                    {/* Feature: Embed / Incide Button */}
                                    {layer.groupId === 'decoration' && !layer.locked && (
                                        <div className="mt-2 pt-2 border-t border-zinc-800/50">
                                            <button
                                                onClick={() => {
                                                    // Logic: Embed Flush
                                                    // User Request: "Layer 2 starts from Base Extrusion to - Incision"
                                                    // Implementation: Position the Logo so its top is at Base Height, and it extends down by Incision Depth.

                                                    // Find Base Height (First Solid Base Layer or Default)
                                                    const baseLayer = layers.find(l => l.isSolid) || layers[0];
                                                    const baseHeight = baseLayer?.extrusionHeight || 2.0;
                                                    const embedOffset = baseHeight - engravingDepth;

                                                    console.log(`[UltraControls] Immersing Layer ${layer.id}. Base: ${baseHeight}mm, Incision: ${engravingDepth}mm. New Z: ${embedOffset}mm`);

                                                    onUpdateLayer(layer.id, {
                                                        zOffset: embedOffset,
                                                        extrusionHeight: engravingDepth // Ensure height matches incision setting
                                                    });
                                                }}
                                                className="w-full bg-zinc-800 hover:bg-zinc-700 text-zinc-400 py-1.5 rounded-lg flex items-center justify-center gap-2 active:scale-[0.98] transition-all text-[10px] uppercase font-bold tracking-wider hover:text-white"
                                                title={`Embed Flush into Template (Top aligned to Base)`}
                                            >
                                                <Layers className="w-3 h-3 text-lime-400" />
                                                Immerse / Embed (Incision)
                                            </button>
                                        </div>
                                    )}

                                    {/* Height Controls */}
                                    {layer.isVisible && !layer.groupId && !layer.locked && (
                                        <div className="space-y-1 mt-3">
                                            <div className="flex justify-between text-[10px] text-zinc-500 uppercase tracking-wider">
                                                <span>Height</span>
                                                <span>{layer.extrusionHeight.toFixed(1)}mm</span>
                                            </div>
                                            <input
                                                type="range"
                                                min="0.2"
                                                max="20"
                                                step="0.2"
                                                value={layer.extrusionHeight}
                                                onChange={(e) => onUpdateLayer(layer.id, { extrusionHeight: parseFloat(e.target.value) })}
                                                className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
                                            />
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}

            {/* Export Button & View Controls */}
            {layers.length > 0 && (
                <div className="flex flex-col gap-3">
                    <button
                        type="button"
                        onClick={onResetView}
                        className="w-full flex items-center justify-center gap-2 font-bold py-3 rounded-xl border border-zinc-700 bg-zinc-800/50 hover:bg-zinc-800 text-zinc-300 transition-all uppercase tracking-[0.15em] text-xs hover:text-white"
                    >
                        <Focus className="w-4 h-4" />
                        Center View
                    </button>
                    <div className="grid grid-cols-3 gap-3">
                        <button
                            type="button"
                            onClick={() => onExport('stl')}
                            className="flex items-center justify-center gap-2 font-bold py-4 rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-all uppercase tracking-[0.1em] text-[10px] hover:text-white"
                        >
                            <Download className="w-4 h-4" />
                            STL
                        </button>
                        <button
                            type="button"
                            onClick={() => onExport('obj')}
                            className="flex items-center justify-center gap-2 font-bold py-4 rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-all uppercase tracking-[0.1em] text-[10px] hover:text-white"
                        >
                            <Download className="w-4 h-4" />
                            OBJ
                        </button>
                        <button
                            type="button"
                            onClick={() => onExport('3mf')}
                            className="flex items-center justify-center gap-2 font-black py-4 rounded-xl shadow-lg transition-all transform uppercase tracking-[0.1em] bg-purple-500 hover:bg-purple-400 text-white shadow-[0_0_20px_rgba(168,85,247,0.3)] active:scale-[0.98] text-[10px]"
                        >
                            <Download className="w-4 h-4" />
                            3MF (Color)
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};
