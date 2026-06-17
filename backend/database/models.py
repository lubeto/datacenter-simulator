"""
DC Monitoring Simulator - Modelos de Base de Datos
SQLAlchemy ORM - SQLite
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


# ============================================================
# ESTUDIANTES / USUARIOS
# ============================================================
class Student(Base):
    __tablename__ = "students"

    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String(100), nullable=False)
    email            = Column(String(150), unique=True, index=True, nullable=False)
    password_hash    = Column(String(200), nullable=False)
    role             = Column(String(20), default="student")
    created_at       = Column(DateTime, default=datetime.utcnow)
    is_active        = Column(Boolean, default=True)

    # Métricas acumuladas
    total_sessions      = Column(Integer, default=0)
    total_incidents     = Column(Integer, default=0)
    avg_mttd_seconds    = Column(Float, default=0.0)   # Mean Time To Detect
    avg_mttr_seconds    = Column(Float, default=0.0)   # Mean Time To Resolve
    avg_score           = Column(Float, default=0.0)

    # Relaciones
    sessions            = relationship("Session", back_populates="student")
    reports             = relationship("Report", back_populates="student")
    mitigation_actions  = relationship("MitigationAction", back_populates="student")


# ============================================================
# SESIONES DE MONITOREO
# ============================================================
class Session(Base):
    __tablename__ = "sessions"

    id                  = Column(Integer, primary_key=True, index=True)
    student_id          = Column(Integer, ForeignKey("students.id"), nullable=False)
    started_at          = Column(DateTime, default=datetime.utcnow)
    ended_at            = Column(DateTime, nullable=True)
    duration_min        = Column(Float, default=0.0)
    is_active           = Column(Boolean, default=True)

    # Resultados de la sesión
    incidents_detected  = Column(Integer, default=0)
    incidents_missed    = Column(Integer, default=0)
    false_positives     = Column(Integer, default=0)
    score               = Column(Float, default=0.0)
    notes               = Column(Text, nullable=True)

    # Relaciones
    student             = relationship("Student", back_populates="sessions")
    incidents           = relationship("Incident", back_populates="session")
    reports             = relationship("Report", back_populates="session")


# ============================================================
# MÉTRICAS DE NODOS (time-series)
# ============================================================
class Metric(Base):
    __tablename__ = "metrics"

    id              = Column(Integer, primary_key=True, index=True)
    node_id         = Column(String(50), index=True, nullable=False)
    node_type       = Column(String(30), nullable=False)   # server, switch, router, etc.
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)

    # Compute
    cpu_pct         = Column(Float, default=0.0)
    ram_pct         = Column(Float, default=0.0)
    disk_io_mbps    = Column(Float, default=0.0)
    disk_used_pct   = Column(Float, default=0.0)

    # Red
    net_in_mbps     = Column(Float, default=0.0)
    net_out_mbps    = Column(Float, default=0.0)
    latency_ms      = Column(Float, default=0.0)
    packet_loss_pct = Column(Float, default=0.0)
    connections     = Column(Integer, default=0)

    # Estado
    is_online       = Column(Boolean, default=True)
    uptime_pct      = Column(Float, default=99.9)


# ============================================================
# LECTURAS SST (Salud y Seguridad en el Trabajo)
# ============================================================
class SSTReading(Base):
    __tablename__ = "sst_readings"

    id              = Column(Integer, primary_key=True, index=True)
    sensor_id       = Column(String(50), index=True, nullable=False)
    sensor_type     = Column(String(30), nullable=False)  # temp, humidity, smoke, ups, access
    zone            = Column(String(50), nullable=False)  # sala_servidores, pasillo_frio, etc.
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)

    # Temperatura (°C)
    temperature_c   = Column(Float, nullable=True)
    temp_threshold  = Column(Float, default=27.0)

    # Humedad (%)
    humidity_pct    = Column(Float, nullable=True)

    # Humo / incendio
    smoke_detected  = Column(Boolean, default=False)
    smoke_ppm       = Column(Float, default=0.0)

    # UPS / Energía
    ups_battery_pct = Column(Float, nullable=True)
    ups_load_pct    = Column(Float, nullable=True)
    power_kw        = Column(Float, nullable=True)
    pue             = Column(Float, nullable=True)  # Power Usage Effectiveness

    # Control de acceso
    access_event    = Column(String(100), nullable=True)
    unauthorized    = Column(Boolean, default=False)

    # Estado del sensor
    alert_level     = Column(String(20), default="normal")


# ============================================================
# MONITOREO SSL / TLS
# ============================================================
class SSLCertificate(Base):
    __tablename__ = "ssl_certificates"

    id              = Column(Integer, primary_key=True, index=True)
    node_id         = Column(String(50), index=True, nullable=False)
    domain          = Column(String(200), nullable=False)
    issuer          = Column(String(200), nullable=True)
    common_name     = Column(String(200), nullable=True)
    tls_version     = Column(String(20), nullable=True)   # TLSv1.2, TLSv1.3
    cipher_suite    = Column(String(100), nullable=True)

    issued_at       = Column(DateTime, nullable=True)
    expires_at      = Column(DateTime, nullable=True)
    days_to_expire  = Column(Integer, default=365)

    is_self_signed  = Column(Boolean, default=False)
    is_expired      = Column(Boolean, default=False)
    is_valid        = Column(Boolean, default=True)

    last_checked    = Column(DateTime, default=datetime.utcnow)
    alert_level     = Column(String(20), default="normal")
    alert_message   = Column(String(300), nullable=True)


# ============================================================
# INCIDENTES / ATAQUES
# ============================================================
class Incident(Base):
    __tablename__ = "incidents"

    id                  = Column(Integer, primary_key=True, index=True)
    session_id          = Column(Integer, ForeignKey("sessions.id"), nullable=True)

    # Clasificación
    incident_type       = Column(String(50), nullable=False)   # dos, ddos, brute_force, etc.
    category            = Column(String(30), nullable=False)   # attack, hardware, sst, ssl
    severity            = Column(String(20))
    node_affected       = Column(String(50), nullable=False)
    description         = Column(Text, nullable=True)

    # Timeline
    started_at          = Column(DateTime, nullable=False)
    detected_at         = Column(DateTime, nullable=True)
    resolved_at         = Column(DateTime, nullable=True)
    auto_resolved       = Column(Boolean, default=False)

    # Métricas de respuesta
    mttd_seconds        = Column(Float, nullable=True)   # Mean Time To Detect
    mttr_seconds        = Column(Float, nullable=True)   # Mean Time To Resolve
    mitigation_score    = Column(Float, nullable=True)   # 0-100

    # Estado
    status              = Column(String(20), default="active")
    root_cause          = Column(Text, nullable=True)
    resolution_notes    = Column(Text, nullable=True)

    # Relaciones
    session             = relationship("Session", back_populates="incidents")
    alerts              = relationship("Alert", back_populates="incident")
    mitigation_actions  = relationship("MitigationAction", back_populates="incident")


# ============================================================
# ALERTAS
# ============================================================
class Alert(Base):
    __tablename__ = "alerts"

    id              = Column(Integer, primary_key=True, index=True)
    incident_id     = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    node_id         = Column(String(50), nullable=False)
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)

    alert_type      = Column(String(50), nullable=False)
    severity        = Column(String(20))
    message         = Column(String(500), nullable=False)
    metric_name     = Column(String(50), nullable=True)
    metric_value    = Column(Float, nullable=True)
    threshold       = Column(Float, nullable=True)

    is_active       = Column(Boolean, default=True)
    acknowledged    = Column(Boolean, default=False)
    acknowledged_by = Column(Integer, ForeignKey("students.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)

    # Relaciones
    incident        = relationship("Incident", back_populates="alerts")


# ============================================================
# ACCIONES DE MITIGACIÓN
# ============================================================
class MitigationAction(Base):
    __tablename__ = "mitigation_actions"

    id                  = Column(Integer, primary_key=True, index=True)
    incident_id         = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    student_id          = Column(Integer, ForeignKey("students.id"), nullable=False)

    action_taken        = Column(String(200), nullable=False)
    action_category     = Column(String(50), nullable=True)  # block_ip, restart_service, etc.
    was_correct         = Column(Boolean, nullable=True)
    timestamp           = Column(DateTime, default=datetime.utcnow)
    effectiveness_pct   = Column(Float, default=0.0)
    notes               = Column(Text, nullable=True)

    # Relaciones
    incident            = relationship("Incident", back_populates="mitigation_actions")
    student             = relationship("Student", back_populates="mitigation_actions")


# ============================================================
# REPORTES GENERADOS
# ============================================================
class Report(Base):
    __tablename__ = "reports"

    id              = Column(Integer, primary_key=True, index=True)
    student_id      = Column(Integer, ForeignKey("students.id"), nullable=True)
    session_id      = Column(Integer, ForeignKey("sessions.id"), nullable=True)

    report_type     = Column(String(50), nullable=False)  # incident, health, student_shift, ssl, sst
    title           = Column(String(200), nullable=False)
    generated_at    = Column(DateTime, default=datetime.utcnow)
    file_path       = Column(String(500), nullable=True)
    file_format     = Column(String(10), default="pdf")   # pdf, csv

    # Resumen en JSON
    summary_json    = Column(Text, nullable=True)
    period_from     = Column(DateTime, nullable=True)
    period_to       = Column(DateTime, nullable=True)

    # Relaciones
    student         = relationship("Student", back_populates="reports")
    session         = relationship("Session", back_populates="reports")


class PracticeSession(Base):
    """Registro de práctica del Laboratorio de Mitigación."""
    __tablename__ = "practice_sessions"

    id               = Column(Integer, primary_key=True, index=True)
    student_id       = Column(Integer, ForeignKey("students.id"), nullable=False)
    scenario_type    = Column(String(60), nullable=False)
    scenario_name    = Column(String(200), nullable=False)
    score            = Column(Float, default=0.0)
    duration_sec     = Column(Float, default=0.0)
    steps_completed  = Column(Integer, default=0)
    total_steps      = Column(Integer, default=0)
    completed_at     = Column(DateTime, default=datetime.utcnow)

    student          = relationship("Student", backref="practice_sessions")


class GuidedSession(Base):
    """Registro de diagnóstico guiado completado por un estudiante."""
    __tablename__ = "guided_sessions"

    id              = Column(Integer, primary_key=True, index=True)
    student_id      = Column(Integer, ForeignKey("students.id"), nullable=False)
    attack_type     = Column(String(60), nullable=False)
    node_id         = Column(String(50), nullable=False)
    score           = Column(Float, default=0.0)
    correct_answers = Column(Integer, default=0)
    total_questions = Column(Integer, default=4)
    hints_used      = Column(Integer, default=0)
    duration_sec    = Column(Float, default=0.0)
    completed_at    = Column(DateTime, default=datetime.utcnow)

    student         = relationship("Student", backref="guided_sessions")


class SSTProtocolSession(Base):
    """Registro de protocolo SST completado por un estudiante."""
    __tablename__ = "sst_protocol_sessions"

    id              = Column(Integer, primary_key=True, index=True)
    student_id      = Column(Integer, ForeignKey("students.id"), nullable=False)
    protocol_type   = Column(String(60), nullable=False)
    protocol_name   = Column(String(200), nullable=False)
    sensor_name     = Column(String(200), nullable=False)
    sensor_value    = Column(String(50), nullable=True)
    score           = Column(Float, default=0.0)
    correct_answers = Column(Integer, default=0)
    total_questions = Column(Integer, default=4)
    bitacora        = Column(Text, nullable=True)
    duration_sec    = Column(Float, default=0.0)
    completed_at    = Column(DateTime, default=datetime.utcnow)

    student         = relationship("Student", backref="sst_sessions")


# ============================================================
# BITÁCORAS DE INCIDENTES
# ============================================================
class Bitacora(Base):
    """Bitácora reflexiva que el aprendiz redacta al mitigar un incidente."""
    __tablename__ = "bitacoras"

    id                  = Column(Integer, primary_key=True, index=True)
    student_id          = Column(Integer, ForeignKey("students.id"), nullable=False)

    # Datos técnicos (llenados automáticamente por el sistema)
    incident_id         = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    node_id             = Column(String(50), nullable=False)
    attack_type         = Column(String(60), nullable=False)
    severity            = Column(String(20), nullable=True)
    score               = Column(Float, default=0.0)
    correct_answers     = Column(Integer, default=0)
    total_questions     = Column(Integer, default=4)
    hints_used          = Column(Integer, default=0)
    mttd_seconds        = Column(Float, nullable=True)   # capturado si existe en incidente
    duration_sec        = Column(Float, default=0.0)     # duración del diagnóstico guiado

    # Campos redactados por el aprendiz
    sintomas_observados = Column(Text, nullable=False)   # ¿Qué detectó?
    causa_raiz          = Column(Text, nullable=False)   # ¿Por qué ocurrió?
    acciones_tomadas    = Column(Text, nullable=False)   # ¿Qué hizo?
    lecciones           = Column(Text, nullable=False)   # ¿Qué aprendió?

    # Sala colaborativa (nullable — bitácoras individuales no tienen sala)
    collab_room_id      = Column(Integer, ForeignKey("collab_rooms.id"), nullable=True)

    # Metadata
    created_at          = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    student             = relationship("Student", backref="bitacoras")
    incident            = relationship("Incident", backref="bitacoras", foreign_keys=[incident_id])


# ============================================================
# SALA COLABORATIVA
# ============================================================
class CollabRoom(Base):
    """Sala colaborativa creada por el instructor para un incidente grupal."""
    __tablename__ = "collab_rooms"

    id              = Column(Integer, primary_key=True, index=True)
    name            = Column(String(100), nullable=False)           # "Sala A", "Equipo Rojo"
    instructor_id   = Column(Integer, ForeignKey("students.id"), nullable=False)
    attack_type     = Column(String(60), nullable=True)             # Tipo de ataque asignado
    node_id         = Column(String(50), nullable=True)             # Nodo objetivo
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    ended_at        = Column(DateTime, nullable=True)

    # Relaciones
    members         = relationship("CollabMember", back_populates="room", cascade="all, delete-orphan")
    actions         = relationship("CollabAction", back_populates="room", cascade="all, delete-orphan")


class CollabMember(Base):
    """Estudiante asignado a una sala colaborativa con un rol específico."""
    __tablename__ = "collab_members"

    id          = Column(Integer, primary_key=True, index=True)
    room_id     = Column(Integer, ForeignKey("collab_rooms.id"), nullable=False)
    student_id  = Column(Integer, ForeignKey("students.id"), nullable=False)
    # Roles: T1-Monitor, T2-Analista, Responder, Comunicador
    role        = Column(String(30), nullable=False, default="T1-Monitor")
    joined_at   = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    room        = relationship("CollabRoom", back_populates="members")
    student     = relationship("Student", backref="collab_memberships")


class CollabAction(Base):
    """Acción técnica realizada por un miembro dentro de la sala (log compartido)."""
    __tablename__ = "collab_actions"

    id          = Column(Integer, primary_key=True, index=True)
    room_id     = Column(Integer, ForeignKey("collab_rooms.id"), nullable=False)
    student_id  = Column(Integer, ForeignKey("students.id"), nullable=False)
    action_type = Column(String(50), nullable=False)   # block_ip, restart_service, chat, terminal_cmd
    detail      = Column(Text, nullable=False)          # "bloqueó 203.0.113.45 en FW-01" / mensaje chat
    is_chat     = Column(Boolean, default=False)        # True = mensaje de chat, False = acción técnica
    timestamp   = Column(DateTime, default=datetime.utcnow, index=True)

    # Relaciones
    room        = relationship("CollabRoom", back_populates="actions")
    student     = relationship("Student", backref="collab_actions")


# ============================================================
# BITÁCORA COLABORATIVA — una por sala, cada rol llena su sección
# ============================================================
class CollabBitacora(Base):
    """Bitácora grupal: una por sala, cada miembro completa la sección de su rol."""
    __tablename__ = "collab_bitacoras"

    id              = Column(Integer, primary_key=True, index=True)
    room_id         = Column(Integer, ForeignKey("collab_rooms.id"), unique=True, nullable=False)
    incident_type   = Column(String(60), nullable=True)
    node_id         = Column(String(50), nullable=True)

    # Sección T1-Monitor
    t1_student_id   = Column(Integer, ForeignKey("students.id"), nullable=True)
    t1_sintomas     = Column(Text, nullable=True)
    t1_saved_at     = Column(DateTime, nullable=True)

    # Sección T2-Analista
    t2_student_id   = Column(Integer, ForeignKey("students.id"), nullable=True)
    t2_causa        = Column(Text, nullable=True)
    t2_saved_at     = Column(DateTime, nullable=True)

    # Sección Responder
    resp_student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    resp_acciones   = Column(Text, nullable=True)
    resp_saved_at   = Column(DateTime, nullable=True)

    # Sección Comunicador
    com_student_id  = Column(Integer, ForeignKey("students.id"), nullable=True)
    com_lecciones   = Column(Text, nullable=True)
    com_saved_at    = Column(DateTime, nullable=True)

    created_at      = Column(DateTime, default=datetime.utcnow)
    completed_at    = Column(DateTime, nullable=True)

    room            = relationship("CollabRoom", backref="bitacora", uselist=False)


# ============================================================
# SESIONES EVALUATIVAS GRUPALES
# ============================================================
class EvalGroup(Base):
    """Grupo de aprendices evaluados en una sesión grupal colaborativa."""
    __tablename__ = "eval_groups"

    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(String(200), nullable=True)          # Nombre del grupo (opcional)
    student_ids_json = Column(Text, nullable=False)                # JSON: [1, 2, 3]
    session_ids_json = Column(Text, nullable=True)                 # JSON: [10, 11, 12]
    started_at       = Column(DateTime, default=datetime.utcnow)
    ended_at         = Column(DateTime, nullable=True)
    is_active        = Column(Boolean, default=True)
    group_score      = Column(Float, nullable=True)                # Promedio grupal final
    notes            = Column(Text, nullable=True)
