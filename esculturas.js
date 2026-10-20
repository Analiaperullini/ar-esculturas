// Datos de las esculturas.
// Para sumar una nueva, copiá un bloque { ... } y cambiá los valores.
// El "id" es lo que va en la URL: index.html?e=<id> (sin espacios ni acentos).
// "poster" y "sonido" son opcionales: si no los tenés, borrá la línea o dejala vacía.

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
  }
];
