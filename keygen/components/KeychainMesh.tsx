import React, { useMemo, forwardRef, useState } from 'react';
import { useLoader } from '@react-three/fiber';
import { Center } from '@react-three/drei';
import * as THREE from 'three';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';
import { SVGLoader } from 'three/addons/loaders/SVGLoader.js';
import * as BufferGeometryUtils from 'three/addons/utils/BufferGeometryUtils.js';
import { KeychainConfig } from '../types';

// Helper: Calculate bounding box of shapes safely
const getShapesBoundingBox = (shapes: THREE.Shape[]) => {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

  if (!shapes || !Array.isArray(shapes) || shapes.length === 0) {
    return { minX: 0, maxX: 0, minY: 0, maxY: 0, width: 0, height: 0, centerX: 0, centerY: 0 };
  }

  shapes.forEach(shape => {
    if (!shape) return;
    const points = shape.getPoints();
    points.forEach(p => {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    });
  });

  if (minX === Infinity) return { minX: 0, maxX: 0, minY: 0, maxY: 0, width: 0, height: 0, centerX: 0, centerY: 0 };

  return {
    minX, maxX, minY, maxY,
    width: maxX - minX,
    height: maxY - minY,
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2
  };
};

// Helper for Point in Polygon (Ray Casting)
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

export const KeychainMesh = forwardRef<THREE.Group, { config: KeychainConfig }>(({ config }, ref) => {
  const [measuredSize, setMeasuredSize] = useState({ width: 0, height: 0 });

  // Fixed Ring Dimensions
  const ringOuterRadius = 4.0;
  const ringInnerRadius = 3.0;

  const font = useLoader(FontLoader, config.fontUrl);

  // 1. GENERATE TEXT SHAPES
  const { solidShapes, hollowShapes } = useMemo(() => {
    if (!font) return { solidShapes: [], hollowShapes: [] };
    const solid: THREE.Shape[] = [];
    const hollow: THREE.Shape[] = [];
    let cursorX = 0;

    const textToRender = config.text || " ";
    const chars = Array.from(textToRender);

    chars.forEach(char => {
      const charShapes = font.generateShapes(char, config.fontSize);

      // Calculate advance width
      let advance = config.fontSize * 0.5;
      if (font.data && font.data.glyphs) {
        const glyph = font.data.glyphs[char] || font.data.glyphs['?'];
        const resolution = font.data.resolution || 1000;
        if (glyph && glyph.ha) {
          advance = (glyph.ha / resolution) * config.fontSize;
        }
      }

      charShapes.forEach(originalShape => {
        // Apply stretch (fontScaleX) and cursor position
        const transform = (pts: THREE.Vector2[]) => {
          return pts.map(p => new THREE.Vector2(p.x * config.fontScaleX + cursorX, p.y));
        };

        const scaledPoints = transform(originalShape.getPoints());

        // Hollow Shape (Text Internal)
        const hShape = new THREE.Shape(scaledPoints);
        if (originalShape.holes) {
          originalShape.holes.forEach(hole => {
            hShape.holes.push(new THREE.Path(transform(hole.getPoints())));
          });
        }
        hollow.push(hShape);

        // Solid Shape (Base for Outline mode)
        // User wants the base to be a solid backing (no holes), so we ignore internal holes here.
        solid.push(new THREE.Shape(scaledPoints));
      });

      cursorX += (advance * config.fontScaleX) + config.letterSpacing;
    });

    return { solidShapes: solid, hollowShapes: hollow };
  }, [font, config.text, config.fontSize, config.fontScaleX, config.letterSpacing]);

  // 1b. CALCULATE TEXT BOUNDS (Shared)
  const textBounds = useMemo(() => {
    return getShapesBoundingBox(solidShapes);
  }, [solidShapes]);

  // 2. GENERATE BASE GEOMETRY (Capsule or Outline)
  const { baseGeometry, borderGeometry, accessoryGeometry, secondOutlineGeometry, templateDetailGeometry, templateLayers, maxLayerHeight } = useMemo(() => {
    if (!solidShapes || solidShapes.length === 0) return { baseGeometry: null, borderGeometry: null, accessoryGeometry: null, secondOutlineGeometry: null, templateDetailGeometry: null, templateLayers: [], maxLayerHeight: 0 };

    const centerX = textBounds.centerX;
    const centerY = textBounds.centerY;

    // Default extrude settings for base
    const formExtrudeSettings = {
      depth: config.thickness,
      bevelEnabled: false,
      curveSegments: 64
    };

    // --- CASE A: CAPSULE ---
    if (config.baseShape === 'capsule') {
      const margin = Math.max(config.outlineSize, 3.0);
      const capsuleHeight = textBounds.height + (margin * 2);
      const radius = capsuleHeight / 2;
      const totalWidth = Math.max(capsuleHeight, config.baseWidth);
      const straightLength = totalWidth - (radius * 2);

      const rectMinX = textBounds.centerX - straightLength / 2;
      const rectMaxX = textBounds.centerX + straightLength / 2;

      const drawCapsule = (r: number, minX: number, maxX: number) => {
        const shape = new THREE.Shape();
        // Shift centers to (0,0) instead of centerX/centerY
        shape.moveTo(maxX - centerX, -r);
        shape.absarc(maxX - centerX, 0, r, -Math.PI / 2, Math.PI / 2, false);
        shape.lineTo(minX - centerX, r);
        shape.absarc(minX - centerX, 0, r, Math.PI / 2, Math.PI * 1.5, false);
        shape.lineTo(maxX - centerX, -r);
        return shape;
      };

      const outerShape = drawCapsule(radius, rectMinX, rectMaxX);

      // --- Ring Logic Update ---
      // We explicitly calculate correct bounds for the capsule so the ring attaches to the TIP, not the cap center.
      // And we use the Standardized Ring Helper to generate the mesh.
      const capsuleBounds = {
        minX: rectMinX - radius,
        maxX: rectMaxX + radius,
        minY: textBounds.minY - margin, // approx, mostly for centerY
        maxY: textBounds.maxY + margin,
        width: totalWidth,
        height: capsuleHeight,
        centerX: textBounds.centerX,
        centerY: textBounds.centerY
      };

      // 2. Cut Hole at this position
      // USER REQUEST: "Hole on left side after potential internal border".
      // We anchor to the LEFT TIP (rectMinX - radius).
      // We add space for the Border (2.0) + Hole Radius (3.0) + small padding.
      const ringHole = new THREE.Path();

      const leftTipX = rectMinX - radius;
      const borderOffset = config.addBorder ? 2.0 : 0.0;
      const basePadding = 1.0; // Minimal spacing from border

      // Position = Tip + Border + Padding + Radius + UserOffset
      const holeCenterX = (leftTipX - centerX) + borderOffset + basePadding + ringInnerRadius + (config.ringOverlap || 0);

      ringHole.absarc(holeCenterX, config.ringOffsetY || 0, ringInnerRadius, 0, Math.PI * 2, true);
      outerShape.holes.push(ringHole);

      let bg: THREE.BufferGeometry = new THREE.ExtrudeGeometry(outerShape, formExtrudeSettings);
      bg = BufferGeometryUtils.mergeVertices(bg);
      bg.computeVertexNormals();

      // Border logic
      let borderGeom: THREE.BufferGeometry | null = null;
      if (config.addBorder) {
        const borderThickness = 2.0;
        const innerRadius = radius - borderThickness;
        const innerShape = drawCapsule(radius, rectMinX, rectMaxX); // Outer boundary of border

        // Cut out the inner part
        const innerHolePath = new THREE.Path();
        innerHolePath.moveTo(rectMaxX - centerX, -innerRadius);
        innerHolePath.absarc(rectMaxX - centerX, 0, innerRadius, -Math.PI / 2, Math.PI / 2, false);
        innerHolePath.lineTo(rectMinX - centerX, innerRadius);
        innerHolePath.absarc(rectMinX - centerX, 0, innerRadius, Math.PI / 2, Math.PI * 1.5, false);
        innerHolePath.lineTo(rectMaxX - centerX, -innerRadius);

        innerShape.holes.push(innerHolePath);

        borderGeom = new THREE.ExtrudeGeometry(innerShape, {
          depth: config.textDepth + 0.5, // Slightly higher than base?
          bevelEnabled: false,
          curveSegments: 64
        });
        borderGeom = BufferGeometryUtils.mergeVertices(borderGeom);
        borderGeom.computeVertexNormals();
      }

      // 4. SECOND OUTLINE (Text Outline)
      let secondBg: THREE.BufferGeometry | null = null;
      if (config.addSecondOutline && hollowShapes?.length > 0) {
        // Use logic similar to Outline Mode but for Capsule context
        const effectiveSecondSize = Math.min(config.secondOutlineSize, Math.max(0.1, config.outlineSize - 0.1)); // Clamp logic
        const W2 = config.secondOutlineSize; // Use direct config unless clamping needed? User said "insert outline on text". Usually uses secondOutlineSize.

        const R2 = Math.max(config.secondOutlineEdgeRoundness, 0.01);
        const effectiveR2 = Math.min(R2, W2);
        const effectiveOffset2 = W2 - effectiveR2;

        const secondSettings = {
          depth: config.secondOutlineDepth,
          bevelEnabled: true,
          bevelThickness: effectiveR2,
          bevelSize: effectiveR2,
          bevelOffset: effectiveOffset2,
          bevelSegments: config.roundness > 0 ? config.roundness : 1,
          curveSegments: 64
        };

        const secondOutlineShapes = hollowShapes.map(s => s.clone());
        secondBg = new THREE.ExtrudeGeometry(secondOutlineShapes, secondSettings);

        // Push slightly Z to avoid z-fight with base? Base ends at config.thickness.
        // We render it at Start Z = config.thickness?
        // The main render group logic puts seconOutline at config.thickness.

        // But we need to handle bevelThickness centering if any?
        const bevelThickness4 = secondSettings.bevelThickness;
        secondBg.translate(0, 0, bevelThickness4);

        secondBg = BufferGeometryUtils.mergeVertices(secondBg);
        secondBg.computeVertexNormals();
      }

      return { baseGeometry: bg, borderGeometry: borderGeom, accessoryGeometry: null, secondOutlineGeometry: secondBg, templateDetailGeometry: null, templateLayers: [], maxLayerHeight: config.thickness };
    }

    // --- CASE C: SVG TEMPLATE ---
    else if (config.baseShape === 'template' && config.templateContent) {
      const loader = new SVGLoader();
      const svgData = loader.parse(config.templateContent);

      const allShapes: THREE.Shape[] = [];
      const colorGroups: { color: string, shapes: THREE.Shape[] }[] = [];

      svgData.paths.forEach((path: any) => {
        const shapes = path.toShapes(true);
        // Determine color
        let color = config.color; // Default fallback
        if (path.color) {
          color = '#' + path.color.getHexString();
        }
        // Group by color
        let group = colorGroups.find(g => g.color === color);
        if (!group) {
          group = { color, shapes: [] };
          colorGroups.push(group);
        }
        group.shapes.push(...shapes);
        allShapes.push(...shapes);
      });

      if (allShapes.length === 0) return { baseGeometry: null, borderGeometry: null, accessoryGeometry: null, secondOutlineGeometry: null, templateDetailGeometry: null, templateLayers: [], maxLayerHeight: 0 };

      // We need to center and scale the loaded SVG to fit reasonable dimensions
      // Use GLOBAL bounds for all shapes to ensure relative positions are correct
      const svgBounds = getShapesBoundingBox(allShapes);

      // Scale logic: Fit within Max Dimension
      const svgMaxDim = Math.max(svgBounds.width, svgBounds.height) || 1;
      const TARGET_DIM = config.svgMaxDimension || 50;
      const scale = TARGET_DIM / svgMaxDim;

      // Helper to transform shapes
      const transformShapes = (shapes: THREE.Shape[]) => {
        return shapes.map(shape => {
          let points = shape.getPoints().map(p => new THREE.Vector2(
            (p.x - svgBounds.centerX) * scale,
            ((p.y - svgBounds.centerY) * -1) * scale
          ));

          // Force CCW for Solid Shapes (Area > 0)
          if (THREE.ShapeUtils.area(points) < 0) {
            points = points.reverse();
          }

          const newShape = new THREE.Shape(points);
          if (shape.holes) {
            shape.holes.forEach((hole: THREE.Path) => {
              let holePoints = hole.getPoints().map((p: THREE.Vector2) => new THREE.Vector2(
                (p.x - svgBounds.centerX) * scale,
                ((p.y - svgBounds.centerY) * -1) * scale
              ));

              // Force CW for Holes (Area < 0)
              if (THREE.ShapeUtils.area(holePoints) > 0) {
                holePoints = holePoints.reverse();
              }

              newShape.holes.push(new THREE.Path(holePoints));
            });
          }
          return newShape;
        });
      };



      // Process each Color Group separately
      const layers: { geometry: THREE.BufferGeometry, color: string }[] = [];
      let maxLayerHeight = 0;
      let baseLayerInfo = { depth: config.thickness, offset: 0 }; // Default base info

      colorGroups.forEach(group => {
        const centeredShapes = transformShapes(group.shapes);

        // Nesting Logic (Per Color Group)
        const allContours: THREE.Shape[] = [];
        centeredShapes.forEach(s => {
          allContours.push(new THREE.Shape(s.getPoints()));
          if (s.holes && s.holes.length > 0) {
            s.holes.forEach(h => allContours.push(new THREE.Shape(h.getPoints())));
          }
        });

        const shapesWithDepth = allContours.map((shape, index) => {
          const points = shape.getPoints();
          if (points.length === 0) return { shape, depth: 0, parentIndex: -1, index }; // Safety
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

        const finalShapes: THREE.Shape[] = [];
        const solidsByIndex = new Map<number, THREE.Shape>();

        shapesWithDepth.filter(item => item.depth % 2 === 0).forEach(item => {
          let points = item.shape.getPoints();
          if (THREE.ShapeUtils.area(points) < 0) points = points.reverse();
          const newShape = new THREE.Shape(points);
          solidsByIndex.set(item.index, newShape);
          finalShapes.push(newShape);
        });

        shapesWithDepth.filter(item => item.depth % 2 === 1).forEach(item => {
          const parentItem = shapesWithDepth.find(p => p.index === item.parentIndex);
          if (parentItem) {
            const parentShape = solidsByIndex.get(parentItem.index);
            if (parentShape) {
              let points = item.shape.getPoints();
              if (THREE.ShapeUtils.area(points) > 0) points = points.reverse();
              parentShape.holes.push(new THREE.Path(points));
            }
          }
        });

        if (finalShapes.length > 0) {
          // Determines extrusion settings for this specific color group
          // Priority: layerConfig (per-color) > Base Layer Logic > Default defaults
          let depth = config.thickness;
          let offset = 0;

          const layerSettings = config.layerConfig?.[group.color];

          // Check if this is the base layer
          let isBaseLayer = false;
          if (config.baseLayerColor && group.color) {
            isBaseLayer = config.baseLayerColor.toLowerCase() === group.color.toLowerCase();
          }

          if (layerSettings) {
            depth = layerSettings.depth;
            offset = layerSettings.offset;
          } else {
            // Fallback to "Base Layer Logic" if no detailed config exists
            if (isBaseLayer) {
              offset = -config.thickness;
            }
          }

          // Capture Base Layer Info if this is the base layer
          if (isBaseLayer) {
            baseLayerInfo = { depth, offset };
          }

          // Update Max Height for Text positioning
          const topZ = depth + offset;
          if (topZ > maxLayerHeight) {
            maxLayerHeight = topZ;
          }

          const templateSettings = {
            depth: depth,
            bevelEnabled: false,
            bevelThickness: 0,
            bevelSize: 0,
            bevelSegments: 2,
            curveSegments: 64
          };
          let bg: THREE.BufferGeometry = new THREE.ExtrudeGeometry(finalShapes, templateSettings);

          if (offset !== 0) {
            bg.translate(0, 0, offset);
          }

          bg = BufferGeometryUtils.mergeVertices(bg);
          bg.computeVertexNormals();

          layers.push({ geometry: bg, color: group.color });
        }
      });

      // --- SECOND OUTLINE (Optional) for Template ---
      // --- SECOND OUTLINE (Optional) for Template: NOW TARGETS TEXT ---
      let secondBg: THREE.BufferGeometry | null = null;
      if (config.addSecondOutline && hollowShapes && hollowShapes.length > 0) {
        // Use TEXT shapes (hollowShapes) for the outline, not the template
        const textShapesForOutline = hollowShapes.map(s => s.clone());

        const W2 = config.secondOutlineSize;
        const R2 = Math.max(config.secondOutlineEdgeRoundness, 0.01);
        const effectiveR2 = Math.min(R2, W2);
        const effectiveOffset2 = W2 - effectiveR2;

        const secondSettings = {
          depth: config.secondOutlineDepth,
          bevelEnabled: true,
          bevelThickness: effectiveR2,
          bevelSize: effectiveR2,
          bevelOffset: effectiveOffset2,
          bevelSegments: config.roundness > 0 ? config.roundness : 1,
          curveSegments: 64
        };

        secondBg = new THREE.ExtrudeGeometry(textShapesForOutline, secondSettings);

        // Translate up by bevel thickness if needed, similar to text
        const bevelThickness4 = secondSettings.bevelThickness;
        secondBg.translate(0, 0, bevelThickness4);

        secondBg = BufferGeometryUtils.mergeVertices(secondBg);
        secondBg.computeVertexNormals();
      }



      // Generate Ring Geometry (Using Base Layer Info)
      // We pass the ALL TRANSFORMED shapes to finding bounding/contour, but use baseLayerInfo for extrusion
      const allTransformedForRing = transformShapes(allShapes);
      const ringGeo = getRingGeometry(null, svgBounds, 1, config, allTransformedForRing, baseLayerInfo);

      return { baseGeometry: null, borderGeometry: null, accessoryGeometry: ringGeo, secondOutlineGeometry: secondBg, templateDetailGeometry: null, templateLayers: layers, maxLayerHeight };
    }


    // --- CASE B: OUTLINE (Default) ---
    else {
      // "Inflated" Text approach (Bubble Outline)
      // We use the text shapes themselves + a ring shape, and extrude them with a large bevel (outlineSize)
      // effectively creating a contour around the text.

      let outlineShapes = solidShapes.map(s => {
        const poly = s.getPoints().map(p => new THREE.Vector2(p.x - textBounds.centerX, p.y - textBounds.centerY));
        const newS = new THREE.Shape(poly);
        if (s.holes) {
          s.holes.forEach(h => newS.holes.push(new THREE.Path(h.getPoints().map(p => new THREE.Vector2(p.x - textBounds.centerX, p.y - textBounds.centerY)))));
        }
        return newS;
      });

      // 1. We NO LONGER add the ring to 'outlineShapes'. It is handled purely as an accessory.
      // This ensures fully independent settings (bevel, position, etc.)

      // "Inflated" Text approach (Bubble Outline)
      // Logic Update: Decouple 'Expansion Width' from 'Bevel Radius'.
      // W = outlineSize (Total intended width)
      const W = config.outlineSize;
      const R = Math.max(config.edgeRoundness, 0.01); // Min 0.01 to ensure bevel generation

      // If requested radius R is larger than width W, we cap the radius at W
      const effectiveR = Math.min(R, W);
      const effectiveOffset = W - effectiveR;

      const outlineSettings = {
        depth: config.thickness,
        bevelEnabled: true,
        bevelThickness: effectiveR, // Z-height of bevel matches XY-width for uniform roundness
        bevelSize: effectiveR, // XY-width of bevel
        bevelOffset: effectiveOffset, // Flat expansion before the bevel starts
        bevelSegments: config.baseRoundness > 0 ? config.baseRoundness : 1,
        curveSegments: 64
      };

      let bg: THREE.BufferGeometry = new THREE.ExtrudeGeometry(outlineShapes, outlineSettings);

      // Resolve non-manifold edges: translate up instead of squashing
      const bevelThickness3 = outlineSettings.bevelThickness;
      bg.translate(0, 0, bevelThickness3);

      bg = BufferGeometryUtils.mergeVertices(bg);
      bg.computeVertexNormals();

      // --- SECOND OUTLINE (Optional) ---
      let secondBg: THREE.BufferGeometry | null = null;
      if (config.addSecondOutline) {
        // Enforce constraint: Second outline must be smaller than the first (Base)
        // We clamp the size to be at most outlineSize - 0.1
        const effectiveSecondSize = Math.min(config.secondOutlineSize, Math.max(0.1, config.outlineSize - 0.1));

        const W2 = effectiveSecondSize;
        const R2 = Math.max(config.secondOutlineEdgeRoundness, 0.01);
        const effectiveR2 = Math.min(R2, W2);
        const effectiveOffset2 = W2 - effectiveR2;

        const secondSettings = {
          depth: config.secondOutlineDepth,
          bevelEnabled: true,
          bevelThickness: effectiveR2,
          bevelSize: effectiveR2,
          bevelOffset: effectiveOffset2,
          bevelSegments: config.roundness > 0 ? config.roundness : 1,
          curveSegments: 64
        };

        // Deep clone shapes for the second outline.
        // We use HOLLOW shapes here because the user wants the second outline (border)
        // to respect the inner holes of letters (like 'O'), unlike the solid base.
        const secondOutlineShapes = hollowShapes.map(s => s.clone());

        secondBg = new THREE.ExtrudeGeometry(secondOutlineShapes, secondSettings);

        const bevelThickness4 = secondSettings.bevelThickness;
        secondBg.translate(0, 0, bevelThickness4);

        secondBg = BufferGeometryUtils.mergeVertices(secondBg);
        secondBg.computeVertexNormals();
      }

      // Generate Ring Geometry (Standardized Helper)
      let ringGeo: THREE.BufferGeometry | null = null;
      if (config.showRing) {
        // CONVEX HULL LOGIC:
        // We aggregate ALL points from ALL outline shapes (letters).
        // We compute the Convex Hull to create a single "Rubber Band" shape around the text.
        // This ensures the ring follows the collective outline, bridging gaps between letters.
        let allPoints: THREE.Vector2[] = [];
        outlineShapes.forEach(s => {
          allPoints.push(...s.getPoints());
        });

        // Compute Hull
        const hullPoints = getConvexHull(allPoints);
        const hullShape = new THREE.Shape(hullPoints);

        // Pass this single Hull Shape to helper
        ringGeo = getRingGeometry(null, textBounds, 1, config, [hullShape]);
      }

      return { baseGeometry: bg, borderGeometry: null, accessoryGeometry: ringGeo, secondOutlineGeometry: secondBg, templateLayers: [], maxLayerHeight: config.thickness };
    }

  }, [solidShapes, hollowShapes, textBounds, config.baseShape, config.baseWidth, config.thickness, config.outlineSize, config.roundness, config.baseRoundness, config.addBorder, config.textDepth, config.ringOverlap, config.ringOffsetY, config.edgeRoundness, config.addSecondOutline, config.secondOutlineSize, config.secondOutlineDepth, config.secondOutlineEdgeRoundness, config.templateContent, config.svgMaxDimension, config.textOffsetX, config.textOffsetY, config.showRing, config.ringPosition, config.color, config.layerConfig, config.baseLayerColor]);

  // 3. TEXT GEOMETRY
  const textGeometry = useMemo(() => {
    if (!hollowShapes || hollowShapes.length === 0) return null;
    const settings = {
      depth: config.textDepth,
      bevelEnabled: true,
      bevelThickness: 0.02,
      bevelSize: 0.02,
      bevelOffset: 0,
      bevelSegments: 3,
      curveSegments: 32
    };
    let geo: THREE.BufferGeometry = new THREE.ExtrudeGeometry(hollowShapes, settings);
    geo = BufferGeometryUtils.mergeVertices(geo);
    geo.computeVertexNormals();

    return geo;
  }, [hollowShapes, config.textDepth]);


  return (
    <group ref={ref as any}>
      <Center disableZ disableY={false} disableX={false}>
        <group>
          {baseGeometry && (
            <mesh geometry={baseGeometry}>
              <meshStandardMaterial color={config.color} roughness={0.3} metalness={0.1} />
            </mesh>
          )}
          {/* New Multi-Color Template Rendering */}
          {templateLayers && templateLayers.length > 0 && templateLayers.map((layer, idx) => (
            <mesh key={idx} geometry={layer.geometry}>
              <meshStandardMaterial color={layer.color} roughness={0.3} metalness={0.1} />
            </mesh>
          ))}
          {accessoryGeometry && (
            <mesh geometry={accessoryGeometry}>
              <meshStandardMaterial color={config.color} roughness={0.3} metalness={0.1} />
            </mesh>
          )}
          {borderGeometry && (
            <mesh geometry={borderGeometry} position={[0, 0, config.thickness]}>
              <meshStandardMaterial color={config.textColor} roughness={0.3} metalness={0.1} />
            </mesh>
          )}
          {secondOutlineGeometry && (
            <mesh geometry={secondOutlineGeometry} position={[
              config.textOffsetX - textBounds.centerX,
              config.textOffsetY - textBounds.centerY,
              (config.baseShape === 'template' && (typeof maxLayerHeight !== 'undefined'))
                ? maxLayerHeight
                : config.thickness
            ]}>
              <meshStandardMaterial color="white" roughness={0.3} metalness={0.1} />
            </mesh>
          )}
          {textGeometry && (
            <mesh geometry={textGeometry} position={[
              config.textOffsetX - textBounds.centerX,
              config.textOffsetY - textBounds.centerY,
              (config.baseShape === 'template' && (typeof maxLayerHeight !== 'undefined'))
                ? (maxLayerHeight + (config.textOffsetZ || 0) + (config.addSecondOutline ? config.secondOutlineDepth : 0))
                : (config.thickness + (config.textOffsetZ || 0) + (config.addSecondOutline ? config.secondOutlineDepth : 0))
            ]}>
              <meshStandardMaterial color={config.textColor} />
            </mesh>
          )}
          {templateDetailGeometry && (
            <mesh geometry={templateDetailGeometry}>
              <meshStandardMaterial color="white" roughness={0.3} metalness={0.1} />
            </mesh>
          )}
        </group>
      </Center>
    </group>
  );
});

KeychainMesh.displayName = 'KeychainMesh';

export default KeychainMesh;

// Helper to generate Ring Geometry consistent across modes
// Helper to generate Ring Geometry consistent across modes
function getRingGeometry(bg: THREE.BufferGeometry | null, bounds: any, scale: number = 1, config: KeychainConfig, shapes?: THREE.Shape[], baseLayerInfo?: { depth: number, offset: number }) {
  // 1. Check Visibility
  if (config.showRing === false) return null;

  if (!bounds && !bg) return null;

  // Ring dimensions
  const ringOuterRadius = 4.0;
  const ringInnerRadius = 3.0;

  const ringOverlap = config.ringOverlap || 1.5; // Default overlap if not specified
  const outlineSize = config.outlineSize || 0;

  let ringCX = bounds.minX - (ringOuterRadius - ringOverlap);
  let ringCY = bounds.centerY + (config.ringOffsetY || 0);

  // 2. Dynamic Positioning Logic (Template Mode & Outline Mode) - Active if shapes are provided
  if (shapes && shapes.length > 0) {
    // Find the main shape (largest perimeter)
    let mainShape = shapes[0];
    let maxLen = 0;
    shapes.forEach(s => {
      const len = s.getLength();
      if (len > maxLen) {
        maxLen = len;
        mainShape = s;
      }
    });

    // Calculate position along perimeter
    // Calculate position along perimeter
    // We utilize 'config.ringPosition' (0-1) from the slider.

    // Explicit check for undefined to allow 0 as a valid value
    const hasRingPos = typeof config.ringPosition !== 'undefined';
    let t = Math.max(0, Math.min(1, hasRingPos ? config.ringPosition! : 0));

    // Fallback: If ringPosition is undefined (e.g. legacy or uninitialized) and we have an offset Y,
    // we use offset Y to slide.

    if (!hasRingPos && config.ringOffsetY) {
      const len = mainShape.getLength();
      let shift = config.ringOffsetY / len;

      t = (0 + shift) % 1;
      if (t < 0) t += 1;
    }

    const point = mainShape.getPointAt(t);
    const tangent = mainShape.getTangentAt(t);

    // Tangent (tx, ty).
    // Standard Normal for CCW curve: (-ty, tx) points "left" (Outward).
    // However, shape winding might vary.
    let nx = -tangent.y;
    let ny = tangent.x;

    // ROBUST NORMAL CHECK:
    // We check a point slightly along the normal. If it's INSIDE the shape, the normal is pointing IN.
    // We want the OUTWARD normal.
    // We use a small epsilon distance for the check.
    const checkDist = 0.5; // Enough to clear boundary
    const checkPt = new THREE.Vector2(point.x + nx * checkDist, point.y + ny * checkDist);
    const mainPoly = mainShape.getPoints();

    // If the check point is INSIDE, then 'nx, ny' points INWARD. We must flip to point OUT.
    if (isPointInside(checkPt, mainPoly)) {
      nx = -nx;
      ny = -ny;
    }

    // Desired offset from edge:
    // We want the ring to overlap the shape by 'ringOverlap'.
    // Ring Radius is 'ringOuterRadius'.
    // Distance from Edge to Center = ringOuterRadius - ringOverlap.
    // Direction: Outward (Normal).
    // CRITICAL FIX: In Outline mode, the visual base is expanded by 'outlineSize' via bevelOffset.
    // The 'mainShape' is the unexpanded text shape.
    // So we must push the ring OUT by 'outlineSize' to reach the visual edge.
    const expansion = (config.baseShape === 'outline') ? (config.outlineSize || 0) : 0;
    const dist = ringOuterRadius - ringOverlap + expansion;

    ringCX = point.x + nx * dist;
    ringCY = point.y + ny * dist;

  }

  // Geometry Settings (Bevelled)
  // Use Base Layer Depth if provided
  const depth = baseLayerInfo ? baseLayerInfo.depth : config.thickness;
  const offsetZ = baseLayerInfo ? baseLayerInfo.offset : 0;

  // const R = Math.max(config.baseRoundness > 0 ? (config.secondOutlineEdgeRoundness || 0.5) : 0.01, 0.01);

  const ringWallThickness = 1.0;
  // const maxRingBev = ringWallThickness / 2;
  // const effectiveRingR = Math.min(R, maxRingBev - 0.05);
  // USER REQUEST: No bevels on ring.
  const effectiveRingR = 0;

  const ringBaseOuter = ringOuterRadius - effectiveRingR;
  const ringBaseInner = ringInnerRadius + effectiveRingR;

  const ringBaseShape = new THREE.Shape();
  ringBaseShape.absarc(ringCX, ringCY, ringBaseOuter, 0, Math.PI * 2, false);
  const ringBaseHole = new THREE.Path();
  ringBaseHole.absarc(ringCX, ringCY, ringBaseInner, 0, Math.PI * 2, true);
  ringBaseShape.holes.push(ringBaseHole);

  const ringSettings = {
    depth: depth,
    bevelEnabled: false,
    bevelThickness: 0,
    bevelSize: 0,
    bevelSegments: config.baseRoundness > 0 ? config.baseRoundness : 3,
    curveSegments: 64
  };

  const ringGeo = new THREE.ExtrudeGeometry([ringBaseShape], ringSettings);

  // Apply Z offset
  if (offsetZ !== 0) {
    ringGeo.translate(0, 0, offsetZ);
  }

  // Flatten logic (Bottom flattening only if not offset?)
  const ringPos = ringGeo.attributes.position;
  // If offset is negative (e.g. -thickness), Z goes from -thickness to 0.
  // Flatten logic checks if Z < 0 -> 0.
  // This would flatten the whole ring if it's below zero!
  // We should only flat-bottom if we are grounded at 0.
  // If we are intentionally offset, we might not want to kill the bottom.
  // BUT, usually flattening is to remove bevel sticking out the back?
  // Let's assume standard behavior: Flattening ensures z >= minZ.
  // If offsetZ is applied, the "bottom" is at offsetZ.
  // We should clamp to offsetZ?
  // Or just disable flattening for templates if we trust the extrusion.
  // The original flatten logic was likely for Capsule mode where bevel might poke through?
  // Let's just disable the flattening loop for templates (when baseLayerInfo is present) or adjust it.

  if (!baseLayerInfo) {
    // Only run flattening for standard cases
    for (let i = 0; i < ringPos.count; i++) {
      if (ringPos.getZ(i) < 0) ringPos.setZ(i, 0);
    }
  }

  ringGeo.computeVertexNormals();

  return ringGeo;
}

// Helper: Monotone Chain Convex Hull Algorithm
const getConvexHull = (points: THREE.Vector2[]) => {
  if (points.length < 3) return points;

  // Sort by X then Y
  const sorted = points.slice().sort((a, b) => a.x === b.x ? a.y - b.y : a.x - b.x);

  const cross = (o: THREE.Vector2, a: THREE.Vector2, b: THREE.Vector2) => {
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  };

  const lower: THREE.Vector2[] = [];
  for (let i = 0; i < sorted.length; i++) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], sorted[i]) <= 0) {
      lower.pop();
    }
    lower.push(sorted[i]);
  }

  const upper: THREE.Vector2[] = [];
  for (let i = sorted.length - 1; i >= 0; i--) {
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], sorted[i]) <= 0) {
      upper.pop();
    }
    upper.push(sorted[i]);
  }

  upper.pop();
  lower.pop();
  return lower.concat(upper);
};
