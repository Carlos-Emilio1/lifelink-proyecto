import eventlet
eventlet.monkey_patch() # Parche obligatorio al inicio para estabilidad de WebSockets

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
# 1. PLANTILLAS HTML (ESTILO MÉDICO PROFESIONAL)
# ==========================================

base_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LifeLink - Red de Apoyo Médico</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --brand-blue: #0ea5e9; --brand-dark: #0369a1; }
        .bg-brand { background-color: var(--brand-blue); }
        .text-brand { color: var(--brand-blue); }
        .btn-medical { background-color: var(--brand-blue); color: white; transition: all 0.3s; }
        .btn-medical:hover { background-color: var(--brand-dark); transform: scale(1.02); }
        #map { height: 350px; width: 100%; border-radius: 1rem; z-index: 1; border: 2px solid #e2e8f0; }
        .glass-card { background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px); }
    </style>
</head>
<body class="bg-slate-50 flex flex-col min-h-screen font-sans text-slate-900">
    <nav class="bg-white/90 backdrop-blur-md border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <a href="/" class="flex items-center gap-2">
                        <div class="bg-brand p-1.5 rounded-lg shadow-lg">
                             <svg width="24" height="24" viewBox="0 0 100 100" fill="none" stroke="white" stroke-width="8">
                                <path d="M10 50 L30 50 L40 20 L60 80 L70 50 L90 50" stroke-linecap="round" stroke-linejoin="round"/>
                             </svg>
                        </div>
                        <span class="font-black text-xl tracking-tighter text-slate-800">LifeLink</span>
                    </a>
                </div>
                <div class="flex items-center gap-6">
                    <div class="hidden md:flex gap-6">
                        <a href="{{ url_for('buscar') }}" class="text-sm font-bold text-slate-600 hover:text-brand transition">Recursos</a>
                        {% if current_user.is_authenticated %}
                        <a href="{{ url_for('publicar') }}" class="text-sm font-bold text-slate-600 hover:text-brand transition">Publicar</a>
                        <a href="{{ url_for('dashboard') }}" class="text-sm font-bold text-slate-600 hover:text-brand transition">Gestión</a>
                        {% endif %}
                    </div>
                    {% if current_user.is_authenticated %}
                        <div class="flex items-center gap-3">
                            {% if current_user.email == 'admin@lifelink.com' %}
                                <span class="bg-red-100 text-red-600 text-[10px] px-2 py-0.5 rounded font-black uppercase">Admin</span>
                            {% endif %}
                            <a href="{{ url_for('perfil') }}" class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-brand font-black border-2 border-brand/20">{{ current_user.nombre[0] | upper }}</a>
                        </div>
                    {% else %}
                        <a href="{{ url_for('login') }}" class="text-sm font-bold text-slate-500">Log In</a>
                        <a href="{{ url_for('registro') }}" class="btn-medical px-4 py-2 rounded-lg text-sm font-bold shadow-md">Unirse</a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>
    <main class="flex-grow">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="max-w-4xl mx-auto mt-4 px-4">
                <div class="p-4 rounded-xl {% if category == 'error' %}bg-red-50 text-red-700 border border-red-100{% else %}bg-emerald-50 text-emerald-700 border border-emerald-100{% endif %} flex items-center gap-3 shadow-sm">
                  <i class="fas fa-info-circle"></i> {{ message }}
                </div>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="py-10 bg-white border-t border-slate-100">
        <div class="max-w-7xl mx-auto px-4 text-center">
            <p class="text-[10px] text-slate-400 font-black tracking-[0.3em] uppercase mb-2">LifeLink • TechPulse 2026</p>
            <p class="text-xs text-slate-300">Proyecto Aula 5IV7 - Prototipo Académico de Alta Fidelidad</p>
        </div>
    </footer>
</body>
</html>
"""

home_template = """
{% extends "base.html" %}
{% block content %}
<div class="relative bg-white pt-20 pb-32 overflow-hidden min-h-[85vh] flex items-center">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div class="lg:grid lg:grid-cols-12 lg:gap-12 items-center">
            <div class="sm:text-center lg:col-span-6 lg:text-left">
                <span class="inline-flex items-center px-4 py-1.5 rounded-full text-xs font-black bg-blue-50 text-brand uppercase tracking-widest mb-6 border border-blue-100">
                    <i class="fas fa-microchip mr-2"></i> TechPulse Solutions
                </span>
                <h1 class="text-5xl tracking-tight font-black text-slate-900 sm:text-6xl md:text-7xl leading-[1.1]">
                    Tecnología para <span class="text-brand">salvar vidas.</span>
                </h1>
                <p class="mt-6 text-lg text-slate-500 max-w-lg leading-relaxed">
                    Gestiona donaciones de sangre, insumos médicos y equipos ortopédicos en una red segura y coordinada en tiempo real.
                </p>
                <div class="mt-10 flex flex-wrap gap-4 sm:justify-center lg:justify-start">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-10 py-5 rounded-2xl font-black text-lg shadow-xl flex items-center gap-3">
                        <i class="fas fa-heart-pulse"></i> Buscar Insumos
                    </a>
                    <a href="{{ url_for('registro') }}" class="bg-slate-100 text-slate-700 hover:bg-slate-200 px-10 py-5 rounded-2xl font-black text-lg transition shadow-inner">
                        Registrarse
                    </a>
                </div>
            </div>
            <div class="mt-16 lg:mt-0 lg:col-span-6">
                <div class="relative mx-auto w-full max-w-xl">
                    <div class="absolute -top-10 -left-10 w-72 h-72 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
                    <div class="absolute -bottom-10 -right-10 w-72 h-72 bg-brand rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
                    <div class="relative bg-white p-4 rounded-[2.5rem] shadow-2xl border-8 border-slate-50 overflow-hidden">
                        <img class="w-full rounded-[1.5rem]" src="https://images.unsplash.com/photo-1576091160550-2173bdb999ef?auto=format&fit=crop&q=80&w=1000" alt="Medicina Moderna">
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

register_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-2xl mx-auto py-16 px-4">
    <div class="bg-white p-10 rounded-[2.5rem] shadow-2xl border border-slate-50">
        <h2 class="text-4xl font-black text-slate-900 mb-2">Registro de Perfil</h2>
        <p class="text-slate-500 mb-8">Únete a la red de apoyo médico LifeLink.</p>
        
        <form method="POST" class="space-y-5">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-xs font-black text-slate-400 uppercase mb-2 ml-1">Nombre Completo</label>
                    <input name="nombre" required class="w-full p-4 bg-slate-50 rounded-2xl outline-none focus:ring-2 focus:ring-brand border-none">
                </div>
                <div>
                    <label class="block text-xs font-black text-slate-400 uppercase mb-2 ml-1">Tipo de Sangre</label>
                    <select name="tipo_sangre" required class="w-full p-4 bg-slate-50 rounded-2xl outline-none focus:ring-2 focus:ring-brand border-none">
                        <option value="">Seleccionar</option>
                        <option>O+</option><option>O-</option><option>A+</option><option>A-</option>
                        <option>B+</option><option>B-</option><option>AB+</option><option>AB-</option>
                    </select>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label class="block text-xs font-black text-slate-400 uppercase mb-2 ml-1">Email</label>
                    <input name="email" type="email" required class="w-full p-4 bg-slate-50 rounded-2xl outline-none focus:ring-2 focus:ring-brand border-none">
                </div>
                <div>
                    <label class="block text-xs font-black text-slate-400 uppercase mb-2 ml-1">Teléfono / WhatsApp</label>
                    <input name="telefono" type="tel" required placeholder="55 1234 5678" class="w-full p-4 bg-slate-50 rounded-2xl outline-none focus:ring-2 focus:ring-brand border-none">
                </div>
            </div>

            <div>
                <label class="block text-xs font-black text-slate-400 uppercase mb-2 ml-1">Ubicación (Ciudad/Estado)</label>
                <input name="ubicacion" required placeholder="Ej: CDMX, Iztapalapa" class="w-full p-4 bg-slate-50 rounded-2xl outline-none focus:ring-2 focus:ring-brand border-none">
            </div>

            <div>
                <label class="block text-xs font-black text-slate-400 uppercase mb-2 ml-1">Contraseña</label>
                <input name="password" type="password" required class="w-full p-4 bg-slate-50 rounded-2xl outline-none focus:ring-2 focus:ring-brand border-none">
            </div>

            <button class="w-full btn-medical py-5 rounded-2xl font-black text-xl shadow-xl mt-4">Completar Registro</button>
        </form>
    </div>
</div>
{% endblock %}
"""

soporte_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-5xl mx-auto py-16 px-4">
    <div class="text-center mb-16">
        <h2 class="text-5xl font-black text-slate-900 mb-4">Centro de Soporte</h2>
        <p class="text-slate-500">¿Cómo podemos ayudarte hoy?</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Ayuda Rápida -->
        <div class="lg:col-span-2 space-y-6">
            <h3 class="text-2xl font-black text-slate-800 flex items-center gap-3 mb-6">
                <i class="fas fa-circle-question text-brand"></i> Preguntas Frecuentes
            </h3>
            
            <div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
                <h4 class="font-bold text-slate-800 mb-2">¿Cómo publico una donación de sangre?</h4>
                <p class="text-sm text-slate-500">Ve a la pestaña "Publicar", selecciona la categoría "Sangre" y marca tu ubicación en el mapa. Recuerda poner en la descripción si es urgente.</p>
            </div>
            
            <div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
                <h4 class="font-bold text-slate-800 mb-2">¿Las transacciones son reales?</h4>
                <p class="text-sm text-slate-500">No. LifeLink es un prototipo académico. Toda simulación de pago es ficticia y no se debe ingresar información bancaria real.</p>
            </div>

            <div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-100">
                <h4 class="font-bold text-slate-800 mb-2">¿Cómo funciona el chat?</h4>
                <p class="text-sm text-slate-500">Una vez que solicitas un insumo, se abrirá un canal de chat seguro entre tú y el donante en tu Panel de Gestión.</p>
            </div>
        </div>

        <!-- Formulario de Soporte -->
        <div class="bg-white p-8 rounded-[2.5rem] shadow-2xl border border-slate-50 h-fit sticky top-24">
            <h3 class="text-xl font-black text-slate-900 mb-6 flex items-center gap-2">
                <i class="fas fa-headset text-brand"></i> Hablar con Admin
            </h3>
            <form action="{{ url_for('enviar_soporte') }}" method="POST" class="space-y-4">
                <input name="asunto" placeholder="Asunto del reporte" required class="w-full p-4 bg-slate-50 rounded-2xl outline-none border-none text-sm">
                <textarea name="mensaje" placeholder="Describe tu problema a detalle..." rows="4" required class="w-full p-4 bg-slate-50 rounded-2xl outline-none border-none text-sm"></textarea>
                <button class="w-full btn-medical py-4 rounded-2xl font-black shadow-lg">Enviar Mensaje</button>
            </form>
            <p class="text-[10px] text-slate-400 mt-6 text-center italic">El administrador te responderá vía chat interno en breve.</p>
        </div>
    </div>
</div>
{% endblock %}
"""

# ==========================================
# 2. CONFIGURACIÓN APP Y MODELOS
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lifelink_2026_pro_secure')
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///lifelink.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    telefono = db.Column(db.String(20))
    tipo_sangre = db.Column(db.String(10))
    ubicacion = db.Column(db.String(255))
    def get_id(self): return str(self.id_usuario)

class Publicacion(db.Model):
    __tablename__ = 'insumos'
    id_oferta_insumo = db.Column(db.Integer, primary_key=True)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    tipo_publicacion = db.Column(db.String(50))
    precio = db.Column(db.Float, default=0.0)
    imagen_url = db.Column(db.String(500))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    estado = db.Column(db.String(20), default='Disponible')
    proveedor = db.relationship('Usuario', backref='publicaciones')

class Solicitud(db.Model):
    __tablename__ = 'solicitudes'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('insumos.id_oferta_insumo'))
    solicitante = db.relationship('Usuario', backref='solicitudes_enviadas')
    publicacion = db.relationship('Publicacion', backref='solicitudes_recibidas')

class MensajeSoporte(db.Model):
    __tablename__ = 'soporte_tickets'
    id_ticket = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    asunto = db.Column(db.String(150))
    mensaje = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    leido = db.Column(db.Boolean, default=False)
    usuario = db.relationship('Usuario', backref='tickets')

# Loader de Plantillas
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'register.html': register_template,
    'soporte.html': soporte_template,
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-20 px-4"><div class="bg-white p-10 rounded-[2.5rem] shadow-2xl border border-slate-100"><h2 class="text-3xl font-black mb-8 text-center text-slate-800">Bienvenido de nuevo</h2><form method="POST" class="space-y-4"><input name="email" type="email" placeholder="Correo electrónico" required class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-brand"><input name="password" type="password" placeholder="Contraseña" required class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-brand"><button class="w-full btn-medical py-5 rounded-2xl font-black text-lg shadow-xl mt-4 transition-all">Ingresar al Sistema</button></form></div></div>{% endblock %}""",
    'search.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-10 px-4"><div class="flex flex-col lg:flex-row gap-10"><div class="lg:w-80"><div class="bg-white p-8 rounded-[2rem] shadow-sm border border-slate-100 sticky top-24"><h4 class="font-black text-slate-900 mb-6 uppercase tracking-widest text-xs">Filtrar Recursos</h4><form method="GET"><input name="q" placeholder="Buscar insumo..." class="w-full p-3 bg-slate-50 border-none rounded-xl text-sm mb-4 outline-none focus:ring-2 focus:ring-brand"><button class="w-full btn-medical py-3 rounded-xl text-sm font-bold shadow-md">Aplicar</button></form></div></div><div class="flex-1 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">{% for item in resultados %}<div class="bg-white rounded-[2rem] shadow-sm border border-slate-100 overflow-hidden hover:shadow-2xl transition-all duration-300 group"><div class="relative"><img src="{{ item.imagen_url }}" class="w-full h-56 object-cover group-hover:scale-105 transition-transform duration-500"><div class="absolute top-4 right-4 bg-white/90 backdrop-blur-md px-3 py-1 rounded-full text-[10px] font-black uppercase text-brand">{{ item.categoria }}</div></div><div class="p-6"><h3 class="font-black text-slate-800 text-xl mb-1">{{ item.nombre }}</h3><p class="text-[10px] text-slate-400 font-bold mb-4 uppercase tracking-tighter"><i class="fas fa-user-md mr-1"></i> {{ item.proveedor.nombre }}</p><div class="flex justify-between items-center"><span class="text-2xl font-black text-slate-900">{% if item.tipo_publicacion == 'Venta' %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span><a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="w-12 h-12 bg-blue-50 text-brand rounded-2xl flex items-center justify-center hover:bg-brand hover:text-white transition-colors"><i class="fas fa-arrow-right"></i></a></div></div></div>{% endfor %}</div></div></div>{% endblock %}""",
    'publish.html': """{% extends "base.html" %}{% block content %}<div class="max-w-4xl mx-auto py-10 px-4"><div class="bg-white rounded-[2.5rem] shadow-2xl p-10 border border-slate-50"><h2 class="text-4xl font-black text-slate-900 mb-8">Nueva Publicación</h2><form method="POST" enctype="multipart/form-data" class="space-y-8"><div class="grid grid-cols-1 md:grid-cols-2 gap-8"><div><label class="block text-xs font-black text-slate-400 uppercase mb-3">Foto Real del Insumo</label><div class="p-8 border-4 border-dashed border-slate-100 rounded-[2rem] text-center bg-slate-50/50 hover:border-brand transition-colors"><input type="file" name="imagen" accept="image/*" required class="text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-black file:bg-brand file:text-white"></div></div><div class="space-y-4"><div><label class="block text-xs font-black text-slate-400 uppercase mb-2">Nombre</label><input name="nombre" placeholder="Ej: Silla de ruedas" required class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-brand"></div><div class="grid grid-cols-2 gap-4"><div><label class="block text-xs font-black text-slate-400 uppercase mb-2">Categoría</label><select name="categoria" class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-brand"><option>Medicamento</option><option>Sangre</option><option>Ortopedico</option><option>Equipo</option></select></div><div><label class="block text-xs font-black text-slate-400 uppercase mb-2">Precio ($)</label><input name="precio" type="number" value="0" class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-brand"></div></div></div></div><div class="space-y-4"><div><label class="block text-xs font-black text-slate-400 uppercase mb-2">Ubicación de entrega (Mapa)</label><div id="map"></div><input type="hidden" id="lat" name="lat"><input type="hidden" id="lng" name="lng"></div></div><button class="w-full btn-medical py-5 rounded-[2rem] font-black text-2xl shadow-xl hover:shadow-brand/20 transition-all">Publicar en la Red</button></form></div></div><script>var map = L.map('map').setView([19.4326, -99.1332], 12);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);var marker;map.on('click', function(e){ if(marker) map.removeLayer(marker); marker = L.marker(e.latlng).addTo(map); document.getElementById('lat').value = e.latlng.lat; document.getElementById('lng').value = e.latlng.lng; });</script>{% endblock %}""",
    'dashboard.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-12 px-4"><div class="flex justify-between items-end mb-12"><h1 class="text-5xl font-black text-slate-900 tracking-tighter">Bienvenido, <span class="text-brand">{{ current_user.nombre.split()[0] }}</span></h1><p class="text-slate-400 font-bold uppercase text-[10px] tracking-[0.2em] mb-2">{{ current_user.tipo_sangre }} | {{ current_user.ubicacion }}</p></div><div class="grid grid-cols-1 lg:grid-cols-3 gap-10">{% if current_user.email == 'admin@lifelink.com' %}<div class="lg:col-span-3 bg-red-50 p-10 rounded-[2.5rem] border border-red-100 shadow-sm"><h3 class="text-2xl font-black text-red-700 mb-6 flex items-center gap-2"><i class="fas fa-shield-halved"></i> Reportes de Soporte Técnico</h3><div class="grid grid-cols-1 md:grid-cols-2 gap-6">{% for ticket in tickets_admin %}<div class="bg-white p-6 rounded-3xl shadow-sm border border-red-200"><div><p class="text-[10px] font-black text-red-400 uppercase mb-1">Usuario: {{ ticket.usuario.nombre }}</p><h5 class="font-black text-slate-800 mb-2">{{ ticket.asunto }}</h5><p class="text-xs text-slate-500 mb-4">{{ ticket.mensaje }}</p></div><a href="mailto:{{ ticket.usuario.email }}" class="bg-red-500 text-white px-4 py-2 rounded-xl text-xs font-bold hover:bg-red-600 transition">Contactar Vía Email</a></div>{% else %}<p class="text-red-400 italic">No hay tickets de soporte pendientes.</p>{% endfor %}</div></div>{% endif %}<div class="lg:col-span-2 space-y-8"><h4 class="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2"><div class="w-1 h-1 bg-brand rounded-full"></div> Pedidos Recibidos</h4>{% for s in solicitudes_recibidas %}<div class="bg-white p-8 rounded-[2rem] shadow-sm border border-slate-100 flex justify-between items-center group hover:border-brand transition-colors"><div><p class="text-xs font-black text-brand mb-1 uppercase tracking-tighter">Pedido #{{ s.id_solicitud }}</p><h5 class="font-black text-slate-800 text-xl">{{ s.publicacion.nombre }}</h5><p class="text-xs text-slate-400 mt-1">Solicitante: <b>{{ s.solicitante.nombre }}</b></p></div><div class="flex gap-3"><a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="btn-medical px-6 py-3 rounded-2xl font-black text-sm shadow-md">Abrir Chat</a></div></div>{% else %}<div class="bg-white p-12 rounded-[2rem] text-center border border-dashed border-slate-200"><p class="text-slate-400 font-bold">No has recibido solicitudes aún.</p></div>{% endfor %}</div><div class="space-y-8"><h4 class="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2"><div class="w-1 h-1 bg-brand rounded-full"></div> Tus Publicaciones</h4><div class="grid grid-cols-1 gap-4">{% for p in publicaciones %}<div class="bg-white p-4 rounded-3xl shadow-sm border border-slate-100 flex items-center gap-4"><img src="{{ p.imagen_url }}" class="w-14 h-14 rounded-2xl object-cover"><div class="flex-1 text-sm font-bold text-slate-800">{{ p.nombre }}</div><span class="bg-blue-50 text-brand px-3 py-1 rounded-full text-[10px] font-black uppercase">{{ p.estado }}</span></div>{% endfor %}</div></div></div></div>{% endblock %}""",
    'checkout.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-20 px-4"><div class="bg-white p-12 rounded-[2.5rem] shadow-2xl text-center border border-slate-50"><h2 class="text-4xl font-black text-slate-900 mb-8">Confirmar Solicitud</h2><div class="bg-slate-50 p-6 rounded-3xl mb-10 inline-block mx-auto"><img src="{{ pub.imagen_url }}" class="w-48 h-48 rounded-[2rem] object-cover shadow-lg mx-auto mb-4"><h3 class="text-xl font-black text-slate-800">{{ pub.nombre }}</h3><p class="text-brand font-bold uppercase text-xs tracking-widest">{{ pub.categoria }}</p></div><form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST"><button class="w-full btn-medical py-5 rounded-[2rem] font-black text-2xl shadow-xl hover:shadow-brand/30 transition-all">Solicitar Insumo</button></form><p class="text-xs text-slate-400 mt-6"><i class="fas fa-lock mr-1"></i> Conexión encriptada punto a punto</p></div></div>{% endblock %}""",
    'chat.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-8 px-4 h-[75vh] flex flex-col"><div class="bg-white rounded-[2.5rem] shadow-2xl flex flex-col flex-1 overflow-hidden border border-slate-100"><div class="bg-brand p-6 text-white flex justify-between items-center shadow-lg relative z-10"><div class="flex items-center gap-4"><div class="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center font-black">L</div><div><h3 class="font-black leading-none">Chat Coordinación</h3><p class="text-[10px] text-blue-100 uppercase tracking-widest mt-1">LifeLink Secure Line</p></div></div><a href="{{ url_for('dashboard') }}" class="text-white/80 hover:text-white"><i class="fas fa-times text-xl"></i></a></div><div class="flex-1 overflow-y-auto p-8 space-y-6 bg-slate-50/50" id="chat-box"></div><div class="p-6 bg-white border-t border-slate-100"><form onsubmit="event.preventDefault(); send();" class="flex gap-4"><input id="msg-input" placeholder="Escribe un mensaje..." class="flex-1 p-4 bg-slate-100 rounded-2xl border-none outline-none focus:ring-2 focus:ring-brand font-medium text-sm"><button class="bg-brand text-white w-14 h-14 rounded-2xl shadow-lg hover:scale-105 transition-transform flex items-center justify-center shadow-brand/20"><i class="fas fa-paper-plane text-lg"></i></button></form></div></div></div><script>const socket = io(); const room = "{{ solicitud.id_solicitud }}"; const user = "{{ current_user.nombre }}"; socket.emit('join', {room: room}); socket.on('nuevo_mensaje', function(data){ const box = document.getElementById('chat-box'); const isMe = data.user === user; const d = document.createElement('div'); d.className = `flex ${isMe ? 'justify-end':'justify-start'}`; d.innerHTML = `<div class="${isMe?'bg-brand text-white rounded-l-[1.5rem] rounded-tr-[1.5rem] shadow-brand/20 shadow-md':'bg-white text-slate-700 rounded-r-[1.5rem] rounded-tl-[1.5rem] shadow-sm border border-slate-200'} px-6 py-3 max-w-[85%] animate-in fade-in slide-in-from-bottom-2"><p class="text-[10px] font-black uppercase mb-1 ${isMe?'text-blue-100':'text-slate-400'}">${data.user}</p><p class="text-sm font-medium leading-relaxed">${data.msg}</p></div>`; box.appendChild(d); box.scrollTop = box.scrollHeight; }); function send(){ const i = document.getElementById('msg-input'); if(i.value.trim()){ socket.emit('enviar_mensaje', {msg: i.value, room: room}); i.value=''; } }</script>{% endblock %}""",
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-20 px-4 text-center"><div class="w-40 h-40 bg-brand text-white text-6xl font-black rounded-[2.5rem] flex items-center justify-center mx-auto mb-8 shadow-2xl border-8 border-white animate-bounce-slow">{{ current_user.nombre[0] | upper }}</div><h2 class="text-5xl font-black text-slate-900 mb-2">{{ current_user.nombre }}</h2><p class="text-brand font-black uppercase tracking-[0.4em] text-sm mb-12">Donante Verificado {{ current_user.tipo_sangre }}</p><div class="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">{% for label, val in [('Email', current_user.email), ('WhatsApp', current_user.telefono), ('Ciudad', current_user.ubicacion)] %}<div class="bg-white p-8 rounded-[2rem] shadow-sm border border-slate-100"><p class="text-[10px] text-slate-400 font-black uppercase mb-2 tracking-widest">{{ label }}</p><p class="font-black text-slate-800 break-words">{{ val }}</p></div>{% endfor %}</div><div class="mt-16"><a href="{{ url_for('logout') }}" class="bg-red-50 text-red-500 px-10 py-4 rounded-2xl font-black text-sm hover:bg-red-500 hover:text-white transition-all shadow-sm">Cerrar Sesión Segura</a></div></div>{% endblock %}"""
})

# ==========================================
# 3. RUTAS Y LÓGICA
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
            u = Usuario(
                nombre=request.form['nombre'],
                email=request.form['email'],
                telefono=request.form['telefono'],
                tipo_sangre=request.form['tipo_sangre'],
                ubicacion=request.form['ubicacion'],
                password_hash=generate_password_hash(request.form['password'])
            )
            db.session.add(u)
            db.session.commit()
            login_user(u)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = Usuario.query.filter_by(email=request.form['email']).first()
        if u and check_password_hash(u.password_hash, request.form['password']):
            login_user(u)
            return redirect(url_for('dashboard'))
        flash("Credenciales incorrectas.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        img = request.files.get('imagen')
        img_url = "https://via.placeholder.com/400"
        if img:
            res = cloudinary.uploader.upload(img)
            img_url = res['secure_url']
        
        p = Publicacion(
            id_proveedor=current_user.id_usuario,
            nombre=request.form['nombre'],
            categoria=request.form['categoria'],
            tipo_publicacion=request.form['tipo_publicacion'],
            precio=float(request.form.get('precio', 0) or 0),
            imagen_url=img_url,
            latitud=float(request.form.get('lat', 19.4326)),
            longitud=float(request.form.get('lng', -99.1332))
        )
        db.session.add(p)
        db.session.commit()
        flash("¡Publicación realizada con éxito!", "success")
        return redirect(url_for('dashboard'))
    return render_template('publish.html')

@app.route('/buscar')
def buscar():
    q = request.args.get('q', '')
    res = Publicacion.query.filter(Publicacion.nombre.contains(q)).all()
    return render_template('search.html', resultados=res)

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
    db.session.add(s)
    db.session.commit()
    flash("Solicitud enviada al donante.", "success")
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id_usuario).all()
    pub_ids = [p.id_oferta_insumo for p in pubs]
    sols = Solicitud.query.filter(Solicitud.id_publicacion.in_(pub_ids)).all() if pub_ids else []
    tickets = MensajeSoporte.query.all() if current_user.email == 'admin@lifelink.com' else []
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols, tickets_admin=tickets)

@app.route('/chat/<int:id_solicitud>')
@login_required
def chat(id_solicitud):
    s = Solicitud.query.get_or_404(id_solicitud)
    return render_template('chat.html', solicitud=s)

@app.route('/perfil')
@login_required
def perfil(): return render_template('perfil.html')

@app.route('/soporte')
def soporte(): return render_template('soporte.html')

@app.route('/enviar_soporte', methods=['POST'])
@login_required
def enviar_soporte():
    t = MensajeSoporte(
        id_usuario=current_user.id_usuario,
        asunto=request.form['asunto'],
        mensaje=request.form['mensaje']
    )
    db.session.add(t)
    db.session.commit()
    flash("Ticket de soporte enviado. El administrador revisará tu caso.", "success")
    return redirect(url_for('soporte'))

# Eventos de Socket.IO
@socketio.on('join')
def on_join(data): join_room(data['room'])

@socketio.on('enviar_mensaje')
def handle_msg(data):
    emit('nuevo_mensaje', {'msg': data['msg'], 'user': current_user.nombre}, room=data['room'])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Crear cuenta Admin si no existe
        if not Usuario.query.filter_by(email='admin@lifelink.com').first():
            admin = Usuario(
                nombre="Administrador LifeLink",
                email="admin@lifelink.com",
                password_hash=generate_password_hash("admin123"),
                telefono="55 0000 0000",
                tipo_sangre="N/A",
                ubicacion="Centro de Datos LifeLink"
            )
            db.session.add(admin)
            db.session.commit()
    socketio.run(app, debug=False)
