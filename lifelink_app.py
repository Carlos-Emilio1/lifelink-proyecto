import eventlet
# Parcheo obligatorio en la primera línea para estabilidad de WebSockets en Render
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
# 1. DEFINICIÓN DE PLANTILLAS (ORDENADAS)
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
        .btn-medical:hover { background-color: var(--brand-dark); transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(14, 165, 233, 0.3); }
        #map { height: 350px; width: 100%; border-radius: 1.5rem; z-index: 10; border: 2px solid #f1f5f9; }
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
        .animate-float { animation: float 6s ease-in-out infinite; }
        @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-20px); } 100% { transform: translateY(0px); } }
    </style>
</head>
<body class="bg-[#F8FAFC] flex flex-col min-h-screen font-sans text-slate-900">
    <nav class="bg-white/80 backdrop-blur-md border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-20">
                <div class="flex items-center gap-10">
                    <a href="/" class="flex items-center gap-2">
                        <div class="bg-brand p-2 rounded-xl shadow-lg">
                             <svg width="24" height="24" viewBox="0 0 100 100" fill="none" stroke="white" stroke-width="10">
                                <path d="M10 50 L30 50 L40 20 L60 80 L70 50 L90 50" stroke-linecap="round" stroke-linejoin="round"/>
                             </svg>
                        </div>
                        <span class="font-black text-2xl tracking-tighter text-slate-800 uppercase italic">LifeLink</span>
                    </a>
                    <div class="hidden md:flex gap-8">
                        <a href="{{ url_for('buscar') }}" class="text-[10px] font-black text-slate-400 hover:text-brand transition uppercase tracking-[0.2em]">Explorar Red</a>
                        {% if current_user.is_authenticated %}
                        <a href="{{ url_for('publicar') }}" class="text-[10px] font-black text-slate-400 hover:text-brand transition uppercase tracking-[0.2em]">Publicar</a>
                        <a href="{{ url_for('dashboard') }}" class="text-[10px] font-black text-slate-400 hover:text-brand transition uppercase tracking-[0.2em]">Gestión</a>
                        {% endif %}
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    {% if current_user.is_authenticated %}
                        <div class="flex items-center gap-4 bg-slate-50 p-1.5 pr-5 rounded-2xl border border-slate-100 shadow-sm">
                            <a href="{{ url_for('perfil') }}" class="w-10 h-10 rounded-xl bg-brand text-white flex items-center justify-center font-black shadow-md">{{ current_user.nombre[0] | upper }}</a>
                            <div class="hidden sm:block">
                                <p class="text-[10px] font-black text-slate-800 leading-none">{{ current_user.nombre.split()[0] }}</p>
                                <p class="text-[8px] font-bold text-brand uppercase">Nodo Verificado</p>
                            </div>
                        </div>
                    {% else %}
                        <a href="{{ url_for('login') }}" class="text-xs font-black text-slate-400 uppercase tracking-widest">Entrar</a>
                        <a href="{{ url_for('registro') }}" class="btn-medical px-8 py-3 text-xs font-black uppercase tracking-widest shadow-lg">Unirse</a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>
    <main class="flex-grow">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="max-w-4xl mx-auto mt-6 px-4">
                <div class="p-5 rounded-2xl {% if category == 'error' %}bg-red-50 text-red-700 border-red-100{% else %}bg-emerald-50 text-emerald-700 border-emerald-100{% endif %} flex items-center gap-4 shadow-xl border animate-in slide-in-from-top-4">
                  <i class="fas fa-info-circle text-xl"></i>
                  <span class="text-xs font-black uppercase tracking-tight">{{ message }}</span>
                </div>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="py-12 bg-white border-t border-slate-100 text-center">
        <p class="text-[9px] text-slate-300 font-black uppercase tracking-[0.4em]">LifeLink • TechPulse Solutions • Proyecto Aula • 5IV7</p>
    </footer>
</body>
</html>
"""

home_template = """
{% extends "base.html" %}
{% block content %}
<div class="relative min-h-[85vh] flex items-center bg-white overflow-hidden">
    <div class="max-w-7xl mx-auto px-4 relative z-10 w-full">
        <div class="lg:grid lg:grid-cols-12 lg:gap-12 items-center">
            <div class="sm:text-center lg:col-span-7 lg:text-left">
                <h1 class="text-7xl font-black text-slate-900 tracking-tighter sm:text-8xl leading-[0.9] mb-10 uppercase italic">
                    CONECTANDO <br><span class="text-brand">VIDAS.</span>
                </h1>
                <p class="text-xl text-slate-400 max-w-lg leading-relaxed mb-12 font-medium italic">
                    Plataforma inteligente de coordinación para la gestión de insumos médicos, medicamentos y donaciones de sangre con validación técnica.
                </p>
                <div class="flex flex-wrap gap-8 sm:justify-center lg:justify-start">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-16 py-6 font-black text-xl shadow-2xl flex items-center gap-4 uppercase italic">
                        <i class="fas fa-satellite-dish"></i> Explorar Red
                    </a>
                </div>
            </div>
            <div class="mt-20 lg:mt-0 lg:col-span-5 flex justify-center">
                <div class="relative w-full max-w-md animate-float">
                    <div class="absolute inset-0 bg-brand rounded-[4rem] rotate-6 opacity-10"></div>
                    <div class="relative bg-white p-6 rounded-[4rem] shadow-2xl border-8 border-slate-50 overflow-hidden">
                        <img class="w-full h-[550px] rounded-[3rem] object-cover" src="https://images.unsplash.com/photo-1516549655169-df83a0774514?q=80&w=1000&auto=format&fit=crop" alt="LifeLink Medical">
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

dashboard_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-7xl mx-auto py-16 px-4">
    <div class="flex flex-col md:flex-row justify-between items-start md:items-end mb-16 gap-10">
        <div>
            <h1 class="text-7xl font-black text-slate-900 tracking-tighter uppercase italic leading-none">Centro <br><span class="text-brand">Operativo.</span></h1>
            <p class="text-[11px] font-black text-slate-400 uppercase tracking-[0.5em] mt-3 italic">ID Nodo: LL-{{ current_user.id_usuario }} | Confianza: {{ current_user.rating_promedio|round(1) }} ★</p>
        </div>
        <a href="{{ url_for('publicar') }}" class="btn-medical px-12 py-5 text-[12px] font-black uppercase tracking-widest shadow-2xl">Nueva Publicación</a>
    </div>

    {% if current_user.email == 'admin@lifelink.com' %}
    <div class="mb-24 bg-slate-900 p-16 rounded-[5rem] text-white shadow-2xl relative overflow-hidden font-black">
        <h3 class="text-3xl font-black mb-12 italic uppercase tracking-tighter leading-none italic"><i class="fas fa-shield-halved text-brand"></i> Panel de Auditoría <br>TechPulse Solutions</h3>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-10 mb-16 uppercase">
            <div class="bg-white/5 p-8 rounded-3xl border border-white/10 text-center shadow-inner">
                <p class="text-5xl font-black text-brand mb-2">{{ stats.total_usuarios }}</p>
                <p class="text-[10px] text-slate-500 tracking-widest">Nodos Activos</p>
            </div>
            <div class="bg-white/5 p-8 rounded-3xl border border-white/10 text-center shadow-inner">
                <p class="text-5xl font-black text-emerald-400 mb-2">{{ stats.total_publicaciones }}</p>
                <p class="text-[10px] text-slate-500 tracking-widest">Recursos en Red</p>
            </div>
            <div class="bg-white/5 p-8 rounded-3xl border border-white/10 text-center shadow-inner">
                <p class="text-5xl font-black text-amber-400 mb-2">{{ stats.total_tickets }}</p>
                <p class="text-[10px] text-slate-500 tracking-widest">Reportes Legales</p>
            </div>
        </div>
    </div>
    {% endif %}

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-16 uppercase italic font-black">
        <div class="lg:col-span-2 space-y-16">
             <h4 class="text-[11px] text-slate-300 tracking-[0.5em] italic">Canales de Coordinación Activos</h4>
             <div class="grid gap-10">
                {% for s in solicitudes_recibidas %}
                <div class="bg-white p-12 rounded-[5rem] border border-slate-100 shadow-xl flex flex-col md:flex-row justify-between items-center group relative overflow-hidden">
                    <div class="relative z-10">
                        <span class="text-[10px] font-black bg-blue-50 text-brand px-5 py-2 rounded-full uppercase italic border border-blue-100 shadow-sm">{{ s.estatus }}</span>
                        <h5 class="font-black text-slate-800 text-5xl tracking-tighter uppercase italic leading-none my-6 italic">{{ s.publicacion.nombre }}</h5>
                        <p class="text-xs text-slate-400 font-bold tracking-[0.2em] italic">SOLICITANTE: {{ s.solicitante.nombre }}</p>
                    </div>
                    <a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="btn-medical px-12 py-6 text-[12px] tracking-widest shadow-2xl shadow-blue-200 italic">Entrar al Chat</a>
                </div>
                {% else %}
                <div class="p-20 text-center bg-white rounded-[4rem] border-4 border-dashed border-slate-50">
                    <p class="text-slate-300 font-black text-xs tracking-[0.3em]">Sin transferencias activas</p>
                </div>
                {% endfor %}
             </div>
        </div>

        <div class="space-y-12">
            <h4 class="text-[11px] text-slate-300 tracking-[0.5em] text-center italic">Mi Inventario de Nodo</h4>
            <div class="grid gap-6">
                {% for p in publicaciones %}
                <div class="bg-white p-8 rounded-[3.5rem] border border-slate-100 shadow-xl relative overflow-hidden group">
                    <div class="flex items-center gap-6">
                        <img src="{{ p.imagen_url }}" class="w-20 h-20 rounded-[2.2rem] object-cover shadow-inner group-hover:scale-110 transition-all">
                        <div class="flex-1 min-w-0">
                            <p class="text-[11px] font-black text-slate-800 truncate mb-2 uppercase italic tracking-tighter">{{ p.nombre }}</p>
                            <span class="text-[8px] font-black uppercase text-emerald-500 bg-emerald-50 px-4 py-1.5 rounded-xl tracking-widest border border-emerald-100">Verificado</span>
                        </div>
                        <form action="{{ url_for('borrar_publicacion', id=p.id_oferta_insumo) }}" method="POST">
                            <button class="p-4 text-slate-200 hover:text-red-500 hover:bg-red-50 rounded-[1.5rem] transition-all"><i class="fas fa-trash-can text-lg"></i></button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

publish_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-5xl mx-auto py-12 px-4 uppercase italic font-black">
    <div class="bg-white rounded-[4.5rem] shadow-2xl p-16 border border-slate-50 shadow-blue-50/50">
        <h2 class="text-5xl font-black text-slate-900 mb-4 tracking-tighter italic leading-none italic italic">Nodo de <br><span class="text-brand">Publicación Oficial.</span></h2>
        <p class="text-[11px] font-black text-slate-300 uppercase tracking-[0.5em] mb-16 italic italic">TechPulse audit system enabled</p>
        
        <form method="POST" enctype="multipart/form-data" class="space-y-16">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-16">
                <div>
                    <label class="block text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-6 italic">Evidencia Gráfica (Real)</label>
                    <div class="p-20 border-4 border-dashed border-slate-100 rounded-[4rem] text-center bg-slate-50/50 hover:border-brand transition-all cursor-pointer shadow-inner relative overflow-hidden group">
                        <i class="fas fa-fingerprint text-6xl text-slate-200 group-hover:text-brand transition-colors mb-6"></i>
                        <input type="file" name="imagen" accept="image/*" required class="text-[10px] text-slate-400 font-black w-full relative z-10 italic">
                    </div>
                </div>

                <div class="space-y-10">
                    <div>
                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-3 italic">Denominación del Recurso</label>
                        <input name="nombre" placeholder="Bolsa de Sangre O-" required class="w-full p-6 bg-slate-50 rounded-[2rem] border-none font-black text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-tighter italic">
                    </div>
                    
                    <div class="grid grid-cols-2 gap-6 italic">
                        <div>
                            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-3 italic">Especialidad</label>
                            <select name="categoria" class="w-full p-6 bg-slate-50 rounded-[1.5rem] border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner italic">
                                <option value="Equipo">Insumo Médico</option>
                                <option value="Medicamento">Farmacéutico</option>
                                <option value="Sangre">Hemoderivado</option>
                                <option value="Ortopedico">Ortopédico</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-3 italic">Costo de Recuperación</label>
                            <input name="precio" type="number" placeholder="0.00" class="w-full p-6 bg-slate-50 rounded-[1.5rem] border-none font-black text-xs shadow-inner italic">
                        </div>
                    </div>

                    <div>
                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-3 italic">Tipo de Publicación</label>
                        <select name="tipo_publicacion" class="w-full p-6 bg-slate-50 rounded-[1.5rem] border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner italic">
                            <option value="Venta">Venta Certificada</option>
                            <option value="Donacion">Donación Altruista</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="space-y-8">
                <div id="map" class="shadow-2xl italic"></div>
                <div class="bg-blue-50 p-8 rounded-[3rem] border border-blue-100 flex items-center gap-6 shadow-inner text-brand italic italic">
                    <i class="fas fa-location-crosshairs animate-pulse text-2xl"></i>
                    <input type="text" id="direccion_text" name="direccion_manual" readonly placeholder="Detectando geolocalización de transferencia..." class="bg-transparent w-full outline-none text-[12px] font-black uppercase tracking-widest italic italic">
                </div>
                <input type="hidden" id="lat" name="lat"><input type="hidden" id="lng" name="lng">
            </div>

            <button type="submit" class="w-full btn-medical py-8 rounded-[3.5rem] font-black text-4xl shadow-2xl shadow-blue-200 italic uppercase hover:scale-[1.01] transition-all italic italic">Certificar Recurso</button>
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
        fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${e.latlng.lat}&lon=${e.latlng.lng}`).then(r => r.json()).then(d => { 
            document.getElementById('direccion_text').value = d.display_name; 
        }); 
    });
</script>
{% endblock %}
"""

# ==========================================
# 2. LÓGICA DE SERVIDOR Y MODELOS (SISTEMA BLINDADO)
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lifelink_2026_ultimate_safe_protocol_v5iv7')
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///lifelink_master.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# MODELOS CON NOMBRES NUEVOS PARA RESETEAR LA DB EN RENDER AUTOMÁTICAMENTE
class Usuario(UserMixin, db.Model):
    __tablename__ = 'users_master' 
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
    __tablename__ = 'items_master'
    id_oferta_insumo = db.Column(db.Integer, primary_key=True)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('users_master.id_usuario'))
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    tipo_publicacion = db.Column(db.String(50))
    precio = db.Column(db.Float, default=0.0)
    imagen_url = db.Column(db.String(500))
    estado = db.Column(db.String(20), default='Verificado') 
    proveedor = db.relationship('Usuario', backref='publicaciones')

class Solicitud(db.Model):
    __tablename__ = 'orders_master'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('users_master.id_usuario'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('items_master.id_oferta_insumo'))
    estatus = db.Column(db.String(50), default='En Coordinación') 
    solicitante = db.relationship('Usuario', backref='solicitudes_enviadas')
    publicacion = db.relationship('Publicacion', backref='solicitudes_recibidas')

# Cargador de Plantillas
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'dashboard.html': dashboard_template,
    'publish.html': publish_template,
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-24 px-4 text-center italic font-black uppercase"><div class="bg-white p-12 rounded-[3.5rem] shadow-2xl border border-slate-100 italic"><h2 class="text-4xl font-black mb-10 tracking-tighter italic">Entrar al <br><span class="text-brand">Nodo.</span></h2><form method="POST" class="space-y-6 italic"><input name="email" type="email" placeholder="Correo Electrónico" required class="w-full p-6 bg-slate-50 rounded-2xl border-none outline-none font-black text-xs shadow-inner italic"><input name="password" type="password" placeholder="Contraseña" required class="w-full p-6 bg-slate-50 rounded-2xl border-none outline-none font-black text-xs shadow-inner italic"><button class="w-full btn-medical py-6 rounded-[2.5rem] font-black text-2xl mt-8 shadow-2xl shadow-blue-200 uppercase tracking-tighter italic italic">Ingresar</button></form></div></div>{% endblock %}""",
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-16 px-4 uppercase italic font-black italic"><div class="bg-white p-16 rounded-[4rem] shadow-2xl border border-slate-50 italic italic"><h2 class="text-4xl font-black text-slate-900 mb-10 tracking-tighter italic italic">Cédula de <span class="text-brand italic italic">Registro.</span></h2><form method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-6 italic italic"><input name="nombre" placeholder="Nombre completo" required class="col-span-1 md:col-span-2 p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase italic italic"><select name="tipo_sangre" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner italic italic"><option value="">TIPO SANGRE</option><option>O+</option><option>O-</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option></select><input name="telefono" placeholder="WhatsApp" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase italic"><input name="email" type="email" placeholder="Correo" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase italic"><input name="ubicacion" placeholder="Ciudad" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase italic"><input name="password" type="password" placeholder="Contraseña" required class="col-span-1 md:col-span-2 p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-widest italic italic"><button class="col-span-1 md:col-span-2 w-full btn-medical py-6 rounded-[3rem] font-black text-2xl mt-8 shadow-2xl shadow-blue-100 italic uppercase italic italic">Activar Nodo</button></form></div></div>{% endblock %}""",
    'search.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-16 px-4 italic font-black uppercase italic"><h2 class="text-5xl font-black text-slate-900 mb-12 tracking-tighter uppercase italic italic">Red Médica de <span class="text-brand">Insumos.</span></h2><div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-12 italic italic">{% for item in resultados %}<div class="bg-white rounded-[3.5rem] border border-slate-100 shadow-sm overflow-hidden hover:shadow-2xl transition-all duration-700 group relative italic italic"><img src="{{ item.imagen_url }}" class="w-full h-72 object-cover group-hover:scale-110 transition-transform duration-1000 shadow-inner grayscale group-hover:grayscale-0 italic"><div class="p-10 italic italic"><h3 class="font-black text-slate-800 text-3xl tracking-tighter uppercase italic mb-1 italic">{{ item.nombre }}</h3><p class="text-[10px] text-brand font-black uppercase tracking-[0.1em] mb-8 italic italic">{{ item.categoria }}</p><div class="flex justify-between items-center italic italic"><span class="text-4xl font-black text-slate-900 tracking-tighter italic italic">{% if item.precio > 0 %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span><a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="w-16 h-16 bg-blue-50 text-brand rounded-[2rem] flex items-center justify-center hover:bg-brand hover:text-white transition-all shadow-xl shadow-blue-50 shadow-inner italic italic italic"><i class="fas fa-arrow-right text-xl italic italic"></i></a></div></div></div>{% else %}<div class="col-span-full py-32 text-center italic italic"><p class="text-slate-300 font-black text-3xl tracking-[0.2em] italic">Sin recursos en red</p></div>{% endfor %}</div></div>{% endblock %}""",
    'checkout.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-24 px-4 text-center uppercase italic font-black italic"><div class="bg-white p-16 rounded-[5rem] shadow-2xl border border-slate-100 italic italic"><h2 class="text-5xl font-black mb-12 tracking-tighter italic">Solicitud <br><span class="text-brand">Auditada.</span></h2><div class="bg-slate-50 p-12 rounded-[4rem] mb-12 border border-slate-100 shadow-inner italic italic"><img src="{{ pub.imagen_url }}" class="w-56 h-56 rounded-[3rem] object-cover mx-auto mb-10 shadow-2xl ring-[15px] ring-white italic italic"><h3 class="font-black text-3xl text-slate-800 uppercase italic italic">{{ pub.nombre }}</h3><p class="text-[11px] font-black text-brand uppercase tracking-[0.3em] mt-2 italic italic">VERIFICACIÓN TECHPULSE SOLUTIONS</p></div><form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST" class="italic italic"><button class="w-full btn-medical py-8 rounded-[3.5rem] font-black text-4xl shadow-2xl shadow-blue-200 hover:scale-105 transition-all uppercase italic italic italic">Certificar Compromiso</button></form></div></div>{% endblock %}""",
    'chat.html': """{% extends "base.html" %}{% block content %}<div class="max-w-4xl mx-auto py-8 px-4 h-[80vh] flex flex-col uppercase italic font-black italic"><div class="bg-white rounded-[4rem] shadow-2xl flex flex-col flex-1 overflow-hidden border border-slate-100 shadow-blue-50/50 italic italic"><div class="bg-brand p-10 text-white flex justify-between items-center shadow-lg relative z-10 italic italic"><h3 class="font-black text-2xl italic uppercase italic italic">Línea de Coordinación</h3><a href="{{ url_for('dashboard') }}" class="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center hover:bg-white/20 transition-all italic italic"><i class="fas fa-times text-xl italic italic"></i></a></div><div class="flex-1 overflow-y-auto p-12 space-y-10 bg-slate-50/50 custom-scrollbar italic italic italic italic" id="chat-box"></div><div class="p-10 bg-white border-t border-slate-100 italic italic"><form onsubmit="event.preventDefault(); send();" class="flex gap-6 italic italic"><input id="msg-input" placeholder="Coordina entrega..." class="flex-1 p-6 bg-slate-100 rounded-[2.5rem] border-none outline-none font-black text-sm shadow-inner uppercase tracking-tighter italic italic italic"><button class="bg-brand text-white w-20 h-20 rounded-[2.5rem] shadow-2xl shadow-blue-200 hover:scale-110 transition-transform flex items-center justify-center italic italic italic"><i class="fas fa-paper-plane text-2xl italic italic"></i></button></form></div></div></div><script>const socket = io(); const room = "{{ solicitud.id_solicitud }}"; const user = "{{ current_user.nombre }}"; socket.emit('join', {room: room}); socket.on('nuevo_mensaje', function(data){ const box = document.getElementById('chat-box'); const isMe = data.user === user; const d = document.createElement('div'); d.className = `flex ${isMe ? 'justify-end':'justify-start'}`; d.innerHTML = `<div class="${isMe?'bg-brand text-white rounded-l-[2rem] rounded-tr-[2rem] shadow-2xl shadow-blue-100':'bg-white text-slate-700 rounded-r-[2rem] rounded-tl-[2rem] shadow-sm border border-slate-200'} px-8 py-5 max-w-[85%] italic italic"><p class="text-[9px] font-black uppercase mb-3 ${isMe?'text-blue-100':'text-slate-300'} tracking-widest italic italic italic">${data.user}</p><p class="text-sm font-black leading-relaxed tracking-tight uppercase italic italic italic italic italic">${data.msg}</p></div>`; box.appendChild(d); box.scrollTop = box.scrollHeight; }); function send(){ const i = document.getElementById('msg-input'); if(i.value.trim()){ socket.emit('enviar_mensaje', {msg: i.value, room: room}); i.value=''; } }</script>{% endblock %}""",
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-20 px-4 text-center uppercase italic font-black italic italic italic"><div class="relative inline-block mb-12 italic italic italic italic"><div class="w-48 h-48 bg-brand text-white text-8xl font-black rounded-[4rem] flex items-center justify-center mx-auto shadow-2xl border-[12px] border-white ring-2 ring-slate-100 italic shadow-blue-100 italic italic italic italic italic">{{ current_user.nombre[0] | upper }}</div><div class="absolute -bottom-2 -right-2 bg-emerald-500 w-14 h-14 rounded-2xl flex items-center justify-center text-white border-4 border-white shadow-xl rotate-12 italic italic italic"><i class="fas fa-certificate text-xl italic italic italic"></i></div></div><h2 class="text-6xl font-black text-slate-900 mb-2 tracking-tighter uppercase italic leading-none italic italic italic italic italic">{{ current_user.nombre }}</h2><p class="text-brand font-black uppercase tracking-[0.4em] text-[10px] mb-16 italic italic italic italic italic">Nodo Verificado {{ current_user.tipo_sangre }}</p><div class="grid grid-cols-1 md:grid-cols-2 gap-8 text-left italic italic italic italic">{% for label, icon, val in [('WhatsApp', 'fa-mobile-screen', current_user.telefono), ('Email', 'fa-envelope-open', current_user.email)] %}<div class="bg-white p-10 rounded-[3rem] shadow-sm border border-slate-100 flex flex-col items-center text-center group hover:border-brand transition-all italic italic italic italic"><i class="fas {{ icon }} text-slate-100 text-3xl mb-5 group-hover:text-brand transition-colors italic italic italic italic"></i><p class="text-[9px] text-slate-300 font-black uppercase mb-2 tracking-[0.2em] italic italic italic italic italic italic">{{ label }}</p><p class="font-black text-slate-800 text-xs break-words tracking-tighter uppercase italic italic italic italic italic">{{ val }}</p></div>{% endfor %}</div><div class="mt-24 italic italic italic italic"><a href="{{ url_for('logout') }}" class="text-red-300 font-black text-[9px] uppercase tracking-[0.4em] hover:text-red-500 transition-all underline decoration-red-50 font-bold italic italic italic italic italic">Finalizar Sesión</a></div></div>{% endblock %}"""
})

# ==========================================
# 3. RUTAS DE CONTROL (LOGICA COMPLETA)
# ==========================================
@login_manager.user_loader
def load_user(user_id): return Usuario.query.get(int(user_id))

@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if Usuario.query.filter_by(email=request.form['email']).first():
            flash("Identidad ya registrada en TechPulse.", "error")
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
        flash("Acceso denegado.", "error")
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
    stats = {'total_usuarios': Usuario.query.count(), 'total_publicaciones': Publicacion.query.count(), 'total_tickets': 3} if current_user.email == 'admin@lifelink.com' else {}
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols, stats=stats)

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        img = request.files.get('imagen')
        img_url = "https://via.placeholder.com/400"
        if img: img_url = cloudinary.uploader.upload(img)['secure_url']
        p = Publicacion(id_proveedor=current_user.id_usuario, nombre=request.form['nombre'], categoria=request.form['categoria'], precio=float(request.form.get('precio', 0) or 0), imagen_url=img_url)
        db.session.add(p); db.session.commit()
        flash("Recurso publicado con éxito.", "success")
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
    flash("Certificado emitido. Inicie coordinación en chat.", "success")
    return redirect(url_for('dashboard'))

@app.route('/chat/<int:id_solicitud>')
@login_required
def chat(id_solicitud):
    s = Solicitud.query.get_or_404(id_solicitud)
    return render_template('chat.html', solicitud=s)

@app.route('/perfil')
@login_required
def perfil(): return render_template('perfil.html')

@socketio.on('join')
def on_join(data): join_room(data['room'])

@socketio.on('enviar_mensaje')
def handle_msg(data): emit('nuevo_mensaje', {'msg': data['msg'], 'user': current_user.nombre}, room=data['room'])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Usuario.query.filter_by(email='admin@lifelink.com').first():
            db.session.add(Usuario(nombre="Admin TechPulse", email="admin@lifelink.com", password_hash=generate_password_hash("admin123"), telefono="0000000000", tipo_sangre="N/A", ubicacion="HQ Central"))
            db.session.commit()
    socketio.run(app, debug=False)
