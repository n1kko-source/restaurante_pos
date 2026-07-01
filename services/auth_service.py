"""Autenticación, sesión de usuario y decorador @requiere_rol.

Flujo de capas: ui/ -> services/auth_service.py -> database/db_manager.py
Este módulo nunca importa CustomTkinter ni nada de ui/.
"""

import functools
import math
import sqlite3
from typing import List, Optional, Callable, Any, Tuple

import bcrypt

import database.db_manager as db
from config import PAGINA_TAMANO_DEFAULT
from models.usuario import Usuario

_ROLES_VALIDOS = frozenset({"cajero", "supervisor", "administrador"})


# ============================================================
# EXCEPCIÓN DE CONTROL DE ACCESO
# ============================================================

class ErrorAcceso(Exception):
    """
    Se lanza cuando el usuario actual no tiene el rol requerido
    o no hay sesión activa. La capa UI es responsable de capturarla
    y mostrar el mensaje al usuario.
    """


# ============================================================
# ESTADO DE SESIÓN (un único usuario activo por equipo)
# ============================================================

_usuario_actual: Optional[Usuario] = None
_alerta_inventario_pendiente: Optional[str] = None


def obtener_usuario_actual() -> Optional[Usuario]:
    """Retorna el usuario con sesión activa, o None si no hay sesión."""
    return _usuario_actual


# ============================================================
# AUTENTICACIÓN
# ============================================================

def login(usuario: str, password: str) -> Usuario:
    """
    Valida las credenciales contra el hash bcrypt almacenado en SQLite.

    Retorna el objeto Usuario al autenticar correctamente y lo guarda
    en la variable de sesión. Nunca compara contraseñas en texto plano.

    Lanza ValueError con mensaje claro en cualquier caso de fallo
    (usuario inexistente o contraseña incorrecta) para no revelar
    cuál de los dos datos es incorrecto.
    """
    global _usuario_actual

    if not usuario or not usuario.strip():
        raise ValueError("El nombre de usuario no puede estar vacío.")
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")

    fila = db.obtener_usuario_por_nombre(usuario.strip())

    if fila is None:
        raise ValueError("Usuario o contraseña incorrectos.")

    hash_guardado = fila["password_hash"].encode("utf-8")

    try:
        credenciales_validas = bcrypt.checkpw(password.encode("utf-8"), hash_guardado)
    except Exception:
        raise ValueError("Usuario o contraseña incorrectos.")

    if not credenciales_validas:
        raise ValueError("Usuario o contraseña incorrectos.")

    _usuario_actual = Usuario(
        id=fila["id"],
        nombre=fila["nombre"],
        usuario=fila["usuario"],
        rol=fila["rol"],
    )
    from services import inventario_service

    global _alerta_inventario_pendiente
    _alerta_inventario_pendiente = inventario_service.verificar_alerta_dominical()
    return _usuario_actual


def consumir_alerta_inventario() -> Optional[str]:
    """
    Retorna el mensaje de alerta dominical pendiente (si hay) y lo limpia.
    La UI debe mostrar el popup y llamar a esta función una sola vez tras el login.
    """
    global _alerta_inventario_pendiente
    mensaje = _alerta_inventario_pendiente
    _alerta_inventario_pendiente = None
    return mensaje


def cerrar_sesion() -> None:
    """Cierra la sesión del usuario actual, limpiando la variable de sesión."""
    global _usuario_actual, _alerta_inventario_pendiente
    _usuario_actual = None
    _alerta_inventario_pendiente = None


# ============================================================
# GESTIÓN DE CONTRASEÑAS
# ============================================================

def hashear_password(password: str) -> str:
    """
    Genera un hash bcrypt seguro para una contraseña en texto plano.
    Retorna el hash como string UTF-8 listo para almacenar en BD.
    Usar siempre antes de guardar o actualizar una contraseña.
    """
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def cambiar_password(id_usuario: int, password_nueva: str) -> None:
    """
    Genera un nuevo hash bcrypt y actualiza la contraseña del usuario en BD.

    No verifica la contraseña anterior — la validación previa (pedir la
    contraseña actual) es responsabilidad de la UI antes de llamar aquí.
    Lanza ValueError si la contraseña nueva está vacía o el usuario no existe.
    """
    global _usuario_actual

    if not password_nueva:
        raise ValueError("La contraseña nueva no puede estar vacía.")

    todos = db.obtener_todos_usuarios()
    fila_usuario = next((u for u in todos if u["id"] == id_usuario), None)

    if fila_usuario is None:
        raise ValueError(f"No existe un usuario con id {id_usuario}.")

    nuevo_hash = hashear_password(password_nueva)
    db.actualizar_usuario(
        id=id_usuario,
        nombre=fila_usuario["nombre"],
        usuario=fila_usuario["usuario"],
        password_hash=nuevo_hash,
        rol=fila_usuario["rol"],
    )

    # Si el usuario que cambió contraseña es el activo, refrescar la sesión
    if _usuario_actual is not None and _usuario_actual.id == id_usuario:
        _usuario_actual = Usuario(
            id=fila_usuario["id"],
            nombre=fila_usuario["nombre"],
            usuario=fila_usuario["usuario"],
            rol=fila_usuario["rol"],
        )


# ============================================================
# DECORADOR DE CONTROL DE ACCESO
# ============================================================

def requiere_rol(*roles: str) -> Callable:
    """
    Decorador que restringe el acceso a una función según el rol del usuario activo.

    Uso en UI (primera línea de defensa):
        @requiere_rol("administrador")
        def abrir_ventana_usuarios():
            ...

    Uso en services (defensa en profundidad):
        @requiere_rol("administrador")
        def eliminar_usuario(id: int):
            ...

    Lanza ErrorAcceso si no hay sesión activa o el rol no está en la lista.
    La UI captura ErrorAcceso y muestra el mensaje en un diálogo.
    """
    def decorador(func: Callable) -> Callable:
        @functools.wraps(func)
        def envoltura(*args: Any, **kwargs: Any) -> Any:
            if _usuario_actual is None:
                raise ErrorAcceso(
                    "No hay ningún usuario con sesión activa. "
                    "Inicie sesión para continuar."
                )
            if _usuario_actual.rol not in roles:
                roles_legibles = " o ".join(f'"{r}"' for r in roles)
                raise ErrorAcceso(
                    f"Acceso denegado.\n"
                    f"Esta función requiere el rol {roles_legibles}.\n"
                    f"Su rol actual es: \"{_usuario_actual.rol}\"."
                )
            return func(*args, **kwargs)
        return envoltura
    return decorador


# ============================================================
# GESTIÓN DE USUARIOS (solo administrador)
# ============================================================

def _usuario_desde_fila(fila) -> Usuario:
    """Convierte una fila sqlite3.Row de usuarios en instancia Usuario."""
    return Usuario(
        id=fila["id"],
        nombre=fila["nombre"],
        usuario=fila["usuario"],
        rol=fila["rol"],
    )


def _calcular_total_paginas(total: int, por_pagina: int = PAGINA_TAMANO_DEFAULT) -> int:
    """Calcula el número de páginas para un listado paginado."""
    if total <= 0:
        return 1
    return max(1, math.ceil(total / por_pagina))


def _validar_rol(rol: str) -> str:
    """Valida que el rol esté permitido por el schema."""
    limpio = rol.strip().lower()
    if limpio not in _ROLES_VALIDOS:
        raise ValueError(
            f"Rol inválido: '{rol}'. "
            f"Valores permitidos: cajero, supervisor, administrador."
        )
    return limpio


def _validar_texto_usuario(texto: str, etiqueta: str) -> str:
    """Valida que un campo de texto de usuario no esté vacío."""
    limpio = texto.strip()
    if not limpio:
        raise ValueError(f"El {etiqueta} no puede estar vacío.")
    return limpio


def _obtener_fila_usuario(id_usuario: int):
    """Retorna la fila del usuario o lanza ValueError si no existe."""
    fila = next(
        (u for u in db.obtener_todos_usuarios() if u["id"] == id_usuario),
        None,
    )
    if fila is None:
        raise ValueError(f"No existe un usuario con id {id_usuario}.")
    return fila


def _contar_administradores() -> int:
    """Retorna cuántos usuarios con rol administrador existen."""
    return sum(
        1 for u in db.obtener_todos_usuarios() if u["rol"] == "administrador"
    )


@requiere_rol("administrador")
def listar_usuarios_pagina(
    pagina: int = 1,
    rol: Optional[str] = None,
) -> Tuple[List[Usuario], int, int]:
    """
    Retorna (usuarios, total_registros, total_paginas) para el Treeview.
    pagina es 1-indexado. Si rol no es None, filtra por ese rol.
    """
    if rol is not None:
        rol = _validar_rol(rol)
    total = db.obtener_total_usuarios(rol)
    total_paginas = _calcular_total_paginas(total)
    pagina = max(1, min(pagina, total_paginas))
    filas = db.obtener_usuarios_pagina(pagina, rol=rol)
    return (
        [_usuario_desde_fila(fila) for fila in filas],
        total,
        total_paginas,
    )


@requiere_rol("administrador")
def crear_usuario(nombre: str, usuario: str, password: str, rol: str) -> Usuario:
    """Registra un usuario nuevo con contraseña hasheada en bcrypt."""
    nombre_limpio = _validar_texto_usuario(nombre, "nombre")
    usuario_limpio = _validar_texto_usuario(usuario, "nombre de usuario")
    rol_limpio = _validar_rol(rol)
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")

    password_hash = hashear_password(password)
    try:
        nuevo_id = db.crear_usuario(
            nombre_limpio, usuario_limpio, password_hash, rol_limpio
        )
    except sqlite3.IntegrityError:
        raise ValueError(
            f"Ya existe un usuario con el nombre de acceso '{usuario_limpio}'."
        )
    return Usuario(
        id=nuevo_id,
        nombre=nombre_limpio,
        usuario=usuario_limpio,
        rol=rol_limpio,
    )


@requiere_rol("administrador")
def actualizar_usuario(
    id_usuario: int, nombre: str, usuario: str, rol: str
) -> Usuario:
    """Actualiza nombre, login y rol de un usuario (sin cambiar contraseña)."""
    global _usuario_actual

    nombre_limpio = _validar_texto_usuario(nombre, "nombre")
    usuario_limpio = _validar_texto_usuario(usuario, "nombre de usuario")
    rol_limpio = _validar_rol(rol)

    fila = _obtener_fila_usuario(id_usuario)
    if fila["rol"] == "administrador" and rol_limpio != "administrador":
        if _contar_administradores() <= 1:
            raise ValueError(
                "No puede cambiar el rol del único administrador del sistema."
            )

    try:
        db.actualizar_usuario(
            id=id_usuario,
            nombre=nombre_limpio,
            usuario=usuario_limpio,
            password_hash=fila["password_hash"],
            rol=rol_limpio,
        )
    except sqlite3.IntegrityError:
        raise ValueError(
            f"Ya existe un usuario con el nombre de acceso '{usuario_limpio}'."
        )

    if _usuario_actual is not None and _usuario_actual.id == id_usuario:
        _usuario_actual = Usuario(
            id=id_usuario,
            nombre=nombre_limpio,
            usuario=usuario_limpio,
            rol=rol_limpio,
        )

    return Usuario(
        id=id_usuario,
        nombre=nombre_limpio,
        usuario=usuario_limpio,
        rol=rol_limpio,
    )


@requiere_rol("administrador")
def eliminar_usuario(id_usuario: int) -> None:
    """Elimina un usuario por id con reglas de protección del sistema."""
    if _usuario_actual is not None and _usuario_actual.id == id_usuario:
        raise ValueError(
            "No puede eliminar su propio usuario mientras tiene sesión activa."
        )

    fila = _obtener_fila_usuario(id_usuario)
    if fila["rol"] == "administrador" and _contar_administradores() <= 1:
        raise ValueError("No puede eliminar el único administrador del sistema.")

    db.eliminar_usuario(id_usuario)
