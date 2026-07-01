"""Configuración y detección de la impresora térmica Colpos (ESC/POS)."""

import json
import sys
from typing import Any, Dict, List, Optional, Tuple

from config import IMPRESORA, RUTA_CONFIG_LOCAL
from services.auth_service import requiere_rol

if sys.platform == "win32":
    import winreg

_CLAVES_IMPRESORA = (
    "tipo",
    "puerto",
    "baudrate",
    "ancho_papel",
    "vendor_id",
    "product_id",
)

_BAUDRATES_COMUNES = (9600, 19200, 38400, 115200)
_ANCHOS_PAPEL = (32, 40, 48)

_TIPOS_CONEXION = (
    ("serial", "Puerto COM"),
    ("usb", "USB directo"),
)

_ETIQUETA_POR_TIPO = {clave: etiqueta for clave, etiqueta in _TIPOS_CONEXION}
_TIPO_POR_ETIQUETA = {etiqueta: clave for clave, etiqueta in _TIPOS_CONEXION}


def obtener_config_impresora() -> Dict[str, Any]:
    """Retorna la configuración efectiva (defaults de config.py + archivo local)."""
    config = dict(IMPRESORA)
    guardada = _leer_seccion_impresora()
    for clave in _CLAVES_IMPRESORA:
        if clave in guardada and guardada[clave] is not None:
            config[clave] = guardada[clave]
    return config


def tipos_conexion_ui() -> List[str]:
    """Etiquetas legibles para el selector de tipo de conexión."""
    return [etiqueta for _, etiqueta in _TIPOS_CONEXION]


def etiqueta_tipo_conexion(tipo: str) -> str:
    """Convierte 'serial'/'usb' a la etiqueta mostrada en la UI."""
    return _ETIQUETA_POR_TIPO.get(str(tipo).lower(), _ETIQUETA_POR_TIPO["serial"])


def tipo_desde_etiqueta(etiqueta: str) -> str:
    """Convierte la etiqueta de la UI al valor interno de tipo."""
    return _TIPO_POR_ETIQUETA.get(etiqueta.strip(), "serial")


def anchos_papel_disponibles() -> List[int]:
    """Caracteres por línea según ancho de rollo térmico."""
    actual = int(obtener_config_impresora().get("ancho_papel", 40))
    opciones = list(_ANCHOS_PAPEL)
    if actual not in opciones:
        opciones.append(actual)
    return sorted(set(opciones))


def listar_puertos_com() -> List[str]:
    """Enumera los puertos COM disponibles en Windows."""
    puertos: List[str] = []
    if sys.platform != "win32":
        return puertos

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DEVICEMAP\SERIALCOMM",
        ) as key:
            indice = 0
            while True:
                try:
                    _, valor, _ = winreg.EnumValue(key, indice)
                    puertos.append(str(valor))
                    indice += 1
                except OSError:
                    break
    except OSError:
        pass

    return sorted(set(puertos), key=_ordenar_puerto_com)


def opciones_puerto_com() -> List[str]:
    """
    Retorna puertos COM detectados más el puerto configurado actualmente,
    por si la impresora no está conectada al refrescar la lista.
    """
    puertos = listar_puertos_com()
    actual = str(obtener_config_impresora().get("puerto", "")).strip()
    if actual and actual not in puertos:
        puertos.append(actual)
    return sorted(set(puertos), key=_ordenar_puerto_com)


def baudrates_disponibles() -> List[int]:
    """Velocidades serie habituales para impresoras térmicas ESC/POS."""
    actual = int(obtener_config_impresora().get("baudrate", 9600))
    opciones = list(_BAUDRATES_COMUNES)
    if actual not in opciones:
        opciones.append(actual)
    return sorted(set(opciones))


def listar_dispositivos_usb() -> List[Dict[str, Any]]:
    """
    Enumera dispositivos USB conectados con vendor_id y product_id.
    Intenta pyusb; si no está disponible, usa el registro de Windows.
    """
    dispositivos = _listar_usb_pyusb()
    if not dispositivos and sys.platform == "win32":
        dispositivos = _listar_usb_windows()
    return dispositivos


def opciones_dispositivos_usb() -> List[Dict[str, Any]]:
    """
    Dispositivos USB detectados más el configurado actualmente,
    para no perder la selección si el cable está desconectado.
    """
    dispositivos = listar_dispositivos_usb()
    claves = {d["clave"] for d in dispositivos}
    config = obtener_config_impresora()
    if str(config.get("tipo", "")).lower() == "usb":
        vid = config.get("vendor_id")
        pid = config.get("product_id")
        if vid is not None and pid is not None:
            clave = f"{int(vid):04X}:{int(pid):04X}"
            if clave not in claves:
                dispositivos.append(_dispositivo_desde_ids(int(vid), int(pid)))
    return sorted(dispositivos, key=lambda d: d["etiqueta"].lower())


@requiere_rol("administrador")
def guardar_config_impresora(
    tipo: str,
    ancho_papel: int,
    puerto: Optional[str] = None,
    baudrate: Optional[int] = None,
    vendor_id: Optional[int] = None,
    product_id: Optional[int] = None,
) -> None:
    """Persiste la configuración de impresora (serial o USB directo)."""
    tipo_limpio = str(tipo).lower().strip()
    if tipo_limpio not in ("serial", "usb"):
        raise ValueError("Tipo de conexión inválido. Use Puerto COM o USB directo.")
    if ancho_papel <= 0:
        raise ValueError("El ancho de papel debe ser mayor que cero.")

    config_actual = obtener_config_impresora()
    impresora: Dict[str, Any] = {
        "tipo": tipo_limpio,
        "ancho_papel": int(ancho_papel),
    }

    if tipo_limpio == "serial":
        if not puerto:
            raise ValueError("Seleccione un puerto COM válido.")
        puerto_limpio = puerto.strip().upper()
        if not puerto_limpio.startswith("COM"):
            raise ValueError(f"Puerto inválido: '{puerto}'. Use formato COMn.")
        if baudrate is None or baudrate <= 0:
            raise ValueError("La velocidad (baudrate) debe ser mayor que cero.")
        impresora["puerto"] = puerto_limpio
        impresora["baudrate"] = int(baudrate)
    else:
        if vendor_id is None or product_id is None:
            raise ValueError("Seleccione un dispositivo USB de la lista.")
        impresora["vendor_id"] = int(vendor_id)
        impresora["product_id"] = int(product_id)
        impresora["puerto"] = config_actual.get("puerto", "COM3")
        impresora["baudrate"] = int(config_actual.get("baudrate", 9600))

    _guardar_seccion_local("impresora", impresora)


@requiere_rol("administrador")
def guardar_puerto_serial(puerto: str, baudrate: int) -> None:
    """Compatibilidad: guarda configuración en modo Puerto COM."""
    config = obtener_config_impresora()
    guardar_config_impresora(
        tipo="serial",
        ancho_papel=int(config.get("ancho_papel", 40)),
        puerto=puerto,
        baudrate=baudrate,
    )


@requiere_rol("administrador")
def probar_conexion(
    tipo: Optional[str] = None,
    puerto: Optional[str] = None,
    baudrate: Optional[int] = None,
    vendor_id: Optional[int] = None,
    product_id: Optional[int] = None,
    ancho_papel: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Intenta conectar con la impresora usando la configuración indicada
    o la guardada actualmente. Retorna (éxito, mensaje).
    """
    config = obtener_config_impresora()

    if tipo:
        config["tipo"] = str(tipo).lower().strip()
    if ancho_papel is not None:
        config["ancho_papel"] = int(ancho_papel)

    if config.get("tipo", "serial") == "serial":
        if puerto:
            config["puerto"] = puerto.strip().upper()
        if baudrate is not None:
            config["baudrate"] = int(baudrate)
    else:
        if vendor_id is not None:
            config["vendor_id"] = int(vendor_id)
        if product_id is not None:
            config["product_id"] = int(product_id)

    from printing.colpos_printer import ColposPrinter

    impresora = ColposPrinter(config)
    if impresora.conectar():
        impresora.desconectar()
        return True, _mensaje_conexion_exitosa(config)
    return False, impresora.ultimo_error


def _mensaje_conexion_exitosa(config: Dict[str, Any]) -> str:
    """Genera un mensaje legible tras una conexión de prueba exitosa."""
    if str(config.get("tipo", "serial")).lower() == "usb":
        vid = int(config.get("vendor_id", 0))
        pid = int(config.get("product_id", 0))
        return f"Conexión USB exitosa (VID {vid:04X} / PID {pid:04X})."
    return (
        f"Conexión exitosa en {config.get('puerto', 'N/A')} "
        f"a {config.get('baudrate', 9600)} bps."
    )


def _listar_usb_pyusb() -> List[Dict[str, Any]]:
    """Enumera dispositivos USB con pyusb si la librería está instalada."""
    dispositivos: List[Dict[str, Any]] = []
    vistos = set()
    try:
        import usb.core
        import usb.util
    except ImportError:
        return dispositivos

    try:
        for dev in usb.core.find(find_all=True):
            vid = int(dev.idVendor)
            pid = int(dev.idProduct)
            clave = (vid, pid)
            if clave in vistos:
                continue
            vistos.add(clave)

            nombre = ""
            try:
                fabricante = usb.util.get_string(dev, dev.iManufacturer) or ""
                producto = usb.util.get_string(dev, dev.iProduct) or ""
                nombre = f"{fabricante} {producto}".strip()
            except (ValueError, usb.core.USBError, NotImplementedError):
                pass

            dispositivos.append(_dispositivo_desde_ids(vid, pid, nombre))
    except Exception:
        return []

    return dispositivos


def _listar_usb_windows() -> List[Dict[str, Any]]:
    """Enumera dispositivos USB desde el registro de Windows (sin dependencias extra)."""
    dispositivos: List[Dict[str, Any]] = []
    vistos = set()
    if sys.platform != "win32":
        return dispositivos

    base = r"SYSTEM\CurrentControlSet\Enum\USB"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as usb_raiz:
            total = winreg.QueryInfoKey(usb_raiz)[0]
            for indice in range(total):
                try:
                    vid_pid = winreg.EnumKey(usb_raiz, indice)
                except OSError:
                    continue
                ids = _parsear_vid_pid(vid_pid)
                if ids is None:
                    continue
                vid, pid = ids
                if (vid, pid) in vistos:
                    continue
                vistos.add((vid, pid))
                nombre = _nombre_usb_registro(usb_raiz, vid_pid) or ""
                dispositivos.append(_dispositivo_desde_ids(vid, pid, nombre))
    except OSError:
        pass

    return dispositivos


def _parsear_vid_pid(vid_pid_key: str) -> Optional[Tuple[int, int]]:
    """Extrae vendor_id y product_id de una clave tipo VID_04B8&PID_0E15."""
    partes = vid_pid_key.upper().split("&")
    if len(partes) < 2:
        return None
    try:
        if not partes[0].startswith("VID_") or not partes[1].startswith("PID_"):
            return None
        vid = int(partes[0].split("_", 1)[1], 16)
        pid = int(partes[1].split("_", 1)[1], 16)
        return vid, pid
    except (IndexError, ValueError):
        return None


def _nombre_usb_registro(usb_raiz, vid_pid_key: str) -> Optional[str]:
    """Lee FriendlyName o DeviceDesc del primer subdispositivo USB."""
    try:
        with winreg.OpenKey(usb_raiz, vid_pid_key) as vid_key:
            total = winreg.QueryInfoKey(vid_key)[0]
            for indice in range(total):
                try:
                    instancia = winreg.EnumKey(vid_key, indice)
                    with winreg.OpenKey(vid_key, instancia) as inst_key:
                        for valor in ("FriendlyName", "DeviceDesc"):
                            try:
                                texto, _ = winreg.QueryValueEx(inst_key, valor)
                                texto = str(texto)
                                if ";" in texto:
                                    texto = texto.split(";", 1)[-1]
                                return texto.strip()
                            except OSError:
                                continue
                except OSError:
                    continue
    except OSError:
        pass
    return None


def _dispositivo_desde_ids(
    vendor_id: int,
    product_id: int,
    nombre: str = "",
) -> Dict[str, Any]:
    """Construye el diccionario estándar de un dispositivo USB para la UI."""
    vid = int(vendor_id)
    pid = int(product_id)
    clave = f"{vid:04X}:{pid:04X}"
    etiqueta_base = nombre.strip() if nombre else "Dispositivo USB"
    etiqueta = f"{etiqueta_base} (VID {vid:04X} / PID {pid:04X})"
    return {
        "etiqueta": etiqueta,
        "vendor_id": vid,
        "product_id": pid,
        "clave": clave,
    }


def _leer_seccion_impresora() -> Dict[str, Any]:
    """Lee la sección impresora del archivo de configuración local."""
    if not RUTA_CONFIG_LOCAL.is_file():
        return {}
    try:
        with open(RUTA_CONFIG_LOCAL, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(datos, dict):
        return {}
    seccion = datos.get("impresora", {})
    return dict(seccion) if isinstance(seccion, dict) else {}


def _guardar_seccion_local(clave: str, valor: Dict[str, Any]) -> None:
    """Fusiona y escribe una sección en config_local.json."""
    datos: Dict[str, Any] = {}
    if RUTA_CONFIG_LOCAL.is_file():
        try:
            with open(RUTA_CONFIG_LOCAL, "r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
        except (OSError, ValueError, TypeError):
            datos = {}
    if not isinstance(datos, dict):
        datos = {}
    datos[clave] = valor
    RUTA_CONFIG_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    with open(RUTA_CONFIG_LOCAL, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)


def _ordenar_puerto_com(puerto: str) -> int:
    """Ordena COM1, COM2, ..., COM10 de forma numérica."""
    nombre = puerto.upper()
    if nombre.startswith("COM"):
        try:
            return int(nombre[3:])
        except ValueError:
            pass
    return 9999
