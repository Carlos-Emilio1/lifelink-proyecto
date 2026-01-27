import eventlet
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
# 1. PLANTILLAS HTML (UI PROFESIONAL Y FUNCIONALIDADES NUEVAS)
# ==========================================

base_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LifeLink - Red Médica Profesional</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --brand-blue: #0ea5e9; --brand-dark: #0369a1; }
        .bg-brand { background-color: var(--brand-blue); }
        .text-brand { color: var(--brand-blue); }
        .btn-medical { background-color: var(--brand-blue); color: white; transition: all 0.3s; border-radius: 1rem; }
        .btn-medical:hover { background-color: var(--brand-dark); transform: translateY(-2px); }
        #map { height: 350px; width: 100%; border-radius: 1.5rem; z-index: 10; border: 2px solid #f1f5f9; }
        .animate-float { animation: float 6s ease-in-out infinite; }
        @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-20px); } 100% { transform: translateY(0px); } }
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
                        <a href="{{ url_for('registro') }}" class="btn-medical px-4 py-2 text-sm font-bold shadow-md">Unirse</a>
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
                <div class="p-4 rounded-xl {% if category == 'error' %}bg-red-50 text-red-700 border border-red-100{% else %}bg-emerald-50 text-emerald-700 border border-emerald-100{% endif %} flex items-center gap-3 shadow-sm border">
                  <i class="fas fa-info-circle"></i> {{ message }}
                </div>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="py-12 bg-white border-t border-slate-100 mt-20">
        <div class="max-w-7xl mx-auto px-4 text-center">
            <p class="text-[10px] text-slate-400 font-black tracking-[0.3em] uppercase mb-4">LifeLink • TechPulse © 2026</p>
            <div class="flex justify-center gap-6 text-xs text-slate-400 font-bold mb-6">
                <a href="{{ url_for('soporte') }}" class="hover:text-brand">Privacidad</a>
                <a href="{{ url_for('soporte') }}" class="hover:text-brand">Modelo de Negocio</a>
                <a href="{{ url_for('soporte') }}" class="hover:text-brand">Legal</a>
            </div>
            <p class="text-[9px] text-slate-300 max-w-lg mx-auto leading-relaxed">Proyecto Aula 5IV7. Toda transacción comercial es una simulación académica. La venta de sangre está prohibida y regulada por las leyes de salud vigentes.</p>
        </div>
    </footer>
</body>
</html>
"""

home_template = """
{% extends "base.html" %}
{% block content %}
<div class="relative min-h-[90vh] flex items-center overflow-hidden">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 w-full">
        <div class="lg:grid lg:grid-cols-12 lg:gap-12 items-center">
            <div class="sm:text-center lg:col-span-6 lg:text-left">
                <div class="inline-flex items-center px-4 py-1.5 rounded-full text-[10px] font-black bg-blue-50 text-brand uppercase tracking-widest mb-8 border border-blue-100">
                    <span class="relative flex h-2 w-2 mr-2"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand opacity-75"></span><span class="relative inline-flex rounded-full h-2 w-2 bg-brand"></span></span>
                    Red de Apoyo 24/7 Activa
                </div>
                <h1 class="text-6xl tracking-tight font-black text-slate-900 sm:text-7xl leading-[1.05] mb-8">
                    Conectando <span class="text-brand">Salud</span> con Altruismo.
                </h1>
                <p class="text-xl text-slate-500 max-w-lg leading-relaxed mb-10">
                    La primera plataforma inteligente para la gestión de donaciones de sangre e insumos médicos verificados.
                </p>
                <div class="flex flex-wrap gap-5">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-10 py-5 font-black text-lg shadow-2xl flex items-center gap-3">
                        <i class="fas fa-hand-holding-medical"></i> Explorar Red
                    </a>
                    <a href="{{ url_for('registro') }}" class="bg-white border-2 border-slate-200 px-10 py-5 rounded-2xl font-black text-lg hover:border-brand transition shadow-sm">Unirse</a>
                </div>
            </div>
            <div class="mt-16 lg:mt-0 lg:col-span-6 flex justify-center">
                <div class="relative w-full max-w-md animate-float">
                    <div class="absolute inset-0 bg-brand rounded-[3rem] rotate-6 opacity-10"></div>
                    <div class="relative bg-white p-4 rounded-[3rem] shadow-2xl border-8 border-slate-50">
                        <img class="w-full h-[500px] rounded-[2rem] object-cover" src="https://images.unsplash.com/photo-1551076805-e1869033e561?q=80&w=1000&auto=format&fit=crop" alt="LifeLink Medical">
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

publish_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto py-12 px-4">
    <div class="bg-white rounded-[2.5rem] shadow-2xl p-10 border border-slate-50">
        <h2 class="text-4xl font-black text-slate-900 mb-2">Publicar Insumo</h2>
        <p class="text-slate-500 mb-10 italic">Asegúrate de que el producto sea legal y esté vigente.</p>
        
        <form method="POST" enctype="multipart/form-data" class="space-y-8">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
                <div class="space-y-6">
                    <div>
                        <label class="block text-xs font-black text-slate-400 uppercase mb-3">Foto del Producto</label>
                        <div class="relative group">
                            <div class="p-8 border-4 border-dashed border-slate-100 rounded-[2rem] text-center bg-slate-50/50 group-hover:border-brand transition-all cursor-pointer">
                                <i class="fas fa-camera text-4xl text-slate-200 mb-4 group-hover:text-brand"></i>
                                <input type="file" name="imagen" accept="image/*" required class="text-xs text-slate-400 w-full">
                            </div>
                        </div>
                    </div>
                    
                    <div id="receta_section" class="hidden">
                        <label class="block text-xs font-black text-red-400 uppercase mb-3"><i class="fas fa-file-prescription"></i> Subir Receta Médica (Obligatorio)</label>
                        <div class="p-4 border-2 border-red-100 bg-red-50/30 rounded-2xl">
                            <input type="file" name="receta" accept="image/*,application/pdf" class="text-xs">
                        </div>
                    </div>
                </div>

                <div class="space-y-5">
                    <div>
                        <label class="block text-xs font-black text-slate-400 uppercase mb-2">Categoría</label>
                        <select name="categoria" id="cat_select" onchange="toggleLegalFiltros(this.value)" class="w-full p-4 bg-slate-50 rounded-2xl outline-none border-none font-bold text-slate-700">
                            <option value="Equipo">Equipo Médico</option>
                            <option value="Medicamento">Medicamento (Requiere Receta)</option>
                            <option value="Sangre">Donación de Sangre (Solo Altruista)</option>
                            <option value="Ortopedico">Ortopédico</option>
                        </select>
                    </div>

                    <div>
                        <label class="block text-xs font-black text-slate-400 uppercase mb-2">Nombre del Insumo</label>
                        <input name="nombre" placeholder="Ej: Concentrador de Oxígeno" required class="w-full p-4 bg-slate-50 rounded-2xl outline-none border-none">
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs font-black text-slate-400 uppercase mb-2">Tipo</label>
                            <select name="tipo_publicacion" id="tipo_pub" class="w-full p-4 bg-slate-50 rounded-2xl outline-none border-none text-sm font-bold">
                                <option value="Venta">Venta</option>
                                <option value="Donacion">Donación</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs font-black text-slate-400 uppercase mb-2">Precio ($)</label>
                            <input name="precio" id="precio_input" type="number" value="0" class="w-full p-4 bg-slate-50 rounded-2xl outline-none border-none font-bold">
                        </div>
                    </div>
                </div>
            </div>

            <div class="space-y-4">
                <label class="block text-xs font-black text-slate-400 uppercase mb-2">Ubicación de Entrega</label>
                <div id="map"></div>
                <div class="bg-blue-50 p-4 rounded-2xl border border-blue-100 flex items-center gap-3">
                    <i class="fas fa-location-dot text-brand"></i>
                    <input type="text" id="direccion_text" name="direccion_manual" readonly placeholder="Haz clic en el mapa para detectar dirección..." class="bg-transparent w-full outline-none text-sm font-bold text-brand italic">
                </div>
                <input type="hidden" id="lat" name="lat">
                <input type="hidden" id="lng" name="lng">
            </div>

            <button type="submit" class="w-full btn-medical py-6 rounded-3xl font-black text-2xl shadow-xl hover:shadow-brand/40 transition-all">Publicar en la Red</button>
        </form>
    </div>
</div>

<script>
    var map = L.map('map').setView([19.4326, -99.1332], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    var marker;

    map.on('click', function(e) {
        if(marker) map.removeLayer(marker);
        marker = L.marker(e.latlng).addTo(map);
        document.getElementById('lat').value = e.latlng.lat;
        document.getElementById('lng').value = e.latlng.lng;
        
        // --- API DE DIRECCIÓN (NOMINATIM) ---
        fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${e.latlng.lat}&lon=${e.latlng.lng}`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('direccion_text').value = data.display_name || "Ubicación detectada";
        });
    });

    function toggleLegalFiltros(val) {
        const tipoPub = document.getElementById('tipo_pub');
        const precioInp = document.getElementById('precio_input');
        const recetaSec = document.getElementById('receta_section');

        if(val === 'Sangre') {
            tipoPub.value = 'Donacion';
            tipoPub.disabled = true;
            precioInp.value = 0;
            precioInp.disabled = true;
            recetaSec.classList.add('hidden');
        } else if(val === 'Medicamento') {
            tipoPub.disabled = false;
            precioInp.disabled = false;
            recetaSec.classList.remove('hidden');
        } else {
            tipoPub.disabled = false;
            precioInp.disabled = false;
            recetaSec.classList.add('hidden');
        }
    }
</script>
{% endblock %}
"""

soporte_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-5xl mx-auto py-16 px-4">
    <div class="text-center mb-16">
        <h2 class="text-5xl font-black text-slate-900 mb-6">Modelo y Legalidad</h2>
        <p class="text-slate-500 max-w-2xl mx-auto">LifeLink no es solo una página, es un ecosistema regulado por TechPulse para garantizar seguridad médica.</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
        <div class="bg-white p-10 rounded-[2.5rem] shadow-xl border border-slate-50">
            <h3 class="text-2xl font-black text-slate-800 mb-6 flex items-center gap-2">
                <i class="fas fa-coins text-amber-500"></i> ¿Cómo ganamos dinero?
            </h3>
            <ul class="space-y-4 text-sm text-slate-600">
                <li class="flex items-start gap-3"><i class="fas fa-check text-emerald-500 mt-1"></i> <b>Cuentas Premium:</b> Hospitales y farmacias pagan suscripción para aparecer como "Verificados".</li>
                <li class="flex items-start gap-3"><i class="fas fa-check text-emerald-500 mt-1"></i> <b>Comisión de Enlace:</b> Por cada venta de equipo ortopédico, LifeLink retiene el 5% para mantenimiento.</li>
                <li class="flex items-start gap-3"><i class="fas fa-check text-emerald-500 mt-1"></i> <b>Logística:</b> Alianzas con servicios de paquetería médica especializada.</li>
            </ul>
        </div>

        <div class="bg-slate-900 p-10 rounded-[2.5rem] shadow-xl text-white">
            <h3 class="text-2xl font-black mb-6 flex items-center gap-2">
                <i class="fas fa-scale-balanced text-brand"></i> Cumplimiento Legal
            </h3>
            <div class="space-y-6 text-xs text-slate-400 leading-relaxed">
                <p><b>PROHIBICIÓN:</b> La Ley General de Salud prohíbe la comercialización de órganos, tejidos y sangre. LifeLink bloquea cualquier intento de venta en estas categorías.</p>
                <p><b>RECETAS:</b> Para medicamentos controlados, el sistema exige una receta digital que es validada por nuestro equipo de soporte antes de publicar.</p>
                <p><b>VERIFICACIÓN:</b> Contamos con un sistema de reportes para dar de baja a usuarios que intenten vender productos ilegales o caducos.</p>
            </div>
        </div>
    </div>

    <div class="mt-20 bg-white p-10 rounded-[2.5rem] shadow-2xl border border-blue-50">
        <h3 class="text-3xl font-black text-slate-900 mb-8 text-center">Hablar con Soporte Humano</h3>
        <form action="{{ url_for('enviar_soporte') }}" method="POST" class="max-w-2xl mx-auto space-y-4">
            <input name="asunto" placeholder="¿En qué podemos ayudarte?" required class="w-full p-4 bg-slate-50 rounded-2xl outline-none border-none">
            <textarea name="mensaje" placeholder="Describe tu situación..." rows="4" required class="w-full p-4 bg-slate-50 rounded-2xl outline-none border-none"></textarea>
            <button class="w-full btn-medical py-5 rounded-2xl font-black shadow-lg">Enviar a Revisión</button>
        </form>
    </div>
</div>
{% endblock %}
"""

# ==========================================
# 2. CONFIGURACIÓN APP Y MODELOS (PERSISTENCIA)
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
    receta_url = db.Column(db.String(500)) # NUEVO: Para medicamentos
    direccion_exacta = db.Column(db.String(500)) # NUEVO: Dirección de Nominatim
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
    usuario = db.relationship('Usuario', backref='tickets')

# Loader de Plantillas
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'register.html': register_template,
    'soporte.html': soporte_template,
    'publish.html': publish_template,
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-20 px-4"><div class="bg-white p-10 rounded-[2.5rem] shadow-2xl border border-slate-100"><h2 class="text-3xl font-black mb-8 text-center text-slate-800">Bienvenido</h2><form method="POST" class="space-y-4"><input name="email" type="email" placeholder="Email" required class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-brand"><input name="password" type="password" placeholder="Pass" required class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-brand"><button class="w-full btn-medical py-5 rounded-2xl font-black shadow-xl mt-4 transition-all">Ingresar</button></form></div></div>{% endblock %}""",
    'search.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-10 px-4"><div class="flex flex-col lg:flex-row gap-10"><div class="lg:w-80"><div class="bg-white p-8 rounded-[2rem] shadow-sm border border-slate-100 sticky top-24"><h4 class="font-black text-slate-900 mb-6 uppercase tracking-widest text-xs">Buscador Inteligente</h4><form method="GET"><input name="q" placeholder="Ej: Sangre O+..." class="w-full p-3 bg-slate-50 border-none rounded-xl text-sm mb-4 outline-none focus:ring-2 focus:ring-brand"><button class="w-full btn-medical py-3 rounded-xl text-sm font-bold shadow-md">Buscar Ahora</button></form></div></div><div class="flex-1 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">{% for item in resultados %}<div class="bg-white rounded-[2rem] shadow-sm border border-slate-100 overflow-hidden hover:shadow-2xl transition-all group">{% if item.receta_url %}<div class="absolute z-20 top-2 left-2 bg-red-500 text-white text-[8px] px-2 py-1 rounded-full font-bold">RECETA REQUERIDA</div>{% endif %}<img src="{{ item.imagen_url }}" class="w-full h-56 object-cover group-hover:scale-105 transition-transform duration-500"><div class="p-6"><h3 class="font-black text-slate-800 text-xl">{{ item.nombre }}</h3><p class="text-[10px] text-brand font-bold uppercase mb-4 tracking-tighter">{{ item.categoria }}</p><div class="flex justify-between items-center"><span class="text-2xl font-black text-slate-900">{% if item.tipo_publicacion == 'Venta' %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span><a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="w-12 h-12 bg-blue-50 text-brand rounded-2xl flex items-center justify-center hover:bg-brand hover:text-white transition-colors"><i class="fas fa-chevron-right"></i></a></div><p class="text-[9px] text-slate-400 mt-4"><i class="fas fa-location-dot"></i> {{ item.direccion_exacta[:40] }}...</p></div></div>{% endfor %}</div></div></div>{% endblock %}""",
    'dashboard.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-12 px-4"><div class="flex justify-between items-end mb-12"><h1 class="text-5xl font-black text-slate-900 tracking-tighter">Bienvenido, <span class="text-brand">{{ current_user.nombre.split()[0] }}</span></h1></div><div class="grid grid-cols-1 lg:grid-cols-3 gap-10">{% if current_user.email == 'admin@lifelink.com' %}<div class="lg:col-span-3 bg-red-50 p-10 rounded-[2.5rem] border border-red-100 shadow-sm"><h3 class="text-2xl font-black text-red-700 mb-6 flex items-center gap-2"><i class="fas fa-shield-halved"></i> Panel Administrativo TechPulse</h3><div class="grid grid-cols-1 md:grid-cols-2 gap-6">{% for ticket in tickets_admin %}<div class="bg-white p-6 rounded-3xl shadow-sm"><div><p class="text-[10px] font-black text-red-400 uppercase mb-1">DE: {{ ticket.usuario.nombre }}</p><h5 class="font-black text-slate-800 mb-2">{{ ticket.asunto }}</h5><p class="text-xs text-slate-500 mb-4">{{ ticket.mensaje }}</p></div><a href="mailto:{{ ticket.usuario.email }}" class="bg-brand text-white px-4 py-2 rounded-xl text-xs font-bold">Responder</a></div>{% else %}<p class="text-red-400 italic">No hay mensajes.</p>{% endfor %}</div></div>{% endif %}<div class="lg:col-span-2 space-y-8"><h4 class="text-xs font-black text-slate-400 uppercase tracking-widest">Coordinación en Curso</h4>{% for s in solicitudes_recibidas %}<div class="bg-white p-8 rounded-[2rem] shadow-sm flex justify-between items-center"><div><h5 class="font-black text-slate-800 text-xl">{{ s.publicacion.nombre }}</h5><p class="text-xs text-slate-400">Solicitado por: {{ s.solicitante.nombre }}</p></div><a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="btn-medical px-6 py-3 rounded-2xl font-black text-sm">Abrir Chat</a></div>{% endfor %}</div></div></div>{% endblock %}""",
    'chat.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-8 px-4 h-[75vh] flex flex-col"><div class="bg-white rounded-[2.5rem] shadow-2xl flex flex-col flex-1 overflow-hidden border border-slate-100"><div class="bg-brand p-6 text-white flex justify-between items-center"><div class="flex items-center gap-4"><div><h3 class="font-black leading-none italic">LifeLink Secure Line</h3></div></div><a href="{{ url_for('dashboard') }}"><i class="fas fa-times text-xl"></i></a></div><div class="flex-1 overflow-y-auto p-8 space-y-6 bg-slate-50/50" id="chat-box"></div><div class="p-6 bg-white border-t border-slate-100"><form onsubmit="event.preventDefault(); send();" class="flex gap-4"><input id="msg-input" placeholder="Escribe aquí..." class="flex-1 p-4 bg-slate-100 rounded-2xl border-none outline-none focus:ring-2 focus:ring-brand"><button class="bg-brand text-white w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg"><i class="fas fa-paper-plane"></i></button></form></div></div></div><script>const socket = io(); const room = "{{ solicitud.id_solicitud }}"; const user = "{{ current_user.nombre }}"; socket.emit('join', {room: room}); socket.on('nuevo_mensaje', function(data){ const box = document.getElementById('chat-box'); const isMe = data.user === user; const d = document.createElement('div'); d.className = `flex ${isMe ? 'justify-end':'justify-start'}`; d.innerHTML = `<div class="${isMe?'bg-brand text-white rounded-l-[1.5rem] rounded-tr-[1.5rem] shadow-brand/20 shadow-md':'bg-white text-slate-700 rounded-r-[1.5rem] rounded-tl-[1.5rem] shadow-sm border border-slate-200'} px-6 py-3 max-w-[85%] animate-in fade-in slide-in-from-bottom-2"><p class="text-[10px] font-black uppercase mb-1 ${isMe?'text-blue-100':'text-slate-400'}">${data.user}</p><p class="text-sm font-medium leading-relaxed">${data.msg}</p></div>`; box.appendChild(d); box.scrollTop = box.scrollHeight; }); function send(){ const i = document.getElementById('msg-input'); if(i.value.trim()){ socket.emit('enviar_mensaje', {msg: i.value, room: room}); i.value=''; } }</script>{% endblock %}""",
    'checkout.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-20 px-4 text-center"><div class="bg-white p-12 rounded-[2.5rem] shadow-2xl border border-slate-50"><h2 class="text-3xl font-black mb-8">Confirmar Pedido</h2><div class="bg-slate-50 p-6 rounded-3xl mb-8"><img src="{{ pub.imagen_url }}" class="w-48 h-48 rounded-[2rem] object-cover mx-auto mb-4"><h3 class="font-black">{{ pub.nombre }}</h3><p class="text-xs font-bold text-brand italic">Entrega en: {{ pub.direccion_exacta }}</p></div><form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST"><button class="w-full btn-medical py-5 rounded-[2rem] font-black text-2xl shadow-xl">Confirmar Solicitud</button></form></div></div>{% endblock %}""",
    'register.html': register_template,
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-20 px-4 text-center"><div class="w-32 h-32 bg-brand text-white text-5xl font-black rounded-[2.5rem] flex items-center justify-center mx-auto mb-6 shadow-2xl border-8 border-white">{{ current_user.nombre[0] | upper }}</div><h2 class="text-4xl font-black text-slate-800">{{ current_user.nombre }}</h2><p class="text-brand font-black uppercase tracking-widest text-xs mb-10">{{ current_user.tipo_sangre }} | {{ current_user.email }}</p><div class="grid grid-cols-2 gap-4 text-left"><div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-100"><p class="text-xs text-slate-400 font-black mb-1">WhatsApp</p><p class="font-black text-slate-800">{{ current_user.telefono }}</p></div><div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-100"><p class="text-xs text-slate-400 font-black mb-1">Ciudad</p><p class="font-black text-slate-800">{{ current_user.ubicacion }}</p></div></div><div class="mt-16"><a href="{{ url_for('logout') }}" class="text-red-500 font-black text-sm uppercase underline">Cerrar Sesión</a></div></div>{% endblock %}"""
})

# ==========================================
# 3. RUTAS Y LÓGICA (ADMIN Y VERIFICACIÓN)
# ==========================================
@login_manager.user_loader
def load_user(user_id): return Usuario.query.get(int(user_id))

@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if Usuario.query.filter_by(email=request.form['email']).first():
            flash("Email ya registrado.", "error")
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
        flash("Datos incorrectos.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        img = request.files.get('imagen')
        rect = request.files.get('receta')
        img_url = "https://via.placeholder.com/400"
        rect_url = None
        
        if img:
            res = cloudinary.uploader.upload(img)
            img_url = res['secure_url']
        if rect:
            res_rect = cloudinary.uploader.upload(rect)
            rect_url = res_rect['secure_url']
        
        p = Publicacion(
            id_proveedor=current_user.id_usuario,
            nombre=request.form['nombre'],
            categoria=request.form['categoria'],
            tipo_publicacion=request.form['tipo_publicacion'],
            precio=float(request.form.get('precio', 0) or 0),
            imagen_url=img_url,
            receta_url=rect_url,
            direccion_exacta=request.form.get('direccion_manual', 'Ubicación Desconocida'),
            latitud=float(request.form.get('lat', 19.4326)),
            longitud=float(request.form.get('lng', -99.1332))
        )
        db.session.add(p)
        db.session.commit()
        flash("Publicación guardada y verificada.", "success")
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
    flash("Solicitud procesada con éxito.", "success")
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
    flash("Ticket de soporte enviado. Revisaremos tu caso pronto.", "success")
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
                ubicacion="Centro de Datos TechPulse"
            )
            db.session.add(admin)
            db.session.commit()
    socketio.run(app, debug=False)
