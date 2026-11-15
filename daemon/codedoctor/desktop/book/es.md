# Manual de funciones de Lumen

Lumen es un equipo de IA que se instala en tu PC con Windows. Tú solo hablas con Lumen, en lenguaje natural; él reparte el trabajo entre el miembro del equipo más adecuado, elige por sí mismo las herramientas que hacen falta y te entrega el resultado cuando termina. Puede escribir código, buscar problemas, editar vídeos, crear modelos 3D, hacer páginas web y PDF, buscar información en internet y manejar el equipo.

## 1. Primeros pasos

- **Lo que necesitas**: Windows, Python 3.12 y una IA: Claude Code o Codex (después de instalarlo, inicia sesión una vez en la terminal), o una clave de API (sirve cualquier servicio compatible con la API de OpenAI o con la de Anthropic).
- **Instalación**: dentro de la carpeta de Lumen, ejecuta `setup.ps1` (las instrucciones en chino están en `安装环境.ps1`). Creará un `.venv` en esa misma carpeta e instalará los paquetes que Lumen necesita, sin tocar el Python de tu sistema. Después, haz doble clic en `Lumen.cmd` para abrirlo.
- **Primera vez**: después de la pantalla de bienvenida, elige el idioma de la interfaz y una carpeta de trabajo, y ya puedes empezar. El modelo puedes cambiarlo más tarde, debajo del cuadro de entrada.
- **Próximas veces**: Lumen vuelve a la última carpeta que usaste. La barra lateral izquierda te permite cambiar de carpeta, abrir un chat nuevo o buscar en tus chats.

## 2. Enviar mensajes

- Escribe lo que quieres hacer en el cuadro de entrada y pulsa Intro para enviarlo. Puedes arrastrar archivos hasta el cuadro o pegarlos.
- **Entrada por voz**: pulsa el micrófono y habla. No hace falta que hables con precisión: Lumen entiende el sentido de lo que dices y no se fija en la gramática.
- **Modelo**: debajo del cuadro de entrada eliges qué IA usar (modelos de Claude Code, de Codex o del servicio que hayas conectado), y junto a él, la intensidad de razonamiento. El modelo lo decides tú por completo; Lumen nunca lo cambia por su cuenta.
- **Si no está seguro, te pregunta primero**: cuando no tiene claro lo que quieres, aparece un panel de preguntas, cada una con sus opciones; basta con elegir. Si no quieres responder, sáltalo y deja que decida por sí mismo.
- **Debajo de cada respuesta**: puedes copiarla, recordarla, pedir que vuelva a responder o modificar tu pregunta y enviarla de nuevo. Cuando termina la respuesta, sus pasos se pliegan y solo queda el resultado; haz clic para ver cada paso.

## 3. Aprobaciones

Debajo del cuadro de entrada eliges la forma de aprobación de esta conversación. Determina si la IA te pregunta antes de actuar:

| Aprobaciones | Cuándo te pregunta |
|---|---|
| Totalmente abierto | Nunca pregunta; lo hace directamente |
| Revisar por mí | Solo antes de borrar archivos y antes de usar el ratón o el teclado en el equipo |
| Preguntar siempre | Antes de cada acción que modifique algo |

Cuando tenga que preguntarte, aparecerá una pequeña tarjeta encima del cuadro de entrada, abajo a la derecha: una línea que explica lo que quiere hacer, junto a **Permitir** y **No permitir**. Si pulsas **No permitir**, solo se omite esa acción y las demás siguen. Fuera de esto, Lumen no tiene más restricciones de permisos: puede usar cada carpeta y cada unidad del equipo.

## 4. Equipo de Lumen

| Miembro | Se encarga de |
|---|---|
| Lumen | Coordinador: habla contigo, reparte el trabajo y te da la respuesta final |
| Spark | Escribe código, y también usa las distintas herramientas de creación |
| Prism | Inspecciona |
| Torch | Prueba en real: ejecuta el programa de verdad |
| Ray | Busca información en internet |
| Lantern | Gestiona archivos |
| Beacon | Supervisa: revisa los resultados de los demás |
| Iris | Maneja el equipo |

Cada miembro tiene su propia memoria de trabajo y puede llamar a ayudantes puntuales cuando haga falta. Los miembros pueden trabajar a la vez sin pisarse el trabajo.

**Lumen y tú estáis al mismo nivel.** Habla como un compañero competente: si te equivocas, te lo dice directamente y explica por qué; si tiene razón, no cambia de opinión aunque insistas, salvo que des un motivo. Cuando la decisión es tuya, una vez que la tomas, la ejecuta bien.

## 5. Uso automático de herramientas (sin @)

Basta con decir lo que quieres, por ejemplo: «convierte esta imagen en PDF», «recorta este vídeo a los primeros 10 segundos», «haz un cubo 3D rojo». Lumen sabe qué herramientas tiene instaladas este equipo, elige la adecuada y se la asigna al miembro que puede usarla.

También puedes escribir @ en el cuadro de entrada para nombrar una herramienta concreta; en ese caso, solo se usa la que nombres.

| Herramienta | Para qué sirve |
|---|---|
| CodeCut | Edición de vídeo: cortes, unión, subtítulos, música de fondo, exportación |
| Code3D | Modelos y escenas 3D con el Blender de tu equipo; exporta GLB e imágenes |
| CodeSound | Música y efectos de sonido |
| CodePage | Páginas web |
| CodeGame | Minijuegos para jugar |
| CodeDeck | Diapositivas y documentos (PowerPoint, Word, PDF) |
| CodeData | Analiza Excel y CSV; cada cifra del informe se puede rastrear hasta su origen |
| CodeCAD | Piezas listas para imprimir en 3D, con medidas en milímetros |
| CodeLab | Registros y progreso del entrenamiento de modelos |
| CodeTools | Decenas de utilidades: pósteres de marca, diagramas de flujo, códigos QR, subtítulos, doblaje, retoque por lotes, organización de archivos y más |
| CodeFilm | Un cortometraje a partir de una sola frase |
| CodePDF | Imagen a PDF, unir, dividir, comprimir, rotar y seleccionar páginas |

## 6. Panel derecho

- **Ventana de herramienta**: cuando el equipo usa una herramienta, se abre automáticamente a la derecha para que puedas ver cómo trabaja. Esta ventana es exclusiva de la IA: ella hace clic y escribe dentro, sin ocupar tu ratón ni tu teclado; verás un pequeño ratón azul moviéndose. Pulsa × en la ventana para cerrarla.
- **Navegador** (Ctrl+Shift+B): aquí buscas y abres páginas web; los enlaces del chat también se abren aquí. Cuando el equipo busca información en internet, también se muestra aquí.
- **Terminal** (Ctrl+J): una PowerShell de verdad, en la carpeta actual. Los comandos que ejecuta el equipo aparecen aquí en colores.

## 7. Memoria a largo plazo

- **La IA te recuerda**: antes de cada conversación nueva, la IA repasa los chats anteriores y resume lo importante en una memoria: sobre ti (quién eres, cómo hablas, qué te gusta, las reglas que has fijado; común a todos los proyectos) y sobre este proyecto (qué se ha hecho, qué se decidió, en qué punto está). Cada chat nuevo empieza con esa memoria, así que no tienes que volver a explicarlo todo.
- **Su tamaño depende del historial**: si has hablado poco, son unas pocas líneas; si has hablado mucho, será más larga: normalmente hasta 50 000 caracteres, y como máximo unos 80 000. Si supera ese tamaño, se vuelve a comprimir, solo se reducen los detalles y no se pierden las cosas importantes.
- **Te avisa cuando tiene que esperar**: si la memoria de la conversación anterior todavía no se ha organizado, el chat nuevo muestra «Revisando chats anteriores…» y espera como máximo 90 segundos.
- **Puedes verla, cambiarla y borrarla**: en «Ajustes → Memoria a largo plazo → Lo que la IA recuerda de ti». Lo que cambies, la IA lo seguirá a partir de entonces. Si la borras, los chats anteriores tampoco se volverán a usar para reorganizarla.
- Los miembros también anotan los hechos que merece la pena recordar y los recuperan automáticamente la próxima vez. Si eliges un modelo de embeddings, pueden encontrar conclusiones antiguas aunque estén expresadas con otras palabras.

## 8. Hacer varias cosas a la vez

- Varias conversaciones pueden avanzar a la vez sin esperarse: si una espera tu respuesta a una pregunta, otra sigue trabajando.
- Puedes abrir varias ventanas de la misma carpeta (Ctrl+Shift+N).
- Lo que aprende una conversación, las siguientes ya lo saben (ver la sección 7).

## 9. Uso del equipo

- Funciona desde el primer momento: capturas de pantalla, ratón, teclado, abrir y cerrar programas y la terminal, en todas las ventanas (excepto las de Lumen). Basta con dar el nombre del programa o su ruta completa para abrir cualquier programa.
- Si te pregunta antes de actuar depende de la forma de aprobación (sección 3).
- **Modo de funcionamiento**: de entrada actúa en segundo plano y no ocupa tu ratón ni tu teclado. Para juegos u otras cosas que necesitan un ratón real, cámbialo a primer plano en «Ajustes → Uso del equipo».
- **Parada de emergencia**: pulsa `Ctrl+Alt+End`, o lleva el ratón a la esquina superior izquierda de la pantalla.
- Si no quieres que la IA toque el equipo: en «Ajustes → Uso del equipo», activa **Prohibir el control del equipo**.

## 10. Cuando hacen falta permisos de administrador

Las carpetas del sistema, como `C:\Windows` y `Program Files`, requieren permisos de administrador. Si Windows muestra «Acceso denegado», la IA vuelve a ejecutar ese comando como administrador. Entonces Windows muestra su propia ventana de confirmación, y tú decides si la permites.

## 11. Pruebas automáticas

En «Ajustes → Pruebas automáticas», escribe el comando de pruebas del proyecto (o pulsa **Detectar automáticamente**). Cuando el equipo cambia código, el sistema ejecuta las pruebas antes de empezar, después de cada cambio y antes de entregar. Esto ocurre sin pasar por el modelo y sin gastar tokens; si alguien rompe una prueba que antes pasaba, se señala al momento. Se recomienda hacer un commit con git antes de empezar, para que siempre puedas ver qué cambió y deshacerlo.

## 12. Idioma de la interfaz

English、Français、Español、Deutsch、Italiano、Português、简体中文, 7 en total. Se cambian en «Ajustes → Apariencia» y se aplican al instante. La ventana de herramienta de la derecha también cambia de idioma. La IA responde en el idioma en que escribes.

## 13. Resumen de ajustes

- **Servicios y claves**: conecta tantos servicios de IA como quieras. Las claves se guardan solo en el Administrador de credenciales de Windows, nunca en un archivo de configuración.
- **Modelos de IA**: qué servicio y qué modelo usa cada miembro, cuánto debe pensar y qué modelo de reserva usar si hay un error.
- **Memoria a largo plazo**: el interruptor de recuerdo, **Lo que la IA recuerda de ti** y el recuerdo por significado.
- **Pruebas automáticas** y **Uso del equipo**: ver más arriba.
- **Apariencia**: idioma, fondo de pantalla, tamaño de letra, color de énfasis, etc. Se aplica al momento.
- **Uso**: cuánto has usado hoy, en los últimos siete días y en total.
- **Manual de funciones**: esta misma página.

## 14. Pequeñas funciones útiles

- **Ctrl+K**: un único cuadro para encontrarlo todo: chats, páginas y acciones. Si escribes al menos dos caracteres, también encuentra lo que se dijo en los chats. **Ctrl+/** muestra todos los atajos.
- **Ctrl+N** para un chat nuevo, **Ctrl+B** para ocultar o mostrar la barra lateral izquierda, **Ctrl+F** para buscar dentro del chat y **Ctrl+,** para abrir Ajustes.
- **Clic derecho en un chat**: renombrar, exportar como Markdown u ocultarlo de la lista (sin borrarlo).
- **Frases guardadas**: escribe un texto y pulsa Ctrl+S para guardarlo como frase guardada; luego, en un cuadro de entrada vacío, escribe / para usarla. Si un mensaje no llegó a enviarse, se conserva aunque cierres la ventana.
- **Aviso al terminar**: si la ventana no está al frente, la barra de tareas se ilumina cuando la respuesta termina, y aparece un aviso abajo a la derecha.
- **Navegador**: la estrella guarda esta página en favoritos; Ctrl+Shift+T recupera la pestaña que cerraste; el globo envía esta página a Lumen.
- **Terminal**: haz clic derecho sobre la salida y envía a Lumen lo que tengas seleccionado o la salida más reciente.

## 15. Seguridad y privacidad

- Tú eliges todos los modelos; Lumen nunca los cambia por su cuenta.
- Tus chats, memoria y registros se guardan en tu propio equipo (en la carpeta `~/.codedoctor`).
- Las claves están solo en el Administrador de credenciales de Windows; la memoria nunca guarda claves.
- La IA no hace pagos ni inicios de sesión por ti.

## 16. Consejos

- Cuanto más concreto seas, más cerca estará el primer resultado de lo que quieres; y si no lo eres, no pasa nada: te preguntará antes.
- Para ir más rápido y gastar menos, elige un modelo más pequeño o una intensidad de razonamiento más baja; para los trabajos difíciles, cambia a uno más grande.
- Si se cierra de forma inesperada, envía el archivo `~/.codedoctor/crash.log` al desarrollador.
