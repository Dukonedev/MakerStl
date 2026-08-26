
// Monotone Chain Convex Hull Algorithm
const getConvexHull = (points: THREE.Vector2[]) => {
    points.sort((a, b) => a.x === b.x ? a.y - b.y : a.x - b.x);

    const cross = (o: THREE.Vector2, a: THREE.Vector2, b: THREE.Vector2) => {
        return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
    };

    const lower: THREE.Vector2[] = [];
    for (let i = 0; i < points.length; i++) {
        while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], points[i]) <= 0) {
            lower.pop();
        }
        lower.push(points[i]);
    }

    const upper: THREE.Vector2[] = [];
    for (let i = points.length - 1; i >= 0; i--) {
        while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], points[i]) <= 0) {
            upper.pop();
        }
        upper.push(points[i]);
    }

    upper.pop();
    lower.pop();
    return lower.concat(upper);
};
