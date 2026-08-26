import * as THREE from 'three';
import { OBJExporter } from 'three/addons/exporters/OBJExporter.js';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';
import JSZip from 'jszip';

// ------------------------------------------------------------------
// Abstract Strategy Interface
// ------------------------------------------------------------------
export interface IExportStrategy {
    export(object: THREE.Object3D, filename: string): Promise<void>;
}

// ------------------------------------------------------------------
// Mesh Optimizer (OOP Helper)
// ------------------------------------------------------------------
class MeshOptimizer {
    static optimizeForExport(object: THREE.Object3D): THREE.Object3D {
        // Clone to avoid modifying the live scene
        const clone = object.clone(true);

        clone.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
                const mesh = child as THREE.Mesh;
                if (mesh.geometry) {
                    // Ensure normals are computed for maximum compatibility
                    mesh.geometry.computeVertexNormals();
                }
            }
        });

        return clone;
    }
}

// ------------------------------------------------------------------
// Concrete Strategy: OBJ (With Color/MTL support)
// ------------------------------------------------------------------
export class OBJExportStrategy implements IExportStrategy {
    async export(object: THREE.Object3D, filename: string): Promise<void> {
        console.log("[OBJExportStrategy] optimizing mesh...");
        const optimizedObject = MeshOptimizer.optimizeForExport(object);

        console.log("[OBJExportStrategy] parsing OBJ...");
        const exporter = new OBJExporter();
        let objContent = exporter.parse(optimizedObject);

        // Generate MTL (Material Library)
        const mtlContent = this.generateMTL(optimizedObject);

        // Link MTL in OBJ
        const mtlFilename = `${filename}.mtl`;
        objContent = `mtllib ${mtlFilename}\n` + objContent;

        // Use JSZip to bundle OBJ + MTL
        const zip = new JSZip();
        zip.file(`${filename}.obj`, objContent);
        zip.file(mtlFilename, mtlContent);

        console.log("[OBJExportStrategy] generating ZIP...");
        const content = await zip.generateAsync({ type: 'blob' });

        this.download(content, `${filename}_obj_color.zip`, 'application/zip');
    }

    private generateMTL(object: THREE.Object3D): string {
        let mtlOutput = "# Created by Ultra Studio\n";
        const materials = new Map<string, THREE.MeshStandardMaterial>();

        object.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
                const mesh = child as THREE.Mesh;
                if (mesh.material) {
                    const mat = mesh.material as THREE.MeshStandardMaterial;
                    // Use uuid to ensure uniqueness and validity
                    const matName = mat.name || `Material_${mat.uuid}`;
                    materials.set(matName, mat);

                    // Assign name to mesh userData/material so exporter sees it
                    mat.name = matName;
                }
            }
        });

        materials.forEach((mat, name) => {
            mtlOutput += `\nnewmtl ${name}\n`;
            mtlOutput += `Ns 250.000000\n`;
            mtlOutput += `Ka 1.000000 1.000000 1.000000\n`; // Ambient

            const color = mat.color;
            mtlOutput += `Kd ${color.r.toFixed(6)} ${color.g.toFixed(6)} ${color.b.toFixed(6)}\n`; // Diffuse

            mtlOutput += `Ks 0.500000 0.500000 0.500000\n`; // Specular
            mtlOutput += `Ke 0.000000 0.000000 0.000000\n`; // Emissive
            mtlOutput += `Ni 1.450000\n`;
            mtlOutput += `d ${mat.opacity}\n`; // Opacity
            mtlOutput += `illum 2\n`;
        });

        return mtlOutput;
    }

    private download(content: Blob, filename: string, mimeType: string) {
        const link = document.createElement('a');
        link.href = URL.createObjectURL(content);
        link.download = filename;
        link.click();
    }
}

// ------------------------------------------------------------------
// Concrete Strategy: STL
// ------------------------------------------------------------------
export class STLExportStrategy implements IExportStrategy {
    async export(object: THREE.Object3D, filename: string): Promise<void> {
        console.log("[STLExportStrategy] optimizing mesh...");
        const optimizedObject = MeshOptimizer.optimizeForExport(object);

        const exporter = new STLExporter();
        const result = exporter.parse(optimizedObject, { binary: true });

        this.download(result, `${filename}.stl`, 'application/octet-stream');
    }

    private download(content: DataView | string, filename: string, mimeType: string) {
        const blob = new Blob([content], { type: mimeType });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
    }
}

// ------------------------------------------------------------------
// Concrete Strategy: 3MF
// ------------------------------------------------------------------
export class ThreeMFExportStrategy implements IExportStrategy {
    async export(object: THREE.Object3D, filename: string): Promise<void> {
        const zip = new JSZip();
        const rels = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />
</Relationships>`;
        zip.folder("_rels")?.file(".rels", rels);

        let modelXML = `<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel">
 <resources>
`;
        let buildXML = ` <build>\n`;
        let objectId = 1;

        object.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
                const mesh = child as THREE.Mesh;
                const geo = mesh.geometry;
                if (!geo) return;

                const positions = geo.getAttribute('position');
                modelXML += `  <object id="${objectId}" type="model">\n   <mesh>\n    <vertices>\n`;
                for (let i = 0; i < positions.count; i++) {
                    modelXML += `     <vertex x="${positions.getX(i)}" y="${positions.getY(i)}" z="${positions.getZ(i)}" />\n`;
                }
                modelXML += `    </vertices>\n    <triangles>\n`;

                if (geo.index) {
                    for (let i = 0; i < geo.index.count; i += 3) {
                        modelXML += `     <triangle v1="${geo.index.getX(i)}" v2="${geo.index.getX(i + 1)}" v3="${geo.index.getX(i + 2)}" />\n`;
                    }
                } else {
                    for (let i = 0; i < positions.count; i += 3) {
                        modelXML += `     <triangle v1="${i}" v2="${i + 1}" v3="${i + 2}" />\n`;
                    }
                }

                modelXML += `    </triangles>\n   </mesh>\n  </object>\n`;
                buildXML += `  <item objectid="${objectId}" />\n`;
                objectId++;
            }
        });

        modelXML += ` </resources>\n`;
        modelXML += buildXML;
        modelXML += ` </build>\n</model>`;

        zip.folder("3D")?.file("3dmodel.model", modelXML);

        const content = await zip.generateAsync({ type: 'blob' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(content);
        link.download = `${filename}.3mf`;
        link.click();
    }
}


// ------------------------------------------------------------------
// Factory / Context
// ------------------------------------------------------------------
export class ExportManager {
    static async exportScene(sceneGroup: THREE.Object3D, format: 'obj' | 'stl' | '3mf', filename: string) {
        let strategy: IExportStrategy;

        switch (format) {
            case 'obj':
                strategy = new OBJExportStrategy();
                break;
            case 'stl':
                strategy = new STLExportStrategy();
                break;
            case '3mf':
                strategy = new ThreeMFExportStrategy();
                break;
            default:
                throw new Error(`Unsupported export format: ${format}`);
        }

        await strategy.export(sceneGroup, filename);
    }
}
