// Datos de las esculturas.
// Para sumar una nueva, copiá un bloque { ... } y cambiá los valores.
// El "id" es lo que va en la URL: index.html?e=<id> (sin espacios ni acentos).
// "poster", "sonido", "animacion" y "arEscala" son opcionales: si no los tenés, borrá la línea o dejala vacía.
// arEscala: "auto" deja que la realidad aumentada achique el modelo si no entra; sin el campo, se ve en tamaño real.

// "?v=2" al final de un archivo: obliga al navegador a bajar la versión nueva (subí el número cada vez que cambies el modelo).
window.ESCULTURAS = [
  {
    id: "gliptodonte",
    nombre: "Gliptodonte",
    cientifico: "Cranithlastus xibiensis",
    lugar: "Parque Xibi Xibi, San Salvador de Jujuy",
    epoca: "Hace unos 6 millones de años",
    tamano: "Entre 100 y 300 kg",
    modelo: "modelos/gliptodonte.glb",
    poster: "modelos/gliptodonte-poster.webp",
    animacion: "pastar",   // opcional: animación inicial del modelo ("pastar" o "caminar")
    sonido: "",
    texto: [
      "No era un dinosaurio: era un mamífero acorazado del grupo de los cingulados, parientes de las mulitas y los quirquinchos. Los gliptodontes vivieron en América del Sur desde hace unos 35 millones de años hasta hace menos de 10.000 años.",
      "Cranithlastus xibiensis lleva el nombre del río Xibi Xibi, y sus restos se conocen solo en Jujuy y Salta. Pesaba entre 100 y 300 kg: mucho menos que su pariente pampeano Doedicurus, que pudo superar los 2.000 kg.",
      "¿Cómo sabemos su edad? En las barrancas del Xibi Xibi hay capas de ceniza volcánica que permiten fechar a esta fauna en unos 6 millones de años.",
      "Si encontrás un fósil, no lo saques ni lo toques: está protegido por la Ley Nacional 25.743 y la Ley Provincial 5.751. Avisá a la Dirección de Patrimonio de Jujuy."
    ],
    credito: "Información: «Gliptodontes jujeños», Municipalidad de San Salvador de Jujuy (textos de J. S. Salgado-Ahumada, S. González-Patagua, J. P. Villalba Ulberich, A. Álvarez, M. Ercoli y A. Rivero). Modelo 3D ilustrativo."
  },
  {
    id: "hadrosaurio",
    nombre: "Hadrosaurio",
    cientifico: "Hadrosauridae",
    lugar: "Parque San Martín, San Salvador de Jujuy",
    epoca: "Hace unos 66 a 70 millones de años",
    tamano: "Unos 7 m de largo",   // REVISAR con el paleontólogo (es la ESCALA de herramientas/generar_hadrosaurio.py)
    modelo: "modelos/hadrosaurio.glb?v=4",
    poster: "modelos/hadrosaurio-poster.webp?v=4",
    animacion: "reposo",
    arEscala: "auto",              // mide más de 6 m: en realidad aumentada se ajusta para entrar en el espacio
    sonido: "",
    texto: [
      "Este dinosaurio herbívoro vivió en el período Cretácico, hace unos 66 a 70 millones de años.",
      "En Jujuy no se encontraron huesos de hadrosaurios, pero sí huellas: quedaron marcadas en Maimará y en otras localidades de la Quebrada.",
      "La escultura se basa en esas huellas para mostrar cómo pudo haber sido este animal que se alimentaba de plantas.",
      "Si encontrás un fósil, no lo saques ni lo toques: avisá a las autoridades. Está protegido por la Ley 25.743."
    ],
    credito: "Modelo 3D ilustrativo basado en las esculturas de Jorge González (asesoramiento: Juan Sebastián Salgado, UNJu)."
  },
  {
    id: "abelisaurio",
    nombre: "Abelisaurio",
    cientifico: "Abelisauridae",
    lugar: "Parque San Martín, San Salvador de Jujuy",
    epoca: "Hace unos 66 a 70 millones de años",
    tamano: "Unos 6,5 m de largo", // REVISAR con el paleontólogo (es la ESCALA de herramientas/generar_abelisaurio.py)
    modelo: "modelos/abelisaurio.glb?v=3",
    poster: "modelos/abelisaurio-poster.webp?v=3",
    animacion: "reposo",
    arEscala: "auto",              // mide más de 6 m: en realidad aumentada se ajusta para entrar en el espacio
    sonido: "",
    texto: [
      "Este dinosaurio carnívoro caminaba en dos patas y vivió en el período Cretácico, hace unos 66 a 70 millones de años.",
      "En Jujuy no se encontraron huesos de abelisaurios, pero sí huellas: quedaron marcadas en Maimará y en otras localidades de la Quebrada.",
      "La escultura se basa en esas huellas para mostrar cómo pudo haber sido este carnívoro que andaba en dos patas.",
      "Si encontrás un fósil, no lo saques ni lo toques: avisá a las autoridades. Está protegido por la Ley 25.743."
    ],
    credito: "Modelo 3D ilustrativo basado en las esculturas de Jorge González (asesoramiento: Juan Sebastián Salgado, UNJu)."
  }
];
