"""Helpers para serializar datetimes como UTC explícito (sufijo Z).

Todo el backend usa datetime.utcnow() (naive). Al serializar con .isoformat()
sin indicar zona, el navegador interpreta el string como hora LOCAL del
sistema en vez de UTC, desfasando las horas mostradas en bitácoras, reportes
y cálculos de "tiempo en sesión". iso_utc() corrige esto en el límite de
serialización sin tocar la lógica interna (que sigue siendo naive-UTC consistente).
"""
from datetime import datetime


def iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()


def parse_naive_utc(s: str) -> datetime:
    """Parsea un string producido por iso_utc() (puede traer sufijo 'Z') de
    vuelta a un datetime NAIVE en UTC — consistente con el resto del backend,
    que guarda y compara todo como naive (datetime.utcnow()).

    Sin esto: datetime.fromisoformat() en Python 3.11+ interpreta el 'Z' y
    devuelve un datetime AWARE, que luego revienta con
    "can't subtract offset-naive and offset-aware datetimes" (o un error de
    asyncpg) al compararlo/insertarlo contra columnas DateTime naive.
    """
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt
