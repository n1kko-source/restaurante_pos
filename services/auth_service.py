"""Autenticación, sesión de usuario y decorador @requiere_rol.

Flujo de capas: ui/ -> services/auth_service.py -> database/db_manager.py
Este módulo nunca importa CustomTkinter ni nada de ui/.
"""

import functools
from typing import Optional, Callable, Any

import bcrypt

import database.db_manager as db
from models.usuario import Usuario


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
    return _usuario_actual


def cerrar_sesion() -> None:
    """Cierra la sesión del usuario actual, limpiando la variable de sesión."""
    global _usuario_actual
    _usuario_actual = None


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
