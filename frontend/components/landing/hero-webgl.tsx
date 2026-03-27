"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const maxGrid = 20;
const cubeSize = 0.85;
const gap = 1.0;
const maxCubes = maxGrid * maxGrid * maxGrid;

/** Hero framing: orbit target offsets shift the cluster in the viewport (camera at ~diagonal +X,+Z). */
const HERO_ORBIT_TARGET_X = 1.9;
/** Lower = cluster projects higher in the 2D card (less top margin, more below before caption). */
const HERO_ORBIT_TARGET_Y = 2.12;
/** Per-instance bulge scale (noise amplitude on each small cube). */
const HERO_VOXEL_SCALE = 0.78;
/**
 * Scales lattice positions toward the origin: <1 shrinks the whole “cube of cubes” footprint
 * in world space without changing individual voxel behavior.
 */
const HERO_CLUSTER_SPREAD = 0.87;
/** Camera distance for hero framing. Higher = camera farther = slightly smaller cluster on screen. */
const HERO_CAMERA_DISTANCE_SCALE = 0.67;

/** Default look from the former Parameters panel (Perlin, no UI). */
const params = {
  speed: 1.01,
  freq: 0.25,
  exag: 1.3,
  scaleMax: 2.45,
  brightColor: new THREE.Color(1, 1, 1),
  darkColor: new THREE.Color(0, 0, 0),
  colorMix: 3.0,
  contrast: 2.78,
  scaleX: 1.0,
  scaleY: 1.0,
  scaleZ: 1.0,
  gridX: 20,
  gridY: 20,
  gridZ: 20,
};

function mod289(x: number) {
  return x - Math.floor(x / 289.0) * 289.0;
}
function permute(x: number) {
  return mod289((x * 34.0 + 1.0) * x);
}

function noise3D(x: number, y: number, z: number) {
  const X = Math.floor(x) & 255;
  const Y = Math.floor(y) & 255;
  const Z = Math.floor(z) & 255;
  const fx = x - Math.floor(x);
  const fy = y - Math.floor(y);
  const fz = z - Math.floor(z);
  const u = fx * fx * (3 - 2 * fx);
  const v = fy * fy * (3 - 2 * fy);
  const w = fz * fz * (3 - 2 * fz);

  const A = permute(X) + Y;
  const AA = permute(A) + Z;
  const AB = permute(A + 1) + Z;
  const B = permute(X + 1) + Y;
  const BA = permute(B) + Z;
  const BB = permute(B + 1) + Z;

  function grad(hash: number, gx: number, gy: number, gz: number) {
    const h = hash & 15;
    const gu = h < 8 ? gx : gy;
    const gv = h < 4 ? gy : h === 12 || h === 14 ? gx : gz;
    return ((h & 1) === 0 ? gu : -gu) + ((h & 2) === 0 ? gv : -gv);
  }

  const p0 = grad(permute(AA), fx, fy, fz);
  const p1 = grad(permute(BA), fx - 1, fy, fz);
  const p2 = grad(permute(AB), fx, fy - 1, fz);
  const p3 = grad(permute(BB), fx - 1, fy - 1, fz);
  const p4 = grad(permute(AA + 1), fx, fy, fz - 1);
  const p5 = grad(permute(BA + 1), fx - 1, fy, fz - 1);
  const p6 = grad(permute(AB + 1), fx, fy - 1, fz - 1);
  const p7 = grad(permute(BB + 1), fx - 1, fy - 1, fz - 1);

  const x0 = p0 + u * (p1 - p0);
  const x1 = p2 + u * (p3 - p2);
  const x2 = p4 + u * (p5 - p4);
  const x3 = p6 + u * (p7 - p6);
  const y0 = x0 + v * (x1 - x0);
  const y1 = x2 + v * (x3 - x2);
  return y0 + w * (y1 - y0);
}

export function HeroWebGL() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const mount = document.createElement("div");
    mount.className = "absolute inset-0";
    mount.style.touchAction = "none";
    root.appendChild(mount);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 500);
    const d = HERO_CAMERA_DISTANCE_SCALE;
    camera.position.set(34 * d, 28 * d, 34 * d);
    camera.lookAt(HERO_ORBIT_TARGET_X, HERO_ORBIT_TARGET_Y, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 1);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    const canvas = renderer.domElement;
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.display = "block";
    canvas.style.cursor = "grab";
    mount.appendChild(canvas);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(40 * d, 60 * d, 30 * d);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 2048;
    dirLight.shadow.mapSize.height = 2048;
    dirLight.shadow.camera.near = 0.5;
    dirLight.shadow.camera.far = 120;
    /* Tight ortho frustum around the ~20³ grid so shadows don’t span a huge virtual floor */
    const sh = 16;
    dirLight.shadow.camera.left = -sh;
    dirLight.shadow.camera.right = sh;
    dirLight.shadow.camera.top = sh;
    dirLight.shadow.camera.bottom = -sh;
    dirLight.shadow.bias = -0.001;
    dirLight.shadow.normalBias = 0.02;
    dirLight.shadow.camera.updateProjectionMatrix();
    scene.add(dirLight);

    const hemLight = new THREE.HemisphereLight(0xaaccff, 0x446644, 0.4);
    scene.add(hemLight);

    const geometry = new THREE.BoxGeometry(cubeSize, cubeSize, cubeSize);
    const material = new THREE.MeshStandardMaterial({
      metalness: 0.15,
      roughness: 0.6,
    });

    const instancedMesh = new THREE.InstancedMesh(geometry, material, maxCubes);
    instancedMesh.castShadow = true;
    instancedMesh.receiveShadow = true;

    const instColor = new THREE.Color();
    const zeroMatrix = new THREE.Matrix4().makeScale(0, 0, 0);
    for (let i = 0; i < maxCubes; i++) {
      instancedMesh.setMatrixAt(i, zeroMatrix);
      instancedMesh.setColorAt(i, instColor.setRGB(0, 0, 0));
    }
    instancedMesh.instanceMatrix.needsUpdate = true;
    instancedMesh.instanceColor!.needsUpdate = true;
    scene.add(instancedMesh);

    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enableZoom = false;
    controls.minDistance = 10 * d;
    controls.maxDistance = 100 * d;
    controls.target.set(HERO_ORBIT_TARGET_X, HERO_ORBIT_TARGET_Y, 0);
    controls.addEventListener("start", () => {
      canvas.style.cursor = "grabbing";
    });
    controls.addEventListener("end", () => {
      canvas.style.cursor = "grab";
    });

    const clock = new THREE.Clock();
    const tempMatrix = new THREE.Matrix4();
    const tempPos = new THREE.Vector3();
    const tempQuat = new THREE.Quaternion();
    const tempScale = new THREE.Vector3();
    const noiseColor = new THREE.Color();

    function updateSize() {
      const w = mount.clientWidth;
      const h = Math.max(mount.clientHeight, 1);
      if (w === 0) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }

    const ro = new ResizeObserver(() => updateSize());
    ro.observe(mount);
    updateSize();

    let raf = 0;
    function animate() {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      const noiseSpeed = params.speed;
      const noiseFreq = params.freq;

      const gx = Math.round(params.gridX);
      const gy = Math.round(params.gridY);
      const gz = Math.round(params.gridZ);
      const activeCount = gx * gy * gz;
      const offsetX = (gx - 1) * gap * 0.5;
      const offsetY = (gy - 1) * gap * 0.5;
      const offsetZ = (gz - 1) * gap * 0.5;

      let idx = 0;
      for (let x = 0; x < gx; x++) {
        for (let y = 0; y < gy; y++) {
          for (let z = 0; z < gz; z++) {
            const baseX = x * gap - offsetX;
            const baseY = y * gap - offsetY;
            const baseZ = z * gap - offsetZ;

            const normX = gx > 1 ? (x / (gx - 1)) * 19 : 9.5;
            const normY = gy > 1 ? (y / (gy - 1)) * 19 : 9.5;
            const normZ = gz > 1 ? (z / (gz - 1)) * 19 : 9.5;

            const nx = normX * noiseFreq + t * noiseSpeed;
            const ny = normY * noiseFreq + t * noiseSpeed * 0.7;
            const nz = normZ * noiseFreq + t * noiseSpeed * 0.5;

            const n = noise3D(nx, ny, nz);

            const nNorm = Math.pow(
              Math.max(0, Math.min(1, n * 0.5 + 0.5)),
              params.exag,
            );
            const s =
              (0.02 + nNorm * nNorm * params.scaleMax) * HERO_VOXEL_SCALE;

            tempPos.set(
              baseX * HERO_CLUSTER_SPREAD,
              baseY * HERO_CLUSTER_SPREAD,
              baseZ * HERO_CLUSTER_SPREAD,
            );
            tempScale.set(
              s * params.scaleX,
              s * params.scaleY,
              s * params.scaleZ,
            );
            tempMatrix.compose(tempPos, tempQuat.identity(), tempScale);
            instancedMesh.setMatrixAt(idx, tempMatrix);

            const contrasted = Math.pow(nNorm, params.contrast);
            noiseColor
              .copy(params.darkColor)
              .lerp(params.brightColor, contrasted);
            noiseColor.multiplyScalar(params.colorMix);
            instancedMesh.setColorAt(idx, noiseColor);

            idx++;
          }
        }
      }
      for (let i = activeCount; i < maxCubes; i++) {
        instancedMesh.setMatrixAt(i, zeroMatrix);
      }

      instancedMesh.instanceMatrix.needsUpdate = true;
      instancedMesh.instanceColor!.needsUpdate = true;
      instancedMesh.count = activeCount;

      controls.update();
      renderer.render(scene, camera);
    }

    animate();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      if (canvas.parentNode === mount) {
        mount.removeChild(canvas);
      }
      if (mount.parentNode === root) {
        root.removeChild(mount);
      }
      scene.clear();
    };
  }, []);

  return (
    <div
      ref={rootRef}
      className="hero-webgl-mask pointer-events-auto relative z-10 h-full w-full min-h-0"
    />
  );
}
