export interface GadgetSpec {
    id: string;
    name: string;
    description: string;
    svgUrl: string;
    widthMm: number;
    heightMm: number;
    baseExtrusionMm: number;
    engravingDepthMm?: number;
    defaultColor: string;
}

export const GADGETS: GadgetSpec[] = [
    {
        id: 'phone-stand',
        name: 'Phone Stand',
        description: 'Simple phone stand with logo area',
        svgUrl: '/assets/gadgets/phone-stand.svg', // Placeholder
        widthMm: 80,
        heightMm: 120,
        baseExtrusionMm: 5,
        defaultColor: '#ffffff'
    },
    {
        id: 'coaster-round',
        name: 'Round Coaster',
        description: 'Standard 90mm drink coaster',
        svgUrl: '/assets/gadgets/coaster-round.svg', // Placeholder
        widthMm: 90,
        heightMm: 90,
        baseExtrusionMm: 3,
        defaultColor: '#1a1a1a'
    },
    {
        id: 'key-tag-large',
        name: 'Large Key Tag',
        description: 'Hotel style key tag',
        svgUrl: '/assets/gadgets/key-tag.svg', // Placeholder
        widthMm: 45,
        heightMm: 90,
        baseExtrusionMm: 4,
        defaultColor: '#ff0000'
    }
];
