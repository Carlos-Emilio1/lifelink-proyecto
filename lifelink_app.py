import eventlet
# Parcheo obligatorio en la línea 1 para estabilidad de WebSockets en Render
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
    <title>LifeLink - Red Médica</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --brand: #0ea5e9; --brand-dark: #0369a1; }
        .bg-brand { background-color: var(--brand); }
        .text-brand { color: var(--brand); }
        .btn-medical { background-color: var(--brand); color: white; transition: all 0.2s; border-radius: 0.75rem; font-weight: 700; text-transform: uppercase; }
        .btn-medical:hover { background-color: var(--brand-dark); transform: translateY(-1px); }
        #map { height: 300px; width: 100%; border-radius: 1rem; z-index: 10; border: 1px solid #e2e8f0; }
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
    </style>
</head>
<body class="bg-slate-50 flex flex-col min-h-screen font-sans text-slate-900 uppercase font-bold italic">
    <nav class="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 h-16 flex justify-between items-center">
            <div class="flex items-center gap-8">
                <a href="/" class="flex items-center gap-2">
                    <div class="bg-brand p-1.5 rounded-lg shadow-sm">
                         <svg width="20" height="20" viewBox="0 0 100 100" fill="none" stroke="white" stroke-width="10">
                            <path d="M10 50 L30 50 L40 20 L60 80 L70 50 L90 50" stroke-linecap="round" stroke-linejoin="round"/>
                         </svg>
                    </div>
                    <span class="font-black text-xl tracking-tighter text-slate-800">LifeLink</span>
                </a>
                <div class="hidden md:flex gap-6">
                    <a href="{{ url_for('buscar') }}" class="text-[10px] text-slate-400 hover:text-brand transition">Explorar</a>
                    {% if current_user.is_authenticated %}
                    <a href="{{ url_for('publicar') }}" class="text-[10px] text-slate-400 hover:text-brand transition">Publicar</a>
                    <a href="{{ url_for('dashboard') }}" class="text-[10px] text-slate-400 hover:text-brand transition">Gestión</a>
                    {% endif %}
                </div>
            </div>
            <div class="flex items-center gap-4">
                {% if current_user.is_authenticated %}
                    <div class="flex items-center gap-3 bg-slate-50 p-1 pr-4 rounded-xl border border-slate-100">
                        <a href="{{ url_for('perfil') }}" class="w-8 h-8 rounded-lg bg-brand text-white flex items-center justify-center font-black text-xs">{{ current_user.nombre[0] | upper }}</a>
                        <span class="text-[9px] font-black text-slate-500 hidden sm:block">{{ current_user.nombre.split()[0] }}</span>
                    </div>
                    <a href="{{ url_for('logout') }}" class="text-[9px] text-red-400 hover:text-red-600 transition">Salir</a>
                {% else %}
                    <a href="{{ url_for('login') }}" class="text-[10px] text-slate-400">Login</a>
                    <a href="{{ url_for('registro') }}" class="btn-medical px-5 py-2 text-[10px] shadow-sm">Unirse</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <main class="flex-grow">
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            {% for message in messages %}
              <div class="max-w-4xl mx-auto mt-4 px-4">
                <div class="p-3 rounded-xl bg-blue-50 text-blue-700 border border-blue-100 text-[10px] flex items-center gap-2 shadow-sm">
                   <i class="fas fa-info-circle"></i> {{ message }}
                </div>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="py-8 bg-white border-t border-slate-100 text-center">
        <p class="text-[8px] text-slate-300 tracking-[0.2em]">LifeLink • TechPulse Solutions • 2026</p>
    </footer>
</body>
</html>
"""

home_template = """
{% extends "base.html" %}
{% block content %}
<div class="relative min-h-[75vh] flex items-center bg-white overflow-hidden">
    <div class="max-w-7xl mx-auto px-4 w-full">
        <div class="lg:grid lg:grid-cols-12 lg:gap-8 items-center">
            <div class="sm:text-center lg:col-span-7 lg:text-left">
                <h1 class="text-5xl font-black text-slate-900 tracking-tighter sm:text-6xl leading-none mb-6">
                    CONECTANDO <br><span class="text-brand">VIDAS.</span>
                </h1>
                <p class="text-lg text-slate-400 max-w-lg leading-relaxed mb-10 font-medium">
                    Plataforma inteligente de coordinación para insumos médicos, medicamentos y donaciones de sangre con validación técnica.
                </p>
                <div class="flex flex-wrap gap-6 sm:justify-center lg:justify-start">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-10 py-4 font-black text-base shadow-xl flex items-center gap-3">
                        <i class="fas fa-satellite-dish"></i> Explorar Red
                    </a>
                </div>
            </div>
            <div class="mt-12 lg:mt-0 lg:col-span-5 flex justify-center">
                <div class="relative w-full max-w-sm">
                    <div class="absolute inset-0 bg-brand rounded-[2.5rem] rotate-3 opacity-10"></div>
                    <div class="relative bg-white p-4 rounded-[2.5rem] shadow-2xl border-4 border-slate-50 overflow-hidden">
                        <img class="w-full h-[400px] rounded-[1.5rem] object-cover" src="https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&q=80&w=1000" alt="LifeLink">
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
<div class="max-w-7xl mx-auto py-12 px-4">
    <div class="flex flex-col md:flex-row justify-between items-start md:items-end mb-12 gap-6">
        <div>
            <h1 class="text-5xl font-black text-slate-900 tracking-tighter leading-none">MI <span class="text-brand">PANEL.</span></h1>
            <p class="text-[9px] font-black text-slate-400 tracking-[0.3em] mt-2">SESIÓN INICIADA: {{ current_user.nombre }}</p>
        </div>
        <a href="{{ url_for('publicar') }}" class="btn-medical px-8 py-3 text-[10px] shadow-lg">Nueva Publicación</a>
    </div>

    {% if stats %}
    <div class="mb-16 bg-slate-900 p-10 rounded-[3rem] text-white shadow-xl">
        <div class="flex items-center justify-between mb-8">
            <h3 class="text-lg font-black italic uppercase"><i class="fas fa-shield-halved text-brand mr-3"></i> Auditoría de Red</h3>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
            <div class="bg-white/5 p-6 rounded-2xl border border-white/10">
                <p class="text-3xl font-black text-brand">{{ stats.total_usuarios }}</p>
                <p class="text-[8px] text-slate-500 mt-1">NODOS ACTIVOS</p>
            </div>
            <div class="bg-white/5 p-6 rounded-2xl border border-white/10">
                <p class="text-3xl font-black text-emerald-400">{{ stats.total_publicaciones }}</p>
                <p class="text-[8px] text-slate-500 mt-1">RECURSOS</p>
            </div>
            <div class="bg-white/5 p-6 rounded-2xl border border-white/10">
                <p class="text-3xl font-black text-amber-400">{{ stats.total_solicitudes }}</p>
                <p class="text-[8px] text-slate-500 mt-1">TRANSFERENCIAS</p>
            </div>
        </div>
    </div>
    {% endif %}

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <div class="lg:col-span-2 space-y-10">
             <h4 class="text-[10px] text-slate-300 tracking-[0.3em]">GESTIÓN DE SOLICITUDES</h4>
             <div class="grid gap-6">
                {% for s in solicitudes_recibidas %}
                <div class="bg-white p-8 rounded-[3rem] border border-slate-100 shadow-md flex flex-col md:flex-row justify-between items-center group">
                    <div class="text-center md:text-left">
                        <span class="text-[8px] font-black bg-blue-50 text-brand px-3 py-1 rounded-full border border-blue-100 uppercase">{{ s.estatus }}</span>
                        <h5 class="font-black text-slate-800 text-2xl tracking-tighter mt-3 uppercase">{{ s.publicacion.nombre }}</h5>
                        <p class="text-[10px] text-slate-400 mt-1">SOLICITANTE: {{ s.solicitante.nombre }}</p>
                    </div>
                    <a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="btn-medical px-8 py-4 text-[10px] mt-4 md:mt-0 shadow-sm">Abrir Coordinación</a>
                </div>
                {% else %}
                <div class="p-16 text-center bg-white rounded-[3rem] border-2 border-dashed border-slate-100">
                    <p class="text-slate-300 text-[10px]">Sin actividad en este nodo</p>
                </div>
                {% endfor %}
             </div>
        </div>

        <div class="space-y-8">
            <h4 class="text-[10px] text-slate-300 tracking-[0.3em] text-center">MI INVENTARIO</h4>
            {% for p in publicaciones %}
            <div class="bg-white p-6 rounded-[2rem] border border-slate-100 shadow-sm flex items-center gap-4">
                <img src="{{ p.imagen_url }}" class="w-16 h-16 rounded-2xl object-cover shadow-inner">
                <div class="flex-1 min-w-0">
                    <p class="text-[10px] font-black text-slate-800 truncate uppercase">{{ p.nombre }}</p>
                    <span class="text-[7px] font-black uppercase text-emerald-500 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-100">Verificado</span>
                </div>
                <form action="{{ url_for('borrar_publicacion', id=p.id_oferta_insumo) }}" method="POST">
                    <button class="p-3 text-slate-300 hover:text-red-500 transition-colors"><i class="fas fa-trash-can"></i></button>
                </form>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
"""

publish_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto py-12 px-4 uppercase font-black">
    <div class="bg-white rounded-[3.5rem] shadow-2xl p-12 border border-slate-50">
        <h2 class="text-4xl font-black text-slate-900 mb-12 tracking-tighter">NUEVA <span class="text-brand">PUBLICACIÓN.</span></h2>
        
        <form method="POST" enctype="multipart/form-data" class="space-y-10">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
                <div class="space-y-6">
                    <div>
                        <label class="block text-[9px] text-slate-400 mb-3 italic">EVIDENCIA FOTOGRÁFICA</label>
                        <div class="p-12 border-2 border-dashed border-slate-200 rounded-[2.5rem] text-center bg-slate-50/50 hover:border-brand transition-all relative">
                            <i class="fas fa-cloud-arrow-up text-3xl text-slate-300 mb-4"></i>
                            <input type="file" name="imagen" accept="image/*" required class="text-[9px] w-full relative z-10 opacity-50">
                        </div>
                    </div>
                    <div>
                        <label class="block text-[9px] text-slate-400 mb-2 italic">NOMBRE DEL RECURSO</label>
                        <input name="nombre" placeholder="EJ: BOLSA SANGRE O-" required class="w-full p-5 bg-slate-50 rounded-2xl border-none font-black text-xs shadow-inner">
                    </div>
                </div>

                <div class="space-y-6">
                    <div>
                        <label class="block text-[9px] text-slate-400 mb-2 italic">ESPECIALIDAD</label>
                        <select name="categoria" class="w-full p-5 bg-slate-50 rounded-2xl border-none font-black text-[10px] shadow-inner">
                            <option value="Sangre">Hemoderivado</option>
                            <option value="Medicamento">Farmacéutico</option>
                            <option value="Equipo">Insumo Médico</option>
                        </select>
                    </div>
                    
                    <div class="grid grid-cols-1 gap-6">
                         <div>
                            <label class="block text-[9px] text-slate-400 mb-2 italic">TIPO DE PUBLICACIÓN</label>
                            <select id="tipo_pub" name="tipo_publicacion" onchange="togglePrice(this.value)" class="w-full p-5 bg-slate-50 rounded-2xl border-none font-black text-[10px] shadow-inner">
                                <option value="Donacion">Donación Altruista</option>
                                <option value="Venta">Venta Certificada</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-[9px] text-slate-400 mb-2 italic">PRECIO (MXN)</label>
                            <input id="input_precio" name="precio" type="number" step="0.01" value="0.00" disabled class="w-full p-5 bg-slate-100 rounded-2xl border-none font-black text-xs shadow-inner opacity-50">
                        </div>
                    </div>
                </div>
            </div>

            <div class="space-y-4">
                <label class="block text-[9px] text-slate-400 italic">UBICACIÓN EXACTA (DA CLIC EN EL MAPA)</label>
                <div id="map" class="shadow-lg"></div>
                <div class="bg-blue-50 p-5 rounded-2xl border border-blue-100">
                    <p class="text-[9px] text-brand mb-1">DIRECCIÓN DETECTADA:</p>
                    <input type="text" id="dir_text" name="direccion_manual" readonly placeholder="Esperando selección en mapa..." class="bg-transparent w-full outline-none text-[10px] font-black uppercase text-slate-600">
                </div>
                <input type="hidden" id="lat" name="lat"><input type="hidden" id="lng" name="lng">
            </div>

            <button type="submit" class="w-full btn-medical py-6 rounded-[2.5rem] font-black text-2xl shadow-xl mt-6">Certificar Recurso</button>
        </form>
    </div>
</div>

<script>
    // Lógica de Precios
    function togglePrice(val) {
        const input = document.getElementById('input_precio');
        if(val === 'Venta') {
            input.disabled = false;
            input.classList.remove('bg-slate-100', 'opacity-50');
            input.classList.add('bg-slate-50');
            input.value = "0.00";
        } else {
            input.disabled = true;
            input.classList.add('bg-slate-100', 'opacity-50');
            input.classList.remove('bg-slate-50');
            input.value = "0.00";
        }
    }

    // Lógica de Mapa
    var map = L.map('map').setView([19.4326, -99.1332], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    var marker;
    map.on('click', function(e) { 
        if(marker) map.removeLayer(marker); 
        marker = L.marker(e.latlng).addTo(map); 
        document.getElementById('lat').value = e.latlng.lat; 
        document.getElementById('lng').value = e.latlng.lng; 
        
        // Consultar Dirección Real
        fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${e.latlng.lat}&lon=${e.latlng.lng}`)
            .then(res => res.json())
            .then(data => {
                document.getElementById('dir_text').value = data.display_name || "Dirección no identificada";
            });
    });
</script>
{% endblock %}
"""

search_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-7xl mx-auto py-16 px-4">
    <h2 class="text-5xl font-black text-slate-900 mb-12 tracking-tighter uppercase leading-none italic">RED MÉDICA <br><span class="text-brand">DE INSUMOS.</span></h2>
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-10">
        {% for item in resultados %}
        <div class="bg-white rounded-[3rem] border border-slate-100 shadow-sm overflow-hidden hover:shadow-xl transition-all duration-500 group relative italic">
            <img src="{{ item.imagen_url }}" class="w-full h-64 object-cover group-hover:scale-110 transition-transform duration-700 grayscale group-hover:grayscale-0">
            <div class="p-8">
                <h3 class="font-black text-slate-800 text-2xl tracking-tighter uppercase mb-1">{{ item.nombre }}</h3>
                <p class="text-[9px] text-brand font-black uppercase tracking-widest mb-6">{{ item.categoria }}</p>
                <div class="flex justify-between items-center">
                    <span class="text-3xl font-black text-slate-900 tracking-tighter">{% if item.precio > 0 %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span>
                    <a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="w-12 h-12 bg-blue-50 text-brand rounded-2xl flex items-center justify-center hover:bg-brand hover:text-white transition-all shadow-md shadow-blue-50"><i class="fas fa-arrow-right"></i></a>
                </div>
            </div>
        </div>
        {% else %}
        <div class="col-span-full py-32 text-center">
            <p class="text-slate-300 font-black text-2xl tracking-[0.2em]">RED VACÍA ACTUALMENTE</p>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
"""

# ==========================================
# 2. LÓGICA DE SERVIDOR Y MODELOS
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lifelink_final_master_fix_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lifelink.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    __tablename__ = 'users_master_final'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    def get_id(self): return str(self.id)

class Publicacion(db.Model):
    __tablename__ = 'items_master_final'
    id_oferta_insumo = db.Column(db.Integer, primary_key=True)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('users_master_final.id'))
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    tipo_publicacion = db.Column(db.String(50))
    precio = db.Column(db.Float, default=0.0)
    imagen_url = db.Column(db.String(500))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    estado = db.Column(db.String(20), default='Verificado')
    proveedor = db.relationship('User', backref='items')

class Solicitud(db.Model):
    __tablename__ = 'orders_master_final'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('users_master_final.id'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('items_master_final.id_oferta_insumo'))
    estatus = db.Column(db.String(50), default='En Coordinación')
    solicitante = db.relationship('User', backref='solicitudes')
    publicacion = db.relationship('Publicacion', backref='pedidos')

# Cargador de Plantillas
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'dashboard.html': dashboard_template,
    'publish.html': publish_template,
    'search.html': search_template,
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-24 px-4 text-center font-black uppercase italic"><div class="bg-white p-12 rounded-[3rem] shadow-2xl border border-slate-100"><h2>Ingresar</h2><form method="POST" class="space-y-4 mt-8"><input name="email" type="email" placeholder="CORREO" required class="w-full p-4 bg-slate-50 rounded-xl border-none outline-none shadow-inner"><input name="password" type="password" placeholder="CONTRASEÑA" required class="w-full p-4 bg-slate-50 rounded-xl border-none outline-none shadow-inner"><button class="w-full btn-medical py-5 rounded-[2rem] text-xl mt-4">Entrar</button></form></div></div>{% endblock %}""",
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-xl mx-auto py-16 px-4 uppercase font-black italic"><div class="bg-white p-12 rounded-[3rem] shadow-2xl border border-slate-50 text-center"><h2>Registro</h2><form method="POST" class="space-y-4 mt-8"><input name="nombre" placeholder="NOMBRE COMPLETO" required class="w-full p-4 bg-slate-50 rounded-xl border-none shadow-inner"><input name="email" type="email" placeholder="CORREO" required class="w-full p-4 bg-slate-50 rounded-xl border-none shadow-inner"><input name="password" type="password" placeholder="CONTRASEÑA" required class="w-full p-4 bg-slate-50 rounded-xl border-none shadow-inner"><button class="w-full btn-medical py-6 rounded-[2rem] text-xl">Crear Nodo</button></form></div></div>{% endblock %}""",
    'checkout.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-24 px-4 text-center uppercase font-black italic"><div class="bg-white p-12 rounded-[4rem] shadow-2xl border border-slate-100"><h2>Solicitud Auditada</h2><div class="bg-slate-50 p-10 rounded-[3rem] mb-10"><img src="{{ pub.imagen_url }}" class="w-48 h-48 rounded-3xl mx-auto mb-8 shadow-xl object-cover border-4 border-white"><h3 class="font-black text-2xl uppercase">{{ pub.nombre }}</h3><p class="text-[10px] text-brand mt-1 tracking-widest">{{ pub.categoria }}</p></div><form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST"><button class="w-full btn-medical py-6 rounded-[2rem] font-black text-3xl shadow-xl">Confirmar Coordinación</button></form></div></div>{% endblock %}""",
    'chat.html': """{% extends "base.html" %}{% block content %}<div class="max-w-4xl mx-auto py-8 px-4 h-[75vh] flex flex-col uppercase font-black italic"><div class="bg-white rounded-[3.5rem] shadow-2xl flex flex-col flex-1 overflow-hidden border border-slate-100"><div class="bg-brand p-10 text-white flex justify-between items-center shadow-lg relative z-10"><h3 class="font-black text-xl italic uppercase tracking-tighter">Canal de Coordinación</h3><a href="{{ url_for('dashboard') }}" class="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center hover:bg-white/30 transition-all"><i class="fas fa-times"></i></a></div><div class="flex-1 overflow-y-auto p-12 space-y-8 bg-slate-50/50 custom-scrollbar" id="chat-box"></div><div class="p-10 bg-white border-t border-slate-100"><form onsubmit="event.preventDefault(); send();" class="flex gap-6"><input id="msg-input" placeholder="Mensaje..." class="flex-1 p-6 bg-slate-100 rounded-[2.5rem] border-none outline-none font-black text-xs shadow-inner tracking-tighter"><button class="bg-brand text-white w-16 h-16 rounded-[2rem] shadow-xl hover:scale-110 transition-transform flex items-center justify-center"><i class="fas fa-paper-plane text-xl"></i></button></form></div></div></div><script>const socket = io(); const room = "{{ solicitud.id_solicitud }}"; const user = "{{ current_user.nombre }}"; socket.emit('join', {room: room}); socket.on('nuevo_mensaje', function(data){ const box = document.getElementById('chat-box'); const isMe = data.user === user; const d = document.createElement('div'); d.className = `flex ${isMe ? 'justify-end':'justify-start'}`; d.innerHTML = `<div class="${isMe?'bg-brand text-white rounded-l-[1.5rem] rounded-tr-[1.5rem]':'bg-white text-slate-700 rounded-r-[1.5rem] rounded-tl-[1.5rem] shadow-sm border border-slate-200'} px-6 py-4 max-w-[85%] italic"><p class="text-[8px] font-black uppercase mb-2 ${isMe?'text-blue-100':'text-slate-300'} tracking-widest">${data.user}</p><p class="text-xs font-black leading-relaxed tracking-tight uppercase">${data.msg}</p></div>`; box.appendChild(d); box.scrollTop = box.scrollHeight; }); function send(){ const i = document.getElementById('msg-input'); if(i.value.trim()){ socket.emit('enviar_mensaje', {msg: i.value, room: room}); i.value=''; } }</script>{% endblock %}""",
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-20 px-4 text-center uppercase font-black italic"><div class="relative inline-block mb-12"><div class="w-40 h-40 bg-brand text-white text-7xl font-black rounded-[3rem] flex items-center justify-center mx-auto shadow-2xl border-[10px] border-white ring-2 ring-slate-100 shadow-blue-100">{{ current_user.nombre[0] | upper }}</div><div class="absolute -bottom-1 -right-1 bg-emerald-500 w-12 h-12 rounded-xl flex items-center justify-center text-white border-4 border-white shadow-xl rotate-12"><i class="fas fa-check text-base"></i></div></div><h2 class="text-5xl font-black text-slate-900 mb-2 tracking-tighter italic uppercase leading-none">{{ current_user.nombre }}</h2><p class="text-brand font-black uppercase tracking-[0.4em] text-[9px] mb-12 italic">NODO AUTENTICADO</p><div class="grid grid-cols-1 md:grid-cols-2 gap-8 text-left italic"><div class="bg-white p-8 rounded-[2rem] shadow-sm border border-slate-100 flex flex-col items-center text-center group hover:border-brand transition-all italic"><p class="text-[8px] text-slate-300 font-black uppercase mb-2">EMAIL OPERATIVO</p><p class="font-black text-slate-800 text-xs uppercase">{{ current_user.email }}</p></div><div class="bg-white p-8 rounded-[2rem] shadow-sm border border-slate-100 flex flex-col items-center text-center group hover:border-brand transition-all italic"><p class="text-[8px] text-slate-300 font-black uppercase mb-2">SEGURIDAD</p><p class="font-black text-slate-800 text-xs uppercase">PROTOCOLO ACTIVO</p></div></div></div>{% endblock %}"""
})

# --- INICIALIZACIÓN ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@lifelink.com').first():
        admin = User(nombre="ADMINISTRADOR MAESTRO", email="admin@lifelink.com", password_hash=generate_password_hash("admin123"))
        db.session.add(admin); db.session.commit()

# ==========================================
# 3. RUTAS
# ==========================================
@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if User.query.filter_by(email=request.form['email']).first():
            flash("Identidad ya existente.")
        else:
            u = User(nombre=request.form['nombre'], email=request.form['email'], password_hash=generate_password_hash(request.form['password']))
            db.session.add(u); db.session.commit(); login_user(u)
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email']).first()
        if u and check_password_hash(u.password_hash, request.form['password']):
            login_user(u); return redirect(url_for('dashboard'))
        flash("Acceso denegado. Credenciales inválidas.")
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/buscar')
def buscar():
    res = Publicacion.query.all()
    return render_template('search.html', resultados=res)

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id).all()
    pub_ids = [p.id_oferta_insumo for p in pubs]
    sols = Solicitud.query.filter(Solicitud.id_publicacion.in_(pub_ids)).all() if pub_ids else []
    stats = {'total_usuarios': User.query.count(), 'total_publicaciones': Publicacion.query.count(), 'total_solicitudes': Solicitud.query.count()} if current_user.email == 'admin@lifelink.com' else None
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols, stats=stats)

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        img = request.files.get('imagen')
        img_url = "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?q=80&w=1000&auto=format&fit=crop"
        if img: img_url = cloudinary.uploader.upload(img)['secure_url']
        
        p = Publicacion(
            id_proveedor=current_user.id,
            nombre=request.form['nombre'],
            categoria=request.form['categoria'],
            tipo_publicacion=request.form['tipo_publicacion'],
            precio=float(request.form.get('precio', 0) or 0),
            imagen_url=img_url,
            latitud=float(request.form.get('lat', 19.4326)),
            longitud=float(request.form.get('lng', -99.1332))
        )
        db.session.add(p); db.session.commit()
        flash("Recurso publicado con éxito bajo auditoría técnica.")
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
    s = Solicitud(id_solicitante=current_user.id, id_publicacion=p.id_oferta_insumo)
    db.session.add(s); db.session.commit()
    flash("Certificado de coordinación emitido. Inicie chat.")
    return redirect(url_for('dashboard'))

@app.route('/chat/<int:id_solicitud>')
@login_required
def chat(id_solicitud):
    s = Solicitud.query.get_or_404(id_solicitud)
    return render_template('chat.html', solicitud=s)

@app.route('/borrar_publicacion/<int:id>', methods=['POST'])
@login_required
def borrar_publicacion(id):
    p = Publicacion.query.get_or_404(id)
    if p.id_proveedor == current_user.id:
        db.session.delete(p); db.session.commit()
        flash("Publicación retirada de la red.")
    return redirect(url_for('dashboard'))

@app.route('/perfil')
@login_required
def perfil(): return render_template('perfil.html')

# --- SOCKETIO EVENTS ---
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

@socketio.on('join')
def on_join(data): join_room(data['room'])

@socketio.on('enviar_mensaje')
def handle_msg(data): emit('nuevo_mensaje', {'msg': data['msg'], 'user': current_user.nombre}, room=data['room'])

if __name__ == '__main__':
    socketio.run(app, debug=False)
