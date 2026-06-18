import * as THREE from './vendor/three.module.js';
import { OrbitControls } from './vendor/OrbitControls.js';
import { STLLoader } from './vendor/STLLoader.js';

const C = {
  bg: 0x0c0d0e, copper: 0xc4873a, perimeter: 0xfbbf24, fill: 0xb45309, travel: 0x6a7180,
  accent: 0xf5a524, gridMinor: 0x202327, gridMajor: 0x33373d, axisX: 0xe5564b, axisY: 0x3dbe78,
};

export class Viewer {
  constructor(container) {
    this.container = container;
    this.originLabel = document.getElementById('originLabel');

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(C.bg);
    this.scene.fog = new THREE.Fog(C.bg, 400, 2000);

    this.camera = new THREE.PerspectiveCamera(45, this._aspect(), 0.1, 20000);
    this.camera.up.set(0, 0, 1);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = Math.PI * 0.49;

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x303030, 1.1));
    const key = new THREE.DirectionalLight(0xffffff, 0.85);
    key.position.set(1, -1, 2);
    const fill = new THREE.DirectionalLight(C.accent, 0.15);
    fill.position.set(-1, 1, -0.5);
    this.scene.add(key, fill);

    this.loader = new STLLoader();
    this.solidGroup = new THREE.Group();
    this.bedGroup = new THREE.Group();
    this.pathGroup = new THREE.Group();
    this.scene.add(this.solidGroup, this.bedGroup, this.pathGroup);

    this.travelObj = null;
    this.originWorld = null;
    this.mode = 'solid';
    this._solidBounds = null;
    this._pathBounds = null;

    window.addEventListener('resize', () => this._onResize());
    this._animate();
  }

  showSolid(arrayBuffer) {
    const geometry = this.loader.parse(arrayBuffer);
    geometry.computeVertexNormals();
    geometry.computeBoundingBox();
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    geometry.boundingBox.getSize(size);
    geometry.boundingBox.getCenter(center);

    this._clear(this.solidGroup);
    const material = new THREE.MeshStandardMaterial({
      color: C.copper, metalness: 0.3, roughness: 0.6, emissive: 0x140a02,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.sub(center);
    this.solidGroup.add(mesh);

    const half = size.clone().multiplyScalar(0.5);
    this._solidBounds = { min: half.clone().negate(), max: half };
    return { x: size.x, y: size.y, z: size.z };
  }

  showToolpaths(data) {
    this._clear(this.pathGroup);
    this._clear(this.bedGroup);
    const zDraw = 0.05;
    const zTravel = 0.6;

    const kinds = data.kinds || [];
    const perimeter = [];
    const fill = [];
    data.strokes.forEach((stroke, index) => {
      const target = kinds[index] === 'fill' ? fill : perimeter;
      for (let i = 0; i < stroke.length - 1; i++) {
        target.push(stroke[i][0], stroke[i][1], zDraw, stroke[i + 1][0], stroke[i + 1][1], zDraw);
      }
    });
    this.pathGroup.add(this._lines(fill, new THREE.LineBasicMaterial({ color: C.fill, transparent: true, opacity: 0.75 })));
    this.pathGroup.add(this._lines(perimeter, new THREE.LineBasicMaterial({ color: C.perimeter })));

    const travel = [];
    for (let i = 0; i < data.strokes.length - 1; i++) {
      const a = data.strokes[i][data.strokes[i].length - 1];
      const b = data.strokes[i + 1][0];
      travel.push(a[0], a[1], zTravel, b[0], b[1], zTravel);
    }
    this.travelObj = this._lines(
      travel,
      new THREE.LineDashedMaterial({ color: C.travel, dashSize: 1.2, gapSize: 0.8, transparent: true, opacity: 0.55 }),
    );
    this.travelObj.computeLineDistances();
    this.pathGroup.add(this.travelObj);

    this._buildBed(data.bounds);
    this._buildOrigin(data.origin);
    this.originWorld = new THREE.Vector3(data.origin[0], data.origin[1], 0);
    if (this.originLabel) this.originLabel.textContent = `⊕ X${data.origin[0]} Y${data.origin[1]}`;

    const [minx, miny, maxx, maxy] = data.bounds;
    this._pathBounds = { min: new THREE.Vector3(minx, miny, 0), max: new THREE.Vector3(maxx, maxy, 2) };
  }

  setMode(mode) {
    this.mode = mode;
    this.solidGroup.visible = mode === 'solid';
    this.bedGroup.visible = mode === 'toolpaths';
    this.pathGroup.visible = mode === 'toolpaths';
    if (this.originLabel) this.originLabel.classList.toggle('hidden', mode !== 'toolpaths' || !this.originWorld);
  }

  setTravelVisible(visible) {
    if (this.travelObj) this.travelObj.visible = visible;
  }

  fit() {
    this._frame();
  }

  _buildBed(bounds) {
    let [minx, miny, maxx, maxy] = bounds;
    minx = Math.floor((minx - 20) / 10) * 10;
    miny = Math.floor((miny - 20) / 10) * 10;
    maxx = Math.ceil((maxx + 20) / 10) * 10;
    maxy = Math.ceil((maxy + 20) / 10) * 10;

    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(maxx - minx, maxy - miny),
      new THREE.MeshStandardMaterial({ color: 0x101216, roughness: 0.95 }),
    );
    plane.position.set((minx + maxx) / 2, (miny + maxy) / 2, -0.05);
    this.bedGroup.add(plane);

    this.bedGroup.add(this._grid(minx, miny, maxx, maxy, 2, C.gridMinor, 0.5));
    this.bedGroup.add(this._grid(minx, miny, maxx, maxy, 10, C.gridMajor, 0.9));
    this.bedGroup.add(this._lines(
      [minx, miny, 0, maxx, miny, 0, maxx, miny, 0, maxx, maxy, 0,
        maxx, maxy, 0, minx, maxy, 0, minx, maxy, 0, minx, miny, 0],
      new THREE.LineBasicMaterial({ color: C.accent, transparent: true, opacity: 0.35 }),
    ));
  }

  _grid(minx, miny, maxx, maxy, step, color, opacity) {
    const pts = [];
    for (let x = minx; x <= maxx + 1e-6; x += step) pts.push(x, miny, 0, x, maxy, 0);
    for (let y = miny; y <= maxy + 1e-6; y += step) pts.push(minx, y, 0, maxx, y, 0);
    return this._lines(pts, new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
  }

  _buildOrigin([ox, oy]) {
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(1.2, 1.6, 40),
      new THREE.MeshBasicMaterial({ color: C.accent, side: THREE.DoubleSide }),
    );
    ring.position.set(ox, oy, 0.02);
    this.bedGroup.add(ring);
    this.bedGroup.add(this._lines([ox, oy, 0.02, ox + 12, oy, 0.02], new THREE.LineBasicMaterial({ color: C.axisX })));
    this.bedGroup.add(this._lines([ox, oy, 0.02, ox, oy + 12, 0.02], new THREE.LineBasicMaterial({ color: C.axisY })));
  }

  _lines(flat, material) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3));
    return new THREE.LineSegments(geometry, material);
  }

  _frame() {
    const bounds = this.mode === 'toolpaths' ? this._pathBounds : this._solidBounds;
    if (!bounds) return;
    const size = new THREE.Vector3().subVectors(bounds.max, bounds.min);
    const center = new THREE.Vector3().addVectors(bounds.min, bounds.max).multiplyScalar(0.5);
    const span = Math.max(size.x, size.y, size.z) || 1;
    const dist = (span / (2 * Math.tan((Math.PI / 180) * this.camera.fov / 2))) * 1.6;
    const view = this.mode === 'toolpaths' ? [0.2, -0.55, 0.9] : [0.35, -0.75, 0.65];
    this.camera.position.set(center.x + dist * view[0], center.y + dist * view[1], center.z + dist * view[2]);
    this.camera.near = span / 100;
    this.camera.far = span * 100;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(center);
    this.controls.update();
    this.scene.fog.near = dist;
    this.scene.fog.far = dist * 5;
  }

  _updateOriginLabel() {
    if (this.mode !== 'toolpaths' || !this.originWorld || !this.originLabel) return;
    const projected = this.originWorld.clone().project(this.camera);
    if (projected.z > 1) return;
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.originLabel.style.left = `${(projected.x * 0.5 + 0.5) * w}px`;
    this.originLabel.style.top = `${(-projected.y * 0.5 + 0.5) * h}px`;
  }

  _clear(group) {
    while (group.children.length) {
      const child = group.children.pop();
      if (child.geometry) child.geometry.dispose();
      if (child.material) child.material.dispose();
      group.remove(child);
    }
  }

  _aspect() {
    return this.container.clientWidth / Math.max(1, this.container.clientHeight);
  }

  _onResize() {
    this.camera.aspect = this._aspect();
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
  }

  _animate() {
    requestAnimationFrame(() => this._animate());
    this.controls.update();
    this._updateOriginLabel();
    this.renderer.render(this.scene, this.camera);
  }
}
