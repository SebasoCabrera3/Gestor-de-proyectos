from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship

# Base de datos
# -------------------------------------------------------------------
db = SQLAlchemy()

class Area(db.Model):
    __tablename__ = 'area'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    codigo = db.Column(db.String(16), unique=True, nullable=False)

    users = db.relationship('User', back_populates='area', lazy=True)
    projects = db.relationship('Project', back_populates='area', lazy=True)
    tareas_generales = db.relationship('TareaGeneral', back_populates='area', lazy=True)

    def __repr__(self):
        return f"<Area {self.name} | Código: {self.codigo}>"


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='apoyo')
    area_id = db.Column(db.Integer, db.ForeignKey('area.id'), nullable=True)
    area = db.relationship('Area', back_populates='users')

    leader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    leader = db.relationship('User', remote_side=[id], back_populates='apoyos')
    apoyos = db.relationship('User', back_populates='leader', lazy=True)

    is_active = db.Column(db.Boolean, default=True)
    confirmed = db.Column(db.Boolean, default=False)

    created_projects = db.relationship('Project', back_populates='creator', lazy=True, foreign_keys='Project.creator_id')
    tareas_generales_creadas = db.relationship('TareaGeneral', back_populates='creator', lazy=True, foreign_keys='TareaGeneral.creator_id')
    subtareas_asignadas = db.relationship('Subtarea', back_populates='assigned_user', lazy=True, foreign_keys='Subtarea.assigned_user_id')
    subtareas_creadas = db.relationship('Subtarea', back_populates='creator', lazy=True, foreign_keys='Subtarea.creator_id')
    subtareas_validadas = db.relationship('Subtarea', back_populates='validador', lazy=True, foreign_keys='Subtarea.validador_id')

    def __repr__(self):
        return f"<User {self.username} ({self.role}) - Área: {self.area.name if self.area else 'N/A'}>"


class Project(db.Model):
    __tablename__ = 'project'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='En ejecución')

    area_id = db.Column(db.Integer, db.ForeignKey('area.id'), nullable=True)
    area = db.relationship('Area', back_populates='projects')
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', back_populates='created_projects', foreign_keys=[creator_id])

    tareas_generales = db.relationship('TareaGeneral', back_populates='project', lazy=True, cascade="all, delete-orphan")
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def porcentaje_avance(self):
        avances = [tg.avance_automatico for tg in self.tareas_generales]
        return round(sum(avances) / len(avances), 1) if avances else 0.0

    @property
    def estado(self):
        self.actualizar_estado_auto()
        return self.status

    def actualizar_estado_auto(self, override_estado=None):
        hoy = datetime.utcnow().date()
        avance = self.porcentaje_avance or 0
        try:
            fecha_limite = self.end_date.date()
        except AttributeError:
            fecha_limite = self.end_date

        if override_estado and override_estado.lower() in ['suspendido', 'cancelado']:
            self.status = override_estado.title()
        elif override_estado and override_estado.lower() in ['pendiente', 'en ejecución', 'en ejecucion', 'finalizado']:
            self.status = override_estado.title()
        else:
            if avance >= 100:
                self.status = 'Finalizado'
            elif fecha_limite and hoy > fecha_limite and avance < 100:
                self.status = 'Retrasado'
            elif avance > 0:
                self.status = 'En ejecución'
            else:
                self.status = 'Pendiente'

    def __repr__(self):
        return f"<Project {self.name} | Área: {self.area.name if self.area else 'No Asignada'}>"


class TareaGeneral(db.Model):
    __tablename__ = 'tarea_general'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    fecha_limite = db.Column(db.Date, nullable=True)
    prioridad = db.Column(db.String(20), default='Media')
    status = db.Column(db.String(50), default='Pendiente')
    porcentaje_avance = db.Column(db.Float, default=0.0)

    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    project = db.relationship('Project', back_populates='tareas_generales')
    area_id = db.Column(db.Integer, db.ForeignKey('area.id'), nullable=False)
    area = db.relationship('Area', back_populates='tareas_generales')
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', back_populates='tareas_generales_creadas', foreign_keys=[creator_id])
    subtareas = db.relationship('Subtarea', back_populates='tarea_general', lazy=True, cascade="all, delete-orphan")

    @property
    def avance_automatico(self):
        if not self.subtareas:
            return 0
        valores = [s.avance_validado or 0 for s in self.subtareas]
        return round(sum(valores) / len(valores), 1)

    @property
    def estado(self):
        self.actualizar_estado_auto()
        return self.status

    def actualizar_estado_auto(self, override_estado=None):
        hoy = datetime.utcnow().date()
        avance = self.avance_automatico or 0
        try:
            fecha_limite = self.fecha_limite.date()
        except AttributeError:
            fecha_limite = self.fecha_limite

        if override_estado and override_estado.lower() in ['suspendido', 'cancelado']:
            self.status = override_estado.title()
        elif override_estado and override_estado.lower() in ['pendiente', 'en ejecución', 'en ejecucion', 'finalizado']:
            self.status = override_estado.title()
        else:
            if avance >= 100:
                self.status = 'Finalizado'
            elif fecha_limite and hoy > fecha_limite and avance < 100:
                self.status = 'Retrasado'
            elif avance > 0:
                self.status = 'En ejecución'
            else:
                self.status = 'Pendiente'

    def __repr__(self):
        return f"<TareaGeneral {self.title} - Área: {self.area.name if self.area else 'N/A'}>"


class Subtarea(db.Model):
    __tablename__ = 'subtarea'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='Pendiente')
    prioridad = db.Column(db.String(20), nullable=False, default='Media')
    fecha_limite = db.Column(db.Date, nullable=True)
    avance = db.Column(db.Integer, default=0)
    documento_aporte = db.Column(db.String(256), nullable=True)
    avance_validado = db.Column(db.Integer, default=0)
    validado = db.Column(db.Boolean, default=False)

    validador_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    validador = db.relationship('User', back_populates='subtareas_validadas', foreign_keys=[validador_id])
    tarea_general_id = db.Column(db.Integer, db.ForeignKey('tarea_general.id'), nullable=False)
    tarea_general = db.relationship('TareaGeneral', back_populates='subtareas')
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    assigned_user = db.relationship('User', back_populates='subtareas_asignadas', foreign_keys=[assigned_user_id])
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', back_populates='subtareas_creadas', foreign_keys=[creator_id])

    @property
    def estado(self):
        self.actualizar_estado_auto()
        return self.status

    def actualizar_estado_auto(self, override_estado=None):
        hoy = datetime.utcnow().date()
        avance = self.avance_validado or 0
        try:
            fecha_limite = self.fecha_limite.date()
        except AttributeError:
            fecha_limite = self.fecha_limite

        if override_estado and override_estado.lower() in ['suspendido', 'cancelado']:
            self.status = override_estado.title()
        elif override_estado and override_estado.lower() in ['pendiente', 'en ejecución', 'en ejecucion', 'finalizado']:
            self.status = override_estado.title()
        else:
            if avance >= 100:
                self.status = 'Finalizado'
            elif fecha_limite and hoy > fecha_limite and avance < 100:
                self.status = 'Retrasado'
            elif avance > 0:
                self.status = 'En ejecución'
            else:
                self.status = 'Pendiente'

    def __repr__(self):
        return f"<Subtarea {self.title} - Estado {self.status}>"
