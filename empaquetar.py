"""Genera el ejecutable standalone del POS con PyInstaller.

Uso (una sola vez, en el entorno de desarrollo):
    pip install pyinstaller
    python empaquetar.py

El .exe resultante en dist/ llevará el icono Hogareños en el Explorador,
la barra de tareas y el menú Inicio de Windows.
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ICONO = RAIZ / "assets" / "logo_hogarenos.ico"
LOGO_PNG = RAIZ / "assets" / "logo_hogarenos.png"
ICONOS_DIR = RAIZ / "assets" / "iconos"
SCHEMA = RAIZ / "database" / "schema.sql"
ENTRADA = RAIZ / "main.py"


def _asegurar_icono_valido() -> None:
    """Regenera el .ico desde el PNG si hace falta un formato válido para Windows."""
    from ui.tema import exportar_icono_a_assets

    if LOGO_PNG.is_file():
        if exportar_icono_a_assets():
            print("Icono regenerado desde logo_hogarenos.png")
            return
    if not ICONO.is_file():
        print(f"No se encontró el icono: {ICONO}")
        sys.exit(1)


def _separador_datos() -> str:
    """Separador de rutas para --add-data según el SO."""
    return ";" if sys.platform == "win32" else ":"


def main() -> None:
    """Invoca PyInstaller con icono y recursos embebidos."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller no está instalado. Ejecute: pip install pyinstaller")
        sys.exit(1)

    if not ICONO.is_file() and not LOGO_PNG.is_file():
        print(f"No se encontró el icono ni el PNG en assets/")
        sys.exit(1)

    _asegurar_icono_valido()

    if not ICONO.is_file():
        print(f"No se pudo generar el icono: {ICONO}")
        sys.exit(1)

    sep = _separador_datos()
    datos = [
        f"{LOGO_PNG}{sep}assets",
        f"{ICONO}{sep}assets",
        f"{ICONOS_DIR}{sep}assets/iconos",
        f"{SCHEMA}{sep}database",
    ]

    comando = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--name",
        "SistemaPOS_Hogarenos",
        f"--icon={ICONO}",
    ]
    for item in datos:
        comando.append(f"--add-data={item}")
    comando.append(str(ENTRADA))

    print("Empaquetando:", " ".join(comando))
    subprocess.check_call(comando)
    print("\nListo. Ejecutable en:", RAIZ / "dist" / "SistemaPOS_Hogarenos.exe")


if __name__ == "__main__":
    main()
