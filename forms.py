# forms.py

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, TextAreaField, SelectField,
    DateField, IntegerField, FileField, SubmitField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, Optional,
    ValidationError, NumberRange
)
from wtforms_sqlalchemy.fields import QuerySelectField
from flask_wtf.file import FileAllowed, FileRequired

from models import User, Area


# -------------------------------------------------------------------
# FORMULARIO DE REGISTRO PARA “APOYO” (por código de área)
# -------------------------------------------------------------------
class ApoyoRegisterForm(FlaskForm):
    username = StringField(
        'Nombre de usuario',
        validators=[DataRequired(), Length(min=2, max=20)]
    )
    email = StringField(
        'Correo electrónico',
        validators=[DataRequired(), Email(message="Introduce un correo válido")]
    )
    password = PasswordField(
        'Contraseña',
        validators=[DataRequired()]
    )
    confirm_password = PasswordField(
        'Confirmar contraseña',
        validators=[DataRequired(), EqualTo('password', message="Las contraseñas deben coincidir")]
    )
    area_codigo = StringField(
        'Código de área',
        validators=[DataRequired(), Length(min=4, max=16)]
    )
    submit = SubmitField('Registrarme como Apoyo')

    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first():
            raise ValidationError('Ese nombre de usuario ya existe.')

    def validate_email(self, email):
        if User.query.filter_by(email=email.data).first():
            raise ValidationError('Ese correo ya está registrado.')


# -------------------------------------------------------------------
# FORMULARIO DE LOGIN
# -------------------------------------------------------------------
class LoginForm(FlaskForm):
    username_or_email = StringField(
        'Usuario o correo',
        validators=[DataRequired()]
    )
    password = PasswordField(
        'Contraseña',
        validators=[DataRequired()]
    )
    submit = SubmitField('Iniciar sesión')


# -------------------------------------------------------------------
# FORMULARIO PARA PROYECTOS
# -------------------------------------------------------------------
class ProjectForm(FlaskForm):
    name = StringField(
        'Nombre del proyecto',
        validators=[DataRequired(), Length(min=4, max=300)]
    )
    description = TextAreaField(
        'Descripción',
        validators=[Optional(), Length(max=500)]
    )
    start_date = DateField(
        'Fecha de inicio (YYYY-MM-DD)',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    end_date = DateField(
        'Fecha de fin (YYYY-MM-DD)',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    # El estado se puede sobreescribir manualmente, pero por defecto se calcula en la ruta
    status = SelectField(
        'Estado (opcional)',
        choices=[
            ('En ejecución', 'En ejecución'),
            ('Finalizado',   'Finalizado'),
            ('Suspendido',   'Suspendido'),
            ('Cancelado',    'Cancelado')
        ],
        validators=[Optional()]
    )
    submit = SubmitField('Guardar proyecto')


# -------------------------------------------------------------------
# FORMULARIO PARA TAREAS GENERALES
# -------------------------------------------------------------------
class TareaGeneralForm(FlaskForm):
    title = StringField(
        'Título de la Tarea General',
        validators=[DataRequired(), Length(min=4, max=100)]
    )
    description = TextAreaField(
        'Descripción (opcional)',
        validators=[Optional(), Length(max=500)]
    )
    fecha_limite = DateField(
        'Fecha límite (YYYY-MM-DD)',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    prioridad = SelectField(
        'Prioridad',
        choices=[('Alta', 'Alta'), ('Media', 'Media'), ('Baja', 'Baja')],
        validators=[DataRequired()]
    )
    area_id = QuerySelectField(
        'Área asignada',
        query_factory=lambda: Area.query.order_by(Area.name).all(),
        get_label='name',
        allow_blank=False,
        validators=[DataRequired()]
    )
    # NO incluimos status aquí; el estado se calcula automáticamente según avance de subtareas
    submit = SubmitField('Guardar Tarea General')


# -------------------------------------------------------------------
# FORMULARIO PARA EDITAR EL ESTADO DE UNA TAREA GENERAL
# (solo si quieres sobreescribir manualmente el status)
# -------------------------------------------------------------------
class EditarEstadoTareaForm(FlaskForm):
    status = SelectField(
        'Estado',
        choices=[
            ('En ejecución', 'En ejecución'),
            ('Finalizado',   'Finalizado'),
            ('Suspendido',   'Suspendido'),
            ('Cancelado',    'Cancelado')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Actualizar Estado')


# -------------------------------------------------------------------
# FORMULARIO PARA QUE EL “APOYO” SUBA UN DOCUMENTO DE APORTE
# -------------------------------------------------------------------
class SubtareaAporteForm(FlaskForm):
    documento = FileField(
        'Documento de Evidencia (PDF, DOCX, XLSX)',
        validators=[
            FileRequired(message="Debe seleccionar un archivo."),
            FileAllowed(['pdf', 'doc', 'docx', 'xlsx'], "Solo se permiten archivos PDF/DOC/DOCX/XLSX.")
        ]
    )
    submit = SubmitField('Subir Aporte')


# -------------------------------------------------------------------
# FORMULARIO PARA “APOYO” ACTUALIZAR SU AVANCE (solo porcentaje)
# -------------------------------------------------------------------
class SubtareaAvanceForm(FlaskForm):
    avance = IntegerField(
        'Avance (%)',
        validators=[DataRequired(), NumberRange(min=0, max=100)],
        default=0
    )
    submit = SubmitField('Actualizar Avance')


# -------------------------------------------------------------------
# FORMULARIO PARA “ENCARGADO” / “SUPERVISOR”:
# gestionar subtarea y validar avance
# -------------------------------------------------------------------
class SubtareaForm(FlaskForm):
    title = StringField(
        'Título de la Subtarea',
        validators=[DataRequired(), Length(min=2, max=200)]
    )
    description = TextAreaField(
        'Descripción',
        validators=[Optional(), Length(max=500)]
    )
    fecha_limite = DateField(
        'Fecha límite (YYYY-MM-DD)',
        format='%Y-%m-%d',
        validators=[Optional()]
    )
    status = SelectField(
        'Estado (opcional)',
        choices=[
            ('En ejecución', 'En ejecución'),
            ('Finalizado',   'Finalizado'),
            ('Suspendido',   'Suspendido'),
            ('Cancelado',    'Cancelado')
        ],
        validators=[Optional()]
    )
    prioridad = SelectField(
        'Prioridad',
        choices=[('Alta', 'Alta'), ('Media', 'Media'), ('Baja', 'Baja')],
        validators=[DataRequired()]
    )
    assigned_user = QuerySelectField(
        'Asignar a Usuario (Apoyo)',
        query_factory=lambda: User.query.filter_by(role='apoyo').order_by(User.username).all(),
        get_label='username',
        allow_blank=True,
        blank_text='-- Sin asignar --'
    )
    # Campos para que el encargado valide el % de avance final
    avance_validado = IntegerField(
        'Avance Validado (%)',
        validators=[Optional(), NumberRange(min=0, max=100)],
        default=0
    )
    validado = SelectField(
        'Validado',
        choices=[('no', 'No Validado'), ('si', 'Validado')],
        validators=[Optional()]
    )
    submit = SubmitField('Guardar Cambios')


# -------------------------------------------------------------------
# FORMULARIO PARA “APOYO” ACTUALIZAR SU AVANCE Y OPCIONALMENTE SUBIR EVIDENCIA
# -------------------------------------------------------------------
class SubtareaAvanceAporteForm(FlaskForm):
    avance = IntegerField(
        'Avance (%)',
        validators=[Optional(), NumberRange(min=0, max=100)],
        render_kw={"placeholder": "0–100"}
    )
    documento = FileField(
        'Documento de Evidencia (PDF, DOCX, XLSX)',
        validators=[
            Optional(),  # Si el apoyo ya subió antes, podría no querer volver a subir.
            FileAllowed(['pdf', 'doc', 'docx', 'xlsx'], "Solo se permiten PDF/DOC/DOCX/XLSX.")
        ]
    )
    submit = SubmitField('Guardar Avance/Aporte')
