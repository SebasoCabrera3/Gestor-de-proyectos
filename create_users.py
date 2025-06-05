# create_users.py
from app import app, db, bcrypt, User, Area

with app.app_context():
    print("Inicializando datos...")

    # 🟢 Crear áreas primero
    areas_data = [
        ('Jurídica', 'JUR01'),
        ('Planeación', 'PLA02'),
        ('Operaciones', 'OPE03'),
        ('Infraestructura', 'INF04'),
        ('Sociopredial', 'SOC05'),
        ('Financiera', 'FIN06'),
        ('Ambiental', 'AMB07'),
        ('Comunicaciones', 'COM08'),
        ('Administrativa', 'ADM09'),
    ]
    for nombre, codigo in areas_data:
        if not Area.query.filter_by(name=nombre).first():
            db.session.add(Area(name=nombre, codigo=codigo))
            print(f"Añadida área: {nombre}")

    db.session.commit()  # IMPORTANTE: Commit antes de usar las áreas

    # 🟢 Crear o reemplazar usuario admin (supervisor)
    admin_email = 'oficinaproyectos@movilidadfutura.gov.co'
    admin_username = 'Oficina de proyectos'
    admin_password = 'clave_admin_123'
    hashed_password_admin = bcrypt.generate_password_hash(admin_password).decode('utf-8')

    existing_admin = User.query.filter_by(email=admin_email).first()
    if existing_admin:
        db.session.delete(existing_admin)
        print(f"Eliminado usuario admin existente: {admin_email}")

    db.session.add(User(
        username=admin_username, 
        email=admin_email, 
        password=hashed_password_admin, 
        role='supervisor'
    ))
    print(f"Añadido usuario supervisor: {admin_email}")

    # 🟢 Crear encargados de área (con area_id correctamente asignado)
    encargados_data = [
        ('Operaciones', 'operaciones@movilidadfutura.gov.co', 'clave_op_123'),
        ('Infraestructura', 'infraestructura@movilidadfutura.gov.co', 'clave_inf_123'),
        ('Comunicaciones', 'comunicaciones@movilidadfutura.gov.co', 'clave_com_123'),
        ('Financiera', 'financiera@movilidadfutura.gov.co', 'clave_fin_123'),
        ('Administrativa', 'administrativa@movilidadfutura.gov.co', 'clave_adm_123'),
        ('Sociopredial', 'sociopredial@movilidadfutura.gov.co', 'clave_soc_123'),
        ('Ambiental', 'ambiental@movilidadfutura.gov.co', 'clave_amb_123'),
        ('Planeación', 'planeacion@movilidadfutura.gov.co', 'clave_pla_123'),
        ('Jurídica', 'juridica@movilidadfutura.gov.co', 'clave_jur_123')
    ]
    for nombre_area, email, password in encargados_data:
        username = email.split('@')[0]
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Vincular el encargado a su área
        area = Area.query.filter_by(name=nombre_area).first()
        if not area:
            print(f"Área no encontrada para el encargado: {nombre_area}")
            continue

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            db.session.delete(existing_user)
            print(f"Eliminado encargado existente: {email}")

        db.session.add(User(
            username=username, 
            email=email, 
            password=hashed_password, 
            role='encargado', 
            area_id=area.id
        ))
        print(f"Añadido encargado: {email} con área: {nombre_area}")

    db.session.commit()
    print("✅ Usuarios y áreas creados correctamente.")
