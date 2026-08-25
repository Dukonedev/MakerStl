import * as THREE from 'three';

let mainCamera, mainControls, rafId;
let isAnimating = false;

/**
 * Initialise the View Navigator (Home button and camera utilities)
 * @param {HTMLElement} _ (Not used anymore, but kept for signature compatibility)
 * @param {THREE.Camera} _mainCamera 
 * @param {OrbitControls} _mainControls 
 * @param {Function} requestRender 
 */
export function initViewNavigator(_, _mainCamera, _mainControls, requestRender) {
  console.log('[ViewNavigator] Initialising Home Button logic...');
  
  mainCamera = _mainCamera;
  mainControls = _mainControls;

  // Home Button wiring
  const homeBtn = document.getElementById('nav-home-btn');
  if (homeBtn) {
    homeBtn.addEventListener('click', () => {
      // Default isometric view
      animateCameraTo([0.6, -1.2, 0.8], [0, 0, 1], requestRender);
    });
  }
}

/**
 * Empty stub to maintain compatibility with viewer.js
 */
export function updateViewNavigator(activeCam) {
  if (activeCam) mainCamera = activeCam;
}

/**
 * Smoothly animate the main camera to a new orientation
 */
export function animateCameraTo(targetPosDir, upDir, requestRender) {
  if (isAnimating) return;
  isAnimating = true;

  const startPos = mainCamera.position.clone();
  const startTarget = mainControls.target.clone();
  
  // Find orbit radius
  const radius = startPos.distanceTo(startTarget);
  
  // Calculate final position
  const dir = new THREE.Vector3(...targetPosDir).normalize();
  const endPos = startTarget.clone().addScaledVector(dir, radius);
  const endUp = new THREE.Vector3(...upDir);

  const duration = 500; // ms
  const startTime = performance.now();

  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic

    mainCamera.position.lerpVectors(startPos, endPos, ease);
    mainCamera.up.lerpVectors(mainCamera.up, endUp, ease);
    mainCamera.lookAt(startTarget);
    
    mainControls.update();
    requestRender();

    if (progress < 1) {
      rafId = requestAnimationFrame(step);
    } else {
      isAnimating = false;
    }
  }

  cancelAnimationFrame(rafId);
  rafId = requestAnimationFrame(step);
}
