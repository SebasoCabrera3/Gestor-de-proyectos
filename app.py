import os
import io
from flask import Flask, render_template, redirect, url_for, request, flash, current_app
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail
from flask import send_from_directory
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from datetime import datetime, date
from sqlalchemy.orm import joinedload # Import para optimizar consultas de relaciones
from sqlalchemy import desc, asc, func # Asegúrate que db está inicializado en models.py y que las clases están bien definidas
from models import db, User, Area, Project, TareaGeneral, Subtarea
from forms import (
    LoginForm, ApoyoRegisterForm,
    ProjectForm, TareaGeneralForm, SubtareaForm,
    SubtareaAporteForm, SubtareaAvanceForm, SubtareaAvanceAporteForm
)
from config import Config
from models import Subtarea, TareaGeneral, User, db
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload
from flask import send_file



# --- Inicialización de la aplicación ---
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
mail = Mail(app)
bcrypt = Bcrypt(app)
migrate = Migrate(app, db)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)



@app.context_processor
def inject_now():
    """Inyecta el objeto datetime.utcnow() en todas las plantillas Jinja2."""
    return {'now': datetime.utcnow()}

# --- Autenticación ---
@login_manager.user_loader
def load_user(user_id):
    """Carga un usuario dado su ID para Flask-Login."""
    # SQLAlchemy 2.0 recomienda Session.get() en lugar de Query.get()
    return db.session.get(User, int(user_id))

# --- Funciones auxiliares para verificar el estado de las tareas ---


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def es_retrasada_subtarea(subtarea):
    """
    Verifica si una subtarea está retrasada.
    Se considera retrasada si su fecha límite ha pasado y no está en un estado finalizado/suspendido/cancelado.
    """
    if subtarea.fecha_limite is None:
        return False
    # Comparar solo la fecha, ignorando la hora
    return subtarea.fecha_limite < date.today() and subtarea.status.lower() not in ['finalizado', 'suspendido', 'cancelado']

def es_retrasada_tarea_general(tarea_general):
    """
    Verifica si una tarea general está retrasada.
    Esto podría basarse en su propia fecha límite o en si tiene subtareas retrasadas.
    Para este ejemplo, usaremos su propia fecha límite.
    """
    if tarea_general.fecha_limite is None:
        return False
    return tarea_general.fecha_limite < date.today() and tarea_general.status.lower() not in ['finalizado', 'suspendido', 'cancelado']

# --- Rutas principales ---

# ¡CORRECCIÓN IMPORTANTE! No puedes tener dos rutas idénticas ('/')
# Una de ellas debe ser la ruta principal (index) y la otra es redundante o un error.
# He eliminado `welcome` y la he consolidado en `index`.
# He renombrado `welcome.html` a `index.html` como acordamos previamente.

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard')) # Si está logeado, va al dashboard
    return render_template('index.html') # Si no, va a la página de bienvenida (index.html)

# 3. Selección de rol
@app.route('/roles')
def roles():
    return render_template('roles.html')



@app.route('/gestionar_usuarios')
@login_required
def gestionar_usuarios():
    if current_user.role not in ['supervisor', 'encargado']:
        flash('No autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    if current_user.role == 'supervisor':
        usuarios = User.query.all()
    else:  # encargado
        usuarios = User.query.filter_by(area_id=current_user.area_id).all()

    return render_template('gestionar_usuarios.html', usuarios=usuarios)


@app.route('/eliminar_usuario/<int:user_id>', methods=['POST'])
@login_required
def eliminar_usuario(user_id):
    if current_user.role not in ['supervisor', 'encargado']:
        flash('No autorizado.', 'danger')
        return redirect(url_for('dashboard'))

    usuario = User.query.get_or_404(user_id)

    # Solo supervisores pueden eliminar cualquier usuario
    # Encargado solo puede eliminar usuarios de su área y nunca a sí mismo
    if current_user.role == 'encargado':
        if usuario.area_id != current_user.area_id or usuario.id == current_user.id:
            flash('No puedes eliminar este usuario.', 'danger')
            return redirect(url_for('gestionar_usuarios'))

    db.session.delete(usuario)
    db.session.commit()
    flash('Usuario eliminado exitosamente.', 'success')
    return redirect(url_for('gestionar_usuarios'))





@app.route('/login', methods=['GET', 'POST'])
def login():
    """Maneja el inicio de sesión de los usuarios según rol."""
    # 1) Capturamos el role que venga en la query string
    role_param = request.args.get('role')  # 'supervisor', 'lider_area' o 'apoyo'

    # 2) Mapeo a los roles internos que tienes en la BD
    role_map = {
        'supervisor': 'supervisor',
        'lider_area': 'encargado',  # en create_users.py usas role='encargado'
        'apoyo': 'apoyo'
    }
    target_role = role_map.get(role_param)

    # 3) Si ya está logueado, lo enviamos al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(
            (User.username == form.username_or_email.data) |
            (User.email    == form.username_or_email.data)
        ).first()

        if user and bcrypt.check_password_hash(user.password, form.password.data):
            # 4) Verificamos que el usuario tenga el role adecuado
            if target_role and user.role != target_role:
                flash(f'No tienes permiso para iniciar sesión como {role_param.replace("_"," ")}.', 'danger')
                return render_template('login.html', form=form, role=role_param)

            # 5) Si todo OK, iniciamos sesión
            login_user(user)
            flash(f'¡Bienvenido, {user.username}!', 'success')
            return redirect(url_for('dashboard'))

        flash('Credenciales inválidas. Verifica usuario/email y contraseña.', 'danger')

    # 6) Renderizamos la plantilla, pasando form y role
    return render_template('login.html', form=form, role=role_param)



# --------------------------------------------------
# LOGOUT → volvemos a 'roles' como solicitaste
# --------------------------------------------------
@app.route('/logout')
@login_required
def logout():
    """Cierra la sesión del usuario y vuelve a la pantalla de roles."""
    logout_user()
    flash('Sesión cerrada exitosamente.', 'info')
    return redirect(url_for('roles'))


# --------------------------------------------------
# REGISTER APOYO → al registrarse, redirige al login con role=apoyo
# --------------------------------------------------
@app.route('/register-apoyo', methods=['GET', 'POST'])
def register_apoyo():
    """Maneja el registro de nuevos usuarios con rol 'apoyo'."""
    # Si un usuario ya logueado intenta registrarse, lo mandamos al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = ApoyoRegisterForm()
    if form.validate_on_submit():
        area = Area.query.filter_by(codigo=form.area_codigo.data).first()
        if not area:
            flash('Código de área inválido. Por favor, verifica el código de tu área.', 'danger')
            return render_template('register_apoyo.html', form=form)

        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_password,
            role='apoyo',
            area=area
        )
        db.session.add(user)
        db.session.commit()

        flash('Registro exitoso. Ahora puedes iniciar sesión cuando tu cuenta sea aprobada.', 'success')
        # Redirigimos al login y pasamos role=apoyo para que muestre el enlace de "Regístrate"
        return redirect(url_for('login', role='apoyo'))

    return render_template('register_apoyo.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    # 1) Parámetros de filtro/orden desde la URL
    search_project_query = request.args.get('search_project', '').strip()
    status_project_query = request.args.get('status_project', '')
    sort_by_query        = request.args.get('sort_by', 'project_end_date')  # Orden por defecto
    sort_order_query     = request.args.get('sort_order', 'desc')           # Sentido por defecto

    # Listas de salida para la plantilla
    proyectos_para_sidebar            = []
    main_projects_list                = []
    tareas_generales_encargado        = []
    subtareas_del_area_para_encargado = []
    subtareas_del_apoyo               = []
    subtareas_retrasadas_data         = []

    # 2) Comprobar si existe la ruta gestionar_usuarios
    has_gestionar_usuarios_route = 'gestionar_usuarios' in current_app.view_functions

    # 3) Construir "proyectos_para_sidebar" y "subtareas_retrasadas_data" según rol
    projects_db_for_sidebar = Project.query.options(
        joinedload(Project.tareas_generales)
            .subqueryload(TareaGeneral.area)
            .joinedload(Area.users),
        joinedload(Project.tareas_generales)
            .subqueryload(TareaGeneral.subtareas)
            .joinedload(Subtarea.assigned_user)
    ).order_by(Project.name.asc()).all()

    if current_user.role == 'supervisor':
        for proyecto in projects_db_for_sidebar:
            pd = {'id': proyecto.id, 'nombre': proyecto.name, 'tareas_generales': []}
            for tg in proyecto.tareas_generales:
                area_data = None
                if tg.area:
                    area_data = {
                        'id': tg.area.id,
                        'nombre': tg.area.name,
                        'apoyos': [
                            {'id': u.id, 'username': u.username.replace('_',' ').title()}
                            for u in tg.area.users if u.role == 'apoyo'
                        ]
                    }
                subt_list = []
                for s in tg.subtareas:
                    sd = {
                        'id': s.id,
                        'nombre': s.title,
                        'fecha_limite': s.fecha_limite,
                        'status': s.status,
                        'proyecto_nombre': proyecto.name,
                        'asignado_a_nombre': s.assigned_user.username.replace('_',' ').title() if s.assigned_user else 'Sin asignar',
                        'avance_validado': s.avance_validado or 0
                    }
                    subt_list.append(sd)
                    # Solo para advertir de subtareas retrasadas
                    if s.fecha_limite and s.status.lower() not in ['finalizado', 'suspendido', 'cancelado']:
                        fecha_limite_date = s.fecha_limite
                        if hasattr(s.fecha_limite, 'date'):
                            fecha_limite_date = s.fecha_limite.date()
                        if fecha_limite_date < date.today():
                            subtareas_retrasadas_data.append(sd)
                tg_data = {
                    'id': tg.id,
                    'nombre': tg.title,
                    'area': area_data,
                    'subtareas': subt_list,
                }
                pd['tareas_generales'].append(tg_data)
            proyectos_para_sidebar.append(pd)

    elif current_user.role == 'encargado':
        for proyecto in projects_db_for_sidebar:
            tg_list_area = []
            for tg in proyecto.tareas_generales:
                if tg.area_id == current_user.area_id:
                    area_data = None
                    if tg.area:
                        area_data = {
                            'id': tg.area.id,
                            'nombre': tg.area.name,
                            'apoyos': [
                                {'id': u.id, 'username': u.username.replace('_',' ').title()}
                                for u in tg.area.users if u.role == 'apoyo'
                            ]
                        }
                    subt_list = []
                    for s in tg.subtareas:
                        sd = {
                            'id': s.id,
                            'nombre': s.title,
                            'fecha_limite': s.fecha_limite,
                            'status': s.status,
                            'proyecto_nombre': proyecto.name,
                            'asignado_a_nombre': s.assigned_user.username.replace('_',' ').title() if s.assigned_user else 'Sin asignar',
                            'avance_validado': s.avance_validado or 0
                        }
                        subt_list.append(sd)
                        if s.fecha_limite and s.status.lower() not in ['finalizado', 'suspendido', 'cancelado']:
                            fecha_limite_date = s.fecha_limite
                            if hasattr(s.fecha_limite, 'date'):
                                fecha_limite_date = s.fecha_limite.date()
                            if fecha_limite_date < date.today():
                                subtareas_retrasadas_data.append(sd)
                    tg_data = {'id': tg.id, 'nombre': tg.title, 'area': area_data, 'subtareas': subt_list}
                    tg_list_area.append(tg_data)

                    # Guardar el objeto TareaGeneral para la vista de Encargado
                    tareas_generales_encargado.append(tg)

                    for s_obj in tg.subtareas:
                        subtareas_del_area_para_encargado.append(s_obj)

            if tg_list_area:
                proyectos_para_sidebar.append({
                    'id': proyecto.id,
                    'nombre': proyecto.name,
                    'tareas_generales': tg_list_area
                })

    elif current_user.role == 'apoyo':
        for proyecto in projects_db_for_sidebar:
            pa = {'id': proyecto.id, 'nombre': proyecto.name, 'tareas_generales': []}
            tiene_algo_para_sidebar = False
            for tg in proyecto.tareas_generales:
                subt_list_para_sidebar = []
                for s in tg.subtareas:
                    if s.assigned_user_id == current_user.id:
                        sd = {
                            'id': s.id,
                            'nombre': s.title,
                            'fecha_limite': s.fecha_limite,
                            'status': s.status,
                            'proyecto_nombre': proyecto.name,
                            'asignado_a_nombre': s.assigned_user.username.replace('_',' ').title() if s.assigned_user else 'Sin asignar',
                            'avance_validado': s.avance_validado or 0
                        }
                        subt_list_para_sidebar.append(sd)
                        if s.fecha_limite and s.status.lower() not in ['finalizado', 'suspendido', 'cancelado']:
                            fecha_limite_date = s.fecha_limite
                            if hasattr(s.fecha_limite, 'date'):
                                fecha_limite_date = s.fecha_limite.date()
                            if fecha_limite_date < date.today():
                                subtareas_retrasadas_data.append(sd)
                        subtareas_del_apoyo.append(s)
                if subt_list_para_sidebar:
                    tiene_algo_para_sidebar = True
                    area_data = None
                    if tg.area:
                        area_data = {'id': tg.area.id, 'nombre': tg.area.name}
                    pa['tareas_generales'].append({
                        'id': tg.id,
                        'nombre': tg.title,
                        'area': area_data,
                        'subtareas': subt_list_para_sidebar
                    })
            if tiene_algo_para_sidebar:
                proyectos_para_sidebar.append(pa)

    # 4) Construir la query de “main_projects_list” para la tabla de vista general
    if current_user.role == 'supervisor':
        main_projects_query = Project.query
    elif current_user.role == 'encargado':
        main_projects_query = Project.query.join(Project.tareas_generales).filter(
            TareaGeneral.area_id == current_user.area_id
        ).distinct()
    elif current_user.role == 'apoyo':
        main_projects_query = Project.query.join(Project.tareas_generales).join(TareaGeneral.subtareas).filter(
            Subtarea.assigned_user_id == current_user.id
        ).distinct()
    else:
        main_projects_query = Project.query.filter(Project.id == -1)

    if search_project_query:
        main_projects_query = main_projects_query.filter(Project.name.ilike(f'%{search_project_query}%'))
    if status_project_query:
        main_projects_query = main_projects_query.filter(func.lower(Project.status) == func.lower(status_project_query))

    order_map = {
        'project_name':     Project.name,
        'project_status':   Project.status,
        'project_end_date': Project.end_date
    }
    order_attr = order_map.get(sort_by_query, Project.end_date)
    if sort_order_query == 'desc':
        main_projects_query = main_projects_query.order_by(desc(order_attr))
    else:
        main_projects_query = main_projects_query.order_by(asc(order_attr))

    main_projects_list = main_projects_query.all()

    # 5) Contadores globales
    estado_ejec = 'en ejecución'
    estado_pend = 'pendiente'

    total_proyectos_activos = 0
    total_tareas_pendientes = 0

    if current_user.role == 'supervisor':
        total_proyectos_activos = Project.query.filter(func.lower(Project.status) == estado_ejec).count()
        total_tareas_pendientes = TareaGeneral.query.filter(func.lower(TareaGeneral.status) == estado_pend).count()
    elif current_user.role == 'encargado':
        total_proyectos_activos = Project.query.join(Project.tareas_generales).filter(
            TareaGeneral.area_id == current_user.area_id,
            func.lower(Project.status) == estado_ejec
        ).distinct().count()
        total_tareas_pendientes = TareaGeneral.query.filter(
            TareaGeneral.area_id == current_user.area_id,
            func.lower(TareaGeneral.status) == estado_pend
        ).count()
    elif current_user.role == 'apoyo':
        total_proyectos_activos = Project.query.join(Project.tareas_generales).join(TareaGeneral.subtareas).filter(
            Subtarea.assigned_user_id == current_user.id,
            func.lower(Project.status) == estado_ejec
        ).distinct().count()
        total_tareas_pendientes = TareaGeneral.query.join(TareaGeneral.subtareas).filter(
            Subtarea.assigned_user_id == current_user.id,
            func.lower(TareaGeneral.status) == estado_pend
        ).distinct().count()

    # Si hay subtareas retrasadas y no se recibieron parámetros GET, mostramos flash
    if subtareas_retrasadas_data and not request.args:
        flash(f'¡Atención! Tienes {len(subtareas_retrasadas_data)} subtarea(s) retrasada(s).', 'danger')

    # 6) Preparar datos para los gráficos (solo Supervisor)
    chart_proyectos_labels = []
    chart_proyectos_values = []
    chart_tareas_labels    = []
    chart_tareas_values    = []

    if current_user.role == 'supervisor':
        # Gráfico 1: Proyectos por Estado
        estados_proyecto = ['Pendiente', 'En Ejecución', 'Finalizado', 'Suspendido', 'Cancelado']
        for e in estados_proyecto:
            cnt = Project.query.filter(func.lower(Project.status) == e.lower()).count()
            if cnt > 0:
                chart_proyectos_labels.append(e)
                chart_proyectos_values.append(cnt)
        if not chart_proyectos_labels:
            chart_proyectos_labels.append("Sin Proyectos")
            chart_proyectos_values.append(0)

        # Gráfico 2: Tareas Generales por Prioridad
        prioridades_tg = ['Alta', 'Media', 'Baja']
        for p in prioridades_tg:
            cnt2 = TareaGeneral.query.filter(func.lower(TareaGeneral.prioridad) == p.lower()).count()
            if cnt2 > 0:
                chart_tareas_labels.append(p)
                chart_tareas_values.append(cnt2)
        cnt_sin_prioridad = TareaGeneral.query.filter(
            (TareaGeneral.prioridad == None) |
            (func.lower(TareaGeneral.prioridad) == 'sin prioridad')
        ).count()
        if cnt_sin_prioridad > 0:
            chart_tareas_labels.append('Sin Prioridad')
            chart_tareas_values.append(cnt_sin_prioridad)
        if not chart_tareas_labels:
            chart_tareas_labels.append("Sin Tareas")
            chart_tareas_values.append(0)

    # 7) Mapas de progreso basados en las propiedades de los modelos
    project_progress_map = {}
    tasks_progress_map   = {}  # ← se inicializa aquí como diccionario, para TODOS los roles

    # Si es supervisor, cargamos los proyectos y TODOS los TG
    if current_user.role == 'supervisor':
        # Avance global de cada proyecto
        for proyecto in main_projects_list:
            project_progress_map[proyecto.id] = round(proyecto.porcentaje_avance, 1)

        # Avance por cada TareaGeneral (todas)
        for tg_obj in TareaGeneral.query.all():
            tasks_progress_map[tg_obj.id] = round(tg_obj.avance_automatico, 1)

    # Si es encargado, solo cargamos el avance de SUS Tareas Generales
    elif current_user.role == 'encargado':
        # `tareas_generales_encargado` ya fue llenado más arriba con las TG asignadas a este encargado
        for tg in tareas_generales_encargado:
            tasks_progress_map[tg.id] = round(tg.avance_automatico, 1)

    # (Para “apoyo” no necesitamos rellenar tasks_progress_map;
    #  el bloque de “APOYO” en la plantilla NO usa tasks_progress_map,
    #  sino que extrae directamente `s.avance` de cada Subtarea.)



    # 8) Renderizar plantilla, enviando todas las variables necesarias
    return render_template(
        'dashboard.html',
        proyectos                           = proyectos_para_sidebar,
        main_projects                       = main_projects_list,
        subtareas_retrasadas_data           = subtareas_retrasadas_data,
        total_proyectos_activos             = total_proyectos_activos,
        total_tareas_pendientes             = total_tareas_pendientes,
        has_gestionar_usuarios_route        = has_gestionar_usuarios_route,
        search_project_val                  = search_project_query,
        status_project_val                  = status_project_query,
        current_sort_by                     = sort_by_query,
        current_sort_order                  = sort_order_query,
        tareas_generales_encargado          = tareas_generales_encargado,
        subtareas_del_area_para_encargado   = subtareas_del_area_para_encargado,
        subtareas_del_apoyo                 = subtareas_del_apoyo,
        project_progress_map                = project_progress_map,
        tasks_progress_map                  = tasks_progress_map,
        chart_proyectos_labels              = chart_proyectos_labels,
        chart_proyectos_values              = chart_proyectos_values,
        chart_tareas_labels                 = chart_tareas_labels,
        chart_tareas_values                 = chart_tareas_values
    )


@app.route('/crear_proyecto', methods=['GET', 'POST'])
@login_required
def crear_proyecto():
    if current_user.role != 'supervisor':
        flash('No autorizado. Solo los supervisores pueden crear proyectos.', 'danger')
        return redirect(url_for('dashboard'))
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(
            name=form.name.data,
            description=form.description.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            status='En ejecución',
            creator_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()
        flash('Proyecto creado exitosamente.', 'success')
        return redirect(url_for('dashboard'))

    # === NUEVO: Pasa la variable aquí también ===
    has_gestionar_usuarios_route = 'gestionar_usuarios' in app.view_functions
    return render_template('crear_proyecto.html', form=form, has_gestionar_usuarios_route=has_gestionar_usuarios_route)


# Rutas para ver detalles (simples redirecciones por ahora, necesitarás plantillas detalladas)


@app.route('/proyecto/<int:project_id>')
@login_required
def ver_proyecto(project_id):
    """Muestra los detalles de un proyecto específico y sus tareas generales,
       aprovechando las propiedades del modelo para el cálculo automático."""

    # 1) Cargar el proyecto junto con sus TareaGeneral → Subtarea
    project = Project.query.options(
        joinedload(Project.tareas_generales)
            .joinedload(TareaGeneral.subtareas)
    ).get_or_404(project_id)

    # 2) Permisos
    can_view = False
    if current_user.role == 'supervisor':
        can_view = True
    elif current_user.role == 'encargado' and project.area_id == current_user.area_id:
        can_view = True
    elif current_user.role == 'apoyo':
        tiene_subtarea = Subtarea.query.join(TareaGeneral).filter(
            Subtarea.assigned_user_id == current_user.id,
            TareaGeneral.project_id == project_id
        ).first()
        if tiene_subtarea:
            can_view = True

    if not can_view:
        flash('No tienes permiso para ver este proyecto.', 'danger')
        return redirect(url_for('dashboard'))

    # 3) Recuperar todas las TareaGeneral del proyecto (ya traídas por joinedload)
    tareas_generales = project.tareas_generales

    # 4) Si el rol es “apoyo”, filtrar solo las TG que contengan alguna subtarea suya
    if current_user.role == 'apoyo':
        tareas_filtradas = []
        for tg in tareas_generales:
            if Subtarea.query.filter_by(
                   tarea_general_id=tg.id,
                   assigned_user_id=current_user.id
               ).first():
                tareas_filtradas.append(tg)
        tareas_generales = tareas_filtradas

    # 5) Cálculo de avance global del proyecto:
    #    - PROMEDIO SIMPLE de avance_automatico (propiedad de TareaGeneral)
    #    - PROMEDIO PONDERADO por número de subtareas

    # 5.1) Avance simple
    if tareas_generales:
        suma_tg = sum(tg.avance_automatico for tg in tareas_generales)
        # Redondeamos a entero para la barra (si quieres mostrar “73%” en lugar de “73.4%”)
        avance_proy_simple = int(round(suma_tg / len(tareas_generales), 0))
    else:
        avance_proy_simple = 0

    # 5.2) Avance ponderado
    total_subtareas = 0
    suma_avances_subt = 0
    for tg in tareas_generales:
        total_subtareas += len(tg.subtareas)
        suma_avances_subt += sum((s.avance_validado or 0) for s in tg.subtareas)

    if total_subtareas > 0:
        avance_proy_ponderado = int(round(suma_avances_subt / total_subtareas, 0))
    else:
        avance_proy_ponderado = 0

    # 6) Variable extra para el template (igual que antes)
    has_gestionar_usuarios_route = 'gestionar_usuarios' in current_app.view_functions

    # 7) Renderizar plantilla pasando:
    return render_template(
        'project_details.html',
        project=project,
        tareas_generales=tareas_generales,
        user_role=current_user.role,
        has_gestionar_usuarios_route=has_gestionar_usuarios_route,
        avance_proy_simple=avance_proy_simple,
        avance_proy_ponderado=avance_proy_ponderado
    )

@app.route('/editar_proyecto/<int:project_id>', methods=['GET', 'POST'])
@login_required
def editar_proyecto(project_id):
    proyecto = Project.query.get_or_404(project_id)
    if current_user.role != 'supervisor':
        flash('No autorizado. Solo los supervisores pueden editar proyectos.', 'danger')
        return redirect(url_for('dashboard'))

    form = ProjectForm(obj=proyecto)
    if form.validate_on_submit():
        form.populate_obj(proyecto)
        db.session.commit()
        flash('Proyecto actualizado exitosamente.', 'success')
        return redirect(url_for('ver_proyecto', project_id=project_id))

    return render_template('crear_proyecto.html',
                           form=form,
                           project=proyecto,
                           action="Editar")

@app.route('/eliminar_proyecto/<int:project_id>', methods=['POST'])
@login_required
def eliminar_proyecto(project_id):
    """Elimina un proyecto (solo para supervisores)."""
    proyecto = Project.query.get_or_404(project_id)
    if current_user.role != 'supervisor':
        flash('No autorizado. Solo los supervisores pueden eliminar proyectos.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Eliminar subtareas y tareas generales asociadas antes de eliminar el proyecto
    for tg in proyecto.tareas_generales:
        for s in tg.subtareas:
            db.session.delete(s)
        db.session.delete(tg)
    
    db.session.delete(proyecto)
    db.session.commit()
    flash('Proyecto eliminado exitosamente.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/proyecto/<int:project_id>/nueva_tarea_general', methods=['GET', 'POST'])
@login_required
def nueva_tarea_general(project_id):
    """Maneja la creación de una nueva tarea general dentro de un proyecto."""
    project = Project.query.get_or_404(project_id)

    # Permisos: Solo supervisores pueden crear tareas generales
    if current_user.role != 'supervisor':
        flash('Solo los supervisores pueden crear tareas generales.', 'danger')
        return redirect(url_for('dashboard'))

    form = TareaGeneralForm()
    
    # La QuerySelectField para Area debe tener una query_factory que filtre si es necesario
    # Por ejemplo, si un supervisor solo puede asignar a ciertas áreas.
    # Si la QuerySelectField de `area_id` se define en `forms.py` usando `query_factory=lambda: Area.query.all()`,
    # entonces el formulario ya manejará la carga de áreas.
    
    if form.validate_on_submit():
        assigned_area = form.area_id.data # QuerySelectField ya devuelve el objeto Area seleccionado
        
        # Validar si el área existe y es válida (aunque QuerySelectField ya lo hace hasta cierto punto)
        if assigned_area:
            nueva_tg = TareaGeneral(
                title=form.title.data,
                description=form.description.data,
                fecha_limite=form.fecha_limite.data,
                prioridad=form.prioridad.data,
                status='Pendiente',
                project=project,
                area=assigned_area, # Asigna el objeto Area
                creator=current_user
            )
            db.session.add(nueva_tg)
            db.session.commit()
            flash('Tarea general creada exitosamente.', 'success')
            return redirect(url_for('ver_proyecto', project_id=project.id))
        else:
            flash('Error: El área asignada es inválida o no fue seleccionada.', 'danger')

    return render_template('crear_tarea_general.html', form=form, proyecto=project, action="Crear")




@app.route('/proyecto/<int:project_id>/descargar_reporte')
@login_required
def descargar_reporte_proyecto(project_id):
    project = Project.query.get_or_404(project_id)
    # Sólo el supervisor puede descargar el reporte (ajusta esto si deseas
    # permitir también al encargado o a otros roles)
    if current_user.role != 'supervisor':
        flash('No tienes permiso para descargar este reporte.', 'danger')
        return redirect(url_for('ver_proyecto', project_id=project.id))

    # 1) Recopilar la información principal del proyecto
    report_content = f"Reporte del Proyecto: {project.name}\n"
    report_content += f"======================================\n"
    report_content += f"Descripción: {project.description or 'N/A'}\n"
    report_content += f"Estado: {project.status}\n"
    report_content += f"Fecha de Inicio: {project.start_date.strftime('%Y-%m-%d') if project.start_date else 'N/A'}\n"
    report_content += f"Fecha de Fin Estimada: {project.end_date.strftime('%Y-%m-%d') if project.end_date else 'N/A'}\n"
    report_content += f"\n--- Tareas Generales ---\n"
    for tg in project.tareas_generales:
        report_content += f"\n  Tarea: {tg.title}\n"
        report_content += f"  Estado: {tg.status} | Prioridad: {tg.prioridad}\n"
        # “avance_automatico” es la propiedad que ya calcula el %
        report_content += f"  Avance: {tg.avance_automatico}%\n"
        if tg.subtareas:
            report_content += f"  Subtareas:\n"
            for sub in tg.subtareas:
                report_content += (
                    f"    - {sub.title} "
                    f"(Estado: {sub.status}, Avance Aporte: {sub.avance}%, "
                    f"Avance Validado: {sub.avance_validado}%)\n"
                )

    # 2) Convertir el string a un buffer en memoria para enviarlo con send_file
    text_io = io.BytesIO(report_content.encode('utf-8'))
    text_io.seek(0)

    # 3) Enviar el archivo como descarga de texto plano
    return send_file(
        text_io,
        mimetype='text/plain',
        as_attachment=True,
        download_name=f'reporte_{project.name.replace(" ", "_")}.txt'
    )
# -------------------------
# tarea general
# -------------------------


@app.route('/tarea_general/<int:tarea_general_id>')
@login_required
def ver_tarea_general(tarea_general_id):
    # 1) Traer la TG con sus subtareas y los usuarios asignados en una sola consulta
    tarea_general = TareaGeneral.query.options(
        joinedload(TareaGeneral.subtareas).joinedload(Subtarea.assigned_user)
    ).get_or_404(tarea_general_id)

    # 2) Lógica de permisos (igual que antes)…
    can_view = False
    if current_user.role == 'supervisor':
        can_view = True
    elif current_user.role == 'encargado' and current_user.area_id == tarea_general.area_id:
        can_view = True
    elif current_user.role == 'apoyo':
        for s in tarea_general.subtareas:
            if s.assigned_user_id == current_user.id:
                can_view = True
                break

    if not can_view:
        flash("No tienes permiso para ver esta tarea general.", "danger")
        return redirect(url_for('dashboard'))

    # 3) Filtrar subtareas solo si es apoyo
    subtareas = tarea_general.subtareas
    if current_user.role == 'apoyo':
        subtareas = [s for s in subtareas if s.assigned_user_id == current_user.id]

    return render_template(
        'tarea_general_details.html',
        tarea_general=tarea_general,
        subtareas=subtareas,
        es_retrasada_subtarea=es_retrasada_subtarea
    )


# -------------------------
# Editar tarea general
# -------------------------

@app.route('/tarea_general/<int:tarea_general_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_tarea_general(tarea_general_id):
    """Maneja la edición de una tarea general."""
    tarea_general = TareaGeneral.query.get_or_404(tarea_general_id)

    # Permisos para editar tarea general
    if current_user.role != 'supervisor' and \
       (current_user.role != 'encargado' or current_user.area_id != tarea_general.area_id):
        flash("No tienes permiso para editar esta tarea general.", "danger")
        return redirect(url_for('dashboard'))

    form = TareaGeneralForm(obj=tarea_general)  # Pre‐llena el formulario con los datos existentes
    
    if form.validate_on_submit():
        tarea_general.title        = form.title.data
        tarea_general.description  = form.description.data
        tarea_general.fecha_limite = form.fecha_limite.data
        tarea_general.prioridad    = form.prioridad.data

        # Si tu Form trae un campo area_id, asigna el nuevo Area:
        nueva_area = Area.query.get(form.area_id.data)
        if nueva_area:
            tarea_general.area = nueva_area

        db.session.commit()
        flash("Tarea general actualizada exitosamente.", "success")
        return redirect(url_for('ver_tarea_general', tarea_general_id=tarea_general.id))

    return render_template(
        'crear_tarea_general.html',
        form=form,
        proyecto=tarea_general.project,
        tarea_general=tarea_general,
        action="Editar"
    )


# -------------------------
# Eiminar tarea general
# -------------------------

@app.route('/tarea_general/<int:tarea_general_id>/eliminar', methods=['POST'])
@login_required
def eliminar_tarea_general(tarea_general_id):
    """Elimina una tarea general y sus subtareas asociadas."""
    tarea_general = TareaGeneral.query.get_or_404(tarea_general_id)

    # Permisos para eliminar tarea general
    if current_user.role != 'supervisor' and \
       (current_user.role != 'encargado' or current_user.area_id != tarea_general.area_id):
        flash("No tienes permiso para eliminar esta tarea general.", "danger")
        return redirect(url_for('dashboard'))

    proyecto_id_asociado = tarea_general.project_id
    
    # Eliminar subtareas antes de eliminar la tarea general
    for subtarea in tarea_general.subtareas:
        db.session.delete(subtarea)

    db.session.delete(tarea_general)
    db.session.commit()
    flash("Tarea general eliminada exitosamente.", "success")

    # Redirige al detalle del proyecto recién modificado
    if proyecto_id_asociado:
        return redirect(url_for('ver_proyecto', project_id=proyecto_id_asociado))
    else:
        return redirect(url_for('dashboard'))


# ---------------------------------------
# Crear nueva subtarea para tarea general
# --------------------------------------- 

@app.route('/tarea_general/<int:tarea_general_id>/nueva_subtarea', methods=['GET', 'POST'])
@login_required
def crear_subtarea(tarea_general_id):
    tarea_general = TareaGeneral.query.get_or_404(tarea_general_id)

    # Solo Supervisor o Encargado de esa área pueden crear subtareas
    if current_user.role == 'apoyo' or \
       (current_user.role == 'encargado' and current_user.area_id != tarea_general.area_id):
        flash('No tienes permiso para crear subtareas en esta tarea general.', 'danger')
        return redirect(url_for('ver_tarea_general', tarea_general_id=tarea_general.id))

    form = SubtareaForm()
    # El campo assigned_user solo debe listar apoyos de la misma área:
    form.assigned_user.query_factory = lambda: User.query.filter_by(
        role='apoyo',
        area_id=tarea_general.area_id
    ).order_by(User.username).all()

    if form.validate_on_submit():
        assigned = form.assigned_user.data  # Objeto User o None
        if assigned and assigned.role != 'apoyo':
            flash('El usuario asignado debe ser un Apoyo.', 'danger')
            return render_template(
                'crear_subtarea.html',
                form=form,
                tarea_general=tarea_general,
                project=tarea_general.project,
                action="Crear"
            )

        nueva = Subtarea(
            title=form.title.data,
            description=form.description.data,
            fecha_limite=form.fecha_limite.data,
            prioridad=form.prioridad.data,
            status=form.status.data,      # Puede venir ‘Pendiente’ o ‘En ejecución’
            avance=0,                     # El Apoyo puede subir luego su "aporte"
            avance_validado=0,            # Arranca en 0% validado
            validado=False,
            validador_id=None,
            tarea_general=tarea_general,
            assigned_user=assigned,       # Objeto User o None
            creator=current_user
        )
        db.session.add(nueva)
        db.session.commit()

        # 1) Actualizar estado de la nueva sutarea según avance_validado (=0 → ‘En ejecución’ o ‘Pendiente’)
        nueva.actualizar_estado_auto()
        db.session.commit()

        # 2) Actualizar estado de la Tarea General padre
        tg = nueva.tarea_general
        tg.actualizar_estado_auto()
        db.session.commit()

        # 3) Actualizar estado del Proyecto padre, si corresponde
        proyecto = tg.project
        if proyecto.porcentaje_avance >= 100:
            proyecto.status = 'Finalizado'
        else:
            proyecto.status = 'En ejecución'
        db.session.commit()

        flash('Subtarea creada exitosamente.', 'success')
        return redirect(url_for('ver_tarea_general', tarea_general_id=tarea_general.id))

    return render_template(
        'crear_subtarea.html',
        form=form,
        tarea_general=tarea_general,
        project=tarea_general.project,
        action="Crear"
    )




# -------------------------
# Ver detalle de Subtarea
# -------------------------
@app.route('/subtarea/<int:subtarea_id>')
@login_required
def ver_subtarea(subtarea_id):
    subtarea = Subtarea.query.get_or_404(subtarea_id)
    tg = subtarea.tarea_general
    proyecto = tg.project if tg else None

    # Permisos de visualización:
    can_view = False
    if current_user.role == 'supervisor':
        can_view = True
    elif current_user.role == 'encargado' and tg and current_user.area_id == tg.area_id:
        can_view = True
    elif current_user.role == 'apoyo' and subtarea.assigned_user_id == current_user.id:
        can_view = True

    if not can_view:
        flash("No tienes permiso para ver esta Subtarea.", "danger")
        return redirect(url_for('dashboard'))

    return render_template(
        'subtarea_details.html',
        subtarea=subtarea,
        tarea_general=tg,
        project=proyecto
    )


# -------------------------
# Editar Subtarea (Apoyo o Encargado)
# -------------------------
@app.route('/subtarea/<int:subtarea_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_subtarea(subtarea_id):
    """
    Permite editar una Subtarea según el rol del usuario:
      - Apoyo: solo puede actualizar su % de avance (y opcionalmente subir un documento de aporte).
      - Encargado/Supervisor: pueden actualizar cualquier campo y validar el avance_validado.
    Además, se actualiza automáticamente el estado de la subtarea, la tarea general y el proyecto padre.
    """

    # 1) Recuperar la subtarea (o 404 si no existe)
    subtarea = Subtarea.query.get_or_404(subtarea_id)
    tg = subtarea.tarea_general
    proyecto = tg.project if tg else None

    # 2) Verificar permisos
    can_edit = False
    if current_user.role == 'supervisor':
        can_edit = True
    elif current_user.role == 'encargado' and current_user.area_id == tg.area_id:
        can_edit = True
    elif current_user.role == 'apoyo' and subtarea.assigned_user_id == current_user.id:
        can_edit = True

    if not can_edit:
        flash("No tienes permiso para editar esta subtarea.", "danger")
        return redirect(url_for('ver_tarea_general', tarea_general_id=tg.id))

    # ======================================================
    # 3) Bloque para el rol "APOYO": Subir avance/aporte
    # ======================================================
    if current_user.role == 'apoyo':
        form = SubtareaAvanceAporteForm(avance=subtarea.avance)
        if form.validate_on_submit():
            # 1) Actualizar el porcentaje de avance
            subtarea.avance = form.avance.data

            # 2) Si viene un archivo, lo guardamos:
            archivo = form.documento.data
            if archivo:
                # (Supongamos que ya tienes ENABLED UPLOAD_FOLDER en config)
                filename = secure_filename(archivo.filename)
                path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                # Si quieres renombrar para evitar colisiones:
                base, ext = os.path.splitext(filename)
                contador = 1
                while os.path.exists(path):
                    filename = f"{base}_{contador}{ext}"
                    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    contador += 1
                archivo.save(path)
                # Guardamos solo el nombre (o la ruta que prefieras) en la BD:
                subtarea.documento_aporte = filename

            # Cada vez que el apoyo actualiza avance, desmarcamos validado
            subtarea.validado = False
            subtarea.validador_id = None

            db.session.commit()
            flash('Tu avance/aporte fue actualizado. Espera validación.', 'success')
            return redirect(url_for('dashboard'))

        return render_template(
            'editar_subtarea_avance.html',
            form=form,
            subtarea=subtarea
        )

    # ======================================================
    # 4) Bloque para el rol "ENCARGADO" o "SUPERVISOR"
    # ======================================================
    form = SubtareaForm(obj=subtarea)
    form.assigned_user.query_factory = lambda: User.query.filter_by(
        role='apoyo',
        area_id=tg.area_id
    ).order_by(User.username).all()

    if form.validate_on_submit():
        subtarea.title = form.title.data
        subtarea.description = form.description.data
        subtarea.prioridad = form.prioridad.data
        subtarea.fecha_limite = form.fecha_limite.data
        subtarea.status = form.status.data
        subtarea.assigned_user = form.assigned_user.data

        if subtarea.documento_aporte:
            try:
                avance_validado = int(request.form.get('avance_validado', 0))
            except (ValueError, TypeError):
                avance_validado = 0
            subtarea.avance_validado = avance_validado

            validado_flag = (request.form.get('validado') == 'on')
            subtarea.validado = validado_flag
            subtarea.validador_id = current_user.id if validado_flag else None

        db.session.commit()

        subtarea.actualizar_estado_auto(override_estado=None)
        db.session.commit()

        tg.actualizar_estado_auto(override_estado=None)
        db.session.commit()

        if proyecto.porcentaje_avance >= 100:
            proyecto.status = 'Finalizado'
        else:
            proyecto.status = 'En ejecución'
        db.session.commit()

        flash("Subtarea y validación guardadas correctamente.", "success")
        return redirect(url_for('ver_tarea_general', tarea_general_id=tg.id))

    return render_template(
        'editar_subtarea_encargado.html',
        form=form,
        subtarea=subtarea,
        tarea_general=tg,
        project=proyecto
    )

# -------------------------
# Eliminar Subtarea
# -------------------------
@app.route('/subtarea/<int:subtarea_id>/eliminar', methods=['POST'])
@login_required
def eliminar_subtarea(subtarea_id):
    subtarea = Subtarea.query.get_or_404(subtarea_id)
    tg = subtarea.tarea_general

    # Permisos: Supervisor o Encargado de área puede eliminar
    can_delete = False
    if current_user.role == 'supervisor':
        can_delete = True
    elif current_user.role == 'encargado' and current_user.area_id == tg.area_id:
        can_delete = True

    if not can_delete:
        flash("No tienes permiso para eliminar esta Subtarea.", "danger")
        return redirect(url_for('ver_tarea_general', tarea_general_id=tg.id))

    # Guardar referencia a proyecto para redirigir luego
    proyecto_id = tg.project.id

    db.session.delete(subtarea)
    db.session.commit()

    # 1) Después de eliminar la subtarea, actualizamos estado de la TG
    tg.actualizar_estado_auto()
    db.session.commit()

    # 2) Actualizamos estado del Proyecto
    proyecto = tg.project
    if proyecto.porcentaje_avance >= 100:
        proyecto.status = 'Finalizado'
    else:
        # Si no hay TG o no se completaron, en ejecución
        proyecto.status = 'En ejecución'
    db.session.commit()

    flash('Subtarea eliminada exitosamente.', 'success')
    return redirect(url_for('ver_tarea_general', tarea_general_id=tg.id))



@app.route('/subtarea/<int:subtarea_id>/aporte', methods=['GET', 'POST'])
@login_required
def agregar_aporte_subtarea(subtarea_id):
    subtarea = Subtarea.query.get_or_404(subtarea_id)
    tarea_general = subtarea.tarea_general

    # Solo el apoyo asignado puede subir aporte
    if current_user.role != 'apoyo' or subtarea.assigned_user_id != current_user.id:
        flash("No tienes permiso para subir un aporte a esta subtarea.", "danger")
        return redirect(url_for('dashboard'))

    # Si ya subió un documento antes, no dejamos volver a subir
    if subtarea.documento_aporte:
        flash("Ya has subido un documento para esta subtarea.", "info")
        return redirect(url_for('dashboard'))

    form = SubtareaAporteForm()
    if form.validate_on_submit():
        file = form.documento.data
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            # Si existe un archivo con el mismo nombre, puedes optar por renombrar:
            base, ext = os.path.splitext(filename)
            contador = 1
            while os.path.exists(upload_path):
                filename = f"{base}_{contador}{ext}"
                upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                contador += 1

            file.save(upload_path)
            # Guardamos en la BD la ruta relativa (solo nombre de archivo):
            subtarea.documento_aporte = filename
            db.session.commit()

            flash("Documento subido correctamente. El líder de área validará tu aporte pronto.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Archivo no permitido.", "danger")

    return render_template('agregar_avance_subtarea.html', form=form, subtarea=subtarea)




@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)






@app.route('/tarea_general/<int:tarea_general_id>/avance', methods=['POST'])
@login_required
def cargar_avance_tarea_general(tarea_general_id):
    tarea_general = TareaGeneral.query.get_or_404(tarea_general_id)

    # Permitir solo al encargado de área correspondiente
    if current_user.role != 'encargado' or current_user.area_id != tarea_general.area_id:
        flash("No tienes permisos para modificar el avance de esta tarea general.", "danger")
        return redirect(url_for('ver_tarea_general', tarea_general_id=tarea_general_id))

    # Obtén los datos del formulario
    porcentaje = request.form.get('porcentaje_avance')
    comentario = request.form.get('comentario_avance')

    try:
        porcentaje = int(porcentaje)
        if porcentaje < 0 or porcentaje > 100:
            raise ValueError("El porcentaje debe estar entre 0 y 100.")
        tarea_general.porcentaje_avance = porcentaje
        tarea_general.comentario_avance = comentario
        db.session.commit()
        flash("¡Avance actualizado correctamente!", "success")
    except Exception as e:
        flash(f"Error al actualizar el avance: {e}", "danger")

    return redirect(url_for('ver_tarea_general', tarea_general_id=tarea_general_id))







@app.route('/area/<int:area_id>')
@login_required
def ver_area(area_id):
    area = Area.query.get_or_404(area_id)
    # Lógica de permisos: un supervisor o el encargado del área puede verla.
    # Un apoyo puede verla si pertenece a esa área.
    can_view = False
    if current_user.role == 'supervisor':
        can_view = True
    elif current_user.role == 'encargado' and current_user.area_id == area_id:
        can_view = True
    elif current_user.role == 'apoyo' and current_user.area_id == area_id:
        can_view = True
    
    if not can_view:
        flash("No tienes permiso para ver los detalles de esta área.", "danger")
        return redirect(url_for('dashboard'))

    # Puedes obtener proyectos, tareas generales, y usuarios (líderes/apoyos) asociados a esta área
    # y pasarlos a una plantilla `area_details.html`
    
    # Usuarios en esta área (asumiendo que User tiene una relación con Area)
    users_in_area = User.query.filter_by(area_id=area_id).all()
    
    # Tareas generales directamente asignadas a esta área
    tareas_generales_area = TareaGeneral.query.filter_by(area_id=area_id).all()

    return render_template('area_details.html', area=area, users_in_area=users_in_area, tareas_generales_area=tareas_generales_area)

# --- Ruta para ver perfil de usuario (líder o apoyo) ---
@app.route('/user_profile/<int:user_id>')
@login_required
def ver_perfil_usuario(user_id):
    user_profile = User.query.get_or_404(user_id)
    
    # Lógica de permisos para ver perfiles:
    # Supervisor: puede ver cualquier perfil
    # Encargado: puede ver perfiles de usuarios en su área
    # Apoyo: solo puede ver su propio perfil
    can_view = False
    if current_user.role == 'supervisor':
        can_view = True
    elif current_user.role == 'encargado' and user_profile.area_id == current_user.area_id:
        can_view = True
    elif current_user.role == 'apoyo' and user_profile.id == current_user.id:
        can_view = True

    if not can_view:
        flash("No tienes permiso para ver este perfil de usuario.", "danger")
        return redirect(url_for('dashboard'))
    
    # También puedes pasar las subtareas asignadas a este usuario si es un "apoyo" o "encargado"
    subtasks_assigned = []
    if user_profile.role == 'apoyo' or user_profile.role == 'encargado':
        subtasks_assigned = Subtarea.query.filter_by(assigned_user_id=user_profile.id).order_by(Subtarea.fecha_limite).all()

    return render_template('user_profile.html', user_profile=user_profile, subtasks_assigned=subtasks_assigned)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)