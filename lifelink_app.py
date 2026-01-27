import eventlet
# Parcheo de seguridad para Render
eventlet.monkey_patch()

import os
import jinja2
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room
import cloudinary
import cloudinary.uploader

# --- CONFIGURACIÓN CLOUDINARY ---
cloudinary.config(
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
  api_key = os.environ.get('CLOUDINARY_API_KEY'),
  api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
  secure = True
)

# ==========================================
# 1. DEFINICIÓN DE PLANTILLAS (PRIMERO PARA EVITAR ERRORES)
# ==========================================

base_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LifeLink - Red Médica</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --brand-blue: #0ea5e9; }
        .bg-brand { background-color: var(--brand-blue); }
        .text-brand { color: var(--brand-blue); }
        .btn-medical { background-color: var(--brand-blue); color: white; transition: all 0.3s; border-radius: 0.5rem; }
        .btn-medical:hover { background-color: #0284c7; transform: translateY(-1px); }
        #map { height: 350px; width: 100%; border-radius: 1rem; z-index: 10; border: 1px solid #e2e8f0; }
    </style>
</head>
<body class="bg-slate-50 flex flex-col min-h-screen font-sans text-slate-900">
    <nav class="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 h-16 flex justify-between items-center">
            <a href="/" class="flex items-center gap-2">
                <div class="bg-brand p-1.5 rounded-lg">
                     <svg width="20" height="20" viewBox="0 0 100 100" fill="none" stroke="white" stroke-width="10">
                        <path d="M10 50 L30 50 L40 20 L60 80 L70 50 L90 50" stroke-linecap="round" stroke-linejoin="round"/>
                     </svg>
                </div>
                <span class="font-bold text-xl tracking-tight text-slate-800">LifeLink</span>
            </a>
            <div class="flex items-center gap-6">
                <a href="{{ url_for('buscar') }}" class="text-sm font-medium text-slate-500 hover:text-brand transition">Explorar</a>
                {% if current_user.is_authenticated %}
                <a href="{{ url_for('dashboard') }}" class="text-sm font-medium text-slate-500 hover:text-brand transition">Panel</a>
                <a href="{{ url_for('perfil') }}" class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center text-brand font-bold border border-blue-100 italic">{{ current_user.nombre[0] | upper }}</a>
                {% else %}
                <a href="{{ url_for('login') }}" class="text-sm font-medium text-slate-500">Entrar</a>
                <a href="{{ url_for('registro') }}" class="btn-medical px-4 py-2 text-sm font-bold shadow-sm">Unirse</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <main class="flex-grow">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="max-w-4xl mx-auto mt-4 px-4">
                <div class="p-3 rounded-lg {% if category == 'error' %}bg-red-50 text-red-700 border-red-100{% else %}bg-emerald-50 text-emerald-700 border-emerald-100{% endif %} border text-sm font-medium flex items-center gap-2">
                  <i class="fas fa-info-circle"></i> {{ message }}
                </div>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="py-8 bg-white border-t border-slate-100 text-center">
        <p class="text-[10px] text-slate-400 font-bold uppercase tracking-widest">LifeLink • Proyecto Aula • 5IV7</p>
    </footer>
</body>
</html>
"""

home_template = """
{% extends "base.html" %}
{% block content %}
<div class="relative min-h-[80vh] flex items-center bg-white overflow-hidden">
    <div class="max-w-7xl mx-auto px-4 w-full">
        <div class="lg:grid lg:grid-cols-12 lg:gap-12 items-center">
            <div class="sm:text-center lg:col-span-6 lg:text-left">
                <h1 class="text-5xl font-extrabold text-slate-900 tracking-tight sm:text-6xl leading-tight mb-6">
                    Conectando <span class="text-brand">Vidas.</span>
                </h1>
                <p class="text-lg text-slate-500 max-w-lg leading-relaxed mb-10">
                    Plataforma de coordinación para la gestión de insumos médicos, medicamentos y donaciones de sangre de forma segura y directa.
                </p>
                <div class="flex flex-wrap gap-4 sm:justify-center lg:justify-start">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-8 py-4 font-bold text-lg shadow-lg flex items-center gap-2">
                        <i class="fas fa-search"></i> Explorar Recursos
                    </a>
                </div>
            </div>
            <div class="mt-12 lg:mt-0 lg:col-span-6 flex justify-center">
                <div class="relative w-full max-w-md">
                    <div class="absolute -inset-1 bg-brand rounded-3xl blur opacity-10"></div>
                    <div class="relative bg-white p-2 rounded-3xl shadow-xl overflow-hidden">
                        <!-- IMAGEN PROFESIONAL CORREGIDA -->
                        <img class="w-full h-[450px] rounded-2xl object-cover" src="https://images.unsplash.com/photo-1551076805-e1869033e561?auto=format&fit=crop&q=80&w=1000" alt="LifeLink Medical Care">
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

search_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-7xl mx-auto py-12 px-4">
    <div class="flex items-center justify-between mb-10">
        <h2 class="text-3xl font-bold text-slate-900">Recursos <span class="text-brand">Disponibles</span></h2>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
        {% for item in resultados %}
        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow group">
            <img src="{{ item.imagen_url }}" class="w-full h-56 object-cover group-hover:scale-105 transition-transform duration-500">
            <div class="p-6">
                <h3 class="font-bold text-slate-800 text-xl mb-1">{{ item.nombre }}</h3>
                <p class="text-xs text-brand font-bold uppercase tracking-wider mb-4">{{ item.categoria }}</p>
                <div class="flex justify-between items-center border-t border-slate-50 pt-4">
                    <span class="text-xl font-bold text-slate-900">{% if item.precio > 0 %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span>
                    <a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="bg-blue-50 text-brand px-4 py-2 rounded-lg font-bold hover:bg-brand hover:text-white transition-colors">Solicitar</a>
                </div>
            </div>
        </div>
        {% else %}
        <div class="col-span-full py-20 text-center">
            <i class="fas fa-box-open text-slate-200 text-6xl mb-4"></i>
            <p class="text-slate-400 font-medium">Aún no hay recursos publicados en tu zona.</p>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
"""

# ==========================================
# 2. LÓGICA DE SERVIDOR Y MODELOS (TABLAS RESETEADAS)
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lifelink_2026_fixed_stable_key')
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///lifelink.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# CAMBIAMOS LOS NOMBRES DE LAS TABLAS (__tablename__) PARA FORZAR UN RESET EN RENDER Y QUITAR EL ERROR 500
class Usuario(UserMixin, db.Model):
    __tablename__ = 'users_v2' 
    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    telefono = db.Column(db.String(20))
    tipo_sangre = db.Column(db.String(10))
    ubicacion = db.Column(db.String(255))
    def get_id(self): return str(self.id_usuario)

    @property
    def rating_promedio(self): return 5.0

class Publicacion(db.Model):
    __tablename__ = 'items_v2'
    id_oferta_insumo = db.Column(db.Integer, primary_key=True)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('users_v2.id_usuario'))
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    tipo_publicacion = db.Column(db.String(50))
    precio = db.Column(db.Float, default=0.0)
    imagen_url = db.Column(db.String(500))
    estado = db.Column(db.String(20), default='Verificado') 
    proveedor = db.relationship('Usuario', backref='publicaciones')

class Solicitud(db.Model):
    __tablename__ = 'orders_v2'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('users_v2.id_usuario'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('items_v2.id_oferta_insumo'))
    estatus = db.Column(db.String(50), default='En Proceso') 
    solicitante = db.relationship('Usuario', backref='solicitudes_enviadas')
    publicacion = db.relationship('Publicacion', backref='solicitudes_recibidas')

app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'search.html': search_template,
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-20 px-4"><div class="bg-white p-10 rounded-2xl shadow-xl border border-slate-100 text-center"><h2 class="text-3xl font-bold mb-8">Entrar a <span class="text-brand">LifeLink</span></h2><form method="POST" class="space-y-4"><input name="email" type="email" placeholder="Correo Electrónico" required class="w-full p-4 bg-slate-50 rounded-xl border-none outline-none focus:ring-2 focus:ring-brand shadow-inner"><input name="password" type="password" placeholder="Contraseña" required class="w-full p-4 bg-slate-50 rounded-xl border-none outline-none focus:ring-2 focus:ring-brand shadow-inner"><button class="w-full btn-medical py-4 rounded-xl font-bold text-xl mt-4 shadow-md">Ingresar</button></form><p class="mt-6 text-sm text-slate-400">¿No tienes cuenta? <a href="{{ url_for('registro') }}" class="text-brand font-bold">Regístrate</a></p></div></div>{% endblock %}""",
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-xl mx-auto py-16 px-4"><div class="bg-white p-10 rounded-2xl shadow-xl border border-slate-100"><h2 class="text-3xl font-bold mb-8 text-center">Crear Perfil</h2><form method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-4"><input name="nombre" placeholder="Nombre completo" required class="md:col-span-2 p-4 bg-slate-50 rounded-xl border-none shadow-inner"><select name="tipo_sangre" required class="p-4 bg-slate-50 rounded-xl border-none shadow-inner"><option value="">TIPO SANGRE</option><option>O+</option><option>O-</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option></select><input name="telefono" placeholder="WhatsApp" required class="p-4 bg-slate-50 rounded-xl border-none shadow-inner"><input name="email" type="email" placeholder="Correo" required class="p-4 bg-slate-50 rounded-xl border-none shadow-inner"><input name="ubicacion" placeholder="Ciudad" required class="p-4 bg-slate-50 rounded-xl border-none shadow-inner"><input name="password" type="password" placeholder="Contraseña" required class="md:col-span-2 p-4 bg-slate-50 rounded-xl border-none shadow-inner"><button class="md:col-span-2 w-full btn-medical py-4 rounded-xl font-bold text-xl mt-4">Registrarme</button></form></div></div>{% endblock %}""",
    'dashboard.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-12 px-4"><div class="flex justify-between items-center mb-10"><h1 class="text-3xl font-bold text-slate-900">Mi Panel de Gestión</h1><a href="{{ url_for('publicar') }}" class="btn-medical px-6 py-3 font-bold">Nueva Publicación</a></div><div class="grid grid-cols-1 lg:grid-cols-3 gap-10"><div class="lg:col-span-2"> <h4 class="font-bold text-slate-400 uppercase text-xs tracking-widest mb-4">Solicitudes Recibidas</h4> {% for s in solicitudes_recibidas %}<div class="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex justify-between items-center mb-4"><div><p class="font-bold text-lg">{{ s.publicacion.nombre }}</p><p class="text-xs text-slate-400">Interesado: {{ s.solicitante.nombre }}</p></div><span class="bg-blue-50 text-brand px-4 py-1 rounded-full text-xs font-bold">{{ s.estatus }}</span></div>{% else %}<p class="text-slate-300 italic">No tienes solicitudes pendientes.</p>{% endfor %}</div><div class="space-y-4"> <h4 class="font-bold text-slate-400 uppercase text-xs tracking-widest mb-4">Mi Inventario</h4> {% for p in publicaciones %}<div class="bg-white p-4 rounded-xl border border-slate-100 shadow-sm flex items-center gap-3"><img src="{{ p.imagen_url }}" class="w-10 h-10 rounded-lg object-cover"><div class="flex-1"><p class="text-sm font-bold">{{ p.nombre }}</p></div><form action="{{ url_for('borrar_publicacion', id=p.id_oferta_insumo) }}" method="POST"><button class="text-slate-300 hover:text-red-500"><i class="fas fa-trash-alt"></i></button></form></div>{% endfor %}</div></div></div>{% endblock %}""",
    'publish.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-12 px-4"><div class="bg-white p-10 rounded-2xl shadow-xl border border-slate-100"><h2 class="text-3xl font-bold mb-8">Publicar Recurso</h2><form method="POST" enctype="multipart/form-data" class="space-y-6"><div><label class="block text-sm font-bold text-slate-400 mb-2">Foto del Insumo</label><input type="file" name="imagen" required class="text-sm"></div><input name="nombre" placeholder="Nombre (Ej: Bolsa de Sangre O-)" required class="w-full p-4 bg-slate-50 rounded-xl border-none shadow-inner"><div class="grid grid-cols-2 gap-4"><select name="categoria" class="p-4 bg-slate-50 rounded-xl border-none shadow-inner"><option>Sangre</option><option>Medicamento</option><option>Equipo</option></select><select name="tipo_publicacion" class="p-4 bg-slate-50 rounded-xl border-none shadow-inner"><option value="Donacion">Donación</option><option value="Venta">Venta</option></select></div><button type="submit" class="w-full btn-medical py-4 rounded-xl font-bold text-xl shadow-lg">Publicar en la Red</button></form></div></div>{% endblock %}""",
    'checkout.html': """{% extends "base.html" %}{% block content %}<div class="max-w-xl mx-auto py-20 px-4 text-center"><div class="bg-white p-10 rounded-2xl shadow-xl border border-slate-100"><h2 class="text-3xl font-bold mb-8">Confirmar Solicitud</h2><div class="bg-slate-50 p-6 rounded-2xl mb-8"><img src="{{ pub.imagen_url }}" class="w-32 h-32 rounded-xl mx-auto mb-4 object-cover shadow-md"><h3 class="font-bold text-xl">{{ pub.nombre }}</h3><p class="text-sm text-slate-400 uppercase font-bold">{{ pub.categoria }}</p></div><form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST"><button class="w-full btn-medical py-4 rounded-xl font-bold text-xl shadow-lg">Confirmar y Contactar</button></form></div></div>{% endblock %}"""
})

# ==========================================
# 3. RUTAS DE CONTROL
# ==========================================
@login_manager.user_loader
def load_user(user_id): return Usuario.query.get(int(user_id))

@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if Usuario.query.filter_by(email=request.form['email']).first():
            flash("Este correo ya está registrado.", "error")
        else:
            u = Usuario(nombre=request.form['nombre'], email=request.form['email'], telefono=request.form['telefono'], tipo_sangre=request.form['tipo_sangre'], ubicacion=request.form['ubicacion'], password_hash=generate_password_hash(request.form['password']))
            db.session.add(u); db.session.commit(); login_user(u)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = Usuario.query.filter_by(email=request.form['email']).first()
        if u and check_password_hash(u.password_hash, request.form['password']):
            login_user(u); return redirect(url_for('dashboard'))
        flash("Datos incorrectos.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/buscar')
def buscar():
    res = Publicacion.query.filter_by(estado='Verificado').all()
    return render_template('search.html', resultados=res)

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id_usuario).all()
    pub_ids = [p.id_oferta_insumo for p in pubs]
    sols = Solicitud.query.filter(Solicitud.id_publicacion.in_(pub_ids)).all() if pub_ids else []
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols)

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        img = request.files.get('imagen')
        img_url = "https://via.placeholder.com/400"
        if img: img_url = cloudinary.uploader.upload(img)['secure_url']
        p = Publicacion(id_proveedor=current_user.id_usuario, nombre=request.form['nombre'], categoria=request.form['categoria'], tipo_publicacion=request.form['tipo_publicacion'], imagen_url=img_url)
        db.session.add(p); db.session.commit()
        flash("¡Publicado con éxito!", "success")
        return redirect(url_for('dashboard'))
    return render_template('publish.html')

@app.route('/confirmar_compra/<int:id>')
@login_required
def confirmar_compra(id):
    p = Publicacion.query.get_or_404(id)
    return render_template('checkout.html', pub=p)

@app.route('/procesar_transaccion/<int:id>', methods=['POST'])
@login_required
def procesar_transaccion(id):
    p = Publicacion.query.get_or_404(id)
    s = Solicitud(id_solicitante=current_user.id_usuario, id_publicacion=p.id_oferta_insumo)
    db.session.add(s); db.session.commit()
    flash("Solicitud enviada al donante. Puedes verla en tu panel.", "success")
    return redirect(url_for('dashboard'))

@app.route('/borrar_publicacion/<int:id>', methods=['POST'])
@login_required
def borrar_publicacion(id):
    p = Publicacion.query.get_or_404(id)
    if p.id_proveedor == current_user.id_usuario:
        db.session.delete(p); db.session.commit()
        flash("Publicación eliminada.", "success")
    return redirect(url_for('dashboard'))

@app.route('/perfil')
@login_required
def perfil():
    return render_template('perfil.html')

@app.route('/chat/<int:id_solicitud>')
@login_required
def chat(id_solicitud):
    return "Módulo de chat disponible tras confirmación inicial."

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=False)
