
import * as THREE from 'three';
import { SUBTRACTION, INTERSECTION, ADDITION, Brush, Evaluator } from 'three-bvh-csg';

export const CSGHelper = {
    clipDecoration: (decorationMesh: THREE.Mesh, baseMesh: THREE.Mesh): THREE.BufferGeometry => {
        // 1. Prepare Brushes
        const decoBrush = new Brush(decorationMesh.geometry);
        decoBrush.updateMatrixWorld();

        // 2. Prepare Base "Prism" (Extrude infinitely up/down to act as a footprint cutter)
        // We Use userData.originalGeometry if available (to avoid clipping against a carved/holed mesh)
        const baseGeoToUse = baseMesh.userData.originalGeometry || baseMesh.geometry;
        const baseGeometry = baseGeoToUse.clone();
        baseGeometry.computeBoundingBox();
        const center = new THREE.Vector3();
        baseGeometry.boundingBox?.getCenter(center);

        const baseBrush = new Brush(baseGeometry);

        // Transform baseBrush to match baseMesh world transform
        baseBrush.position.copy(baseMesh.position);
        baseBrush.rotation.copy(baseMesh.rotation);
        baseBrush.scale.copy(baseMesh.scale);

        // Overwrite Z scale to be huge
        baseBrush.scale.set(baseBrush.scale.x, baseBrush.scale.y, 50);
        baseBrush.updateMatrixWorld();

        // Decoration Transform
        decoBrush.position.copy(decorationMesh.position);
        decoBrush.rotation.copy(decorationMesh.rotation);
        decoBrush.scale.copy(decorationMesh.scale);
        decoBrush.updateMatrixWorld();

        // 3. Perform Intersection
        const evaluator = new Evaluator();
        const result = evaluator.evaluate(decoBrush, baseBrush, INTERSECTION);

        return result.geometry;
    },

    carveBase: (baseMesh: THREE.Mesh, decorationMeshes: THREE.Mesh[]): THREE.BufferGeometry => {
        if (!decorationMeshes || decorationMeshes.length === 0) return baseMesh.geometry;

        // Force update world matrices to capture offsets applied by parent Groups
        baseMesh.updateMatrixWorld(true);

        // 1. Prepare Base Brush
        const baseBrush = new Brush(baseMesh.geometry);
        baseBrush.matrixWorld.copy(baseMesh.matrixWorld);
        baseBrush.matrixAutoUpdate = false; // Important: prevent auto-update from overwriting world matrix with local identity

        // 2. Prepare Evaluator
        const evaluator = new Evaluator();
        evaluator.useGroups = false; // Simplify geometry, single material

        // 3. Iteratively Subtract Decorations
        let resultBrush = baseBrush;

        for (const decoMesh of decorationMeshes) {
            if (!decoMesh.geometry) continue;

            decoMesh.updateMatrixWorld(true);

            // CSG Fix: Scale Z on Geometry directly to avoid messing with MatrixWorld updates
            // We clone (cheap for simple shapes) to avoid mutating original
            const scaledGeo = decoMesh.geometry.clone();
            scaledGeo.scale(1, 1, 1.01); // Expand Z very slightly (1%) for clean cut, avoiding artifacts

            const decoBrush = new Brush(scaledGeo);
            decoBrush.matrixWorld.copy(decoMesh.matrixWorld);
            decoBrush.matrixAutoUpdate = false; // Trust the copied world matrix implicitly

            // Perform Subtraction: Base = Base - Deco
            const result = evaluator.evaluate(resultBrush, decoBrush, SUBTRACTION);
            resultBrush = result;
        }

        // CRITICAL: The result geometry is in World Space because we used matrixWorld in Evaluator.
        // But the Mesh receiving this geometry typically applies its own Local Transform (Position/Rotation/Scale).
        // If we don't inverse-transform the geometry back to Local Space, the Mesh transform will apply ON TOP of the World Space coords,
        // causing double-transformation (misalignment).

        const resultGeometry = resultBrush.geometry.clone();
        const inverseBaseMatrix = baseMesh.matrixWorld.clone().invert();
        resultGeometry.applyMatrix4(inverseBaseMatrix);

        // Do NOT recompute normals here if possible, rely on Evaluator? 
        // Actually Evaluator output usually needs normals. 
        // But if we use 'computeVertexNormals', it smooths everything.
        // three-bvh-csg usually preserves normals? 
        // If we simply return it, it should look flat/sharp where appropriate.
        // resultGeometry.computeVertexNormals();

        return resultGeometry;
    }
};

