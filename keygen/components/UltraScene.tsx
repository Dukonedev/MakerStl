import React, { useRef, forwardRef, useImperativeHandle } from 'react';
import { OrbitControls, Environment, Grid, ContactShadows, Center, Bounds, useBounds } from '@react-three/drei';
import { Canvas } from '@react-three/fiber';
import { ColorLayer } from './UltraStudio';
import { SVGLayerMesh } from './SVGLayerMesh';
import { ExportManager } from './ExportManager';
import { CSGHelper } from './CSGHelper';
import * as THREE from 'three';

interface UltraSceneProps {
    layers: ColorLayer[];
    center: { x: number, y: number };
    scale: number;
}

const SceneContent = forwardRef<any, UltraSceneProps>(({ layers, center, scale }, ref) => {
    const groupRef = useRef<THREE.Group>(null);
    const controlsRef = useRef<any>(null);
    const [baseMesh, setBaseMesh] = React.useState<THREE.Mesh | null>(null);

    // Store refs to decoration meshes for boolean subtraction
    const decoRefs = React.useRef<Map<string, THREE.Mesh>>(new Map());

    // Callback ref to capture base mesh
    const setBaseRef = React.useCallback((node: THREE.Mesh | null) => {
        if (node) setBaseMesh(node);
    }, []);

    useImperativeHandle(ref, () => ({
        export3MF: async (filename: string) => {
            if (!groupRef.current) return;
            await ExportManager.exportScene(groupRef.current, '3mf', filename);
        },
        exportSTL: async (filename: string) => {
            if (!groupRef.current) return;
            await ExportManager.exportScene(groupRef.current, 'stl', filename);
        },
        exportOBJ: async (filename: string) => {
            if (!groupRef.current) return;
            await ExportManager.exportScene(groupRef.current, 'obj', filename);
        },
        resetView: () => {
            if (controlsRef.current) {
                controlsRef.current.reset();
            }
        }
    }));

    return (
        <>
            <OrbitControls ref={controlsRef} makeDefault autoRotate={false} />
            <Environment files="./hdr/potsdamer_platz_1k.hdr" />
            <ambientLight intensity={0.5} />
            <spotLight position={[10, 10, 10]} angle={0.15} penumbra={1} intensity={1} castShadow />

            <Grid
                position={[0, -5, 0]}
                args={[100, 100]}
                cellSize={5}
                cellThickness={1}
                cellColor="#a855f7" // Purple for Ultra
                sectionSize={25}
                sectionThickness={1.5}
                sectionColor="#7e22ce"
                fadeDistance={60}
                fadeStrength={1}
                infiniteGrid
            />

            <ContactShadows position={[0, -4.9, 0]} opacity={0.6} scale={50} blur={2} far={10} color="#000000" />

            {/* Main Group with Scaling - No Rotation (Fixed 180 flip) */}
            <Bounds fit clip observe margin={1.2}>
                <Center>
                    <group ref={groupRef} scale={scale} position={[0, 0, 0]}>
                        {(() => {
                            // Calculate Carve Key (Trigger for Base updates)
                            const carveKey = layers
                                .filter(l => !l.isSolid)
                                .map(l => `${l.id}:${l.offset?.x}_${l.offset?.y}_${l.scale}_${l.zOffset}_${l.extrusionHeight}`)
                                .join('|');

                            // We need to pass the list of decoration meshes to the Base for subtraction.
                            // However, we can't easily pass the *live* array of meshes during the same render cycle
                            // because refs are populated *after* render.
                            // But since SVGLayerMesh uses useLayoutEffect, and we are passing the ref container (Map),
                            // it can iterate the Map inside its effect!

                            return layers.map((layer) => {
                                const isBase = layer.isSolid;
                                const isDeco = !isBase;

                                return (
                                    <group
                                        key={layer.id}
                                        scale={[layer.scale || 1, layer.scale || 1, 1]}
                                        position={[layer.offset?.x || 0, layer.offset?.y || 0, 0]}
                                        visible={layer.isVisible} // Keep in scene graph for CSG, just hide visual
                                    >
                                        <SVGLayerMesh
                                            ref={(el) => {
                                                if (el) {
                                                    if (isBase) setBaseRef(el);
                                                    else decoRefs.current.set(layer.id, el);
                                                } else {
                                                    if (!isBase) decoRefs.current.delete(layer.id);
                                                }
                                            }}
                                            paths={layer.paths}
                                            color={layer.color}
                                            extrusion={layer.extrusionHeight}
                                            center={center}
                                            isSolid={layer.isSolid}
                                            scale={scale}
                                            name={`Layer_${layer.id}`}

                                            // CSG: Base needs to know about Decorations to carve them out
                                            // Decorations need to know about Base to clip themselves in
                                            clipTarget={isDeco ? baseMesh : null}
                                            carveTargets={isBase ? Array.from(decoRefs.current.values()) : undefined}
                                            offsetKey={isBase ? carveKey : `${layer.offset?.x}_${layer.offset?.y}`}

                                            // Explicit Z-Offset Logic
                                            zOffset={(layer.isSolid ? -layer.extrusionHeight : 0) + (layer.zOffset || 0)}
                                            shapes={layer.processedShapes}
                                        />
                                    </group>
                                );
                            });
                        })()}
                    </group>
                </Center>
            </Bounds>
        </>
    );
});

export const UltraScene = forwardRef<any, UltraSceneProps>((props, ref) => {
    return (
        <Canvas shadows camera={{ position: [0, 50, 50], fov: 45 }} gl={{ preserveDrawingBuffer: true }}>
            <SceneContent ref={ref} {...props} />
        </Canvas>
    );
});
