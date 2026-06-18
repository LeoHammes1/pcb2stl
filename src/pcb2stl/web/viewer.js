import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { STLLoader } from './vendor/STLLoader.js';

export class Viewer {
  constructor(container) {
    this.container = container;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0f1115);

    this.camera = new THREE.PerspectiveCamera(45, this._aspect(), 0.1, 10000);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x303030, 1.2));
    const key = new THREE.DirectionalLight(0xffffff, 1.0);
    key.position.set(1, -1, 2);
    this.scene.add(key);

    this.loader = new STLLoader();
    this.mesh = null;

    window.addEventListener('resize', () => this._onResize());
    this._animate();
  }

  showSTL(arrayBuffer) {
    const geometry = this.loader.parse(arrayBuffer);
    geometry.computeVertexNormals();
    geometry.computeBoundingBox();
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    geometry.boundingBox.getSize(size);
    geometry.boundingBox.getCenter(center);

    this._dispose();
    const material = new THREE.MeshStandardMaterial({ color: 0xc4873a, metalness: 0.25, roughness: 0.6 });
    this.mesh = new THREE.Mesh(geometry, material);
    this.mesh.position.sub(center);
    this.scene.add(this.mesh);
    this._frame(size);
    return { x: size.x, y: size.y, z: size.z };
  }

  _frame(size) {
    const span = Math.max(size.x, size.y, size.z) || 1;
    const dist = (span / (2 * Math.tan((Math.PI / 180) * this.camera.fov / 2))) * 1.7;
    this.camera.position.set(dist * 0.35, -dist * 0.75, dist * 0.65);
    this.camera.near = span / 100;
    this.camera.far = span * 100;
    this.camera.updateProjectionMatrix();
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  _dispose() {
    if (!this.mesh) return;
    this.scene.remove(this.mesh);
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
    this.mesh = null;
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
    this.renderer.render(this.scene, this.camera);
  }
}
