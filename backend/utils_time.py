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
