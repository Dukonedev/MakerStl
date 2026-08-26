import React, { useRef, forwardRef, useImperativeHandle, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment, Float, ContactShadows, Grid } from '@react-three/drei';
import * as THREE from 'three';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';
import { OBJExporter } from 'three/addons/exporters/OBJExporter.js';
import { KeychainConfig } from '../types';
import { KeychainMesh } from './KeychainMesh';

interface SceneProps {
  config: KeychainConfig;
  autoRotate?: boolean;
}

export interface SceneRef {
  exportSTL: () => void;
  resetCamera: () => void;
}

const SceneContent = forwardRef<SceneRef, SceneProps>(({ config, autoRotate }, ref) => {
  const meshRef = useRef<THREE.Group>(null);
  const controlsRef = useRef<any>(null);

  useImperativeHandle(ref, () => ({
    exportSTL: () => {
      if (!meshRef.current) return;
      const exporter = new STLExporter();
      const result = exporter.parse(meshRef.current, { binary: true });
      const blob = new Blob([result], { type: 'application/octet-stream' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `KeyGen3D_${config.text.replace(/\s+/g, '_')}.stl`;
      link.click();
    },
    resetCamera: () => {
      controlsRef.current?.reset();
    }
  }));

  useEffect(() => {
    if (controlsRef.current) {
      controlsRef.current.minPolarAngle = 0;
      controlsRef.current.maxPolarAngle = Math.PI / 1.5;
    }
  }, []);

  return (
    <>
      <OrbitControls ref={controlsRef} makeDefault autoRotate={autoRotate} autoRotateSpeed={2} />
      <Environment files="./hdr/potsdamer_platz_1k.hdr" />
      <ambientLight intensity={0.5} />
      <spotLight position={[10, 10, 10]} angle={0.15} penumbra={1} intensity={1} castShadow />

      <Grid
        position={[0, -15, 0]}
        args={[100, 100]}
        cellSize={5}
        cellThickness={1}
        cellColor="#a3e635"
        sectionSize={25}
        sectionThickness={1.5}
        sectionColor="#4d7c0f"
        fadeDistance={60}
        fadeStrength={1}
        infiniteGrid
      />
      <ContactShadows position={[0, -4, 0]} opacity={0.6} scale={50} blur={2} far={10} resolution={256} color="#000000" />

      <Float speed={2} rotationIntensity={0.2} floatIntensity={0.2}>
        <React.Suspense fallback={null}>
          <KeychainMesh ref={meshRef} config={config} />
        </React.Suspense>
      </Float>
    </>
  );
});

SceneContent.displayName = 'SceneContent';

// Wrapper component to handle the ref forwarding correctly with the Canvas
export const Scene = forwardRef<SceneRef, SceneProps>((props, ref) => {
  return (
    <Canvas shadows camera={{ position: [0, 5, 40], fov: 45 }} className="w-full h-full rounded-xl overflow-hidden bg-gradient-to-b from-black to-zinc-900">
      <color attach="background" args={['#050505']} />

      <SceneContent ref={ref} {...props} />
    </Canvas>
  );
});

Scene.displayName = 'Scene';