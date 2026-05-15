"""
DC Monitoring Simulator - Modelos de Base de Datos
SQLAlchemy ORM - SQLite
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, Text, Enum
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
    role             = Column(Enum("student", "instructor", name="role_enum"), default="student")
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
    alert_level     = Column(Enum("normal", "warning", "critical", name="sst_alert_enum"), default="normal")


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
    alert_level     = Column(Enum("normal", "warning", "critical", name="ssl_alert_enum"), default="normal")
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
    severity            = Column(Enum("info", "warning", "critical", name="severity_enum"))
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
    status              = Column(Enum("active", "detected", "mitigating", "resolved", "missed",
                                      name="incident_status_enum"), default="active")
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
    severity        = Column(Enum("info", "warning", "critical", name="alert_severity_enum"))
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
