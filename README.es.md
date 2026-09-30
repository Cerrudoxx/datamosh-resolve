<div align="center">

# ⚡ Datamosh-Resolve ⚡
### Datamoshing de Vídeo y Transiciones en Cortes para DaVinci Resolve

[![Plataforma](https://img.shields.io/badge/Plataforma-Windows%2010%20%7C%2011%20%2864--bit%29-0078d7?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![DaVinci Resolve](https://img.shields.io/badge/DaVinci_Resolve-20%2B_%28Free_%2F_Studio%29-1a1a2e?style=for-the-badge&logo=davinciresolve&logoColor=white)](https://www.blackmagicdesign.com/products/davinciresolve)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Powered-007808?style=for-the-badge&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![Licencia: MIT](https://img.shields.io/badge/Licencia-MIT-yellow.svg?style=for-the-badge)](LICENSE)

<p align="center">
  <b>Eliminación automatizada de I-frames, transiciones por desplazamiento de vectores de movimiento e importación directa al Media Pool en DaVinci Resolve.</b>
</p>

*Idioma: [English](README.md) | [Español](README.es.md)*

</div>

---

> [!IMPORTANT]
> ### ⚠️ Aviso de Proyecto & Atribución Vibecoding
> Este proyecto ha sido en gran parte **vibecodeado** (desarrollado con herramientas de programación asistida por IA) y adaptado a partir del software de código abierto **[Datamosher Pro](https://github.com/Akascape/Datamosher-Pro)** creado por **[Akash Bora](https://github.com/Akascape)**.
>
> Al fin y al cabo lo necesitaba rápido para hacer un par de cosas y no podía perder tiempo en esto, pero si a alguien le interesa y le sirve, bienvenido sea. Cualquier contribución es válida. Yo lo iré actualizando de vez en cuando según mi propia necesidad porque hay cosas que no funcionan del todo bien o quizás quiera añadir más funcionalidad, quién sabe. **PERO NO PROMETO NADA.**
>
> Todo el mérito por los algoritmos fundamentales de manipulación de flujo de bits de vídeo pertenece a:
> - 👤 **[Akash Bora](https://github.com/Akascape)** (*Datamosher Pro*) — Arquitectura del flujo y lógica de automatización.
> - 👤 **[Kasper Ravel](https://github.com/itsKaspar)** (*Tomato Automosh*) — Algoritmos de manipulación de fotogramas delta en contenedores AVI.
> - 👤 **[grampajoe](https://github.com/grampajoe)** (*pymosh*) — Análisis sintáctico de contenedores RIFF/AVI y manipulación de fotogramas MPEG-4.
>
> **Cumplimiento de Licencias:**  
> Datamosher Pro, Tomato Automosh y pymosh se distribuyen bajo la permisiva **Licencia MIT**, que permite explícitamente incorporar, modificar y redistribuir código siempre que se conserven los avisos de derechos de autor y permisos originales. Consulte el archivo [LICENSE](LICENSE) para más información.

---

## 🔬 Descripción Técnica del Flujo de Trabajo

El datamoshing genera artefactos visuales mediante la alteración directa del flujo de datos de vídeo comprimido antes de su decodificación, a diferencia de los filtros convencionales de posprocesamiento de imagen 2D. En la compresión inter-frame (como MPEG-4 Parte 2):
- **Fotogramas intra (I-frames):** Establecen la imagen de referencia espacial completa.
- **Fotogramas predichos (P-frames):** Almacenan únicamente vectores de movimiento y diferencias residuales respecto a fotogramas anteriores.

Al suprimir el fotograma I en el punto de corte entre dos planos, el decodificador de vídeo aplica los vectores de movimiento de la nueva escena directamente sobre el búfer de píxeles no refrescado de la escena anterior, desgarrando los macrobloques a través del corte.

```mermaid
flowchart LR
    A["🎬 Corte en Timeline\n(DaVinci Resolve)"] --> B["📍 Detección de Cabezal\n(API Scripting Python)"]
    B --> C["🎞️ AVI MPEG-4 Intermedio\n(Sin B-frames, GOP estricto)"]
    C --> D["✂️ Cirugía Binaria de Bitstream\n(Drop de I-Frame / Loop Delta)"]
    D --> E["⚙️ Transcodificación libavcodec\n(Fijar glitch en H.264 limpio)"]
    E --> F["📥 Auto-Import al Media Pool\n(Listo para la línea de tiempo)"]

    style A fill:#1e1e2e,stroke:#00b4d8,stroke-width:2px,color:#fff
    style B fill:#1e1e2e,stroke:#0077b6,stroke-width:2px,color:#fff
    style C fill:#1e1e2e,stroke:#7209b7,stroke-width:2px,color:#fff
    style D fill:#1e1e2e,stroke:#f72585,stroke-width:2px,color:#fff
    style E fill:#1e1e2e,stroke:#4cc9f0,stroke-width:2px,color:#fff
    style F fill:#1e1e2e,stroke:#06d6a0,stroke-width:2px,color:#fff
```

---

## ✨ Características Principales

- 🔀 **Transiciones Automáticas en Cortes entre 2 Clips:** Une el plano saliente y el entrante, elimina el fotograma clave exactamente en el corte y renderiza la transición fijada.
- 📍 **Detección Inteligente por Cabezal (Playhead):** Consulta la línea de tiempo activa de DaVinci Resolve para identificar de forma instantánea los dos clips del corte en cualquier pista de vídeo.
- 📋 **Índice Desplegable de Clips:** Menú con todos los elementos de vídeo presentes en la línea de tiempo para combinaciones personalizadas.
- 📁 **Multi-Selección en Media Pool:** Selecciona dos clips en el Media Pool (`Ctrl + Clic`) y cárgalos con un solo botón.
- 🎬 **Datamosh en un Solo Clip:** Aplica estelas de movimiento, dispersión de velocidad y bucles de fotogramas en rangos temporales definidos por el usuario.
- 📥 **Reimportación Automatizada:** Importa automáticamente el archivo final MP4 al Media Pool del proyecto activo.
- 🆓 **Compatibilidad Total:** 100% funcional tanto en **DaVinci Resolve Free** como en **Studio** (v20+ en Windows de 64 bits).

---

## 📸 Interfaz y Flujo de Trabajo

<div align="center">

### 1. Acceso desde el Menú de DaVinci Resolve
Abre la herramienta desde la barra de menú superior en **Workspace -> Scripts -> Datamosher_Pro**:

<img src="docs/images/resolve_menu.png" alt="Menú Workspace de DaVinci Resolve" width="85%" />

---

### 2. Interfaz de Configuración de la Transición
Detecta los clips en el corte o elígelos desde el Media Pool / desplegables, ajusta duración y delta, y genera la transición:

<img src="docs/images/gui_transition.png" alt="Interfaz de Datamosher Pro en DaVinci" width="85%" />

---

### 3. Resultado de la Transición
Una vez concluido el renderizado, el clip generado se deposita de manera automática en tu **Media Pool** activo. Contiene el glitch real de datamoshing consolidado, donde los vectores de movimiento de la nueva escena arrastran y desgarran los macrobloques de la imagen anterior congelada. ¡Solo tienes que arrastrarlo a tu línea de tiempo sobre el corte!

</div>

---

## 🎛️ Referencia de Algoritmos

| Modo | Motor | Comportamiento Técnico |
|:---|:---|:---|
| 🟢 **Classic** | *Avidemux / pymosh* | Elimina el marcador de fotograma clave (`00 01 B0`) en el corte, forzando al decodificador a aplicar los vectores de movimiento sobre el lienzo anterior no refrescado. |
| 🟣 **Bloom** | *Tomato Automosh* | Duplica fotogramas delta mediante factores de escala, generando una dispersión expansiva de macrobloques. |
| 🔵 **Repeat** | *MPEG Packet Loop* | Repite paquetes consecutivos de fotogramas P (`00 01 B6`) para generar patrones de desplazamiento continuo en bucle. |
| ⚫ **Void** | *Tomato Automosh* | Detecta cambios de escena y elimina fotogramas de referencia para disolver el vídeo entrante en oscuridad. |

---

## 💻 Requisitos del Sistema

- **Sistema Operativo:** Windows 10 o Windows 11 (únicamente de 64 bits).
- **Software Host:** DaVinci Resolve 20.0 o posterior (Free o Studio).
- **Python:** Python 3.8 a 3.12 (registrado en el `PATH` del sistema).
- **FFmpeg:** Binario de FFmpeg accesible desde el `PATH` del sistema.
  - Para instalarlo rápidamente en PowerShell:
    ```powershell
    winget install Gyan.FFmpeg
    ```

---

## 📦 Instalación (Windows)

### Opción A: Instalador Automático en 1 Clic (Recomendado)
1. Clona o descarga este repositorio en tu equipo:
   ```cmd
   git clone https://github.com/Cerrudoxx/datamosh-resolve.git
   ```
2. Haz doble clic en el archivo **`install.bat`**.
3. El instalador comprobará dependencias, colocará `Datamosher_Pro.py` en Scripts de Fusion y desplegará las librerías (`DatamoshLib/`, `pymosh/`) en Modules de Fusion (evitando que DaVinci ensucie el menú de Scripts con submódulos).
4. Reinicia DaVinci Resolve si estaba abierto.

### Opción B: Instalación Manual
1. Copia `Datamosher_Pro.py` en:
   ```
   %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Edit\
   ```
2. Copia las carpetas `DatamoshLib/` y `pymosh/` en:
   ```
   %APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Modules\
   ```
   *(Colocar las librerías en `Modules` permite que se carguen automáticamente sin aparecer como scripts en el menú de DaVinci).*

---

## 🚀 Guía de Uso Paso a Paso

### Transición entre 2 Clips en un Corte
1. Abre un proyecto y una línea de tiempo en DaVinci Resolve.
2. En la página **Edit**, coloca el cabezal de reproducción sobre el corte entre dos clips.
3. Abre el script desde el menú superior:
   👉 **Workspace → Scripts → Datamosher_Pro**
4. Haz clic en **`📍 Detect 2 Clips at Cut (Playhead)`**. Se cargarán automáticamente el Clip 1 (Saliente) y el Clip 2 (Entrante).
5. Configura los parámetros:
   - **Cut Glitch Duration:** Duración en segundos de la distorsión del movimiento tras el corte (ej. `1.5s`).
   - **Motion Trail Multiplier (Delta):** Intensidad de multiplicación de vectores de movimiento (ej. `8`).
   - **Transition Algorithm:** `Classic`, `Bloom` o `Repeat`.
6. Haz clic en **`💥 CREATE DATAMOSH TRANSITION`**.
7. El archivo generado se guardará en la carpeta de origen y se añadirá de forma automática a tu **Media Pool**. ¡Arrástralo directamente a la línea de tiempo sobre el corte!

---

## ❓ Preguntas Frecuentes

<details>
<summary><b>¿Funciona con la versión gratuita de DaVinci Resolve?</b></summary>
¡Sí! El script se comunica con la API de Python de DaVinci Resolve y procesa la cirugía de vídeo con Python y FFmpeg. Es totalmente compatible con DaVinci Resolve 20 Free sin marcas de agua ni restricciones.
</details>

<details>
<summary><b>¿Por qué es necesario FFmpeg?</b></summary>
El datamoshing auténtico no se puede lograr con filtros de imagen 2D. Requiere manipular físicamente los paquetes de compresión MPEG-4 (eliminando secuencias de bytes <code>00 01 B0</code>) y re-decodificar con <code>libavcodec</code> para fijar los artefactos visuales de descompresión reales.
</details>

---

## 📄 Licencia y Créditos

Este proyecto se distribuye bajo la **Licencia MIT**. Consulta [LICENSE](LICENSE) para más detalles.
- **[Datamosher Pro](https://github.com/Akascape/Datamosher-Pro)** de Akash Bora (Licencia MIT).
- **[Tomato Automosh](https://github.com/itsKaspar/tomato)** de Kasper Ravel (Licencia MIT).
- **[pymosh](https://github.com/grampajoe/pymosh)** de grampajoe (Licencia MIT).
- Las herramientas externas como FFmpeg se rigen por sus respectivas licencias (LGPL/GPL).
