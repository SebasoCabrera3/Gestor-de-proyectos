# Gestor de Proyectos

Una aplicación web para el seguimiento de proyectos por roles (supervisor, encargado, apoyo).  
Desarrollada en Flask con MySQL/SQLite, con funcionalidades de asignación de tareas, control de avance y gestión de usuarios.

---

## Índice

1. [Instalación](#instalación)  
2. [Uso](#uso)  
3. [Estructura de carpetas](#estructura-de-carpetas)  
4. [Autor](#autor)  
5. [Licencia](#licencia)  

---

## Instalación

1. Clona este repositorio:  
   ```bash
   git clone https://github.com/tu-usuario/gestor-proyectos.git
   ```
2. Entra a la carpeta del proyecto:  
   ```bash
   cd gestor-proyectos
   ```
3. Crea un entorno virtual (recomendado) e instala dependencias:  
   ```bash
   python -m venv venv
   source venv/bin/activate      # En Linux/Mac
   venv\Scripts\activate         # En Windows PowerShell
   pip install -r requirements.txt
   ```
4. Configura tu base de datos (SQLite por defecto). Si quieres MySQL, edita `config.py` o la línea `SQLALCHEMY_DATABASE_URI` en `app.py`.
5. Inicializa la DB (si usas Flask-Migrate/SQLAlchemy):  
   ```bash
   flask db init
   flask db migrate -m "Creación inicial"
   flask db upgrade
   ```
6. Ejecuta la aplicación:  
   ```bash
   flask run
   ```
   Luego abre en tu navegador: `http://127.0.0.1:5000/`

---

## Uso

- **Roles disponibles:**  
  - **Supervisor:** Solo el supervisor puede crear proyectos.  
  - **Encargado:** Ve los proyectos asignados a su área, asigna tareas generales.  
  - **Apoyo:** Visualiza la lista de subtareas, registra avances semanales.  

- **Pantallas principales:**  
  1. **Login / Registro:** Página de autenticación de usuarios.  
  2. **Dashboard Supervisor:** Lista todos los proyectos, su avance global y estado.  
  3. **Dashboard Encargado:** Ver tareas generales asignadas a su área (con botón “Ver detalles” para agregar subtareas).  
  4. **Dashboard Apoyo:** Visualiza sus subtareas actuales y registra el avance.  
  5. **Vista “Ver Detalles” (por Proyecto):** Muestra datos del proyecto, lista de tareas generales, porcentaje automático.  
  6. **Vista “Ver Detalles de Tarea”:** Permite asignar subtareas dentro de esa tarea general, definir fechas y prioridades.  

- **Comentarios de diseño:**  
  - La columna “Número de Participantes” aparece en la tabla principal de proyectos.  
  - El porcentaje de avance se distribuye automáticamente entre proyecto, tareas generales y subtareas.  
  - Validaciones: el nombre de usuario no puede repetirse, contraseña con mínimo de dígitos.  

---

## Estructura de carpetas

```
gestor-proyectos/
│
├─ app.py
├─ config.py            # (opcional si manejas settings separados)
├─ requirements.txt
├─ LICENSE
├─ README.md
├─ templates/
│   ├─ base.html
│   ├─ index.html
│   ├─ login.html
│   ├─ dashboard_supervisor.html
│   ├─ dashboard_encargado.html
│   ├─ dashboard_apoyo.html
│   └─ ver_detalle.html
│   └─ ver_detalle_tarea.html
│
├─ static/
│   ├─ css/
│   │   └─ style.css
│   ├─ uploads/
│   │   └─ Archivos.pdf
│   └─ images/
│       └─ logo.png
│
├─ models.py
├─ forms.py
├─ migrations/
└─ venv/
```

---

## Autor

**Sebastián Cabrera**  
Estudiante de Arquitectura (noveno semestre)  
Pasantía en Movilidad Futura  
Email: jaircabrera@unimayor.edu.co 

© 2025 Jair Sebastián Cabrera Molano. Todos los derechos reservados.

---

## Licencia

Este proyecto está protegido por derechos de autor.  
Consulta el archivo `LICENSE` para más detalles.
