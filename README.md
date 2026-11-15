# Esculturas que cobran vida

Sitio estático para ver esculturas de Jujuy en realidad aumentada desde un código QR.
HTML, CSS y JS puro: no hace falta instalar ni compilar nada.

```
index.html     → portada y ficha de cada escultura (index.html?e=<id>)
qr.html        → generador de carteles QR A5 para imprimir
esculturas.js  → datos de las esculturas
modelos/       → modelos 3D (.glb) y sus pósters (.webp)
herramientas/  → scripts que generan, validan y fotografían los modelos (no hacen falta para el sitio)
referencias/   → imágenes de las esculturas usadas como modelo (solo en la computadora, no se sube)
```

## Publicar en GitHub Pages

1. Creá un repositorio en GitHub y subí todos estos archivos (incluida la carpeta `modelos/`).
2. En el repositorio andá a **Settings → Pages**.
3. En **Build and deployment**, elegí **Source: Deploy from a branch**, rama **main** y carpeta **/ (root)**. Guardá.
4. En uno o dos minutos el sitio queda en `https://<tu-usuario>.github.io/<nombre-del-repo>/`.

## Probar desde el celular

- Abrí la dirección de GitHub Pages en el celular, por ejemplo
  `https://<tu-usuario>.github.io/<nombre-del-repo>/?e=gliptodonte`.
- La realidad aumentada **necesita HTTPS** (GitHub Pages ya lo tiene). Abriendo el archivo local o por `http://` en la red de tu casa, el modelo 3D se ve pero el botón de AR no aparece.
- **Android:** funciona en Chrome con Google Play Services for AR (ARCore).
- **iPhone/iPad:** funciona en Safari con iOS 12 o más nuevo (usa Quick Look).
- Si el celular no tiene AR, igual se puede girar y hacer zoom al modelo.

Para generar los carteles abrí `https://<tu-usuario>.github.io/<nombre-del-repo>/qr.html` (desde la dirección pública, así la URL base se completa sola), revisá la URL y tocá **Imprimir**. Se imprime un cartel A5 por hoja. Escaneá cada QR impreso antes de colgarlo.

## Sumar una escultura nueva

1. Subí el modelo a la carpeta `modelos/`, por ejemplo `modelos/condor.glb`.
   - Tiene que estar **en metros y a escala real**: el sitio lo muestra en tamaño real (`ar-scale="fixed"`).
     Si es muy grande para un living (más de 6 m), agregá `arEscala: "auto"` y la realidad aumentada lo ajusta.
   - Conviene que pese menos de 10–15 MB para que cargue rápido con datos móviles.
   - Para que funcione en iPhone sin un archivo `.usdz` aparte, model-viewer lo convierte solo.
2. Abrí `esculturas.js` y agregá un bloque nuevo dentro de la lista (ojo con la coma entre bloques):

```js
  {
    id: "condor",                       // va en la URL: ?e=condor (sin espacios ni acentos)
    nombre: "Cóndor andino",
    cientifico: "Vultur gryphus",
    lugar: "Plaza Belgrano, San Salvador de Jujuy",
    epoca: "Actual",
    tamano: "3 metros con las alas abiertas",
    modelo: "modelos/condor.glb",
    poster: "",                         // opcional: imagen mientras carga
    sonido: "",                         // opcional: ruta a un .mp3
    animacion: "",                      // opcional: nombre de la animación del .glb que arranca sola
    arEscala: "",                       // opcional: "auto" si en tamaño real no entra en el espacio
    texto: [
      "Primer párrafo.",
      "Segundo párrafo."
    ],
    credito: "Modelo 3D: Nombre Apellido"
  }
```

3. Subí los cambios a GitHub. La escultura aparece sola en la portada y en `qr.html`.

Si el `.glb` todavía no está subido, la ficha igual se muestra con un aviso en lugar del modelo.

Si el modelo tiene animaciones, debajo del visor aparece un botón por cada una. Los textos de los botones
salen del objeto `nombres` de `index.html` (por ejemplo `rugir` → "Rugir").

## Regenerar los modelos 3D (gliptodonte, hadrosaurio, abelisaurio)

Los tres modelos se generan con código, en `herramientas/`:

```
comun.py                  → funciones compartidas (formas, texturas, poses, exportación)
generar_gliptodonte.py    → gliptodonte
generar_hadrosaurio.py    → hadrosaurio (Parque San Martín)
generar_abelisaurio.py    → abelisaurio (Parque San Martín)
validar.mjs               → revisa los .glb con gltf-validator
capturas.mjs              → fotos desde 3 ángulos y 4 momentos de cada animación, y el póster
```

Una sola vez, para instalar lo necesario (Python 3.12 y Node):

```
cd herramientas
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
npm install
```

Para regenerar, validar y fotografiar un modelo (por ejemplo el hadrosaurio):

```
.venv/Scripts/python generar_hadrosaurio.py      # escribe ../modelos/hadrosaurio.glb
node validar.mjs ../modelos/hadrosaurio.glb      # no puede tener errores
node capturas.mjs hadrosaurio --poster           # capturas/ y ../modelos/hadrosaurio-poster.webp
```

El tamaño real de cada dinosaurio está en la constante `ESCALA` al principio de su script
(marcada "REVISAR con el paleontólogo"). Si se cambia, hay que regenerar el modelo y actualizar
el campo `tamano` en `esculturas.js`. Las capturas usan el Chrome instalado en la computadora.
