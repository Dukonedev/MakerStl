
export interface KeychainConfig {
  text: string;
  fontSize: number;
  thickness: number;
  textDepth: number;
  color: string;
  textColor: string;
  fontUrl: string;
  baseShape: 'outline' | 'capsule' | 'template';
  templateName?: string;
  templateContent?: string;
  fontScaleX: number;
  letterSpacing: number;
  baseWidth: number;
  outlineSize: number;
  roundness: number;
  ringOverlap: number;
  ringOffsetY: number;
  textOffsetY: number;
  edgeRoundness: number;
  addBorder: boolean;
  addSecondOutline: boolean;
  secondOutlineSize: number;
  secondOutlineDepth: number;
  secondOutlineEdgeRoundness: number;
  baseRoundness: number;
  // Custom SVG / Ultra Mode
  textOffsetX: number;
  textOffsetZ?: number;
  svgMaxDimension: number; // Max dimension in mm (50-120)
  showRing: boolean;
  ringPosition: number; // 0-1 along perimeter
  baseLayerColor?: string; // Hex color of the chosen base layer
  layerConfig?: Record<string, { depth: number; offset: number }>; // Per-color customized settings
}

export interface GeneratedIdea {
  text: string;
  category: string;
}