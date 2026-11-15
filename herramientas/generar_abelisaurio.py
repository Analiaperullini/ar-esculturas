"""Abelisaurio (dinosaurio carnívoro bípedo, grupo de Carnotaurus) — escultura del Parque San Martín,
San Salvador de Jujuy. Modelo 3D ilustrativo para AR basado en la escultura de Jorge González
(referencias/abelisaurio.png).

Metros, Y arriba, mira hacia +Z. El animal se modela parado en dos patas (pose neutra) y la pose de la
escultura se arma rotando las juntas: echado como un ave sentada sobre una roca, con el pecho levantado,
el cuello grueso en S y la cabeza en alto, las patas plegadas con las garras agarradas al borde de la
roca, los brazos diminutos y la cola apoyada atrás.
Animaciones: "reposo", "rugir" y "caminar" (se para y camina en el lugar).

Uso: python generar_abelisaurio.py [salida.glb]
"""
import sys
import numpy as np
import trimesh

from comun import (Loft, Elipsoide, Espejo, Roca, Modelo, Esqueleto, patron_roca, quat, qmul, giro,
                   resolver_pata, apoyar_cadena, verificar, minimo, canales, suavizar, smooth,
                   fbm3, worley3, mezcla, sumar)

# REVISAR con el paleontólogo: largo total de un abelisaurio adulto típico de Sudamérica
# (de la punta del hocico a la punta de la cola), en metros.
ESCALA = 6.5

OUT = sys.argv[1] if len(sys.argv) > 1 else "../modelos/abelisaurio.glb"
X = np.array([1.0, 0, 0])

# ================================================================ colores (de la escultura)
OSCURO = np.array([0.27, 0.29, 0.24])      # lomo y cola, gris oscuro verdoso
MUSGO = np.array([0.40, 0.42, 0.22])       # zonas verde oliva tipo musgo
CLARO = np.array([0.70, 0.67, 0.59])       # cara, mandíbula y garganta, gris claro beige
CRESTA = np.array([0.31, 0.27, 0.22])      # crestas rugosas sobre los ojos
BOCA = np.array([0.42, 0.15, 0.13])

# ================================================================ pivotes (pose neutra, parado)
H = np.array([0.32, 1.85, 0.02]); K = np.array([0.37, 1.05, 0.34]); A = np.array([0.37, 0.40, -0.02])
B = np.array([0.37, 0.07, 0.20]); T = np.array([0.37, 0.02, 0.62])          # cadera, rodilla, tobillo, dedos, punta
HEAD_O = np.array([0.0, 2.62, 1.92])
HF = np.array([0.0, -0.12, 0.993]); HF /= np.linalg.norm(HF)                # eje de la cabeza (adelante)
HU = np.cross(HF, X)                                                        # arriba de la cabeza
BISAGRA = HEAD_O + 1.25 * (HF * -0.06 + HU * -0.08)                         # articulación de la mandíbula
HOMBRO = np.array([0.28, 1.52, 1.08]); CODO = np.array([0.33, 1.33, 1.17])

def espejo(p):
    return np.asarray(p, float) * [-1, 1, 1]

PIV = {"raiz": np.zeros(3), "cuerpo": np.array([0, 1.85, 0.0]),
       "cuello1": np.array([0, 1.98, 1.30]), "cuello2": np.array([0, 2.28, 1.62]), "cabeza": HEAD_O,
       "mandibula": BISAGRA,
       "cola1": np.array([0, 1.95, -0.80]), "cola2": np.array([0, 1.90, -1.60]),
       "cola3": np.array([0, 1.78, -2.40]), "cola4": np.array([0, 1.65, -3.15])}
for lado, f in (("I", lambda p: np.asarray(p, float)), ("D", espejo)):
    PIV.update({f"muslo{lado}": f(H), f"pierna{lado}": f(K), f"pie{lado}": f(A), f"dedos{lado}": f(B),
                f"brazo{lado}": f(HOMBRO), f"antebrazo{lado}": f(CODO)})
PADRE = {"cuerpo": "raiz", "cuello1": "cuerpo", "cuello2": "cuello1", "cabeza": "cuello2", "mandibula": "cabeza",
         "cola1": "cuerpo", "cola2": "cola1", "cola3": "cola2", "cola4": "cola3"}
for lado in "ID":
    PADRE.update({f"muslo{lado}": "cuerpo", f"pierna{lado}": f"muslo{lado}", f"pie{lado}": f"pierna{lado}",
                  f"dedos{lado}": f"pie{lado}", f"brazo{lado}": "cuerpo", f"antebrazo{lado}": f"brazo{lado}"})
GRUPOS = list(PADRE)
COLA = ["cola1", "cola2", "cola3", "cola4"]

# ================================================================ geometría
M = Modelo()
M.nuevo_atlas("cuerpo", 1024, 512)
M.nuevo_atlas("roca", 1024, 256)
M.plano("ojo", [0.95, 0.60, 0.12], 0.25)
M.plano("pupila", [0.02, 0.02, 0.02], 0.2)
M.plano("una", [0.13, 0.12, 0.11], 0.5)
M.plano("diente", [0.86, 0.82, 0.70], 0.45)

CS = 1.25  # escala de la cabeza (la de la escultura es grande)

def fila_cabeza(t, h, rx, ru, rd, e=1.0, tp=0.0):
    return [*(HEAD_O + CS * (HF * t + HU * h)), CS * rx, CS * ru, CS * rd, e, tp]

#   columna: [x, y, z, semiancho, alto al lomo, alto al vientre, expo, afina]
torso = Loft([[0, 1.95, -0.95, .30, .32, .36, 1.0, .25],
              [0, 2.00, -0.45, .42, .38, .52, .95, .30],
              [0, 1.97, 0.10, .52, .40, .66, .92, .30],
              [0, 1.88, 0.62, .54, .38, .74, .92, .28],
              [0, 1.84, 1.02, .48, .36, .66, .95, .25],
              [0, 1.90, 1.32, .38, .33, .48, 1.0, .20],
              [0, 2.00, 1.50, .30, .28, .36]], s0=-0.95)
M.agregar("torso", "cuerpo", torso, 100, 64, "cuerpo")

# cuello grueso; cada tramo arranca en su pivote con una tapa redonda
M.agregar("cuello1", "cuello1", Loft([[0, 1.98, 1.30, .38, .33, .42], [0, 2.15, 1.48, .34, .30, .38],
                                      [0, 2.34, 1.68, .31, .28, .34]], s0=1.30), 30, 44, "cuello")
M.agregar("cuello2", "cuello2", Loft([[0, 2.28, 1.62, .31, .28, .34], [0, 2.48, 1.78, .29, .27, .31],
                                      [0, 2.66, 1.98, .27, .26, .28]], s0=1.62), 30, 44, "cuello")

# cabeza: cráneo corto y alto; la mandíbula es una pieza aparte (para rugir)
CRANEO = [(-0.10, 0.02, .22, .24, .10), (0.02, 0.03, .25, .29, .10), (0.18, 0.02, .24, .31, .10),
          (0.34, 0.00, .19, .28, .09), (0.48, -0.02, .15, .23, .08), (0.60, -0.04, .11, .16, .07),
          (0.66, -0.05, .08, .10, .06)]
MAND = [(-0.06, -0.10, .20, .05, .17), (0.10, -0.11, .21, .05, .18), (0.30, -0.12, .175, .05, .14),
        (0.48, -0.115, .135, .05, .10), (0.60, -0.10, .10, .05, .075), (0.665, -0.09, .075, .045, .055)]
M.agregar("craneo", "cabeza", Loft([fila_cabeza(*f, e=0.92) for f in CRANEO], cupula=(1.0, 0.8)), 60, 56,
          "cabeza", detalle=2.0)
M.agregar("mandibula", "mandibula", Loft([fila_cabeza(*f, e=0.92) for f in MAND], cupula=(1.0, 0.8)), 44, 40,
          "mandibula", detalle=2.0)

def en_cabeza(t, h, x=0.0):
    """Punto de la cabeza: t hacia adelante, h hacia arriba, x al costado (antes de escalar)."""
    return HEAD_O + CS * (HF * t + HU * h + X * x)

OJO = en_cabeza(0.20, 0.10, 0.205)
NARINA = en_cabeza(0.58, 0.05, 0.07)

def rugoso(seed, fuerza):
    return lambda d: fuerza * (fbm3(d * 3.0, 0.5, seed, 3) - 0.5)

for lado, f in (("I", lambda p: p), ("D", espejo)):
    M.agregar(f"ojo{lado}", "cabeza", Elipsoide(f(OJO), CS * np.array([0.046, 0.044, 0.046])), 16, 20, "ojo",
              material="ojo")
    M.agregar(f"pupila{lado}", "cabeza", Elipsoide(f(OJO + X * CS * 0.041), CS * np.array([0.009, 0.026, 0.012])),
              10, 14, "ojo", material="pupila")
    # crestas rugosas sobre los ojos
    M.agregar(f"cresta{lado}", "cabeza", Elipsoide(f(en_cabeza(0.12, 0.26, 0.13)), CS * np.array([0.055, 0.035, 0.15]),
                                                   deform=rugoso(41, 0.035)), 22, 26, "cresta", detalle=1.5)
    M.agregar(f"ceja{lado}", "cabeza", Elipsoide(f(en_cabeza(0.24, 0.19, 0.175)), CS * np.array([0.045, 0.03, 0.09]),
                                                 deform=rugoso(43, 0.025)), 16, 20, "cresta", detalle=1.5)

# dientes: arriba apuntan hacia abajo y abajo hacia arriba; con la boca cerrada quedan adentro
def lerp_tabla(tabla, t, k):
    ts = [f[0] for f in tabla]
    return np.interp(t, ts, [f[k] for f in tabla])

dientes_sup, dientes_inf = [], []
for lado in (1, -1):
    for t in np.linspace(0.12, 0.48, 7):
        base = en_cabeza(t, lerp_tabla(CRANEO, t, 1) - 0.85 * lerp_tabla(CRANEO, t, 4),
                         lado * 0.55 * lerp_tabla(CRANEO, t, 2))
        dientes_sup.append((base, -HU, CS * 0.048))
    for t in np.linspace(0.14, 0.44, 6):
        base = en_cabeza(t, lerp_tabla(MAND, t, 1) + 0.6 * lerp_tabla(MAND, t, 3), lado * 0.50 * lerp_tabla(MAND, t, 2))
        dientes_inf.append((base, HU, CS * 0.036))

def cono(base, eje, largo, radio):
    c = trimesh.creation.cone(radius=radio, height=largo, sections=8)
    c.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], eje))
    c.apply_translation(base)
    return c

DIENTES = {"dientes_sup": ("cabeza", trimesh.util.concatenate([cono(b, e, l, 0.014) for b, e, l in dientes_sup])),
           "dientes_inf": ("mandibula", trimesh.util.concatenate([cono(b, e, l, 0.011) for b, e, l in dientes_inf]))}

# brazos diminutos
brazo = Loft([[0.24, 1.56, 1.06, .075, .075, .075], [0.30, 1.45, 1.11, .065, .065, .065],
              [0.33, 1.33, 1.17, .055, .055, .055]])
antebrazo = Loft([[0.33, 1.34, 1.17, .05, .05, .05], [0.34, 1.26, 1.24, .042, .042, .042],
                  [0.345, 1.20, 1.30, .036, .03, .03]])
M.agregar("brazoI", "brazoI", brazo, 16, 16, "pata")
M.agregar("brazoD", "brazoD", Espejo(brazo), 16, 16, "pata", comparte="brazoI")
M.agregar("antebrazoI", "antebrazoI", antebrazo, 14, 14, "pata")
M.agregar("antebrazoD", "antebrazoD", Espejo(antebrazo), 14, 14, "pata", comparte="antebrazoI")

# patas traseras (lado izquierdo = +X; el derecho es el espejo y comparte la textura)
pata = {
    "muslo": Loft([[0.22, 2.12, -0.05, .26, .30, .34], [0.32, 1.82, 0.06, .30, .34, .40],
                   [0.36, 1.40, 0.22, .19, .19, .21], [0.37, 1.07, 0.33, .13, .13, .13]]),
    "pierna": Loft([[0.37, 1.10, 0.34, .13, .13, .14], [0.37, 0.75, 0.17, .11, .10, .13],
                    [0.37, 0.42, -0.01, .08, .075, .075]]),
    "pie": Loft([[0.37, 0.44, -0.02, .085, .08, .08], [0.37, 0.24, 0.09, .078, .066, .066],
                 [0.37, 0.08, 0.19, .085, .062, .062]]),
}
for nombre, forma in pata.items():
    zona = "pie" if nombre == "pie" else "pata"
    M.agregar(f"{nombre}I", f"{nombre}I", forma, 30, 28, zona)
    M.agregar(f"{nombre}D", f"{nombre}D", Espejo(forma), 30, 28, zona, comparte=f"{nombre}I")
DEDOS = {"dedo_m": (np.array([0.37, 0.045, 0.60]), 0.06), "dedo_i": (np.array([0.27, 0.045, 0.50]), 0.052),
         "dedo_e": (np.array([0.47, 0.045, 0.50]), 0.052)}
for nombre, (punta, r) in DEDOS.items():
    base = B + [0, 0.0, 0.0]
    medio = (base + punta) / 2 + [0, 0.012, 0]
    forma = Loft([[*base, r * 1.2, r, r], [*medio, r, r * 0.85, r * 0.85], [*punta, r * 0.8, r * 0.7, r * 0.7]],
                 cupula=(1.0, 0.9))
    M.agregar(f"{nombre}I", "dedosI", forma, 18, 16, "pie", detalle=1.5)
    M.agregar(f"{nombre}D", "dedosD", Espejo(forma), 18, 16, "pie", comparte=f"{nombre}I")
    # garra larga y curva
    d = (punta - base) / np.linalg.norm(punta - base)
    g = Loft([[*(punta - d * 0.01), r * 0.6, r * 0.6, r * 0.6], [*(punta + d * 0.08 + [0, -0.02, 0]), r * 0.42, r * 0.45, r * 0.4],
              [*(punta + d * 0.13 + [0, -0.08, 0]), r * 0.12, r * 0.12, r * 0.12]], cupula=(1.0, 0.6))
    M.agregar(f"garra_{nombre}I", "dedosI", g, 14, 10, "una", material="una")
    M.agregar(f"garra_{nombre}D", "dedosD", Espejo(g), 14, 10, "una", material="una")

cola = [Loft([[0, 1.95, -0.80, .30, .36, .40, .95, .3], [0, 1.95, -1.20, .25, .31, .33, .95, .3],
              [0, 1.90, -1.72, .20, .26, .27, .95, .3]], s0=-0.80),
        Loft([[0, 1.90, -1.60, .21, .27, .28, .95, .3], [0, 1.85, -2.00, .17, .21, .22, .95, .3],
              [0, 1.78, -2.50, .13, .16, .16]], s0=-1.60),
        Loft([[0, 1.78, -2.40, .14, .17, .17], [0, 1.71, -2.75, .10, .12, .12], [0, 1.66, -3.22, .07, .085, .085]],
             s0=-2.40),
        Loft([[0, 1.65, -3.15, .075, .09, .09], [0, 1.60, -3.50, .045, .05, .05], [0, 1.55, -3.92, .018, .02, .02]],
             s0=-3.15)]
for k, c in enumerate(cola):
    M.agregar(f"cola{k + 1}", f"cola{k + 1}", c, [40, 36, 30, 24][k], [40, 32, 28, 20][k], "cola")

# roca de la base: larga, para que entre la cola. Su borde de adelante se ubica más abajo, donde
# quedan los dedos en la pose de la escultura (así las garras se agarran del borde)
ROCA = Roca(centro=(0.0, -2.0), rx=1.25, rz=2.35, alto=0.38, seed=12)
TOP = ROCA.alto

# ================================================================ patrón de color y relieve (horneado)
OJOS = [OJO, espejo(OJO)]
NARINAS = [NARINA, espejo(NARINA)]

def mezclar(a, b, t):
    return a * (1 - t[:, None]) + b * t[:, None]

def patron_animal(P, N, info, zona):
    n = len(P)
    d, s = info["dorsal"], info["s"]
    var = fbm3(P, 0.4, 51, 4)
    fino = fbm3(P, 0.05, 52, 3)
    col = OSCURO * (0.85 + 0.3 * var[:, None]) * np.ones((n, 1))
    # manchas de musgo en el lomo, los flancos y la cola
    musgo = smooth(0.56, 0.72, fbm3(P + 3.1, 0.30, 53, 4)) * smooth(-0.4, 0.2, d)
    if zona in ("cuerpo", "cola", "cuello", "pata"):
        col = mezclar(col, MUSGO * (0.85 + 0.3 * fino[:, None]), 0.6 * musgo)
    # cara, mandíbula y garganta claras; vientre algo más claro
    if zona == "cabeza":
        claro = smooth(0.55, 0.15, d)
        col = mezclar(col, CLARO * (0.9 + 0.15 * var[:, None]), claro)
    elif zona == "mandibula":
        col = CLARO * (0.88 + 0.18 * var[:, None]) * np.ones((n, 1))
    elif zona == "cuello":
        col = mezclar(col, CLARO * (0.9 + 0.15 * var[:, None]), smooth(-0.05, -0.45, d))
    elif zona == "cuerpo":
        col = mezclar(col, CLARO * 0.85 * (0.9 + 0.15 * var[:, None]), smooth(-0.45, -0.80, d))
    elif zona == "pie":
        col = col * 0.8
    if zona == "cresta":
        col = CRESTA * (0.75 + 0.5 * fbm3(P, 0.02, 55, 3)[:, None]) * np.ones((n, 1))
    # boca por dentro (solo se ve al rugir)
    boca = np.zeros(n)
    if zona == "cabeza":
        boca = smooth(-0.80, -0.92, d)
    elif zona == "mandibula":
        boca = smooth(0.78, 0.92, d)
    col = mezclar(col, BOCA * (0.85 + 0.3 * fino[:, None]), boca)
    if zona == "cabeza":
        dn = np.min([np.linalg.norm(P - o, axis=1) for o in NARINAS], 0)
        col = mezclar(col, np.array([0.10, 0.09, 0.08]), smooth(0.035, 0.022, dn))
        de = np.min([np.linalg.norm(P - o, axis=1) for o in OJOS], 0)
        col = col * (1 - 0.35 * smooth(0.085, 0.05, de))[:, None]          # párpado oscuro
    # escamas tipo guijarro, tubérculos en el lomo y piel muy arrugada
    cell = {"cabeza": 0.022, "mandibula": 0.022, "pie": 0.024, "pata": 0.03, "cresta": 0.018}.get(zona, 0.036)
    F1, F2, cid = worley3(P, cell, 61)
    guijarro = smooth(0.0, 0.22, F2 - F1) * (1 - 0.6 * F1)
    h = 0.003 * guijarro
    col = col * ((0.78 + 0.22 * guijarro) * (0.94 + 0.12 * cid))[:, None]
    if zona in ("cuerpo", "cola", "cuello"):
        G1, G2, gid = worley3(P, 0.11, 62)
        tuberculo = (gid > 0.72) * smooth(0.45, 0.15, G1) * smooth(0.0, 0.5, d)
        h = h + 0.012 * tuberculo
        col = col * (1 - 0.15 * tuberculo)[:, None]
    arruga = 1 - np.abs(2 * fbm3(P, 0.09, 63, 3) - 1)
    h = h - 0.004 * arruga ** 4
    if zona in ("cuello", "mandibula"):                 # pliegues del cuello
        pl = 1 - np.abs(np.sin(np.pi * s / 0.06 + 3.0 * (fbm3(P, 0.2, 64, 3) - 0.5)))
        pl = pl ** 3 * (1.0 if zona == "cuello" else 0.5)
        h = h - 0.007 * pl
        col = col * (1 - 0.25 * pl)[:, None]
    if zona == "cresta":
        h = h + 0.008 * fbm3(P, 0.015, 65, 3)
    h = h * (1 - boca)
    rough = 0.8 - 0.25 * boca
    return np.clip(col, 0, 1), h, rough

# las piezas de dientes no son superficies paramétricas: se agregan directo como mallas planas
for nombre, (grupo, malla) in DIENTES.items():
    class _F:
        wrap_v = False
        largo_u = largo_v = 0.1
    p = M.agregar(nombre, grupo, _F(), 2, 2, "diente", material="diente")
    p.malla_fija = malla

# ================================================================ esqueleto y poses
esq = Esqueleto(GRUPOS, PADRE, PIV)
locales = M.preparar(PIV)
ANIMAL = [n for n in locales if n != "roca"]

def juntas_tras(f):
    return [f(H), f(K), f(A), f(B), f(T)]

def pose(p):
    """Pose a partir de parámetros: cuerpo (alto, z, cabeceo), cuello, cabeza, mandíbula, cola, brazos y patas."""
    rot, tras = {}, {}
    tras["cuerpo"] = np.array([0.0, TOP + p["alto"], p["z"]])
    rot["cuerpo"] = quat([1, 0, 0], p["cabeceo"])
    rot["cuello1"] = giro(p["c1"][1], p["c1"][0])
    rot["cuello2"] = giro(p["c2"][1], p["c2"][0])
    rot["cabeza"] = giro(p["cab"][1], p["cab"][0])
    rot["mandibula"] = quat([1, 0, 0], p["boca"])
    for k, g in enumerate(COLA):
        rot[g] = giro(p["cola"][k][1], p["cola"][k][0])
    for lado, sx in (("I", 1), ("D", -1)):
        rot[f"brazo{lado}"] = giro(0.0, p["brazo"], sx * 0.15)
        rot[f"antebrazo{lado}"] = quat([1, 0, 0], p["antebrazo"])
    W = esq.mundo(rot, tras)
    for lado, f in (("I", lambda q: np.asarray(q, float)), ("D", espejo)):
        ty, tz = p["tobillo" + lado]
        rot.update(resolver_pata(esq, W, [f"muslo{lado}", f"pierna{lado}", f"pie{lado}", f"dedos{lado}"],
                                 juntas_tras(f), [0, TOP + ty, tz], [p["meta" + lado], p["dedos" + lado]], True))
        # echado, las patas se abren a los costados de la panza (como un ave sentada)
        sx = 1 if lado == "I" else -1
        rot[f"muslo{lado}"] = qmul(quat([0, 0, 1], sx * p.get("abre", 0.0)), rot[f"muslo{lado}"])
    return rot, tras

# ---------------------------------------------------------------- pose de la escultura (echado)
SENTADO = {"alto": 0.70, "z": 0.0, "cabeceo": -0.60,
           "c1": (-0.70, 0.0), "c2": (0.25, 0.0), "cab": (0.68, 0.0), "boca": 0.0,
           "cola": [(0.0, 0.0), (0.0, -0.06), (0.0, -0.08), (0.0, -0.10)],
           "brazo": 0.35, "antebrazo": -0.6,
           "abre": 0.50, "tobilloI": (0.0, -0.15), "tobilloD": (0.0, -0.15),
           "metaI": np.pi / 2 + 0.06, "metaD": np.pi / 2 + 0.06,
           "dedosI": np.pi / 2 + 0.55, "dedosD": np.pi / 2 + 0.55}

def acomodar_cola(p):
    rot, tras = pose(p)
    puntos = [PIV["cola2"], PIV["cola3"], PIV["cola4"], np.array([0, 1.55, -3.92])]
    radios = [0.27, 0.16, 0.085, 0.02]
    rot, pitches = apoyar_cadena(esq, rot, tras, COLA, [c[1] for c in p["cola"]], puntos,
                                 [TOP + r + 0.01 for r in radios], rango=(-0.8, 1.6))
    q = dict(p); q["cola"] = [(pt, c[1]) for pt, c in zip(pitches, p["cola"])]
    return q

def ajustar_alto(p, nombres=("torso", "musloI", "musloD", "piernaI", "piernaD"), objetivo=0.03):
    lo, hi = 0.2, 2.5
    for _ in range(30):
        mid = (lo + hi) / 2
        q = dict(p); q["alto"] = mid
        r, t = pose(q)
        if minimo(esq, locales, r, t, nombres, ROCA.piso) < objetivo:
            lo = mid
        else:
            hi = mid
    q = dict(p); q["alto"] = hi
    return q

SENTADO = ajustar_alto(SENTADO)

def ubicar_roca():
    """Corre la roca para que su borde de adelante quede justo delante de la base de los dedos."""
    r, t = pose(SENTADO)
    bola = esq.punto(esq.mundo(r, t), "dedosI", B)
    ph = np.arctan2(1.0, bola[0] / ROCA.rx)              # ángulo del borde a la altura del pie
    borde = ROCA.borde(np.array([ph]))[0] * np.sin(ph) * ROCA.rz
    ROCA.cz = bola[2] + 0.05 - borde

ubicar_roca()
M.agregar("roca", "raiz", ROCA, 90, 120, "roca", atlas="roca")
locales = M.preparar(PIV)
SENTADO = acomodar_cola(SENTADO)

# ---------------------------------------------------------------- pose parada (para caminar)
ZP = SENTADO["z"] - 0.30
PARADO = {"alto": H[1] + 0.01, "z": ZP, "cabeceo": 0.0, "abre": 0.0,
          "c1": (-0.12, 0.0), "c2": (0.04, 0.0), "cab": (0.10, 0.0), "boca": 0.0,
          "cola": [(0.05, 0.0), (0.03, 0.0), (0.02, 0.0), (0.02, 0.0)],
          "brazo": 0.2, "antebrazo": -0.5,
          "tobilloI": (A[1] + 0.01, ZP + A[2] - H[2]), "tobilloD": (A[1] + 0.01, ZP + A[2] - H[2]),
          "metaI": np.arctan2(B[2] - A[2], B[1] - A[1]), "metaD": np.arctan2(B[2] - A[2], B[1] - A[1]),
          "dedosI": np.arctan2(T[2] - B[2], T[1] - B[1]), "dedosD": np.arctan2(T[2] - B[2], T[1] - B[1])}

# ================================================================ animaciones
FPS = 15

def anim_reposo():
    P = 8.0
    ts = np.linspace(0, P, int(P * FPS) + 1)
    poses = []
    for t in ts:
        w, r = 2 * np.pi * t / P, 2 * np.pi * t / 4.0           # mira alrededor / respira
        p = sumar(SENTADO, alto=0.015 * np.sin(r), cabeceo=-0.012 * np.sin(r),
                  c1=(0.0, 0.16 * np.sin(w)), c2=(0.02 * np.sin(r), 0.12 * np.sin(w - 0.4)),
                  cab=(0.05 * np.sin(r + 0.5), 0.22 * np.sin(w - 0.8)),
                  brazo=0.08 * np.sin(r), antebrazo=0.10 * np.sin(r + 1),
                  cola=[(0, 0.04 * np.sin(w + 0.6 * k)) for k in range(4)])
        poses.append(pose(p))
    return "reposo", ts, poses

def anim_rugir():
    P = 5.0
    ts = np.linspace(0, P, int(P * FPS) + 1)
    poses = []
    for t in ts:
        sube = suavizar((t - 0.2) / 1.0) * (1 - suavizar((t - 3.6) / 1.1))     # levanta la cabeza
        abre = suavizar((t - 1.0) / 0.5) * (1 - suavizar((t - 3.0) / 0.5))      # abre y cierra la boca
        tiembla = 0.04 * np.sin(2 * np.pi * t * 6) * abre
        p = sumar(SENTADO, alto=0.08 * sube, cabeceo=-0.10 * sube,
                  c1=(-0.22 * sube, 0.0), c2=(-0.12 * sube, tiembla), cab=(-0.28 * sube - 0.06 * abre, tiembla),
                  boca=0.62 * abre, brazo=0.15 * abre, antebrazo=-0.2 * abre,
                  cola=[(0.12 * sube if k == 0 else 0.0, 0.05 * np.sin(2 * np.pi * t / 2.5 + 0.6 * k) * sube)
                        for k in range(4)])
        poses.append(pose(p))
    return "rugir", ts, poses

def anim_caminar():
    sube, paso, ciclos = 1.6, 1.3, 3
    P = 2 * sube + paso * ciclos
    ts = np.linspace(0, P, int(P * FPS) + 1)
    poses = []
    for t in ts:
        b = suavizar(t / sube) * (1 - suavizar((t - sube - paso * ciclos) / sube))
        p = mezcla(SENTADO, PARADO, b)
        arco = 0.12 * np.sin(np.pi * np.clip(b, 0, 1))          # al pararse, los pies se reacomodan
        for k in ("tobilloI", "tobilloD"):
            p[k] = (p[k][0] + arco, p[k][1])
        if sube < t < sube + paso * ciclos:                       # camina en el lugar
            fase = 2 * np.pi * (t - sube) / paso
            lev = lambda f: 0.20 * max(0.0, np.sin(f)) ** 1.5
            p["tobilloI"] = (p["tobilloI"][0] + lev(fase), p["tobilloI"][1] + 0.05 * np.sin(fase))
            p["tobilloD"] = (p["tobilloD"][0] + lev(fase + np.pi), p["tobilloD"][1] + 0.05 * np.sin(fase + np.pi))
            p = sumar(p, alto=0.03 * np.cos(2 * fase), c1=(0.04 * np.sin(2 * fase), 0.06 * np.sin(fase)),
                      cab=(-0.04 * np.sin(2 * fase), -0.07 * np.sin(fase)),
                      cola=[(0.0, 0.10 * np.sin(fase + 0.5 * k)) for k in range(4)])
        poses.append(pose(p))
    return "caminar", ts, poses

# ================================================================ verificación y exportación
if __name__ == "__main__":
    todas = [anim_reposo(), anim_rugir(), anim_caminar()]
    rest_rot, rest_tras = pose(SENTADO)
    problemas = []
    rep, pr = verificar(esq, locales, [("pose escultura", rest_rot, rest_tras)], ROCA.piso, ignorar=("roca",))
    problemas += pr
    print("pose escultura: distancia mínima al piso %.1f cm (%s)" % (100 * rep[0][1], rep[0][2]))
    for nombre, ts, poses in todas:
        rep, pr = verificar(esq, locales, [(f"{nombre} t={t:.2f}", r, tr) for t, (r, tr) in zip(ts, poses)],
                            ROCA.piso, ignorar=("roca",))
        problemas += pr
        peor = min(rep, key=lambda x: x[1])
        print(f"{nombre}: peor distancia al piso {100 * peor[1]:.1f} cm ({peor[2]}, {peor[0]})")
    for nombres, etiqueta in ((["pieI", "dedo_mI"], "pie izq."), (["garra_dedo_mI"], "garra"),
                              (["cola3", "cola4"], "punta de cola"), (["torso", "musloI"], "panza/muslo")):
        print(f"  apoyo {etiqueta}: {100 * minimo(esq, locales, rest_rot, rest_tras, nombres, ROCA.piso):.1f} cm")
    if problemas:
        print("PROBLEMAS:\n  " + "\n  ".join(problemas[:20]))

    Vn = np.vstack([M.mallas[n].vertices for n in ANIMAL])
    largo_base = Vn[:, 2].max() - Vn[:, 2].min()
    k = ESCALA / largo_base
    raiz = np.diag([k, k, k, 1.0])
    anims = [(n, ts, canales(ts, poses, GRUPOS)) for n, ts, poses in todas]
    glb = M.exportar(OUT, GRUPOS, PADRE, PIV, raiz, rest_rot, rest_tras, anims,
                     {"cuerpo": patron_animal, "roca": patron_roca})
    chk = trimesh.load(OUT)
    b = chk.bounds
    print("ok", OUT, f"{len(glb) / 1e6:.2f} MB", "largo del animal: %.2f m" % (largo_base * k),
          "medidas de la escultura (ancho x alto x largo) m:", np.round(b[1] - b[0], 2))
