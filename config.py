# config.py

import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'tu_clave_secreta_super_segura_2025'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    'sqlite:///' + os.path.join(basedir, 'instance', 'site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuración para correos (ajusta según tu email de pruebas)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'jscproyectosvirtual@gmail.com'      # Cámbialo por el tuyo si quieres
    MAIL_PASSWORD = 'pbgxmztermvsbvae'                   # Contraseña de app, cámbiala en producción
    MAIL_DEFAULT_SENDER = 'jscproyectosvirtual@gmail.com'

    # --- Configuración de subida de archivos ---
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # máx. 16 MB
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xlsx'}
