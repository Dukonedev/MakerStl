import React, { useMemo } from 'react';
import * as THREE from 'three';
import { Center } from '@react-three/drei';
import * as BufferGeometryUtils from 'three/addons/utils/BufferGeometryUtils.js';

interface SVGLayerMeshProps {
    paths: any[]; // SVGResultPaths
    color: string;
    extrusion: number;
    center?: { x: number, y: number };
    isSolid?: boolean;
    scale?: number;
    name?: string;
    zOffset?: number;
    shapes?: THREE.Shape[];
    clipTarget?: THREE.Mesh | null; // <--- CSG Target
    carveTargets?: THREE.Mesh[]; // <--- CSG Subtractors (Decoration Meshes)
    offsetKey?: string; // <--- Trigger for CSG Re-calc
}

import { CSGHelper } from './CSGHelper';

export const SVGLayerMesh = React.forwardRef<THREE.Mesh, SVGLayerMeshProps>(({
    paths, color, extrusion, center, isSolid, scale = 1, name, zOffset = 0, shapes, clipTarget, carveTargets, offsetKey
}, ref) => {
    const internalRef = React.useRef<THREE.Mesh>(null);
    React.useImperativeHandle(ref, () => internalRef.current!);

    const geometry = useMemo(() => {
        // 0. Use pre-processed shapes if available (Smart Hole Integration)
        if (shapes && shapes.length > 0) {
            const shapeGeometry = new THREE.ExtrudeGeometry(shapes, {
                depth: extrusion / scale, // Scale normalization
                bevelEnabled: false,
                steps: 1
            });
            // Center geometry? No, pre-processed shapes should already be centered/transformed in UltraControls logic.
            // But wait, ExtrudeGeometry builds around the shape coordinates.
            // If the Smart Hole logic in UltraControls performs centering, we are good.
            // If it keeps original SVG coordinates, we might need centering here.

            // Let's assume for now the Smart Hole logic will output shapes in the same coordinate space 
            // as the paths would have generated, so we might need to apply the centering offset IF 
            // the shapes are raw SVG coords.
            // However, typical SVGLayerMesh logic applies centering via Group or Mesh position, 
            // OR transforms shapes?

            // Re-reading lines 34-37 of original file:
            // It transforms shapes by subtracting center.
            // So if we pass raw SVG shapes, we need to transform them here OR ensure they are pre-transformed.
            // Let's stick to the current pattern: SVGLayerMesh expects to handle the transform.
            // BUT, modifying 'shapes' props is risky inside render.
            // Better strategy: The new 'processSVGShapeHoles' in UltraControls will likely return shapes in SVG Frame.
            // So we should run them through the same transform loop (lines 36-55) effectively?

            // Actually, if we pass 'shapes', we are bypassing the nesting/hole detection logic of SVGLayerMesh logic (lines 57+).
            // So we should just use them.
            // WE MUST ENSURE 'shapes' passed are already correct (holes applied).

            // What about centering?
            // If we use `shapes` directly, we skip the transform loop in Lines 36-55.
            // So we need to apply the translation.

            // Let's modify the Smart Hole logic in UltraControls to return shapes relative to (0,0)? 
            // No, UltraControls doesn't know the scene center easily without recalc.

            // Let's just adjust the passed shapes here.
            // Fix: Do NOT subtract center again if shapes are pre-processed (already centered to 0,0 locally)
            // But wait, the Base is at (0,0) because it IS subtracted by center.
            // If the Logo is at (0,0) locally, and we render it, it appears at (0,0).
            // So we just need to preserve the shape coordinates as-is.

            const centeredShapes = shapes.map(s => {
                // Do not apply 'center' offset here. Use raw shape coords.
                // Flip Y is required because ExtrudeGeometry expects Y+ Up, but SVG is Y+ Down?
                // Actually SVGLoader y-flip is handled.
                // But in the 'paths' logic below (Line 95), there is a negate Y: `-(p.y - centerY)`.
                // The pre-processed shapes came from `UltraControls`, where `toShapes` was called.
                // `path.toShapes` usually returns standard Y-up (Three.js standard) or Y-down?
                // SVGLoader.toShapes usually respects the path logic.

                // Let's assume the shapes passed in are in the correct orientation but just need to NOT be shifted.
                // BUT, we might still need to Flip Y if they are "SVG Coords" (Y Down).
                // `UltraControls` uses `path.toShapes(false)`.

                // Let's check `UltraControls` logic:
                // `const shapes = path.toShapes(false);`
                // And then `p.y - contentCenterY`.
                // If the original SVG path was Y-down (0 at top), `p.y` is positive down.
                // If we subtract center, we get local coords.
                // If we display this in Three.js (Y-up), 0,0 is center. positive Y is up.
                // The points `(x, y)` from SVGLoader are Y-down relative to canvas.
                // To display correctly in 3D, we usually flip Y.

                // In the "Normal" path below (Line 95), we do `-(p.y - centerY)`.
                // So we SHOULD flip Y here too.

                // Wait, if I don't flip Y, it might be upside down?
                // Let's trust that `UltraControls` shapes are just raw 2D.
                // If they are rendered upside down, I will fix Y.
                // Actually, let's look at how vectors are constructed.
                // Below: `new THREE.Vector2(p.x - centerX, -(p.y - centerY))`
                // This implies: Shift then Flip-around-0.

                // Fix: Apply Y-Flip (Upright) but DO NOT Flip X (Un-mirror)
                // User reports "Specchiato" (Mirrored).
                // Removing -x should fix it.

                const points = s.getPoints().map(p => new THREE.Vector2(p.x, -p.y));
                const newShape = new THREE.Shape(points);

                // IMPORTANT: Restore holes!
                if (s.holes && s.holes.length > 0) {
                    s.holes.forEach(h => {
                        const hPoints = h.getPoints().map(p => new THREE.Vector2(p.x, -p.y));
                        newShape.holes.push(new THREE.Path(hPoints));
                    });
                }
                return newShape;
            });

            return new THREE.ExtrudeGeometry(centeredShapes, {
                depth: extrusion / scale,
                bevelEnabled: false,
                steps: 1
            });
        }

        if (!paths || paths.length === 0) return null;

        // 1. Gather all initial shapes from SVGLoader (which might have imperfect hole detection)
        const initialShapes: THREE.Shape[] = [];
        paths.forEach(p => {
            const s = p.toShapes(true);
            initialShapes.push(...s);
        });

        if (initialShapes.length === 0) return null;

        const centerX = center?.x || 0;
        const centerY = center?.y || 0;

        // 2. Transform all shapes to the target coordinate system immediately
        // This makes nesting calculations simpler as they happen in final 2D space
        const transformedShapes = initialShapes.map(s => {
            let points = s.getPoints().map(p => new THREE.Vector2(p.x - centerX, -(p.y - centerY)));

            // Ensure CCW winding for main shapes initially (standardize)
            if (THREE.ShapeUtils.area(points) < 0) {
                points = points.reverse(); // Standard THREE shape usually expects CCW for exterior
            }

            const newS = new THREE.Shape(points);

            // Transform existing holes too if any
            if (s.holes) {
                s.holes.forEach(h => {
                    const holePoints = h.getPoints().map(p => new THREE.Vector2(p.x - centerX, -(p.y - centerY)));
                    newS.holes.push(new THREE.Path(holePoints));
                });
            }
            return newS;
        });

        // 3. Flatten into Contours for Robust Nesting Logic
        // We ignore whatever hierarchy SVGLoader assumed and rebuild it.
        const allContours: THREE.Shape[] = [];
        transformedShapes.forEach(s => {
            allContours.push(new THREE.Shape(s.getPoints())); // Main hull
            if (s.holes) {
                s.holes.forEach(h => allContours.push(new THREE.Shape(h.getPoints()))); // Holes as candidates
            }
        });

        // Helper: Point in Polygon
        const isPointInside = (pt: THREE.Vector2, polygon: THREE.Vector2[]) => {
            let inside = false;
            for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
                const xi = polygon[i].x, yi = polygon[i].y;
                const xj = polygon[j].x, yj = polygon[j].y;
                const intersect = ((yi > pt.y) !== (yj > pt.y))
                    && (pt.x < (xj - xi) * (pt.y - yi) / (yj - yi) + xi);
                if (intersect) inside = !inside;
            }
            return inside;
        };

        // 4. Calculate Nesting Depth
        const shapesWithDepth = allContours.map((shape, index) => {
            const points = shape.getPoints();
            if (points.length === 0) return { shape, depth: 0, parentIndex: -1, index };

            const pt = points[0];
            let depth = 0;
            let parentIndex = -1;
            let smallestParentArea = Infinity;

            for (let j = 0; j < allContours.length; j++) {
                if (index === j) continue;
                const other = allContours[j];
                const otherPoints = other.getPoints();

                if (otherPoints.length > 0 && isPointInside(pt, otherPoints)) {
                    depth++;
                    const area = Math.abs(THREE.ShapeUtils.area(otherPoints));
                    if (area < smallestParentArea) {
                        smallestParentArea = area;
                        parentIndex = j;
                    }
                }
            }
            return { shape, depth, parentIndex, index };
        }).filter(s => s.shape.getPoints().length > 0);

        // 5. Separate Solids (Even) and Holes (Odd)
        const shapesFlipped: THREE.Shape[] = [];
        const solidsByIndex = new Map<number, THREE.Shape>();

        // Process Solids (Depth 0, 2...)
        shapesWithDepth.filter(item => item.depth % 2 === 0).forEach(item => {
            let points = item.shape.getPoints();
            // Ensure Solid is CCW (Area > 0)
            if (THREE.ShapeUtils.area(points) < 0) {
                points = points.reverse();
            }
            const newShape = new THREE.Shape(points);
            solidsByIndex.set(item.index, newShape);
            shapesFlipped.push(newShape);
        });

        // Process Holes (Depth 1, 3...)
        if (!isSolid) { // Only add holes if we are not forcing solid
            shapesWithDepth.filter(item => item.depth % 2 === 1).forEach(item => {
                const parentItem = shapesWithDepth.find(p => p.index === item.parentIndex);
                if (parentItem) {
                    const parentShape = solidsByIndex.get(parentItem.index);
                    if (parentShape) {
                        let points = item.shape.getPoints();
                        // Ensure Hole is CW (Area < 0)
                        if (THREE.ShapeUtils.area(points) > 0) {
                            points = points.reverse();
                        }
                        parentShape.holes.push(new THREE.Path(points));
                    }
                }
            });
        }

        // Compensate for parent scaling
        const s = scale || 1;
        const extrudeSettings = {
            depth: extrusion / s,
            bevelEnabled: false,
            bevelThickness: 0.1 / s,
            bevelSize: 0.1 / s,
            bevelSegments: 2,
            curveSegments: 64 // High Quality (balanced for stability)
        };

        let geo: THREE.BufferGeometry = new THREE.ExtrudeGeometry(shapesFlipped, extrudeSettings);

        // Optimize: Merge vertices to close micro-holes and cracks
        geo = BufferGeometryUtils.mergeVertices(geo, 0.001);
        geo.computeVertexNormals();

        return geo;

    }, [paths, extrusion, center, isSolid, scale]);

    if (!paths || !geometry) return null;

    // Use explicit zOffset (adjusted for scale)
    // zOffset passed in is in "World mm". We need to divide by scale to get "Local units".
    const s = scale || 1;
    const finalZ = zOffset / s;

    // CSG Clipping & Carving Logic
    React.useLayoutEffect(() => {
        const mesh = internalRef.current;
        if (!mesh || !geometry) return;

        // 1. Reset to Original Geometry (Pristine)
        mesh.geometry = geometry;
        mesh.userData.originalGeometry = geometry; // Save for Clipping usage by others
        mesh.updateMatrixWorld();

        // Track disposable geometries created in this effect
        const disposables: THREE.BufferGeometry[] = [];

        try {
            // 2. Apply Carving (Base Logic: Base - Decorations)
            if (carveTargets && carveTargets.length > 0) {
                console.log(`[SVGLayerMesh] Carving Base with ${carveTargets.length} targets...`);
                const carvedGeo = CSGHelper.carveBase(mesh, carveTargets);
                if (carvedGeo) {
                    mesh.geometry = carvedGeo;
                    disposables.push(carvedGeo); // Track for disposal
                    mesh.updateMatrixWorld();
                } else {
                    console.warn("[SVGLayerMesh] Carve returned null geometry");
                }
            }

            // 3. Apply Clipping (Decoration Logic: Decoration INTERSECT Base)
            if (clipTarget) {
                const clippedGeo = CSGHelper.clipDecoration(mesh, clipTarget);
                // If we already carved, that geometry is now replaced. 
                // However, we added it to `disposables` so it will be cleaned up on unmount.
                // BUT, we can clean it up NOW if we want to be strict, but keeping it simple: cleanup on unmount is safe.
                mesh.geometry = clippedGeo;
                disposables.push(clippedGeo);
            }
        } catch (e) {
            console.error("CSG Op Failed", e);
            mesh.geometry = geometry; // Fallback
        }

        // Cleanup: Dispose of any geometries created by this run when dependencies change
        return () => {
            if (mesh.geometry !== geometry) {
                mesh.geometry = geometry; // Revert to base
            }
            disposables.forEach(g => g.dispose());
        };

    }, [geometry, clipTarget, carveTargets, scale, zOffset, offsetKey]); // Re-run when geometry or target changes

    return (
        <mesh ref={internalRef} name={name} geometry={geometry} position={[0, 0, finalZ]} rotation={[0, 0, 0]}>
            <meshStandardMaterial color={color} roughness={0.4} side={THREE.DoubleSide} />
        </mesh>
    );
});
