"""Funciones comunes para generar los modelos 3D de las esculturas (trimesh + numpy + Pillow).

Convenciones (las mismas del gliptodonte): metros, Y hacia arriba, el animal mira hacia +Z.
Los nodos de grupo (cuerpo, cabeza, patas...) tienen el pivote donde rota esa parte y los
nodos geométricos llevan el prefijo "m_" para que no choquen con los nombres de los grupos.

Primera parte: utilidades del gliptodonte, sin cambios.
Segunda parte: formas orgánicas (lofts), atlas de texturas horneadas, poses y verificación,
usadas por los dinosaurios.
"""
import io
import json
import struct

import numpy as np
import trimesh
from PIL import Image
from trimesh.visual.material import PBRMaterial

# ================================================================ utilidades de textura
def periodic_noise(h, w, scale, seed):
    """Ruido suave periódico (se repite sin costuras) filtrando ruido blanco en frecuencia."""
    r = np.random.default_rng(seed).standard_normal((h, w)).astype(np.float32)
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.fftfreq(w)[None, :]
    f = np.sqrt(fx ** 2 + fy ** 2)
    filt = np.exp(-(f * scale) ** 2)
    n = np.real(np.fft.ifft2(np.fft.fft2(r) * filt))
    n -= n.min(); n /= n.max() + 1e-9
    return n

def normal_from_height(hm, strength):
    gx = (np.roll(hm, -1, 1) - np.roll(hm, 1, 1)) * 0.5
    gy = (np.roll(hm, -1, 0) - np.roll(hm, 1, 0)) * 0.5
    nx, ny, nz = -gx * strength, gy * strength, np.ones_like(hm)
    l = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    n = np.stack([nx / l, ny / l, nz / l], -1)
    return Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8))

def to_img(rgb):
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))

def mr_img(rough, metal=0.0):
    z = np.zeros_like(rough)
    return Image.fromarray((np.stack([z, rough, z + metal], -1) * 255).astype(np.uint8))

def mat_flat(rgb, rough, name):
    return PBRMaterial(name=name, baseColorFactor=[*rgb, 1], metallicFactor=0.0, roughnessFactor=rough)

# ================================================================ superficies paramétricas
def surface(fn, nu, nv, wrap_v=False, uv_scale=(1, 1)):
    """fn(u, v) -> (N,3). u,v en [0,1]. Devuelve mesh con UV."""
    u = np.linspace(0, 1, nu); v = np.linspace(0, 1, nv)
    U, V = np.meshgrid(u, v, indexing="ij")
    P = fn(U.ravel(), V.ravel()).reshape(nu, nv, 3)
    verts = P.reshape(-1, 3)
    idx = np.arange(nu * nv).reshape(nu, nv)
    a = idx[:-1, :-1].ravel(); b = idx[1:, :-1].ravel()
    c = idx[1:, 1:].ravel(); d = idx[:-1, 1:].ravel()
    faces = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    uv = np.stack([U.ravel() * uv_scale[0], V.ravel() * uv_scale[1]], 1)
    m = trimesh.Trimesh(verts, faces, process=False)
    return m, uv

def box_uv(m, tile):
    n = m.vertex_normals; v = m.vertices
    ax = np.argmax(np.abs(n), 1)
    uv = np.where((ax == 0)[:, None], v[:, [2, 1]], np.where((ax == 1)[:, None], v[:, [0, 2]], v[:, [0, 1]]))
    return uv / tile

def textured(m, uv, material):
    m.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
    return m

def arc_scale(fn, along="u", n=200):
    """largo aproximado de la curva media en u y v (para escalar UV)."""
    t = np.linspace(0, 1, n)
    pu = fn(t, np.full(n, 0.5)); pv = fn(np.full(n, 0.5), t)
    lu = np.linalg.norm(np.diff(pu, axis=0), axis=1).sum()
    lv = np.linalg.norm(np.diff(pv, axis=0), axis=1).sum()
    return lu, lv

def tube(p0, p1, r0, r1, n_len=12, n_rad=20, bulge=0.0):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    axis = p1 - p0; L = np.linalg.norm(axis); ax = axis / L
    tmp = np.array([1, 0, 0]) if abs(ax[0]) < 0.9 else np.array([0, 1, 0])
    e1 = np.cross(ax, tmp); e1 /= np.linalg.norm(e1); e2 = np.cross(ax, e1)
    def fn(U, V):
        r = r0 + (r1 - r0) * U + bulge * np.sin(np.pi * U)
        a = 2 * np.pi * V
        return p0 + np.outer(U * L, ax) + np.outer(r * np.cos(a), e1) + np.outer(r * np.sin(a), e2)
    return surface(fn, n_len, n_rad, uv_scale=(1.5, 2))

# ================================================================ escena con pivotes y animaciones
Tm = trimesh.transformations.translation_matrix

def quat(axis, ang):
    axis = np.asarray(axis, float); axis /= np.linalg.norm(axis)
    s = np.sin(ang / 2)
    return np.array([axis[0] * s, axis[1] * s, axis[2] * s, np.cos(ang / 2)])  # x, y, z, w

def qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return np.array([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
                     w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2])

def quat_matrix(q):
    """Cuaternión (x, y, z, w) -> matriz 4x4."""
    return trimesh.transformations.quaternion_matrix([q[3], q[0], q[1], q[2]])

def build_scene(parts, groups, parent, pivots, group_of, root_matrix, rest_rot=None, rest_tras=None):
    """Arma la escena: 'raiz' (con root_matrix) y un nodo por grupo con su pivote.
    Cada pieza se cuelga de su grupo como nodo "m_<nombre>" con los vértices relativos al pivote.
    rest_rot / rest_tras: rotación (cuaternión) y traslación de reposo de cada grupo, si las hay."""
    scene = trimesh.Scene()
    scene.graph.update(frame_from=scene.graph.base_frame, frame_to="raiz", matrix=root_matrix)
    local_t = {}
    for g in groups:
        local_t[g] = pivots[g] - pivots[parent[g]]
        M = Tm(local_t[g] if rest_tras is None or g not in rest_tras else rest_tras[g])
        if rest_rot is not None and g in rest_rot:
            M = M @ quat_matrix(rest_rot[g])
        scene.graph.update(frame_from=parent[g], frame_to=g, matrix=M)
    for name, m in parts:
        g = group_of(name)
        m.apply_translation(-pivots[g])
        vn = np.array(m.vertex_normals); bad = np.linalg.norm(vn, axis=1) < 0.5
        if bad.any():
            vn[bad] = [0, 1, 0]; m.vertex_normals = vn
        scene.add_geometry(m, node_name="m_" + name, geom_name=name, parent_node_name=g)
    return scene, local_t

def _split_glb(glb_bytes):
    jl = struct.unpack("<I", glb_bytes[12:16])[0]
    J = json.loads(glb_bytes[20:20 + jl])
    off = 20 + jl
    bl = struct.unpack("<I", glb_bytes[off:off + 4])[0]
    return J, bytearray(glb_bytes[off + 8: off + 8 + bl])

def _join_glb(J, BIN):
    while len(BIN) % 4:
        BIN.append(0)
    J["buffers"][0]["byteLength"] = len(BIN)
    js = json.dumps(J, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(BIN)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(BIN), 0x004E4942) + bytes(BIN))

def add_animations(glb_bytes, anims, animated_nodes):
    """Agrega animaciones por keyframes. anims: [(nombre, tiempos, {(nodo, 'rotation'|'translation'): valores})]."""
    J, BIN = _split_glb(glb_bytes)
    node_idx = {n.get("name"): i for i, n in enumerate(J["nodes"])}
    # los nodos animados no pueden usar "matrix": pasar a translation (+ rotation / scale si hay)
    for g in animated_nodes:
        n = J["nodes"][node_idx[g]]
        if "matrix" in n:
            M = np.array(n.pop("matrix")).reshape(4, 4).T
            n["translation"] = M[:3, 3].tolist()
            sc = np.linalg.norm(M[:3, :3], axis=0)
            R = M[:3, :3] / sc
            if not np.allclose(sc, 1, atol=1e-6):
                n["scale"] = sc.tolist()
            if not np.allclose(R, np.eye(3), atol=1e-7):
                R4 = np.eye(4); R4[:3, :3] = R
                w, x, y, z = trimesh.transformations.quaternion_from_matrix(R4)
                n["rotation"] = [float(x), float(y), float(z), float(w)]

    def push(arr, typ, with_minmax=False):
        nonlocal BIN
        while len(BIN) % 4:
            BIN.append(0)
        data = np.asarray(arr, np.float32)
        J["bufferViews"].append({"buffer": 0, "byteOffset": len(BIN), "byteLength": data.nbytes})
        BIN += data.tobytes()
        acc = {"bufferView": len(J["bufferViews"]) - 1, "componentType": 5126,
               "count": len(data), "type": typ}
        if with_minmax:
            acc["min"] = [float(data.min())]; acc["max"] = [float(data.max())]
        J["accessors"].append(acc)
        return len(J["accessors"]) - 1

    J["animations"] = []
    for name, t, ch in anims:
        a_in = push(t, "SCALAR", True)
        samplers, channels = [], []
        for (node, path), vals in ch.items():
            a_out = push(np.array(vals), "VEC4" if path == "rotation" else "VEC3")
            samplers.append({"input": a_in, "output": a_out, "interpolation": "LINEAR"})
            channels.append({"sampler": len(samplers) - 1, "target": {"node": node_idx[node], "path": path}})
        J["animations"].append({"name": name, "samplers": samplers, "channels": channels})

    return _join_glb(J, BIN)


# ================================================================================================
#   FORMAS ORGÁNICAS (dinosaurios)
# ================================================================================================

# ---------------------------------------------------------------- ruido sólido 3D
def _hash3(ix, iy, iz, seed):
    """Hash entero -> float en [0,1) para celdas de una grilla 3D (vectorizado)."""
    h = (ix.astype(np.int64) * 73856093) ^ (iy.astype(np.int64) * 19349663) ^ (iz.astype(np.int64) * 83492791)
    h = (h ^ (seed * 2654435761)) & 0xFFFFFFFF
    h = (h ^ (h >> 16)) * 0x45D9F3B & 0xFFFFFFFF
    h = (h ^ (h >> 16)) * 0x45D9F3B & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF) / float(0x1000000)

def value_noise3(P, cell, seed):
    """Ruido de valor suave en 3D (0..1), tamaño de rasgo ~ cell metros."""
    Q = P / cell
    b = np.floor(Q).astype(np.int64); f = Q - b
    f = f * f * (3 - 2 * f)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out = out + w * _hash3(b[:, 0] + dx, b[:, 1] + dy, b[:, 2] + dz, seed)
    return out

def fbm3(P, cell, seed, octaves=4, gain=0.5):
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        tot = tot + amp * value_noise3(P, cell / 2 ** o, seed + 17 * o)
        norm += amp; amp *= gain
    return tot / norm

def worley3(P, cell, seed, jitter=0.85):
    """Ruido celular 3D: devuelve F1, F2 (en unidades de celda) e id de celda. Sirve para escamas."""
    Q = P / cell
    b = np.floor(Q).astype(np.int64)
    F1 = np.full(len(P), 9.0); F2 = np.full(len(P), 9.0); cid = np.zeros(len(P))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                cx, cy, cz = b[:, 0] + dx, b[:, 1] + dy, b[:, 2] + dz
                jx = 0.5 + jitter * (_hash3(cx, cy, cz, seed) - 0.5)
                jy = 0.5 + jitter * (_hash3(cx, cy, cz, seed + 1) - 0.5)
                jz = 0.5 + jitter * (_hash3(cx, cy, cz, seed + 2) - 0.5)
                d = np.sqrt((cx + jx - Q[:, 0]) ** 2 + (cy + jy - Q[:, 1]) ** 2 + (cz + jz - Q[:, 2]) ** 2)
                closer = d < F1
                F2 = np.where(closer, F1, np.minimum(F2, d))
                cid = np.where(closer, _hash3(cx, cy, cz, seed + 3), cid)
                F1 = np.where(closer, d, F1)
    return F1, F2, cid

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)

# ---------------------------------------------------------------- lofts (tubos a lo largo de una columna)
def _catmull_rom(pts, per_seg=40):
    """Curva centrípeta por los puntos de control. Devuelve muestras y el parámetro por tramo."""
    P = np.asarray(pts, float)
    ext = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out, seg_t = [], []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        t0 = 0.0
        t1 = t0 + max(np.linalg.norm(p1[:3] - p0[:3]), 1e-6) ** 0.5
        t2 = t1 + max(np.linalg.norm(p2[:3] - p1[:3]), 1e-6) ** 0.5
        t3 = t2 + max(np.linalg.norm(p3[:3] - p2[:3]), 1e-6) ** 0.5
        last = i == len(ext) - 3
        for k in range(per_seg + (1 if last else 0)):
            s = k / per_seg
            t = t1 + s * (t2 - t1)
            a1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
            a2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
            a3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
            b1 = (t2 - t) / (t2 - t0) * a1 + (t - t0) / (t2 - t0) * a2
            b2 = (t3 - t) / (t3 - t1) * a2 + (t - t1) / (t3 - t1) * a3
            out.append((t2 - t) / (t2 - t1) * b1 + (t - t1) / (t2 - t1) * b2)
    return np.array(out)

class Loft:
    """Tubo orgánico a lo largo de una columna.

    ctrl: filas [x, y, z, rx, ry_arriba, ry_abajo] y opcionalmente [expo, afina]:
      rx = semiancho, ry_arriba / ry_abajo = alto hacia el lomo / hacia el vientre,
      expo < 1 hace la sección más cuadrada, afina > 0 la angosta arriba (lomo en quilla).
    "Arriba" es el lado dorsal: para una pata que baja, es el frente.
    Los extremos se cierran con una cúpula redondeada.
    s0: coordenada de columna (m) donde empieza esta pieza, para continuar patrones entre piezas.
    """
    wrap_v = True

    def __init__(self, ctrl, s0=0.0, cupula=(1.0, 1.0), arriba=(0.0, 1.0, 0.0)):
        C = np.array([list(f) + [1.0, 0.0][len(f) - 6:] if len(f) < 8 else list(f) for f in ctrl], float)
        S = _catmull_rom(C, 48)
        S[:, 3:6] = np.maximum(S[:, 3:6], 1e-4)
        cen = S[:, :3]
        seg = np.linalg.norm(np.diff(cen, axis=0), axis=1)
        s = np.concatenate([[0], np.cumsum(seg)])
        T = np.gradient(cen, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True)

        # cúpulas en los extremos
        def cap(i, sign, k):
            r = min(S[i, 3], S[i, 4], S[i, 5]) * k
            ts = np.linspace(1, 0, 14)[:-1] if sign < 0 else np.linspace(0, 1, 14)[1:]
            rows = []
            for t in ts:
                row = S[i].copy()
                row[:3] = cen[i] + sign * T[i] * r * t
                f = np.sqrt(max(1 - t * t, 0))
                row[3:6] = S[i, 3:6] * f + 1e-5
                rows.append(row)
            return np.array(rows), r
        head_rows, r0 = cap(0, -1, cupula[0])
        tail_rows, r1 = cap(len(S) - 1, 1, cupula[1])
        S = np.vstack([head_rows, S, tail_rows])
        s = np.concatenate([-r0 * np.linspace(1, 0, 14)[:-1], s, s[-1] + r1 * np.linspace(0, 1, 14)[1:]])
        cen = S[:, :3]
        T = np.gradient(cen, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True)

        # marcos que minimizan la torsión (doble reflexión). El lado dorsal arranca mirando hacia
        # 'arriba' (o hacia adelante, +Z, si la pieza baja vertical, como una pata)
        X = np.zeros_like(cen)
        x0 = np.cross(np.asarray(arriba, float), T[0])
        if np.linalg.norm(x0) < 0.3:
            x0 = np.cross([0, 0, 1.0], T[0])
        X[0] = x0 / np.linalg.norm(x0)
        for i in range(len(cen) - 1):
            v1 = cen[i + 1] - cen[i]
            c1 = np.dot(v1, v1)
            if c1 < 1e-14:
                X[i + 1] = X[i]; continue
            rL = X[i] - (2 / c1) * np.dot(v1, X[i]) * v1
            tL = T[i] - (2 / c1) * np.dot(v1, T[i]) * v1
            v2 = T[i + 1] - tL
            c2 = np.dot(v2, v2)
            X[i + 1] = rL - (2 / c2) * np.dot(v2, rL) * v2 if c2 > 1e-14 else rL
            X[i + 1] /= np.linalg.norm(X[i + 1])
        B = np.cross(T, X)

        self.s_tab = s - s[0]
        self.S, self.cen, self.T, self.X, self.B = S, cen, T, X, B
        self.L = self.s_tab[-1]
        self.s0 = s0 + s[0]
        Lv = 0.0
        for row in S:
            rx, ru, rd = row[3:6]
            Lv = max(Lv, np.pi * (rx + (ru + rd) / 2) * 1.02)
        self.largo_u, self.largo_v = self.L, Lv

    def _tab(self, U):
        st = np.clip(U, 0, 1) * self.L
        idx = np.clip(np.searchsorted(self.s_tab, st) - 1, 0, len(self.s_tab) - 2)
        f = ((st - self.s_tab[idx]) / np.maximum(self.s_tab[idx + 1] - self.s_tab[idx], 1e-12))[:, None]
        lerp = lambda A: A[idx] * (1 - f) + A[idx + 1] * f
        return lerp(self.cen), lerp(self.X), lerp(self.B), lerp(self.S), st

    def __call__(self, U, V):
        c, X, B, S, _ = self._tab(U)
        a = 2 * np.pi * V - np.pi / 2              # v = 0 en el vientre (costura escondida)
        ca, sa = np.cos(a), np.sin(a)
        e = S[:, 6]
        cx = np.sign(ca) * np.abs(ca) ** e
        sy = np.sign(sa) * np.abs(sa) ** e
        ry = np.where(sa > 0, S[:, 4], S[:, 5])
        rx = S[:, 3] * (1 - S[:, 7] * np.clip(sa, 0, 1))
        return c + X * (rx * cx)[:, None] + B * (ry * sy)[:, None]

    def info(self, U, V):
        """Datos para los patrones: s = coordenada de columna (m), dorsal = +1 lomo / -1 vientre."""
        _, _, _, _, st = self._tab(U)
        a = 2 * np.pi * V - np.pi / 2
        return {"s": self.s0 + st, "dorsal": np.sin(a), "lateral": np.cos(a), "u": np.clip(U, 0, 1)}


class Elipsoide:
    """Elipsoide (opcionalmente deformado) para piezas sueltas: crestas, ojos, almohadillas."""
    wrap_v = True

    def __init__(self, centro, radios, rot=None, deform=None):
        self.c = np.asarray(centro, float); self.r = np.asarray(radios, float)
        self.R = np.eye(3) if rot is None else np.asarray(rot, float)[:3, :3]
        self.deform = deform
        self.largo_u = np.pi * self.r.max(); self.largo_v = 2 * np.pi * self.r.max()

    def __call__(self, U, V):
        th = np.clip(U, 0, 1) * np.pi; ph = 2 * np.pi * V
        d = np.stack([np.sin(th) * np.cos(ph), np.cos(th), np.sin(th) * np.sin(ph)], 1)
        p = d * self.r
        if self.deform is not None:
            p = p + d * self.deform(d)[:, None]
        return self.c + p @ self.R.T

    def info(self, U, V):
        th = np.clip(U, 0, 1) * np.pi
        return {"s": np.zeros_like(U), "dorsal": np.cos(th), "lateral": np.sin(th), "u": np.clip(U, 0, 1)}


class Espejo:
    """La misma forma reflejada en X (lado derecho). Comparte la textura con el original."""
    def __init__(self, forma):
        self.f = forma; self.wrap_v = forma.wrap_v
        self.largo_u, self.largo_v = forma.largo_u, forma.largo_v
    def __call__(self, U, V):
        return self.f(U, V) * [-1, 1, 1]
    def info(self, U, V):
        return self.f.info(U, V)


def _normales(forma, U, V, eps=1e-3):
    du = forma(np.clip(U + eps, 0, 1), V) - forma(np.clip(U - eps, 0, 1), V)
    dv = forma(U, V + eps) - forma(U, V - eps)
    n = np.cross(du, dv)
    ln = np.linalg.norm(n, axis=1)
    bad = ln < 1e-10
    if bad.any():   # polos de las cúpulas: la normal apunta hacia afuera por el eje
        Ub = U[bad]
        inner = np.where(Ub < 0.5, Ub + 0.01, Ub - 0.01)
        ring = np.stack([forma(inner, np.full(len(Ub), k / 8)) for k in range(8)]).mean(0)
        n[bad] = forma(Ub, V[bad]) - ring
        ln[bad] = np.linalg.norm(n[bad], axis=1)
    return n / np.maximum(ln, 1e-12)[:, None]


class Pieza:
    """Una pieza de geometría: forma paramétrica + grupo (para animar) + zona (para el patrón)."""
    def __init__(self, nombre, grupo, forma, nu, nv, zona, atlas="cuerpo", comparte=None, detalle=1.0):
        self.nombre, self.grupo, self.forma, self.zona = nombre, grupo, forma, zona
        self.nu, self.nv, self.atlas = nu, nv, atlas
        self.comparte = comparte      # nombre de otra pieza cuya región de textura reutiliza (espejo)
        self.detalle = detalle        # >1 = más resolución de textura para esta pieza
        self.rect = None

    def malla(self):
        u = np.linspace(0, 1, self.nu); v = np.linspace(0, 1, self.nv)
        U, V = np.meshgrid(u, v, indexing="ij")
        U, V = U.ravel(), V.ravel()
        P = self.forma(U, V)
        N = _normales(self.forma, U, V)
        idx = np.arange(self.nu * self.nv).reshape(self.nu, self.nv)
        a = idx[:-1, :-1].ravel(); b = idx[1:, :-1].ravel()
        c = idx[1:, 1:].ravel(); d = idx[:-1, 1:].ravel()
        faces = np.concatenate([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
        m = trimesh.Trimesh(P, faces, process=False)
        if m.volume < 0:              # que las caras y normales miren hacia afuera
            faces = faces[:, ::-1]; N = -N
            m = trimesh.Trimesh(P, faces, process=False)
        if np.mean(np.einsum("ij,ij->i", N, P - P.mean(0))) < 0 and m.volume > 0:
            N = -N
        m.vertex_normals = N
        self.U, self.V = U, V
        return m


# ---------------------------------------------------------------- atlas de texturas horneadas
class Atlas:
    """Empaqueta las piezas en una textura (color, normal, rugosidad/metal) y las hornea con un patrón.

    patron(P, N, info, zona) -> (color RGB 0..1, altura en metros, rugosidad 0..1)
    El patrón se evalúa en la posición 3D de cada texel: las escamas no se estiran.
    """
    def __init__(self, nombre, tam=1024, pad=4, tam_mr=512):
        self.nombre, self.tam, self.pad, self.tam_mr = nombre, tam, pad, tam_mr
        self.piezas = []

    def agregar(self, pieza):
        self.piezas.append(pieza)

    def _empacar(self, dens):
        W = self.tam; x = y = 0; fila = 0; rects = {}
        for p in sorted([p for p in self.piezas if p.comparte is None], key=lambda p: -p.forma.largo_v):
            w = int(np.ceil(p.forma.largo_u * dens * p.detalle)) + 2 * self.pad
            h = int(np.ceil(p.forma.largo_v * dens * p.detalle)) + 2 * self.pad
            w = max(w, 8 + 2 * self.pad); h = max(h, 8 + 2 * self.pad)
            if w > W:
                return None
            if x + w > W:
                x = 0; y += fila; fila = 0
            if y + h > W:
                return None
            rects[p.nombre] = (x, y, w, h)
            x += w; fila = max(fila, h)
        return rects

    def empacar(self):
        lo, hi = 1.0, 4000.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if self._empacar(mid) is None:
                hi = mid
            else:
                lo = mid
        self.densidad = lo
        rects = self._empacar(lo)
        for p in self.piezas:
            p.rect = rects[p.comparte or p.nombre]
        return lo

    def uv(self, pieza):
        x, y, w, h = pieza.rect
        pad = self.pad
        cu = x + pad + pieza.U * (w - 2 * pad)
        cv = y + pad + pieza.V * (h - 2 * pad)
        return np.stack([cu / self.tam, 1 - cv / self.tam], 1)

    def hornear(self, patron, fuerza_normal=1.0):
        W = self.tam
        col = np.zeros((W, W, 3), np.float32) + 0.5
        alt = np.zeros((W, W), np.float32)
        rug = np.ones((W, W), np.float32) * 0.8
        nrm = np.zeros((W, W, 3), np.float32); nrm[..., 2] = 1
        hechos = set()
        for p in self.piezas:
            if p.comparte is not None or p.nombre in hechos:
                continue
            hechos.add(p.nombre)
            x, y, w, h = p.rect
            pad = self.pad
            jj, ii = np.meshgrid(np.arange(w), np.arange(h))
            U = (jj + 0.5 - pad) / (w - 2 * pad)
            V = (ii + 0.5 - pad) / (h - 2 * pad)
            U, V = U.ravel(), V.ravel()
            if not p.forma.wrap_v:
                V = np.clip(V, 0, 1)
            Uc = np.clip(U, 0, 1)
            P = p.forma(Uc, V)
            N = _normales(p.forma, Uc, V)
            info = p.forma.info(Uc, V)
            c, hgt, r = patron(P, N, info, p.zona)
            c = c.reshape(h, w, 3); hgt = hgt.reshape(h, w); r = r.reshape(h, w)
            Pg = P.reshape(h, w, 3)
            # pendiente de la altura en metros reales -> normal en espacio tangente
            dxm = np.linalg.norm(np.roll(Pg, -1, 1) - np.roll(Pg, 1, 1), axis=2)
            dym = np.linalg.norm(np.roll(Pg, -1, 0) - np.roll(Pg, 1, 0), axis=2)
            gx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) / np.maximum(dxm, 1e-4)
            gy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) / np.maximum(dym, 1e-4)
            gx[:, [0, -1]] = 0; gy[[0, -1], :] = 0
            nx, ny = -gx * fuerza_normal, gy * fuerza_normal
            ln = np.sqrt(nx ** 2 + ny ** 2 + 1)
            n = np.stack([nx / ln, ny / ln, 1 / ln], -1)
            col[y:y + h, x:x + w] = c; rug[y:y + h, x:x + w] = r; nrm[y:y + h, x:x + w] = n
        self.img_color = to_img(col)
        self.img_normal = Image.fromarray(((nrm * 0.5 + 0.5) * 255).astype(np.uint8))
        mr = mr_img(rug)
        self.img_mr = mr.resize((self.tam_mr, self.tam_mr), Image.BILINEAR) if self.tam_mr != W else mr
        return self.img_color, self.img_normal, self.img_mr

    def material(self):
        return PBRMaterial(name=self.nombre, baseColorTexture=self.img_color, normalTexture=self.img_normal,
                           metallicRoughnessTexture=self.img_mr, metallicFactor=0.0, roughnessFactor=1.0)


# ---------------------------------------------------------------- esqueleto: poses y cinemática
def ang(v):
    """Ángulo de un vector en el plano YZ: 0 = arriba, pi/2 = adelante, pi = abajo.
    Una rotación positiva alrededor de +X lo aumenta."""
    return np.arctan2(v[..., 2], v[..., 1])

def ik_dos(H, A, L1, L2, rodilla_adelante=True):
    """Pata de dos huesos en el plano YZ: desde H hasta A. Devuelve los ángulos (ver ang) de cada hueso."""
    d = np.asarray(A, float) - np.asarray(H, float)
    D = np.clip(np.hypot(d[1], d[2]), abs(L1 - L2) + 1e-4, L1 + L2 - 1e-4)
    base = np.arctan2(d[2], d[1])
    beta = np.arccos(np.clip((L1 ** 2 + D ** 2 - L2 ** 2) / (2 * L1 * D), -1, 1))
    cands = [base + beta, base - beta]
    zk = [np.sin(c) for c in cands]
    phi1 = cands[int(np.argmax(zk))] if rodilla_adelante else cands[int(np.argmin(zk))]
    K = np.array([0, np.cos(phi1) * L1, np.sin(phi1) * L1]) + np.asarray(H, float) * [0, 1, 1]
    dk = np.asarray(A, float) - K
    phi2 = np.arctan2(dk[2], dk[1])
    return phi1, phi2


class Esqueleto:
    """Jerarquía de grupos con pivotes (en la pose neutra) para calcular poses y verificar contactos."""
    def __init__(self, grupos, padre, pivotes):
        self.grupos, self.padre, self.piv = grupos, padre, pivotes
        self.local_t = {g: pivotes[g] - pivotes[padre[g]] for g in grupos}

    def mundo(self, rot, tras=None):
        """rot: {grupo: cuaternión local}, tras: {grupo: traslación local}. Matrices en el espacio de 'raiz'."""
        tras = tras or {}
        W = {"raiz": np.eye(4)}
        for g in self.grupos:          # los grupos están ordenados de padres a hijos
            M = Tm(tras.get(g, self.local_t[g]))
            if g in rot:
                M = M @ quat_matrix(rot[g])
            W[g] = W[self.padre[g]] @ M
        return W

    def punto(self, W, g, p_neutro):
        """Posición actual de un punto (dado en coordenadas neutras) que pertenece al grupo g."""
        q = np.append(np.asarray(p_neutro, float) - self.piv[g], 1.0)
        return (W[g] @ q)[:3]


def alfa(W):
    """Inclinación (rotación alrededor de X) de una matriz que solo cabecea."""
    return np.arctan2(W[2, 1], W[1, 1])

def resolver_pata(esq, W, cadena, juntas, objetivo, angulos_pie, rodilla_adelante=True):
    """Calcula las rotaciones locales (alrededor de X) de una pata encadenada.

    cadena: grupos [muslo, pierna, pie, (dedos)]; juntas: puntos neutros [cadera, rodilla, tobillo, (base dedos), punta].
    objetivo: posición (en el espacio de 'raiz') a la que tiene que llegar el tobillo.
    angulos_pie: ángulos (ver ang) que deben tener los huesos después del tobillo (pie y dedos).
    Devuelve {grupo: cuaternión}."""
    J = [np.asarray(j, float) for j in juntas]
    padre = esq.padre[cadena[0]]
    a0 = alfa(W[padre])
    H = esq.punto(W, padre, J[0])
    L1 = np.linalg.norm(J[1] - J[0]); L2 = np.linalg.norm(J[2] - J[1])
    phi1, phi2 = ik_dos(H, objetivo, L1, L2, rodilla_adelante)
    mundo = [phi1, phi2] + list(angulos_pie)
    rot, prev = {}, a0
    for k, g in enumerate(cadena):
        acumulado = mundo[k] - ang(J[k + 1] - J[k])     # rotación total que necesita este hueso
        rot[g] = quat([1, 0, 0], acumulado - prev)
        prev = acumulado
    return rot

def giro(yaw, pitch, roll=0.0):
    """Rotación local: primero cabecea (X), después gira a los costados (Y). roll opcional (Z)."""
    q = qmul(quat([0, 1, 0], yaw), quat([1, 0, 0], pitch))
    return qmul(q, quat([0, 0, 1], roll)) if roll else q

def apoyar_cadena(esq, rot, tras, cadena, yaws, puntos, alturas, rango=(-2.0, 2.0)):
    """Para cada junta de una cadena (p. ej. la cola) busca el cabeceo que deja el punto
    asociado (en coordenadas neutras, del mismo grupo) a la altura pedida. Devuelve rot y los cabeceos."""
    out = dict(rot); pitches = []
    for g, yw, p, h in zip(cadena, yaws, puntos, alturas):
        def err(pitch):
            out[g] = giro(yw, pitch)
            return abs(esq.punto(esq.mundo(out, tras), g, p)[1] - h)
        xs = np.linspace(*rango, 81)
        k = int(np.argmin([err(x) for x in xs]))
        lo, hi = xs[max(k - 1, 0)], xs[min(k + 1, len(xs) - 1)]
        for _ in range(40):                 # sección áurea
            a = hi - 0.618 * (hi - lo); b = lo + 0.618 * (hi - lo)
            if err(a) < err(b):
                hi = b
            else:
                lo = a
        best = (lo + hi) / 2
        out[g] = giro(yw, best); pitches.append(best)
    return out, pitches

def verificar(esq, mallas_locales, poses, piso, tol=0.02, ignorar=()):
    """Revisa cada pose: nada puede atravesar el piso. piso(x, z) devuelve la altura del piso
    (la roca o el suelo) en ese lugar. mallas_locales: {nombre: (grupo, vértices relativos al pivote)}.
    poses: [(etiqueta, rot, tras)]. Devuelve (reporte por pose, lista de problemas)."""
    reporte, problemas = [], []
    for etiqueta, rot, tras in poses:
        W = esq.mundo(rot, tras)
        peor, quien = 1e9, None
        for nombre, (g, V) in mallas_locales.items():
            if nombre in ignorar:
                continue
            Pw = V @ W[g][:3, :3].T + W[g][:3, 3]
            d = (Pw[:, 1] - piso(Pw[:, 0], Pw[:, 2])).min()
            if d < peor:
                peor, quien = d, nombre
        reporte.append((etiqueta, peor, quien))
        if peor < -tol:
            problemas.append(f"{etiqueta}: '{quien}' atraviesa el piso {-100 * peor:.1f} cm")
    return reporte, problemas

def minimo(esq, locales, rot, tras, nombres, piso=None):
    """Distancia mínima al piso (o la altura mínima si piso es None) de las piezas nombradas."""
    W = esq.mundo(rot, tras); peor = 1e9
    for n in nombres:
        g, V = locales[n]
        Pw = V @ W[g][:3, :3].T + W[g][:3, 3]
        d = Pw[:, 1] - (piso(Pw[:, 0], Pw[:, 2]) if piso else 0)
        peor = min(peor, d.min())
    return peor

def mezcla(a, b, t):
    """Interpola dos juegos de parámetros de pose (t de 0 a 1)."""
    out = {}
    for k in a:
        va, vb = a[k], b[k]
        if isinstance(va, list):
            out[k] = [tuple(np.array(x) * (1 - t) + np.array(y) * t) for x, y in zip(va, vb)]
        else:
            out[k] = tuple(np.array(va) * (1 - t) + np.array(vb) * t) if isinstance(va, tuple) else va * (1 - t) + vb * t
    return out

def sumar(p, **delta):
    """Suma desplazamientos a parámetros de pose (números, tuplas o la lista de la cola)."""
    q = dict(p)
    for k, v in delta.items():
        if k == "cola":
            q[k] = [(a + da, b + db) for (a, b), (da, db) in zip(q[k], v)]
        elif isinstance(q[k], tuple):
            q[k] = tuple(np.array(q[k]) + np.array(v))
        else:
            q[k] = q[k] + v
    return q

def suavizar(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)

def canales(tiempos, poses, grupos):
    """Convierte una lista de poses (rot, tras) en canales glTF. Todos los grupos animados reciben
    rotación (y 'cuerpo' traslación) en todas las animaciones, para que no queden valores viejos."""
    ch = {}
    for g in grupos:
        qs = []
        for rot, _ in poses:
            q = np.asarray(rot.get(g, [0, 0, 0, 1.0]), float)
            if qs and np.dot(qs[-1], q) < 0:       # evitar que interpole por el camino largo
                q = -q
            qs.append(q)
        ch[(g, "rotation")] = qs
    for g in {g for _, tras in poses for g in tras}:
        ch[(g, "translation")] = [np.asarray(tras[g], float) for _, tras in poses]
    return ch


# ---------------------------------------------------------------- roca de la base
class Roca:
    """Laja de piedra con la parte de arriba casi plana (donde se apoya la escultura).
    Planta: superelipse de semiejes (rx, rz) centrada en 'centro' (x, z). Base en y = 0."""
    wrap_v = True

    # perfil de la laja (radio relativo, altura relativa): arriba plano, canto redondeado, base
    PERFIL = np.array([[0.0, 1.0], [0.88, 1.0], [0.96, 0.93], [1.0, 0.75], [1.02, 0.45], [1.0, 0.15],
                       [0.94, 0.0], [0.0, 0.0]])

    def __init__(self, centro, rx, rz, alto, seed=5, curva=4.0):
        self.cx, self.cz = centro; self.rx, self.rz, self.alto = rx, rz, alto
        self.seed, self.n = seed, curva
        R = (rx + rz) / 2
        seg = np.hypot(np.diff(self.PERFIL[:, 0]) * R, np.diff(self.PERFIL[:, 1]) * alto)
        self.t_perfil = np.concatenate([[0], np.cumsum(seg)]) / seg.sum()   # u por largo de arco
        self.largo_u = seg.sum(); self.largo_v = 2 * np.pi * max(rx, rz)

    def borde(self, ph):
        c, s = np.cos(ph), np.sin(ph)
        r = 1 / (np.abs(c) ** self.n + np.abs(s) ** self.n) ** (1 / self.n)
        bump = 1 + 0.06 * (fbm3(np.stack([c * 3, s * 3, np.zeros_like(c)], 1), 1.3, self.seed, 3) - 0.5)
        return r * bump

    def __call__(self, U, V):
        u = np.clip(U, 0, 1); ph = 2 * np.pi * V
        rr = np.interp(u, self.t_perfil, self.PERFIL[:, 0])
        yy = np.interp(u, self.t_perfil, self.PERFIL[:, 1])
        rad = rr * self.borde(ph)
        x = self.cx + self.rx * rad * np.cos(ph)
        z = self.cz + self.rz * rad * np.sin(ph)
        P = np.stack([x, self.alto * yy, z], 1)
        # irregularidades: suaves arriba (apoyo), más marcadas en el canto
        n = fbm3(P, 0.35, self.seed + 3, 4) - 0.5
        canto = smooth(0.80, 0.95, rr) * (yy > 0.02)
        P[:, 1] += n * (0.02 + 0.05 * canto) * (yy > 0.02)
        P[:, 0] += n * 0.07 * canto * np.cos(ph); P[:, 2] += n * 0.07 * canto * np.sin(ph)
        return P

    def info(self, U, V):
        u = np.clip(U, 0, 1)
        yy = np.interp(u, self.t_perfil, self.PERFIL[:, 1])
        return {"s": np.zeros_like(U), "dorsal": 2 * yy - 1, "lateral": np.zeros_like(U), "u": u}

    def piso(self, x, z):
        """Altura de apoyo en (x, z): arriba de la roca si cae sobre ella, el suelo si no."""
        ph = np.arctan2((z - self.cz) / self.rz, (x - self.cx) / self.rx)
        rr = np.hypot((x - self.cx) / self.rx, (z - self.cz) / self.rz)
        dentro = rr < self.borde(ph) * 0.9
        return np.where(dentro, self.alto - 0.02, 0.0)


def patron_roca(P, N, info, zona, seed=3):
    """Piedra gris con vetas, grietas y algo de liquen."""
    F1, F2, cid = worley3(P, 0.45, seed, jitter=1.0)
    grieta = (1 - smooth(0.0, 0.035, F2 - F1)) * smooth(0.45, 0.6, fbm3(P, 0.6, seed + 5, 3))
    g1 = fbm3(P, 0.5, seed + 1, 5)
    g2 = fbm3(P, 0.06, seed + 2, 3)
    base = np.array([0.50, 0.49, 0.46])
    col = base * (0.78 + 0.35 * g1[:, None]) * (0.92 + 0.12 * g2[:, None])
    col = col * (1 - 0.35 * grieta[:, None])
    liquen = smooth(0.62, 0.75, fbm3(P + 7, 0.3, seed + 4, 4)) * smooth(-0.2, 0.6, N[:, 1])
    col = col * (1 - 0.35 * liquen[:, None]) + np.array([0.55, 0.56, 0.42]) * 0.35 * liquen[:, None]
    hgt = 0.006 * (g1 - 0.5) + 0.003 * g2 - 0.012 * grieta
    rough = np.clip(0.85 + 0.1 * grieta, 0, 1)
    return col, hgt, rough


# ---------------------------------------------------------------- tangentes (para el mapa de normales)
def _leer_accessor(J, BIN, i):
    a = J["accessors"][i]; bv = J["bufferViews"][a["bufferView"]]
    comps = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}[a["componentType"]]
    o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    arr = np.frombuffer(bytes(BIN[o:o + a["count"] * comps * np.dtype(dt).itemsize]), dt)
    return arr.reshape(a["count"], comps) if comps > 1 else arr

def agregar_tangentes(glb_bytes):
    """Agrega TANGENT a las mallas con mapa de normales, con la convención de glTF
    (bitangente = cross(normal, tangente) * w, apuntando hacia arriba en la imagen)."""
    J, BIN = _split_glb(glb_bytes)
    con_normal = {i for i, m in enumerate(J.get("materials", [])) if "normalTexture" in m}
    for mesh in J["meshes"]:
        for prim in mesh["primitives"]:
            at = prim["attributes"]
            if prim.get("material") not in con_normal or "TEXCOORD_0" not in at or "TANGENT" in at:
                continue
            P = _leer_accessor(J, BIN, at["POSITION"]).astype(np.float64)
            N = _leer_accessor(J, BIN, at["NORMAL"]).astype(np.float64)
            T = _leer_accessor(J, BIN, at["TEXCOORD_0"]).astype(np.float64)
            F = _leer_accessor(J, BIN, prim["indices"]).reshape(-1, 3).astype(np.int64)
            e1 = P[F[:, 1]] - P[F[:, 0]]; e2 = P[F[:, 2]] - P[F[:, 0]]
            d1 = T[F[:, 1]] - T[F[:, 0]]; d2 = T[F[:, 2]] - T[F[:, 0]]
            r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
            r = np.where(np.abs(r) < 1e-12, 1e-12, r)
            tf = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
            bf = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]     # hacia donde crece t (abajo en la imagen)
            tan = np.zeros_like(P); bit = np.zeros_like(P)
            for k in range(3):
                np.add.at(tan, F[:, k], tf); np.add.at(bit, F[:, k], bf)
            tan = tan - N * np.einsum("ij,ij->i", N, tan)[:, None]
            ln = np.linalg.norm(tan, axis=1)
            mala = ln < 1e-9
            alt = np.cross(N, [0, 1, 0]); alt[np.linalg.norm(alt, axis=1) < 1e-6] = [1, 0, 0]
            tan[mala] = alt[mala]; tan /= np.linalg.norm(tan, axis=1, keepdims=True)
            w = np.where(np.einsum("ij,ij->i", np.cross(N, tan), -bit) < 0, -1.0, 1.0)
            data = np.hstack([tan, w[:, None]]).astype(np.float32)
            while len(BIN) % 4:
                BIN.append(0)
            J["bufferViews"].append({"buffer": 0, "byteOffset": len(BIN), "byteLength": data.nbytes})
            BIN += data.tobytes()
            J["accessors"].append({"bufferView": len(J["bufferViews"]) - 1, "componentType": 5126,
                                   "count": len(data), "type": "VEC4"})
            at["TANGENT"] = len(J["accessors"]) - 1
    return _join_glb(J, BIN)


# ---------------------------------------------------------------- armado y exportación de un modelo
class Modelo:
    """Junta piezas, atlas y materiales planos; hornea texturas y exporta el .glb con animaciones."""
    def __init__(self):
        self.piezas, self.atlas, self.planos = [], {}, {}

    def nuevo_atlas(self, nombre, tam=1024, tam_mr=512):
        self.atlas[nombre] = Atlas(nombre, tam=tam, tam_mr=tam_mr)

    def plano(self, nombre, rgb, rugosidad):
        self.planos[nombre] = mat_flat(rgb, rugosidad, nombre)

    def agregar(self, nombre, grupo, forma, nu, nv, zona, atlas="cuerpo", comparte=None, material=None, detalle=1.0):
        p = Pieza(nombre, grupo, forma, nu, nv, zona, atlas=None if material else atlas, comparte=comparte,
                  detalle=detalle)
        p.material = material
        self.piezas.append(p)
        if not material:
            self.atlas[atlas].agregar(p)
        return p

    def preparar(self, pivotes):
        """Arma las mallas (pose neutra) y guarda los vértices relativos al pivote de su grupo,
        para poder medir y verificar poses antes de exportar."""
        self.mallas = getattr(self, "mallas", {})
        for p in self.piezas:            # solo arma las que faltan (se pueden agregar piezas después)
            if p.nombre not in self.mallas:
                self.mallas[p.nombre] = (p.malla_fija.copy() if getattr(p, "malla_fija", None) is not None
                                         else p.malla())
        self.locales = {p.nombre: (p.grupo, np.array(self.mallas[p.nombre].vertices) - pivotes[p.grupo])
                        for p in self.piezas}
        return self.locales

    def exportar(self, salida, grupos, padre, pivotes, raiz_matrix, rest_rot, rest_tras, animaciones, patrones):
        for nombre, at in self.atlas.items():
            at.empacar()
            print(f"  atlas '{nombre}': {at.densidad:.0f} px/m ({at.tam}x{at.tam})")
            at.hornear(patrones[nombre])
        mats = {n: at.material() for n, at in self.atlas.items()}
        mats.update(self.planos)
        parts = []
        mallas = getattr(self, "mallas", None) or {p.nombre: p.malla() for p in self.piezas}
        for p in self.piezas:
            m = mallas[p.nombre]
            uv = self.atlas[p.atlas].uv(p) if p.atlas else None      # material plano: sin coordenadas de textura
            parts.append((p.nombre, textured(m, uv, mats[p.material or p.atlas])))
        grupo_de = {p.nombre: p.grupo for p in self.piezas}
        scene, local_t = build_scene(parts, grupos, padre, pivotes, grupo_de.get, raiz_matrix, rest_rot, rest_tras)
        glb = scene.export(file_type="glb")
        glb = add_animations(glb, animaciones, list(grupos) + ["raiz"])
        glb = agregar_tangentes(glb)
        glb = recomprimir_texturas(glb)
        open(salida, "wb").write(glb)
        return glb


# ---------------------------------------------------------------- empaquetado final del .glb
def recomprimir_texturas(glb_bytes, calidad=90, calidad_normal=92):
    """Pasa las texturas a JPEG (color y normal) para achicar el archivo. Rehace el buffer binario."""
    J, BIN = _split_glb(glb_bytes)
    uso = {}
    for m in J.get("materials", []):
        pbr = m.get("pbrMetallicRoughness", {})
        for clave, tipo in ((pbr.get("baseColorTexture"), "color"), (m.get("normalTexture"), "normal"),
                            (pbr.get("metallicRoughnessTexture"), "mr")):
            if clave is not None:
                uso[J["textures"][clave["index"]]["source"]] = tipo
    nuevos = {}
    for i, im in enumerate(J.get("images", [])):
        bv = J["bufferViews"][im["bufferView"]]
        raw = bytes(BIN[bv.get("byteOffset", 0): bv.get("byteOffset", 0) + bv["byteLength"]])
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        out = io.BytesIO()
        q = calidad_normal if uso.get(i) == "normal" else calidad
        img.save(out, format="JPEG", quality=q, optimize=True, subsampling=0 if uso.get(i) == "normal" else 2)
        nuevos[im["bufferView"]] = out.getvalue()
        im["mimeType"] = "image/jpeg"
    # target de cada vista: datos de vértices o índices (lo recomienda el validador)
    for mesh in J["meshes"]:
        for prim in mesh["primitives"]:
            for acc in prim["attributes"].values():
                J["bufferViews"][J["accessors"][acc]["bufferView"]]["target"] = 34962
            if "indices" in prim:
                J["bufferViews"][J["accessors"][prim["indices"]]["bufferView"]]["target"] = 34963
    NB = bytearray()
    for k, bv in enumerate(J["bufferViews"]):
        data = nuevos.get(k)
        if data is None:
            o = bv.get("byteOffset", 0)
            data = bytes(BIN[o:o + bv["byteLength"]])
        while len(NB) % 4:
            NB.append(0)
        bv["byteOffset"] = len(NB); bv["byteLength"] = len(data)
        NB += data
    return _join_glb(J, NB)
