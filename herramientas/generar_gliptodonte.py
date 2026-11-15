"""Gliptodonte del Xibi Xibi (Cranithlastus xibiensis) — modelo 3D realista para AR.
Y arriba, mira hacia +Z, metros, escala real (~1,6 m con cola).
Texturas procedurales PBR: osteodermos en roseta (coraza), piel arrugada.
Las funciones compartidas con los otros modelos están en comun.py.
"""
import sys
import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial

from comun import (periodic_noise, normal_from_height, to_img, mr_img, mat_flat, surface, box_uv,
                   textured, arc_scale, tube, Tm, quat, qmul, build_scene, add_animations)

OUT = sys.argv[1] if len(sys.argv) > 1 else "gliptodonte.glb"
rng = np.random.default_rng(7)

# ---------------------------------------------------------------- textura de coraza (rosetas)
def shell_texture(W=1024, cols=4, rows=4, seed=1):
    dx = W / cols
    dy = dx * np.sqrt(3) / 2
    H = int(round(rows * dy))
    centers = []
    for j in range(rows):
        for i in range(cols):
            cx = (i + 0.5 * (j % 2)) * dx + rng.uniform(-0.06, 0.06) * dx
            cy = (j + 0.5) * dy + rng.uniform(-0.06, 0.06) * dy
            centers.append((cx, cy))
    centers = np.array(centers, np.float32)
    # copias periódicas
    pts = []
    for oy in (-H, 0, H):
        for ox in (-W, 0, W):
            pts.append(centers + [ox, oy])
    pts = np.concatenate(pts)
    ids = np.tile(np.arange(len(centers)), 9)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # deformación orgánica de los bordes
    xx = xx + (periodic_noise(H, W, 110, seed + 9) - 0.5) * dx * 0.27
    yy = yy + (periodic_noise(H, W, 110, seed + 10) - 0.5) * dx * 0.27
    d1 = np.full((H, W), 1e9, np.float32); d2 = d1.copy()
    best = np.zeros((H, W), np.int32)
    bx = np.zeros((H, W), np.float32); by = bx.copy()
    for k, (px, py) in enumerate(pts):
        d = np.hypot(xx - px, yy - py)
        closer = d < d1
        d2 = np.where(closer, d1, np.minimum(d2, d))
        d1 = np.where(closer, d, d1)
        best = np.where(closer, ids[k], best)
        bx = np.where(closer, xx - px, bx); by = np.where(closer, yy - py, by)
    edge = (d2 - d1) / dx            # 0 en el borde entre placas
    rr = d1 / (dx * 0.5)             # 0 en el centro, ~1 en el borde
    ang = np.arctan2(by, bx)

    cell_rot = rng.uniform(0, 2 * np.pi, len(centers))[best]
    cell_rad = rng.uniform(0.36, 0.44, len(centers))[best]
    nseg = 7

    wob = (periodic_noise(H, W, 70, seed + 11) - 0.5) * 1.2
    h = np.ones((H, W), np.float32)
    # surco entre placas
    groove = np.clip(edge / 0.10, 0, 1) ** 0.8
    h *= 0.25 + 0.75 * groove
    h -= 0.30 * rr ** 2  # placa abombada
    # surco anular que rodea la figura central
    ring = np.exp(-((rr - cell_rad * (1 + 0.12 * wob)) / 0.05) ** 2)
    h -= 0.45 * ring * groove
    # surcos radiales que separan las figuras periféricas
    seg = np.abs(np.sin((ang + cell_rot + wob) * nseg / 2))
    radial = np.exp(-(seg / 0.10) ** 2) * (rr > cell_rad) * groove
    h -= 0.22 * radial
    # figura central levemente abombada
    h += 0.12 * np.clip(1 - rr / cell_rad, 0, 1) ** 0.5
    # poros (folículos) donde se cruzan surcos
    pits = np.exp(-((rr - cell_rad) / 0.05) ** 2) * np.exp(-(seg / 0.18) ** 2)
    h -= 0.25 * pits
    # rugosidad de hueso
    grain = periodic_noise(H, W, 6, seed + 1)
    fine = periodic_noise(H, W, 2.2, seed + 2)
    pitn = periodic_noise(H, W, 1.2, seed + 12)
    h += 0.10 * (grain - 0.5) + 0.06 * (fine - 0.5) - 0.12 * np.clip((pitn - 0.75) * 6, 0, 1)

    # color: hueso pardo con variación por placa, surcos oscuros con tierra
    tint = (rng.uniform(-0.05, 0.05, (len(centers), 1)) * np.ones((1, 3))).astype(np.float32)[best]
    base = np.array([0.47, 0.38, 0.29], np.float32)
    col = base + tint
    col = col * (0.70 + 0.40 * np.clip(h, 0, 1.2)[..., None])
    dirt = periodic_noise(H, W, 30, seed + 3)[..., None]
    dark = np.array([0.18, 0.13, 0.09], np.float32)
    g = (1 - groove)[..., None]
    col = col * (1 - 0.75 * g) + dark * 0.75 * g
    col = col * (0.70 + 0.45 * dirt)
    wear = np.clip(1 - rr * 1.3, 0, 1)[..., None]
    col = col + 0.06 * wear
    lichen = np.clip((periodic_noise(H, W, 40, seed + 4) - 0.72) * 4, 0, 1)[..., None]
    col = col * (1 - 0.15 * lichen) + np.array([0.50, 0.46, 0.38]) * 0.15 * lichen
    # luz ocluida en surcos
    ao = np.clip(0.55 + 0.45 * groove - 0.3 * ring, 0.3, 1)[..., None]
    col *= ao

    rough = np.clip(0.72 + 0.2 * (1 - groove) + 0.05 * fine, 0, 1)
    return to_img(col), normal_from_height(h, 14.0), mr_img(rough), (W, H)

# ---------------------------------------------------------------- textura de piel
def skin_texture(S=512, seed=11):
    n1 = periodic_noise(S, S, 18, seed)
    n2 = periodic_noise(S, S, 5, seed + 1)
    n3 = periodic_noise(S, S, 60, seed + 2)
    wr = 1 - np.abs(2 * n2 - 1)          # arrugas tipo cresta
    h = 0.6 * wr ** 3 + 0.3 * n1 + 0.1 * n3
    base = np.array([0.36, 0.28, 0.22], np.float32)
    col = base * (0.75 + 0.45 * h[..., None]) * (0.9 + 0.2 * n3[..., None])
    rough = np.clip(0.8 + 0.15 * wr, 0, 1)
    return to_img(col), normal_from_height(h, 10.0), mr_img(rough)

SHELL_C, SHELL_N, SHELL_MR, (TW, TH) = shell_texture()
SKIN_C, SKIN_N, SKIN_MR = skin_texture()
TILE_W, TILE_H = 0.24, 0.24 * TH / TW   # metros que cubre una repetición de textura (4 placas de ancho)

def _mat_shell():
    return PBRMaterial(name="coraza", baseColorTexture=SHELL_C, normalTexture=SHELL_N,
                       metallicRoughnessTexture=SHELL_MR, metallicFactor=0.0, roughnessFactor=1.0,
                       doubleSided=True)

def _mat_skin():
    return PBRMaterial(name="piel", baseColorTexture=SKIN_C, normalTexture=SKIN_N,
                       metallicRoughnessTexture=SKIN_MR, metallicFactor=0.0, roughnessFactor=1.0,
                       doubleSided=True)

_MS = None
_MK = None
def mat_shell():
    global _MS
    _MS = _MS or _mat_shell()
    return _MS
def mat_skin():
    global _MK
    _MK = _MK or _mat_skin()
    return _MK

parts = []

# ---------------------------------------------------------------- CORAZA
A_Z, A_X, A_Y = 0.56, 0.37, 0.44     # semiejes (largo, ancho, alto)
YC = 0.26                             # altura del centro del elipsoide
TH0, TH1 = 0.42, 0.50                 # aberturas delantera (cabeza) y trasera (cola)
PHIM = 1.98                           # cuánto baja el borde por los costados

def shell_fn(U, V, inset=0.0):
    th = TH0 + U * (np.pi - TH0 - TH1)          # 0 = adelante (+Z)
    ph = (2 * V - 1) * PHIM                      # 0 = lomo
    s = np.sin(th)
    # domo un poco más alto atrás y apenas aplanado en el lomo
    hump = 1 + 0.07 * np.cos(th - 2.0)
    cph = np.sign(np.cos(ph)) * np.abs(np.cos(ph)) ** 0.85
    sph = np.sign(np.sin(ph)) * np.abs(np.sin(ph)) ** 0.9
    x = (A_X - inset) * s * sph
    y = YC + (A_Y - inset) * s * cph * hump
    z = (A_Z - inset) * np.cos(th)
    # borde anterior y posterior levantado ("escotaduras")
    return np.stack([x, y, z], 1)

lu, lv = arc_scale(shell_fn)
shell, uv = surface(shell_fn, 140, 160, uv_scale=(lu / TILE_H, lv / TILE_W))
uv = uv[:, ::-1]  # u (largo) sobre el eje vertical de la textura
parts.append(("coraza", textured(shell, uv, mat_shell())))

# cara interna oscura (para que no se vea "hueco" desde abajo)
inner, uvi = surface(lambda U, V: shell_fn(U, V, inset=0.025), 60, 60)
inner.invert()
parts.append(("coraza_interior", textured(inner, uvi, mat_flat([0.10, 0.07, 0.05], 1.0, "interior"))))

# reborde: hilera de osteodermos marginales más grandes y salientes
def rim_points():
    out = []
    for side in (-1, 1):
        for U in np.linspace(0.0, 1.0, 26):
            p = shell_fn(np.array([U]), np.array([0.0 if side < 0 else 1.0]))[0]
            q = shell_fn(np.array([U]), np.array([0.03 if side < 0 else 0.97]))[0]
            out.append((p, p - q))
    for V in np.linspace(0.04, 0.96, 18):
        for U, sgn in ((0.0, 1), (1.0, -1)):
            p = shell_fn(np.array([U]), np.array([V]))[0]
            q = shell_fn(np.array([U + 0.02 * sgn]), np.array([V]))[0]
            out.append((p, p - q))
    return out

rim = []
for p, d in rim_points():
    d = d / (np.linalg.norm(d) + 1e-9)
    c = trimesh.creation.icosphere(subdivisions=2, radius=1)
    c.vertices *= [0.026, 0.026, 0.014]
    c.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], d))
    c.apply_translation(p + d * 0.002)
    rim.append(c)
rim = trimesh.util.concatenate(rim)
rim_uv = box_uv(rim, TILE_W * 0.6)
parts.append(("borde", textured(rim, rim_uv, mat_shell())))

# ---------------------------------------------------------------- vientre (piel, apenas visible)
def belly_fn(U, V):
    th = 0.35 + U * (np.pi - 0.7); ph = (2 * V - 1) * np.pi / 2
    return np.stack([0.33 * np.sin(th) * np.sin(ph),
                     0.22 - 0.10 * np.sin(th) * np.cos(ph),
                     0.50 * np.cos(th)], 1)
belly, uvb = surface(belly_fn, 40, 30, uv_scale=(4, 3))
belly.invert()
parts.append(("vientre", textured(belly, uvb, mat_skin())))

# ---------------------------------------------------------------- PATAS

legs_meshes = []
claws = {}
HIPS = []
for sx in (-1, 1):
    for front in (True, False):
        leg_id = len(HIPS)
        z = 0.32 if front else -0.30
        x = sx * (0.15 if front else 0.16)
        r_top = 0.08 if front else 0.095
        HIPS.append(np.array([x, 0.34, z]))
        m, u = tube([x, 0.34, z], [x * 1.05, 0.05, z + (0.02 if front else 0.0)], r_top, 0.07, bulge=0.012)
        legs_meshes.append(textured(m, u, mat_skin()))
        # pie
        foot = trimesh.creation.icosphere(subdivisions=3, radius=1)
        foot.vertices *= [0.075, 0.042, 0.085]
        foot.vertices[:, 1] = np.maximum(foot.vertices[:, 1], -0.03)
        foot.apply_translation([x * 1.05, 0.03, z + 0.03])
        fuv = (foot.vertices[:, [0, 2]] * 6) % 1
        legs_meshes.append(textured(foot, fuv, mat_skin()))
        # uñas
        for k in range(4 if front else 5):
            ang = np.deg2rad(-35 + 70 * k / ((3 if front else 4)))
            c = trimesh.creation.cone(radius=0.014, height=0.045 if front else 0.03, sections=10)
            c.apply_transform(trimesh.transformations.rotation_matrix(np.deg2rad(100), [1, 0, 0]))
            c.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 1, 0]))
            c.apply_translation([x * 1.05 + 0.065 * np.sin(ang), 0.022, z + 0.03 + 0.085 * np.cos(ang)])
            claws.setdefault(leg_id, []).append(c)
for i, m in enumerate(legs_meshes):
    parts.append((f"pata_{i}", m))
MAT_UNAS = mat_flat([0.12, 0.09, 0.07], 0.7, "unas")
for leg_id, cl in claws.items():
    c = trimesh.util.concatenate(cl)
    parts.append((f"unas_{leg_id}", textured(c, np.zeros((len(c.vertices), 2)), MAT_UNAS)))

# ---------------------------------------------------------------- CABEZA
HC = np.array([0.0, 0.25, 0.58])      # centro del cráneo
def head_fn(U, V):
    th = U * np.pi; ph = V * 2 * np.pi
    x = np.sin(th) * np.cos(ph); y = np.sin(th) * np.sin(ph); z = np.cos(th)
    # cráneo corto y alto, hocico profundo que baja hacia adelante
    sx = 0.105 - 0.025 * np.clip(z, 0, 1)
    sy = 0.115 + 0.02 * np.clip(-y, 0, 1)
    sz = 0.15
    X = x * sx; Y = y * sy; Z = z * sz
    Y = Y - 0.05 * np.clip(z, 0, 1) ** 2           # hocico hacia abajo
    Y = Y - 0.035 * np.clip(-y, 0, 1) * np.clip(z + 0.3, 0, 1)  # mandíbula profunda
    return HC + np.stack([X, Y, Z], 1)
head, uvh = surface(head_fn, 48, 48, uv_scale=(2, 4))
parts.append(("cabeza", textured(head, uvh, mat_skin())))

# casquete cefálico (escudo óseo sobre la frente)
def cap_fn(U, V):
    th = U * 0.95; ph = V * 2 * np.pi
    x = np.sin(th) * np.cos(ph); z = np.sin(th) * np.sin(ph); y = np.cos(th)
    return HC + [0, 0.012, 0.015] + np.stack([x * 0.112, y * 0.128, z * 0.13], 1)
cap, uvc = surface(cap_fn, 20, 40)
cap_uv = box_uv(cap, TILE_W * 0.5)
parts.append(("casquete", textured(cap, cap_uv, mat_shell())))

# ojos, narinas, orejas
dark = []
for sx in (-1, 1):
    e = trimesh.creation.icosphere(subdivisions=3, radius=0.011)
    e.apply_translation(HC + [sx * 0.083, 0.03, 0.075])
    dark.append(e)
    n = trimesh.creation.icosphere(subdivisions=2, radius=0.01)
    n.vertices *= [1, 0.6, 1]
    n.apply_translation(HC + [sx * 0.022, -0.052, 0.146])
    dark.append(n)
parts.append(("ojos", textured(d := trimesh.util.concatenate(dark),
                               np.zeros((len(d.vertices), 2)), mat_flat([0.03, 0.025, 0.02], 0.15, "ojos"))))
ears = []
for sx in (-1, 1):
    ear = trimesh.creation.icosphere(subdivisions=2, radius=1)
    ear.vertices *= [0.012, 0.03, 0.022]
    ear.apply_transform(trimesh.transformations.rotation_matrix(sx * 0.5, [0, 0, 1]))
    ear.apply_translation(HC + [sx * 0.095, 0.09, -0.04])
    ears.append(ear)
ears = trimesh.util.concatenate(ears)
parts.append(("orejas", textured(ears, (ears.vertices[:, [0, 1]] * 8) % 1, mat_skin())))

# cuello (une cabeza con el cuerpo, bajo la coraza)
neck, uvn = tube([0, 0.27, 0.36], HC + [0, 0.0, -0.06], 0.13, 0.095, n_len=8)
parts.append(("cuello", textured(neck, uvn, mat_skin())))

# ---------------------------------------------------------------- COLA: anillos + tubo caudal
tail_parts = []
z0, y0 = -0.50, 0.30
r = 0.125
pos = np.array([0, y0, z0])
direction = np.array([0, -0.18, -1.0]); direction /= np.linalg.norm(direction)
for i in range(4):
    L = 0.065
    p1 = pos + direction * L
    m, u = tube(pos, p1, r, r * 0.9, n_len=4, n_rad=28)
    u[:, 1] *= 2.5
    tail_parts.append(textured(m, u, mat_shell()))
    # tubérculos cónicos en el anillo
    for k in range(12):
        a = 2 * np.pi * k / 12 + i * 0.3
        nrm = np.array([np.cos(a), np.sin(a), 0.0])
        c = trimesh.creation.cone(radius=0.020 * (1 - i * 0.1), height=0.016, sections=10)
        c.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], nrm))
        c.apply_translation(pos + direction * L * 0.6 + nrm * r * 0.9)
        tail_parts.append(textured(c, box_uv(c, TILE_W * 0.35) + 0.37, mat_shell()))
    pos = p1 + direction * 0.008
    r *= 0.88
# tubo caudal terminal
p1 = pos + direction * 0.17
m, u = tube(pos, p1, r, r * 0.55, n_len=10, n_rad=28)
u[:, 0] *= 2; u[:, 1] *= 2
tail_parts.append(textured(m, u, mat_shell()))
cap_end = trimesh.creation.icosphere(subdivisions=2, radius=r * 0.55)
cap_end.apply_translation(p1)
tail_parts.append(textured(cap_end, (cap_end.vertices[:, :2] * 20) % 1, mat_shell()))
for side in (-1, 1):
    for k in range(4):
        t = 0.15 + k * 0.22
        c = trimesh.creation.cone(radius=0.022, height=0.02, sections=10)
        nrm = np.array([side, 0.15, 0.0]); nrm /= np.linalg.norm(nrm)
        c.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], nrm))
        c.apply_translation(pos + direction * 0.17 * t + nrm * r * (1 - 0.45 * t))
        tail_parts.append(textured(c, box_uv(c, TILE_W * 0.35) + 0.37, mat_shell()))
for i, m in enumerate(tail_parts):
    parts.append((f"cola_{i}", m))


# ---------------------------------------------------------------- escena con pivotes (para animar)
floor = -min(m.bounds[0][1] for _, m in parts)
HEAD_PIV = HC + np.array([0.0, 0.0, -0.10])   # donde la cabeza se une al cuello
TAIL_PIV = np.array([0.0, 0.30, -0.50])       # base de la cola

def group_of(name):
    if name.startswith("pata_"):
        return f"pata{int(name.split('_')[1]) // 2}"
    if name.startswith("unas_"):
        return f"pata{int(name.split('_')[1])}"
    if name in ("cabeza", "casquete", "ojos", "orejas"):
        return "cabeza"
    if name.startswith("cola_"):
        return "cola"
    return "cuerpo"

# patas: 0 = del. izq, 1 = tras. izq, 2 = del. der, 3 = tras. der
pivots = {"raiz": np.zeros(3), "cuerpo": np.zeros(3), "cabeza": HEAD_PIV, "cola": TAIL_PIV}
for k, h in enumerate(HIPS):
    pivots[f"pata{k}"] = h
parent = {"cuerpo": "raiz", "cabeza": "cuerpo", "cola": "cuerpo", **{f"pata{k}": "raiz" for k in range(4)}}
GROUPS = ["cuerpo", "cabeza", "cola"] + [f"pata{k}" for k in range(4)]

scene, local_t = build_scene(parts, GROUPS, parent, pivots, group_of, Tm([0, floor, 0]))
glb = scene.export(file_type="glb")

# ---------------------------------------------------------------- animaciones (keyframes glTF)
def anim_caminar():
    P = 1.4
    t = np.linspace(0, P, 29)
    ph = 2 * np.pi * t / P
    ch = {}
    fase = {0: 0.0, 3: 0.0, 1: np.pi, 2: np.pi}      # pares diagonales
    for k in range(4):
        ch[(f"pata{k}", "rotation")] = [quat([1, 0, 0], 0.32 * np.sin(p + fase[k])) for p in ph]
    ch[("cuerpo", "translation")] = [local_t["cuerpo"] + [0, 0.007 * np.cos(2 * p), 0.0] for p in ph]
    ch[("cuerpo", "rotation")] = [quat([0, 0, 1], 0.025 * np.sin(p)) for p in ph]
    ch[("cabeza", "rotation")] = [qmul(quat([0, 1, 0], 0.06 * np.sin(p)), quat([1, 0, 0], 0.05 * np.sin(2 * p) + 0.05)) for p in ph]
    ch[("cola", "rotation")] = [quat([0, 1, 0], 0.20 * np.sin(p + 0.6)) for p in ph]
    return "caminar", t, ch

def anim_pastar():
    P = 8.0
    t = np.linspace(0, P, 65)
    w = 2 * np.pi * t / P
    ch = {}
    yaw = 0.38 * np.sin(w)                                  # mira a un lado y al otro
    pitch = 0.32 * np.clip(np.sin(2 * w), 0, 1) ** 2 + 0.03  # baja a comer dos veces
    sniff = 0.025 * np.sin(12 * w)                           # olfatea
    ch[("cabeza", "rotation")] = [qmul(quat([0, 1, 0], y), quat([1, 0, 0], p + s)) for y, p, s in zip(yaw, pitch, sniff)]
    ch[("cola", "rotation")] = [quat([0, 1, 0], 0.12 * np.sin(3 * x)) for x in w]
    ch[("cuerpo", "translation")] = [local_t["cuerpo"] + [0, 0.005 * np.sin(4 * x), 0.0] for x in w]
    return "pastar", t, ch


out = add_animations(glb, [anim_pastar(), anim_caminar()], GROUPS + ["raiz"])
open(OUT, "wb").write(out)
chk = trimesh.load(OUT)
b = chk.bounds
print("ok", OUT, f"{len(out)/1e6:.1f} MB", "medidas m:", np.round(b[1] - b[0], 2))
