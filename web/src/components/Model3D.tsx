import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

// A landmark's real 3D building (CityGML LOD2, Luxembourg 3D buildings 2023, CC0), drawn in the map's ink palette.
// model.bin: float32 triangles (x, y, z metres, z up) then one uint8 kind per triangle (1 roof, 2 wall).
export function Model3D({ url }: { url: string }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = host.current!;
    let stop = false;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(35, 1, 0.5, 5000);
    const controls = new OrbitControls(cam, renderer.domElement);
    controls.enableDamping = true;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.8;
    scene.add(new THREE.HemisphereLight(0xfff4e0, 0x5a6478, 1.4));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(-1, 1.2, 1.5);
    scene.add(sun);
    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      renderer.setSize(w, h);
      cam.aspect = w / h;
      cam.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    fetch(url).then((r) => r.arrayBuffer()).then((buf) => {
      if (stop) return;
      const nTri = Math.floor(buf.byteLength / (9 * 4 + 1));
      const pos = new Float32Array(buf, 0, nTri * 9);
      const kinds = new Uint8Array(buf, nTri * 36, nTri);
      // CityGML axes: x east, y north, z up -> three.js: x east, y up, z south
      const p = new Float32Array(nTri * 9);
      const col = new Float32Array(nTri * 9);
      const wall = new THREE.Color("#d8c39a"), roof = new THREE.Color("#4f5d7c");
      for (let i = 0; i < nTri * 3; i++) {
        p[i * 3] = pos[i * 3]; p[i * 3 + 1] = pos[i * 3 + 2]; p[i * 3 + 2] = -pos[i * 3 + 1];
        const c = kinds[Math.floor(i / 3)] === 1 ? roof : wall;
        col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(p, 3));
      geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
      geo.computeVertexNormals();
      const mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, flatShading: true }));
      scene.add(mesh);
      // ink outlines on sharp edges
      scene.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 30), new THREE.LineBasicMaterial({ color: 0x2a2630 })));
      geo.computeBoundingSphere();
      const r = geo.boundingSphere!.radius;
      const c = geo.boundingSphere!.center;
      controls.target.copy(c);
      cam.position.set(c.x + r * 1.6, c.y + r * 1.1, c.z + r * 1.6);
      controls.update();
    });
    const loop = () => {
      if (stop) return;
      controls.update();
      renderer.render(scene, cam);
      requestAnimationFrame(loop);
    };
    loop();
    return () => {
      stop = true;
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, [url]);
  return <div ref={host} className="model3d" aria-label="3D model of the building; drag to turn it" />;
}
