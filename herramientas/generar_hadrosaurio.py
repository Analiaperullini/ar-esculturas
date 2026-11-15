"""Hadrosaurio (dinosaurio "pico de pato") — escultura del Parque San Martín, San Salvador de Jujuy.
Modelo 3D ilustrativo para AR basado en la escultura de Jorge González (referencias/hadrosaurio.png).

Metros, Y arriba, mira hacia +Z. El animal se modela parado en cuatro patas (pose neutra) y la pose
de la escultura se arma rotando las juntas: agachado sobre una roca, patas delanteras rectas apoyadas
adelante, traseras flexionadas bajo el cuerpo, cuello largo levantado y la cola enroscada al costado.
Animaciones: "reposo", "pastar" y "caminar" (en cuatro patas, sin desplazarse).

Uso: python generar_hadrosaurio.py [salida.glb]
"""
import sys
import numpy as np
import trimesh

from comun import (Loft, Elipsoide, Espejo, Roca, Modelo, Esqueleto, patron_roca, quat, giro,
                   resolver_pata, apoyar_cadena, verificar, minimo, canales, suavizar, smooth,
                   fbm3, worley3, mezcla, sumar)

# REVISAR con el paleontólogo: largo total de un hadrosaurio adulto típico de Sudamérica
# (de la punta del pico a la punta de la cola), en metros.
ESCALA = 7.0

OUT = sys.argv[1] if len(sys.argv) > 1 else "../modelos/hadrosaurio.glb"
X = np.array([1.0, 0, 0])

# ================================================================ colores (de la escultura)
VERDE = np.array([0.42, 0.50, 0.23])        # lomo y flancos, verde musgo
VERDE_OSC = np.array([0.20, 0.26, 0.12])    # rayas verticales
CREMA = np.array([0.86, 0.82, 0.66])        # garganta, cuello por delante y panza
NARANJA = np.array([0.85, 0.35, 0.16])      # pico ancho
VERDE_OJO = np.array([0.34, 0.60, 0.19])    # mancha alrededor del ojo

# ================================================================ pivotes (pose neutra, en cuatro patas)
H = np.array([0.42, 2.00, 0.02]); K = np.array([0.47, 1.20, 0.40]); A = np.array([0.47, 0.42, 0.06])
B = np.array([0.47, 0.10, 0.28]); T = np.array([0.47, 0.03, 0.64])          # cadera, rodilla, tobillo, dedos, punta
S = np.array([0.40, 1.68, 1.55]); E = np.array([0.45, 1.06, 1.36]); Wm = np.array([0.45, 0.36, 1.52])
Mt = np.array([0.45, -0.04, 1.68])                                         # hombro, codo, muñeca, punta de la mano
HEAD_O = np.array([0.0, 2.64, 2.80])
HF = np.array([0.0, -0.29, 0.957]); HF /= np.linalg.norm(HF)                # eje de la cabeza (adelante)
HU = np.array([0.0, 0.957, 0.29]); HU /= np.linalg.norm(HU)                 # arriba de la cabeza

def espejo(p):
    return np.asarray(p, float) * [-1, 1, 1]

PIV = {"raiz": np.zeros(3), "cuerpo": np.array([0, 2.00, 0.0]),
       "cuello1": np.array([0, 1.95, 1.75]), "cuello2": np.array([0, 2.20, 2.15]),
       "cuello3": np.array([0, 2.45, 2.50]), "cabeza": HEAD_O,
       "cola1": np.array([0, 2.15, -0.95]), "cola2": np.array([0, 2.06, -1.80]),
       "cola3": np.array([0, 1.92, -2.55]), "cola4": np.array([0, 1.80, -3.03])}
for lado, f in (("I", lambda p: np.asarray(p, float)), ("D", espejo)):
    PIV.update({f"muslo{lado}": f(H), f"pierna{lado}": f(K), f"pie{lado}": f(A), f"dedos{lado}": f(B),
                f"brazo{lado}": f(S), f"antebrazo{lado}": f(E), f"mano{lado}": f(Wm)})
PADRE = {"cuerpo": "raiz", "cuello1": "cuerpo", "cuello2": "cuello1", "cuello3": "cuello2", "cabeza": "cuello3",
         "cola1": "cuerpo", "cola2": "cola1", "cola3": "cola2", "cola4": "cola3"}
for lado in "ID":
    PADRE.update({f"muslo{lado}": "cuerpo", f"pierna{lado}": f"muslo{lado}", f"pie{lado}": f"pierna{lado}",
                  f"dedos{lado}": f"pie{lado}", f"brazo{lado}": "cuerpo", f"antebrazo{lado}": f"brazo{lado}",
                  f"mano{lado}": f"antebrazo{lado}"})
GRUPOS = list(PADRE)          # ordenados de padres a hijos
COLA = ["cola1", "cola2", "cola3", "cola4"]

# ================================================================ geometría
M = Modelo()
M.nuevo_atlas("cuerpo", 1024, 512)
M.nuevo_atlas("roca", 1024, 256)
M.plano("ojo", [0.93, 0.66, 0.12], 0.25)
M.plano("pupila", [0.02, 0.02, 0.02], 0.2)
M.plano("una", [0.16, 0.14, 0.12], 0.55)

def cabeza_fila(t, h, rx, ru, rd, e=1.0, tp=0.0):
    p = HEAD_O + HF * t + HU * h
    return [*p, rx, ru, rd, e, tp]

#   columna: [x, y, z, semiancho, alto al lomo, alto al vientre, expo, afina]
torso = Loft([[0, 2.12, -1.15, .30, .32, .36, 1.0, .25],
              [0, 2.22, -0.65, .52, .42, .62, .95, .30],
              [0, 2.20, -0.05, .70, .46, .90, .92, .32],
              [0, 2.06, 0.55, .76, .44, .98, .92, .28],
              [0, 1.92, 1.15, .68, .40, .86, .95, .28],
              [0, 1.86, 1.62, .50, .36, .62, 1.0, .20],
              [0, 1.92, 1.95, .36, .30, .40, 1.0, .10]], s0=-1.15)
M.agregar("torso", "cuerpo", torso, 110, 64, "cuerpo")

# el primer tramo arranca en su pivote con una tapa redonda: puede girar mucho sin asomar del pecho
cuellos = [Loft([[0, 1.95, 1.75, .40, .34, .44, 1, .12], [0, 2.06, 1.97, .36, .30, .41, 1, .10],
                 [0, 2.24, 2.24, .33, .27, .37]], s0=1.75),
           Loft([[0, 2.12, 2.08, .34, .28, .39], [0, 2.32, 2.33, .30, .25, .33],
                 [0, 2.50, 2.57, .27, .23, .29]], s0=2.00),
           Loft([[0, 2.40, 2.44, .28, .24, .30], [0, 2.58, 2.70, .24, .21, .25],
                 [0, 2.70, 2.92, .22, .19, .23]], s0=2.40)]
for k, c in enumerate(cuellos):
    M.agregar(f"cuello{k + 1}", f"cuello{k + 1}", c, 32, 44, "cuello")

CS = 1.45  # escala de la cabeza (la de la escultura es grande)
cabeza = Loft([cabeza_fila(CS * -0.06, CS * 0.00, CS * .15, CS * .16, CS * .17, .95),
               cabeza_fila(CS * 0.08, CS * 0.01, CS * .16, CS * .17, CS * .18, .90),
               cabeza_fila(CS * 0.26, CS * 0.00, CS * .14, CS * .15, CS * .17, .90),
               cabeza_fila(CS * 0.45, CS * -0.03, CS * .11, CS * .11, CS * .13, .90),
               cabeza_fila(CS * 0.62, CS * -0.07, CS * .115, CS * .075, CS * .095, .85),
               cabeza_fila(CS * 0.76, CS * -0.10, CS * .13, CS * .05, CS * .06, .80),
               cabeza_fila(CS * 0.84, CS * -0.11, CS * .115, CS * .035, CS * .045, .80)], cupula=(1.0, 0.8))
M.agregar("cabeza", "cabeza", cabeza, 70, 48, "cabeza", detalle=2.0)

OJO = HEAD_O + HF * CS * 0.27 + HU * CS * 0.06 + X * CS * 0.122
NARINA = HEAD_O + HF * CS * 0.66 + HU * CS * -0.035 + X * CS * 0.075
for lado, f in (("I", lambda p: p), ("D", espejo)):
    M.agregar(f"ojo{lado}", "cabeza", Elipsoide(f(OJO), [0.05, 0.048, 0.05]), 16, 20, "ojo", material="ojo")
    M.agregar(f"pupila{lado}", "cabeza", Elipsoide(f(OJO + X * 0.045), [0.01, 0.025, 0.019]), 10, 14, "ojo",
              material="pupila")

cola = [Loft([[0, 2.18, -0.80, .30, .38, .44, .95, .3], [0, 2.15, -1.30, .25, .34, .36, .95, .3],
              [0, 2.08, -1.80, .20, .28, .29, .95, .3], [0, 2.05, -1.95, .19, .27, .28, .95, .3]], s0=-0.80),
        Loft([[0, 2.08, -1.70, .20, .28, .29, .95, .3], [0, 1.99, -2.15, .16, .22, .22, .95, .3],
              [0, 1.92, -2.55, .12, .16, .16], [0, 1.90, -2.65, .115, .15, .15]], s0=-1.70),
        Loft([[0, 1.93, -2.47, .125, .165, .165], [0, 1.85, -2.85, .09, .11, .11],
              [0, 1.80, -3.05, .07, .085, .085], [0, 1.79, -3.10, .068, .08, .08]], s0=-2.47),
        Loft([[0, 1.80, -2.98, .07, .085, .085], [0, 1.75, -3.25, .045, .05, .05],
              [0, 1.72, -3.40, .02, .022, .022]], s0=-2.98)]
for k, c in enumerate(cola):
    M.agregar(f"cola{k + 1}", f"cola{k + 1}", c, [44, 36, 28, 24][k], [40, 32, 28, 20][k], "cola")

# patas (lado izquierdo = +X; el derecho es el espejo y comparte la textura)
pata = {
    "muslo": Loft([[0.30, 2.34, -0.04, .30, .36, .40], [0.42, 1.98, 0.05, .38, .44, .50],
                   [0.46, 1.55, 0.26, .24, .25, .27], [0.47, 1.22, 0.39, .16, .16, .16]]),
    "pierna": Loft([[0.47, 1.26, 0.40, .18, .18, .19], [0.47, 0.85, 0.25, .15, .14, .19],
                    [0.47, 0.45, 0.07, .11, .10, .10]]),
    "pie": Loft([[0.47, 0.46, 0.06, .10, .09, .09], [0.47, 0.26, 0.17, .095, .08, .08],
                 [0.47, 0.10, 0.28, .10, .07, .07]]),
    "brazo": Loft([[0.30, 1.88, 1.55, .24, .26, .26], [0.40, 1.66, 1.53, .22, .23, .24],
                   [0.44, 1.33, 1.44, .16, .16, .16], [0.45, 1.08, 1.37, .13, .13, .13]]),
    "antebrazo": Loft([[0.45, 1.10, 1.37, .13, .13, .13], [0.45, 0.72, 1.44, .105, .11, .105],
                       [0.45, 0.38, 1.52, .085, .085, .085]]),
    "mano": Loft([[0.45, 0.40, 1.52, .085, .085, .085], [0.45, 0.14, 1.58, .095, .095, .085],
                  [0.45, 0.0, 1.65, .11, .10, .07]], cupula=(1.0, 0.7)),
}
dedos = {"dedo_m": [[0.47, 0.10, 0.28, .065, .05, .05], [0.47, 0.06, 0.46, .058, .042, .042],
                    [0.47, 0.045, 0.60, .052, .034, .036]],
         "dedo_i": [[0.44, 0.10, 0.27, .055, .045, .045], [0.40, 0.06, 0.42, .05, .038, .038],
                    [0.38, 0.045, 0.54, .045, .032, .034]],
         "dedo_e": [[0.50, 0.10, 0.27, .055, .045, .045], [0.54, 0.06, 0.42, .05, .038, .038],
                    [0.56, 0.045, 0.54, .045, .032, .034]]}
grupo_pata = {"muslo": "muslo", "pierna": "pierna", "pie": "pie", "brazo": "brazo", "antebrazo": "antebrazo",
              "mano": "mano"}
for nombre, forma in pata.items():
    zona = "pie" if nombre in ("pie", "mano") else "pata"
    M.agregar(f"{nombre}I", f"{grupo_pata[nombre]}I", forma, 30, 28, zona)
    M.agregar(f"{nombre}D", f"{grupo_pata[nombre]}D", Espejo(forma), 30, 28, zona, comparte=f"{nombre}I")
for nombre, filas in dedos.items():
    forma = Loft(filas, cupula=(1.0, 0.9))
    M.agregar(f"{nombre}I", "dedosI", forma, 18, 16, "pie", detalle=1.5)
    M.agregar(f"{nombre}D", "dedosD", Espejo(forma), 18, 16, "pie", comparte=f"{nombre}I")
# uñas tipo pezuña en las puntas de los dedos y de la mano
UNAS_PIE = [(np.array([0.47, 0.04, 0.63]), [0.05, 0.03, 0.045]), (np.array([0.375, 0.04, 0.565]), [0.042, 0.027, 0.04]),
            (np.array([0.565, 0.04, 0.565]), [0.042, 0.027, 0.04])]
UNAS_MANO = [(np.array([0.45 + dx, -0.025, 1.725]), [0.036, 0.028, 0.034]) for dx in (-0.06, 0.0, 0.06)]
for lado, f in (("I", lambda p: p), ("D", espejo)):
    for k, (c, r) in enumerate(UNAS_PIE):
        M.agregar(f"una_pie{k}{lado}", f"dedos{lado}", Elipsoide(f(c), r), 10, 14, "una", material="una")
    for k, (c, r) in enumerate(UNAS_MANO):
        M.agregar(f"una_mano{k}{lado}", f"mano{lado}", Elipsoide(f(c), r), 10, 14, "una", material="una")

# roca de la base
ROCA = Roca(centro=(0.35, 0.05), rx=1.85, rz=2.50, alto=0.35, seed=8)
TOP = ROCA.alto
M.agregar("roca", "raiz", ROCA, 90, 120, "roca", atlas="roca")

# ================================================================ patrón de color y relieve (horneado)
OJOS = [OJO, espejo(OJO)]
NARINAS = [NARINA, espejo(NARINA)]

def mezclar(a, b, t):
    return a * (1 - t[:, None]) + b * t[:, None]

def patron_animal(P, N, info, zona):
    n = len(P)
    d, s = info["dorsal"], info["s"]
    var = fbm3(P, 0.35, 11, 4)
    fino = fbm3(P, 0.05, 12, 3)
    col = VERDE * (0.84 + 0.30 * var[:, None]) * np.ones((n, 1))
    if zona in ("cuerpo", "cuello", "cola"):          # rayas oscuras verticales
        lam = {"cuerpo": 0.30, "cuello": 0.20, "cola": 0.24}[zona]
        fase = s / lam + 1.4 * (fbm3(P, 0.25, 13, 3) - 0.5)
        raya = smooth(0.55, 0.78, 0.5 + 0.5 * np.sin(2 * np.pi * fase)) * smooth(-0.30, 0.30, d)
        col = mezclar(col, VERDE_OSC * (0.9 + 0.2 * var[:, None]), 0.6 * raya)
    if zona == "pata":
        col = col * (0.92 + 0.08 * d[:, None])
    if zona == "pie":
        col = col * 0.85
    if zona in ("cuerpo", "cuello", "cabeza", "cola"):   # panza, garganta y cuello por delante: crema
        lim = {"cuerpo": -0.50, "cuello": -0.25, "cabeza": -0.30, "cola": -0.70}[zona]
        crema = smooth(lim + 0.22, lim - 0.18, d) * (0.85 + 0.3 * fino)
        col = mezclar(col, CREMA * (0.92 + 0.12 * var[:, None]), np.clip(crema, 0, 1))
    pico = np.zeros(n)
    if zona == "cabeza":
        u = info["u"]
        de = np.min([np.linalg.norm(P - o, axis=1) for o in OJOS], 0)
        col = mezclar(col, VERDE_OJO * (0.9 + 0.2 * fino[:, None]), smooth(0.105, 0.065, de))
        pico = smooth(0.70, 0.76, u)
        col = mezclar(col, NARANJA * (0.92 + 0.16 * fino[:, None]), pico)
        dn = np.min([np.linalg.norm(P - o, axis=1) for o in NARINAS], 0)
        col = mezclar(col, np.array([0.18, 0.08, 0.05]), smooth(0.032, 0.02, dn))
    # escamas finas (celdas) y arrugas
    cell = {"cabeza": 0.016, "pie": 0.02, "pata": 0.026}.get(zona, 0.03)
    F1, F2, cid = worley3(P, cell, 21)
    borde = smooth(0.0, 0.2, F2 - F1)
    h = 0.0022 * borde + 0.0006 * (cid - 0.5)
    col = col * ((0.84 + 0.16 * borde) * (0.95 + 0.1 * cid))[:, None]
    if zona in ("cuello", "cabeza"):                  # pliegues marcados del cuello y la garganta
        w = 1 - np.abs(np.sin(np.pi * s / 0.055 + 3.0 * (fbm3(P, 0.2, 31, 3) - 0.5)))
        w = w ** 3 * (1.0 if zona == "cuello" else smooth(0.35, 0.15, info["u"]))
        w = w * (0.5 + 0.5 * smooth(0.3, -0.5, d))
        h = h - 0.006 * w
        col = col * (1 - 0.22 * w)[:, None]
    h = h * (1 - pico) + 0.0006 * fino * pico
    rough = 0.78 - 0.25 * pico - 0.05 * borde
    return np.clip(col, 0, 1), h, rough

# ================================================================ esqueleto y poses
esq = Esqueleto(GRUPOS, PADRE, PIV)
locales = M.preparar(PIV)
ANIMAL = [n for n in locales if n != "roca"]

def juntas_tras(f):
    return [f(H), f(K), f(A), f(B), f(T)]

def juntas_del(f):
    return [f(S), f(E), f(Wm), f(Mt)]

def pose(p):
    """Pose a partir de parámetros: cuerpo (alto, z, cabeceo), cuello, cabeza, cola y apoyos de las patas."""
    rot, tras = {}, {}
    tras["cuerpo"] = np.array([0.0, TOP + p["alto"], p["z"]])
    rot["cuerpo"] = quat([1, 0, 0], p["cabeceo"])
    rot["cuello1"] = giro(p["c1"][1], p["c1"][0])
    rot["cuello2"] = giro(p["c2"][1], p["c2"][0])
    rot["cuello3"] = giro(p["c3"][1], p["c3"][0])
    rot["cabeza"] = giro(p["cab"][1], p["cab"][0])
    for k, g in enumerate(COLA):
        rot[g] = giro(p["cola"][k][1], p["cola"][k][0])
    W = esq.mundo(rot, tras)
    for lado, f in (("I", lambda q: np.asarray(q, float)), ("D", espejo)):
        ty, tz = p["tobillo" + lado]
        rot.update(resolver_pata(esq, W, [f"muslo{lado}", f"pierna{lado}", f"pie{lado}", f"dedos{lado}"],
                                 juntas_tras(f), [0, TOP + ty, tz], [p["meta" + lado], p["dedos" + lado]], True))
        wy, wz = p["muneca" + lado]
        rot.update(resolver_pata(esq, W, [f"brazo{lado}", f"antebrazo{lado}", f"mano{lado}"],
                                 juntas_del(f), [0, TOP + wy, wz], [p["mano" + lado]], False))
    return rot, tras

# ---------------------------------------------------------------- pose de la escultura (sentado)
SENTADO = {"alto": 0.80, "z": -0.30, "cabeceo": -0.75,
           "c1": (-0.50, 0.0), "c2": (0.14, 0.0), "c3": (0.20, 0.0), "cab": (0.80, 0.0),
           "cola": [(0.0, 0.0), (0.0, -0.95), (0.0, -1.05), (0.0, -0.95)],
           "tobilloI": (0.11, -0.70), "tobilloD": (0.11, -0.70),
           "metaI": np.pi / 2 + 0.08, "metaD": np.pi / 2 + 0.08,
           "dedosI": np.pi / 2 + 0.05, "dedosD": np.pi / 2 + 0.05,
           "munecaI": (0.44, 1.22), "munecaD": (0.44, 1.22),
           "manoI": 2.85, "manoD": 2.85}

# la cola se apoya sola sobre la roca: cada tramo baja hasta tocar la piedra
def acomodar_cola(p):
    rot, tras = pose(p)
    puntos = [PIV["cola2"], PIV["cola3"], PIV["cola4"], np.array([0, 1.72, -3.40])]
    radios = [0.28, 0.16, 0.085, 0.03]
    rot, pitches = apoyar_cadena(esq, rot, tras, COLA, [c[1] for c in p["cola"]], puntos,
                                 [TOP + r + 0.01 for r in radios], rango=(-0.8, 1.6))
    q = dict(p); q["cola"] = [(pt, c[1]) for pt, c in zip(pitches, p["cola"])]
    return q

# la cadera baja hasta que la panza y el anca apenas tocan la roca
def ajustar_alto(p, nombres=("torso", "musloI", "musloD"), objetivo=0.03):
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

# las patas delanteras quedan casi rectas con la mano apoyada; si no llegan, el cuerpo se endereza un poco
def apoyar_manos(p):
    alcance = 0.985 * (np.linalg.norm(E - S) + np.linalg.norm(Wm - E))
    q = dict(p)
    for _ in range(40):
        q = ajustar_alto(q)
        r, t = pose(q)
        hombro = esq.punto(esq.mundo(r, t), "cuerpo", S)
        dy = hombro[1] - (TOP + q["munecaI"][0])
        if dy < alcance:
            dz = min(np.sqrt(alcance ** 2 - dy ** 2), 0.40)
            q["munecaI"] = q["munecaD"] = (q["munecaI"][0], hombro[2] + dz)
            return q
        q["cabeceo"] += 0.02
    raise RuntimeError("las manos no llegan a la roca")

SENTADO = acomodar_cola(apoyar_manos(SENTADO))

# ---------------------------------------------------------------- pose parada (para caminar)
PARADO = {"alto": 2.00 - 0.0, "z": -0.35, "cabeceo": 0.02,
          "c1": (-0.32, 0.0), "c2": (0.06, 0.0), "c3": (0.06, 0.0), "cab": (0.28, 0.0),
          "cola": [(0.12, 0.0), (0.05, 0.0), (0.04, 0.0), (0.03, 0.0)],
          "tobilloI": (A[1], -0.35 + A[2] - H[2] + 0.02), "tobilloD": (A[1], -0.35 + A[2] - H[2] + 0.02),
          "metaI": np.arctan2(B[2] - A[2], B[1] - A[1]), "metaD": np.arctan2(B[2] - A[2], B[1] - A[1]),
          "dedosI": np.arctan2(T[2] - B[2], T[1] - B[1]), "dedosD": np.arctan2(T[2] - B[2], T[1] - B[1]),
          "munecaI": (Wm[1] + 0.06, -0.35 + Wm[2]), "munecaD": (Wm[1] + 0.06, -0.35 + Wm[2]),
          "manoI": np.arctan2(Mt[2] - Wm[2], Mt[1] - Wm[1]), "manoD": np.arctan2(Mt[2] - Wm[2], Mt[1] - Wm[1])}

# ================================================================ animaciones
FPS = 15

def anim_reposo():
    P = 8.0
    ts = np.linspace(0, P, int(P * FPS) + 1)
    poses = []
    for t in ts:
        w, r = 2 * np.pi * t / P, 2 * np.pi * t / 4.0           # mira alrededor / respira
        p = sumar(SENTADO, alto=0.012 * np.sin(r), cabeceo=-0.008 * np.sin(r),
                  c1=(0.0, 0.14 * np.sin(w)), c2=(0.02 * np.sin(r), 0.10 * np.sin(w - 0.3)),
                  c3=(0.02 * np.sin(r), 0.08 * np.sin(w - 0.6)),
                  cab=(0.05 * np.sin(r + 0.5), 0.16 * np.sin(w - 0.9)),
                  cola=[(0, 0.04 * np.sin(w + 0.6 * k)) for k in range(4)])
        poses.append(pose(p))
    return "reposo", ts, poses

# pastar: el cuerpo se inclina, el cuello baja y el pico toca el piso (la roca o el suelo, delante).
# La pose se busca con un optimizador y después la cola se vuelve a apoyar sobre la roca.
PUNTA_PICO = HEAD_O + HF * CS * 0.86 + HU * CS * -0.11
X_PASTAR = [0.063, 2.279, -0.084, -0.16, -0.89]   # última solución (inclinación, cuello 1-3, cabeza)

def con_cuello(p, x, b=1.0, cola=None):
    dcab, c1, c2, c3, cab = x
    q = dict(p)
    q["cabeceo"] = p["cabeceo"] + dcab * b
    q["c1"] = (p["c1"][0] + c1 * b, p["c1"][1]); q["c2"] = (p["c2"][0] + c2 * b, p["c2"][1])
    q["c3"] = (p["c3"][0] + c3 * b, p["c3"][1]); q["cab"] = (p["cab"][0] + cab * b, p["cab"][1])
    if cola is not None:
        q["cola"] = [(a0 * (1 - b) + a1 * b, y0) for (a0, y0), (a1, _) in zip(p["cola"], cola)]
    return q

def pose_pastar():
    from scipy.optimize import minimize
    resto = [n for n in ANIMAL if not n.startswith(("cabeza", "ojo", "pupila", "cola"))]
    def costo(x):
        r, t = pose(con_cuello(SENTADO, x))
        W = esq.mundo(r, t)
        punta = esq.punto(W, "cabeza", PUNTA_PICO)
        eje = W["cabeza"][:3, :3] @ HF
        alto_punta = punta[1] - ROCA.piso(np.array([punta[0]]), np.array([punta[2]]))[0]
        c = 20 * (alto_punta - 0.06) ** 2 + 0.5 * (np.arctan2(eje[2], eje[1]) - 2.75) ** 2
        c += 0.2 * x[0] ** 2 + 50 * max(0.0, x[0] - 0.6) ** 2
        c += 0.4 * (x[2] ** 2 + x[3] ** 2) + 0.1 * x[4] ** 2            # que doble sobre todo desde la base
        c += 5 * max(0.0, punta[2] - ROCA.cz - 0.85 * ROCA.rz) ** 2      # que coma sobre la roca
        c += 30 * max(0.0, SENTADO["munecaI"][1] + 0.40 - punta[2]) ** 2  # y delante de las manos
        c += 300 * max(0.0, 0.02 - minimo(esq, locales, r, t, resto, ROCA.piso)) ** 2
        c += 300 * max(0.0, 0.03 - minimo(esq, locales, r, t, ["cabeza"], ROCA.piso)) ** 2
        return c
    # primero refina la última solución conocida; si no sirve (cambió la geometría), busca desde cero
    mejor = minimize(costo, X_PASTAR, method="Nelder-Mead", options={"maxiter": 400, "xatol": 1e-3, "fatol": 1e-7})
    if mejor.fun > 0.2:
        azar = np.random.default_rng(3)
        for _ in range(9):
            x0 = azar.uniform([0, 1.2, -0.2, -0.2, -1.6], [0.6, 2.4, 0.5, 0.5, 0.4])
            res = minimize(costo, x0, method="Nelder-Mead", options={"maxiter": 900, "xatol": 1e-3, "fatol": 1e-7})
            if res.fun < mejor.fun:
                mejor = res
        print("  pastar: nueva solución", np.round(mejor.x, 3))
    x = mejor.x
    # la cola vuelve a apoyarse con el cuerpo inclinado
    q = acomodar_cola(con_cuello(SENTADO, x))
    return x, q["cola"]

def anim_pastar():
    P = 8.0
    x, cola = pose_pastar()
    ts = np.linspace(0, P, int(P * FPS) + 1)
    poses = []
    for t in ts:
        b = suavizar((t - 0.6) / 1.6) * (1 - suavizar((t - 5.6) / 1.8))      # baja, come y vuelve a subir
        come = 0.05 * np.sin(2 * np.pi * t * 1.5) * suavizar((t - 2.2) / 0.4) * (1 - suavizar((t - 5.2) / 0.4))
        p = con_cuello(SENTADO, x, b, cola)
        p = sumar(p, c1=(0.0, 0.06 * np.sin(2 * np.pi * t / P) * b), cab=(-come, 0.0),
                  cola=[(0, 0.05 * np.sin(2 * np.pi * t / 4 + 0.6 * k)) for k in range(4)])
        poses.append(pose(p))
    return "pastar", ts, poses

def anim_caminar():
    sube, paso, ciclos = 1.6, 1.2, 3
    P = 2 * sube + paso * ciclos
    ts = np.linspace(0, P, int(P * FPS) + 1)
    poses = []
    for t in ts:
        b = suavizar(t / sube) * (1 - suavizar((t - sube - paso * ciclos) / sube))
        p = mezcla(SENTADO, PARADO, b)
        # al pararse/sentarse las patas se reacomodan con un pasito (sin atravesar la roca)
        arco = 0.10 * np.sin(np.pi * np.clip(b, 0, 1))
        for k in ("tobilloI", "tobilloD", "munecaI", "munecaD"):
            p[k] = (p[k][0] + arco, p[k][1])
        # caminar en el lugar: pares diagonales levantan la pata y la vuelven a apoyar
        en = np.clip((t - sube) / (paso * ciclos), 0, 1)
        activo = 0 < en < 1
        fase = 2 * np.pi * (t - sube) / paso
        if activo:
            lev = lambda f: 0.16 * max(0.0, np.sin(f)) ** 1.5
            p["tobilloI"] = (p["tobilloI"][0] + lev(fase), p["tobilloI"][1])
            p["munecaD"] = (p["munecaD"][0] + lev(fase), p["munecaD"][1])
            p["tobilloD"] = (p["tobilloD"][0] + lev(fase + np.pi), p["tobilloD"][1])
            p["munecaI"] = (p["munecaI"][0] + lev(fase + np.pi), p["munecaI"][1])
            p = sumar(p, alto=0.025 * np.cos(2 * fase), c1=(0.03 * np.sin(2 * fase), 0.05 * np.sin(fase)),
                      cab=(-0.03 * np.sin(2 * fase), -0.05 * np.sin(fase)),
                      cola=[(0.0, 0.10 * np.sin(fase + 0.5 * k)) for k in range(4)])
        poses.append(pose(p))
    return "caminar", ts, poses

# ================================================================ verificación y exportación
if __name__ == "__main__":
    reposo, pastar, caminar = anim_reposo(), anim_pastar(), anim_caminar()
    todas = [reposo, pastar, caminar]

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
    # partes que deberían tocar: pies y manos apoyados en la pose de la escultura
    for nombres, etiqueta in ((["una_pie0I", "dedo_mI", "pieI"], "pie izq."), (["una_mano1I", "manoI"], "mano izq."),
                              (["cola3", "cola4"], "punta de cola"), (["torso", "musloI"], "panza/muslo")):
        print(f"  apoyo {etiqueta}: {100 * minimo(esq, locales, rest_rot, rest_tras, nombres, ROCA.piso):.1f} cm")
    if problemas:
        print("PROBLEMAS:\n  " + "\n  ".join(problemas[:20]))

    # escala real: el largo de referencia es el del animal en la pose neutra (sin la roca)
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
