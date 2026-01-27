import eventlet
# Parcheo obligatorio e inmediato para evitar errores de mainloop en Python 3.13
eventlet.monkey_patch(all=True) 

import os
import jinja2
from datetime import datetime, date
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
# 1. LÓGICA MÉDICA (Sustento para preguntas)
# ==========================================
BLOOD_COMPATIBILITY = {
    'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'], 
    'O+': ['O+', 'A+', 'B+', 'AB+'],
    'A-': ['A-', 'A+', 'AB-', 'AB+'],
    'A+': ['A+', 'AB+'],
    'B-': ['B-', 'B+', 'AB-', 'AB+'],
    'B+': ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+']
}

# ==========================================
# 2. DEFINICIÓN DE PLANTILLAS (ORDENADAS PARA EVITAR NAMEERROR)
# ==========================================

base_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LifeLink - Gestión Médica Profesional</title>
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
        #map { height: 380px; width: 100%; border-radius: 1.5rem; z-index: 10; border: 2px solid #f1f5f9; }
        .triage-p1 { border: 3px solid #ef4444 !important; animation: pulse-red 2s infinite; }
        @keyframes pulse-red { 0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); } 70% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); } 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); } }
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
    </style>
</head>
<body class="bg-slate-50 flex flex-col min-h-screen font-sans text-slate-900 uppercase">
    <nav class="bg-white/90 backdrop-blur-md border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center gap-8">
                    <a href="/" class="flex items-center gap-2">
                        <div class="bg-brand p-1.5 rounded-lg shadow-lg">
                             <svg width="24" height="24" viewBox="0 0 100 100" fill="none" stroke="white" stroke-width="8">
                                <path d="M10 50 L30 50 L40 20 L60 80 L70 50 L90 50" stroke-linecap="round" stroke-linejoin="round"/>
                             </svg>
                        </div>
                        <span class="font-black text-xl tracking-tighter text-slate-800 italic">LifeLink</span>
                    </a>
                    <div class="hidden md:flex gap-6">
                        <a href="{{ url_for('buscar') }}" class="text-[10px] font-black text-slate-400 hover:text-brand transition tracking-widest">Buscador</a>
                        {% if current_user.is_authenticated %}
                        <a href="{{ url_for('publicar') }}" class="text-[10px] font-black text-slate-400 hover:text-brand transition tracking-widest">Publicar</a>
                        <a href="{{ url_for('dashboard') }}" class="text-[10px] font-black text-slate-400 hover:text-brand transition tracking-widest">Gestión</a>
                        {% endif %}
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    {% if current_user.is_authenticated %}
                        <a href="{{ url_for('perfil') }}" class="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center text-brand font-black border border-blue-100 italic">{{ current_user.nombre[0] | upper }}</a>
                    {% else %}
                        <a href="{{ url_for('login') }}" class="text-xs font-black text-slate-400">Entrar</a>
                        <a href="{{ url_for('registro') }}" class="btn-medical px-6 py-2.5 text-xs font-black shadow-lg">Unirse</a>
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
                <div class="p-4 rounded-xl {% if category == 'error' %}bg-red-50 text-red-700 border-red-100{% else %}bg-emerald-50 text-emerald-700 border-emerald-100{% endif %} flex items-center gap-3 shadow-sm border animate-in slide-in-from-top-2">
                  <i class="fas fa-circle-info"></i>
                  <span class="text-xs font-black italic">{{ message }}</span>
                </div>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
</body>
</html>
"""

home_template = """
{% extends "base.html" %}
{% block content %}
<div class="relative min-h-[85vh] flex items-center bg-white overflow-hidden">
    <div class="max-w-7xl mx-auto px-4 relative z-10 w-full">
        <div class="lg:grid lg:grid-cols-12 lg:gap-12 items-center text-left">
            <div class="sm:text-center lg:col-span-7 lg:text-left">
                <span class="inline-flex items-center px-4 py-1.5 rounded-full text-[10px] font-black bg-slate-900 text-white uppercase tracking-widest mb-8 shadow-xl">
                    Operación Certificada IPN 2026
                </span>
                <h1 class="text-6xl font-black text-slate-900 tracking-tighter sm:text-7xl leading-[1] mb-8 uppercase italic">
                    Red de <br><span class="text-brand italic underline decoration-blue-100">Latidos.</span>
                </h1>
                <p class="text-lg text-slate-500 max-w-lg leading-relaxed mb-10 font-bold italic">
                    Gestión blindada de hemoderivados, fármacos controlados y logística médica especializada con control de caducidad automatizado.
                </p>
                <div class="flex flex-wrap gap-5">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-10 py-5 font-black text-lg shadow-2xl flex items-center gap-3 italic">
                        <i class="fas fa-satellite-dish"></i> Explorar Red
                    </a>
                </div>
            </div>
            <div class="mt-16 lg:mt-0 lg:col-span-5 flex justify-center">
                <div class="relative w-full max-w-md">
                    <div class="absolute inset-0 bg-brand rounded-[3rem] rotate-6 opacity-10"></div>
                    <div class="relative bg-white p-4 rounded-[3rem] shadow-2xl border-8 border-slate-50 overflow-hidden">
                        <img class="w-full h-[500px] rounded-[2rem] object-cover shadow-inner grayscale hover:grayscale-0 transition-all duration-1000" src="https://images.unsplash.com/photo-1576091160550-2173bdb999ef?q=80&w=1000&auto=format&fit=crop" alt="LifeLink Tech">
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
    <div class="flex justify-between items-end mb-12">
        <div>
            <h1 class="text-6xl font-black text-slate-900 tracking-tighter italic uppercase leading-none italic">Centro <br><span class="text-brand text-4xl">Operativo.</span></h1>
            <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest mt-2 italic">Nodo: {{ current_user.nombre }} | Rating: {{ current_user.rating_promedio|round(1) }} ★</p>
        </div>
    </div>

    {% if current_user.email == 'admin@lifelink.com' %}
    <div class="mb-16 bg-slate-900 p-12 rounded-[4rem] text-white shadow-2xl relative overflow-hidden font-black italic">
        <h3 class="text-2xl font-black mb-10 flex items-center gap-4 italic uppercase tracking-tighter"><i class="fas fa-shield-halved text-brand"></i> Panel de Auditoría Central</h3>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12 uppercase">
            <div class="bg-white/5 p-8 rounded-3xl border border-white/10 text-center shadow-inner">
                <p class="text-4xl font-black text-brand mb-2">{{ stats.total_usuarios }}</p>
                <p class="text-[9px] text-slate-500 tracking-widest">Nodos Activos</p>
            </div>
            <div class="bg-white/5 p-8 rounded-3xl border border-white/10 text-center shadow-inner">
                <p class="text-4xl font-black text-emerald-400 mb-2">{{ stats.total_publicaciones }}</p>
                <p class="text-[9px] text-slate-500 tracking-widest text-xs">Recursos Globales</p>
            </div>
            <div class="bg-white/5 p-8 rounded-3xl border border-white/10 text-center shadow-inner">
                <p class="text-4xl font-black text-amber-400 mb-2">{{ stats.total_tickets }}</p>
                <p class="text-[9px] text-slate-500 tracking-widest text-xs">Alertas Legales</p>
            </div>
        </div>

        <div class="space-y-6">
            <h4 class="text-[11px] font-black text-slate-500 tracking-widest mb-6 italic">Validaciones de Farmacia</h4>
            {% for p in pubs_pendientes %}
            <div class="bg-white/5 p-6 rounded-3xl flex justify-between items-center border border-white/10">
                <div class="flex items-center gap-6">
                    <a href="{{ p.receta_url }}" target="_blank" class="w-12 h-12 bg-brand/20 rounded-2xl flex items-center justify-center text-brand border border-brand/30"><i class="fas fa-file-prescription text-xl"></i></a>
                    <div><p class="italic uppercase italic font-black">{{ p.nombre }}</p><p class="text-[9px] text-slate-500 uppercase">DONANTE: {{ p.proveedor.nombre }}</p></div>
                </div>
                <form action="{{ url_for('validar_publicacion', id=p.id_oferta_insumo) }}" method="POST">
                    <button class="bg-brand text-white px-8 py-3 rounded-2xl text-[10px] font-black uppercase tracking-widest hover:bg-white hover:text-brand transition-all shadow-xl">Aprobar</button>
                </form>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-16 font-black uppercase italic">
        <div class="lg:col-span-2 space-y-12">
             <h4 class="text-[11px] font-black text-slate-300 uppercase tracking-widest italic">Transferencias Entrantes</h4>
             <div class="grid gap-6">
                {% for s in solicitudes_recibidas %}<div class="bg-white p-10 rounded-[3.5rem] border border-slate-100 shadow-xl flex flex-col md:flex-row justify-between items-center group hover:scale-[1.01] transition-all">
                    <div>
                        <div class="flex items-center gap-3 mb-4">
                            <span class="text-[9px] font-black bg-blue-50 text-brand px-4 py-1.5 rounded-full uppercase italic border border-blue-100 shadow-sm">{{ s.estatus }}</span>
                        </div>
                        <h5 class="font-black text-slate-800 text-3xl tracking-tighter uppercase italic leading-none mb-3 italic">{{ s.publicacion.nombre }}</h5>
                        <p class="text-xs text-slate-400 font-bold uppercase tracking-widest italic">SOLICITANTE: {{ s.solicitante.nombre }}</p>
                    </div>
                    <div class="mt-8 md:mt-0">
                        <a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="btn-medical px-10 py-5 text-[11px] font-black uppercase tracking-widest shadow-2xl shadow-blue-200 italic">Línea Coordinación</a>
                    </div>
                </div>{% endfor %}
             </div>
        </div>

        <div class="space-y-12">
            <h4 class="text-[11px] font-black text-slate-300 uppercase tracking-widest italic text-center italic">Inventario Local Auditado</h4>
            <div class="grid gap-5">
                {% for p in publicaciones %}<div class="bg-white p-6 rounded-[2.5rem] border border-slate-100 shadow-sm relative overflow-hidden group">
                    <div class="flex items-center gap-5">
                        <img src="{{ p.imagen_url }}" class="w-16 h-16 rounded-2xl object-cover shadow-inner group-hover:rotate-6 transition-all">
                        <div class="flex-1 min-w-0">
                            <p class="text-[10px] font-black text-slate-800 truncate mb-1 uppercase italic tracking-tighter">{{ p.nombre }}</p>
                            <span class="text-[7px] font-black uppercase {% if p.estado == 'Verificado' %}text-emerald-500 bg-emerald-50{% else %}text-amber-500 bg-amber-50{% endif %} px-2 py-0.5 rounded-lg tracking-widest border border-current opacity-80 italic">{{ p.estado }}</span>
                        </div>
                        <form action="{{ url_for('borrar_publicacion', id=p.id_oferta_insumo) }}" method="POST">
                            <button class="p-3 text-slate-200 hover:text-red-500 hover:bg-red-50 rounded-2xl transition-all shadow-inner"><i class="fas fa-trash-can text-sm"></i></button>
                        </form>
                    </div>
                </div>{% endfor %}
            </div>
            <a href="{{ url_for('publicar') }}" class="block w-full bg-brand text-white py-6 rounded-[2.5rem] text-center text-[11px] font-black uppercase tracking-widest hover:scale-105 transition-all shadow-2xl shadow-blue-200 italic">Liberar Nuevo Recurso</a>
        </div>
    </div>
</div>
{% endblock %}
"""

publish_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-5xl mx-auto py-12 px-4 uppercase font-black italic">
    <div class="bg-white rounded-[4rem] shadow-2xl p-16 border border-slate-50 shadow-blue-50/50">
        <h2 class="text-4xl font-black text-slate-900 mb-4 tracking-tighter italic">Nodo de <span class="text-brand">Publicación Oficial.</span></h2>
        <p class="text-[11px] font-black text-slate-300 uppercase tracking-widest mb-16 italic">TechPulse audit system enabled</p>
        
        <form method="POST" enctype="multipart/form-data" class="space-y-12">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-12">
                <div>
                    <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-6 italic">Evidencia Gráfica (Real)</label>
                    <div class="p-20 border-4 border-dashed border-slate-100 rounded-[4rem] text-center bg-slate-50/50 hover:border-brand transition-all cursor-pointer shadow-inner relative overflow-hidden group">
                        <i class="fas fa-fingerprint text-6xl text-slate-200 group-hover:text-brand transition-colors mb-6 italic"></i>
                        <input type="file" name="imagen" accept="image/*" required class="text-[10px] text-slate-400 font-black w-full relative z-10 italic">
                    </div>
                    
                    <div class="mt-8 p-8 bg-amber-50 rounded-[2.5rem] border border-amber-100 shadow-inner italic">
                        <label class="block text-[10px] font-black text-amber-600 uppercase tracking-widest mb-4 italic"><i class="fas fa-calendar-check mr-2"></i> Control de Caducidad</label>
                        <input type="date" name="fecha_caducidad" required class="w-full p-4 bg-white rounded-2xl border-none font-black text-sm text-amber-700 outline-none focus:ring-2 focus:ring-amber-400 shadow-inner italic">
                        <p class="text-[8px] text-amber-400 mt-4 font-bold uppercase tracking-widest leading-relaxed italic">Filtro Automático: El recurso se ocultará automáticamente al alcanzar esta fecha.</p>
                    </div>
                </div>

                <div class="space-y-10">
                    <div>
                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 italic">Nombre del Recurso</label>
                        <input name="nombre" placeholder="Bolsa de Sangre O-" required class="w-full p-6 bg-slate-50 rounded-[2rem] border-none font-black text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-tighter italic">
                    </div>
                    
                    <div class="grid grid-cols-2 gap-6 italic">
                        <div>
                            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 italic">Especialidad</label>
                            <select name="categoria" id="cat_select" onchange="toggleLegal(this.value)" class="w-full p-6 bg-slate-50 rounded-[1.5rem] border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner italic">
                                <option value="Equipo">Insumo Médico</option>
                                <option value="Medicamento">Farmacéutico</option>
                                <option value="Sangre">Hemoderivado</option>
                                <option value="Ortopedico">Ortopédico</option>
                            </select>
                        </div>
                        <div id="receta_section" class="hidden">
                            <label class="block text-[10px] font-black text-red-500 uppercase tracking-widest mb-3 italic underline italic">Carga Receta</label>
                            <input type="file" name="receta" accept="image/*,application/pdf" class="text-[8px] font-black text-red-300 italic uppercase italic">
                        </div>
                    </div>

                    <div>
                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 italic">Marco Jurídico</label>
                        <select name="tipo_publicacion" id="tipo_pub" class="w-full p-6 bg-slate-50 rounded-[1.5rem] border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner italic">
                            <option value="Venta">Venta Certificada</option>
                            <option value="Donacion">Donación Altruista</option>
                        </select>
                    </div>

                    <div class="flex items-center gap-4 bg-red-50 p-6 rounded-[2rem] border border-red-100">
                        <input type="checkbox" name="urgente" class="w-6 h-6 rounded-lg text-red-500 border-red-200 shadow-sm italic">
                        <span class="text-[10px] font-black text-red-600 uppercase tracking-widest italic italic leading-none">Urgencia Crítica P1</span>
                    </div>
                </div>
            </div>

            <div class="space-y-6">
                <div id="map" class="shadow-2xl"></div>
                <div class="bg-blue-50 p-8 rounded-[3rem] border border-blue-100 flex items-center gap-6 shadow-inner text-brand italic">
                    <i class="fas fa-location-crosshairs animate-pulse text-2xl italic"></i>
                    <input type="text" id="direccion_text" name="direccion_manual" readonly placeholder="Aguardando geolocalización..." class="bg-transparent w-full outline-none text-[12px] font-black uppercase tracking-widest italic italic">
                </div>
                <input type="hidden" id="lat" name="lat"><input type="hidden" id="lng" name="lng">
            </div>

            <button type="submit" class="w-full btn-medical py-8 rounded-[3.5rem] font-black text-4xl shadow-2xl shadow-blue-200 italic uppercase hover:scale-[1.01] transition-all italic">Certificar Recurso</button>
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

    function toggleLegal(v){
        const s = document.getElementById('receta_section');
        if(v==='Medicamento'){ s.classList.remove('hidden'); } else { s.classList.add('hidden'); }
    }
</script>
{% endblock %}
"""

search_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-7xl mx-auto py-12 px-4 flex flex-col lg:flex-row gap-16 font-black uppercase italic italic">
    <div class="lg:w-80">
        <div class="bg-white p-10 rounded-[3rem] border border-slate-100 shadow-2xl sticky top-28 italic shadow-blue-50/50 italic italic">
            <h4 class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-8 italic italic">Malla de Búsqueda</h4>
            <form method="GET" class="space-y-4 italic italic">
                <input name="q" placeholder="Ej: Sangre O+..." class="w-full p-4 bg-slate-50 border-none rounded-2xl text-[10px] font-black outline-none shadow-inner italic italic">
                <button class="w-full btn-medical py-4 text-[10px] font-black uppercase tracking-widest italic italic shadow-xl">Actualizar Red</button>
            </form>
        </div>
    </div>
    <div class="flex-1 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-12 italic italic italic">
        {% for item in resultados %}
        <div class="bg-white rounded-[3rem] border border-slate-50 shadow-sm overflow-hidden hover:shadow-2xl transition-all duration-1000 group relative italic italic italic {% if item.urgente %}triage-p1{% endif %}">
            {% if item.urgente %}<div class="absolute z-20 top-6 left-6 bg-red-600 text-white text-[7px] px-3 py-1 rounded-full font-black tracking-widest shadow-xl animate-pulse italic italic italic uppercase italic">Urgencia P1</div>{% endif %}
            <img src="{{ item.imagen_url }}" class="w-full h-72 object-cover group-hover:scale-110 transition-transform duration-1000 shadow-inner grayscale group-hover:grayscale-0 italic">
            <div class="p-8 italic italic italic">
                <h3 class="font-black text-slate-800 text-2xl tracking-tighter uppercase italic mb-1 italic italic">{{ item.nombre }}</h3>
                <p class="text-[9px] text-brand font-black uppercase tracking-[0.1em] mb-6 italic italic italic">{{ item.categoria }}</p>
                <p class="text-[8px] font-black text-red-400 uppercase mb-8 italic italic italic tracking-widest italic">Vence: {{ item.fecha_caducidad }}</p>
                <div class="flex justify-between items-center italic italic">
                    <span class="text-3xl font-black text-slate-900 tracking-tighter italic italic italic italic">{% if item.tipo_publicacion == 'Venta' %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span>
                    <a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="w-14 h-14 bg-blue-50 text-brand rounded-[1.5rem] flex items-center justify-center hover:bg-brand hover:text-white transition-all shadow-xl shadow-blue-50 shadow-inner italic italic italic"><i class="fas fa-chevron-right text-lg italic italic italic italic"></i></a>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
"""

# ==========================================
# 3. LÓGICA DE SERVIDOR Y MODELOS
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lifelink_2026_ultimate_safe_protocol_v5iv7')
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

    @property
    def rating_promedio(self):
        resenas_recibidas = Resena.query.filter_by(id_evaluado=self.id_usuario).all()
        if not resenas_recibidas: return 5.0 
        return sum([r.estrellas for r in resenas_recibidas]) / len(resenas_recibidas)

class Publicacion(db.Model):
    __tablename__ = 'insumos'
    id_oferta_insumo = db.Column(db.Integer, primary_key=True)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    tipo_publicacion = db.Column(db.String(50))
    precio = db.Column(db.Float, default=0.0)
    imagen_url = db.Column(db.String(500))
    receta_url = db.Column(db.String(500))
    direccion_exacta = db.Column(db.String(500))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    fecha_caducidad = db.Column(db.Date)
    urgente = db.Column(db.Boolean, default=False)
    estado = db.Column(db.String(20), default='Pendiente') 
    proveedor = db.relationship('Usuario', backref='publicaciones')

class Solicitud(db.Model):
    __tablename__ = 'solicitudes'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('insumos.id_oferta_insumo'))
    hospital_destino = db.Column(db.String(255), default='Nodo Particular')
    estatus = db.Column(db.String(50), default='En Coordinación') 
    solicitante = db.relationship('Usuario', backref='solicitudes_enviadas')
    publicacion = db.relationship('Publicacion', backref='solicitudes_recibidas')

class Resena(db.Model):
    __tablename__ = 'resenas'
    id_resena = db.Column(db.Integer, primary_key=True)
    id_solicitud = db.Column(db.Integer, db.ForeignKey('solicitudes.id_solicitud'))
    id_evaluador = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    id_evaluado = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    estrellas = db.Column(db.Integer)
    comentario = db.Column(db.Text)
    solicitud = db.relationship('Solicitud', backref='resena')

class MensajeSoporte(db.Model):
    __tablename__ = 'soporte_tickets'
    id_ticket = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    asunto = db.Column(db.String(150))
    mensaje = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario', backref='tickets')

# Cargador de Plantillas (FIXED: Ahora carga después de definir las variables)
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'dashboard.html': dashboard_template,
    'publish.html': publish_template,
    'search.html': search_template,
    'soporte.html': """{% extends "base.html" %}{% block content %}<div class="max-w-5xl mx-auto py-16 px-4 text-center italic font-black uppercase italic tracking-widest"><h2 class="text-6xl font-black mb-12 tracking-tighter uppercase italic italic leading-none italic">Pilar Legal y <span class="text-brand text-4xl italic italic">Compliance.</span></h2><div class="grid grid-cols-1 md:grid-cols-2 gap-10 mb-20 text-left italic font-black italic"><div class="bg-white p-12 rounded-[4rem] border border-slate-100 shadow-2xl italic"><h3 class="text-2xl font-black mb-6 flex items-center gap-3 italic italic"><i class="fas fa-scale-balanced text-brand italic"></i> Legal Tech</h3><p class="text-[10px] text-slate-500 leading-relaxed tracking-widest uppercase italic italic italic">Bloqueamos la monetización de sangre según NOM-253. Auditamos recetas para fármacos y filtramos automáticamente recursos caducados bajo el estándar LFPDPPP.</p></div><div class="bg-slate-900 p-12 rounded-[4rem] text-white shadow-2xl italic italic italic"><h3 class="text-2xl font-black mb-6 flex items-center gap-3 italic italic italic italic"><i class="fas fa-coins text-amber-400 italic italic italic"></i> Monetización B2B</h3><p class="text-[10px] text-slate-400 font-medium leading-relaxed tracking-widest uppercase italic italic italic italic">Suscripciones premium para instituciones de salud ($990 MXN/mes) y tarifas logísticas por gestión de transporte pesado certificado COFEPRIS.</p></div></div><form action="{{ url_for('enviar_soporte') }}" method="POST" class="bg-white p-12 rounded-[4rem] border border-blue-100 shadow-2xl max-w-2xl mx-auto italic"><h3 class="text-2xl font-black mb-8 italic uppercase italic italic italic">Reporte Legal TechPulse</h3><input name="asunto" placeholder="Motivo Jurídico" required class="w-full p-5 bg-slate-50 rounded-2xl border-none outline-none font-black text-xs italic italic mb-4 shadow-inner italic italic italic"><textarea name="mensaje" placeholder="Evidencia..." rows="4" required class="w-full p-5 bg-slate-50 rounded-2xl border-none outline-none font-bold text-sm italic italic shadow-inner italic italic italic"></textarea><button class="w-full btn-medical py-6 text-[10px] font-black uppercase tracking-widest shadow-2xl italic mt-6 italic italic italic italic">Certificar Reporte</button></form></div>{% endblock %}""",
    'checkout.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-20 px-4 text-center animate-in zoom-in-95 duration-700 uppercase italic italic italic"><div class="bg-white p-12 rounded-[5rem] shadow-2xl border border-slate-100 relative overflow-hidden italic italic"><h2 class="text-5xl font-black text-slate-900 mb-12 tracking-tighter italic uppercase leading-none italic italic">Solicitud <br><span class="text-brand italic italic">Auditada.</span></h2><div class="bg-slate-50 p-12 rounded-[4rem] mb-12 border border-slate-100 shadow-inner italic italic"><img src="{{ pub.imagen_url }}" class="w-48 h-48 rounded-[2.5rem] object-cover mx-auto mb-8 shadow-2xl ring-8 ring-white italic italic"><h3 class="font-black text-2xl text-slate-800 uppercase italic italic italic">{{ pub.nombre }}</h3></div>{% if pub.categoria == 'Sangre' %}<div class="mb-10 p-8 bg-red-50 border-2 border-red-100 rounded-[3rem] text-left shadow-inner italic italic italic"><p class="text-[10px] font-black text-red-600 uppercase tracking-widest mb-4 italic italic italic">Registro de Banco de Sangre</p><input name="hospital" placeholder="NOMBRE DEL HOSPITAL" required class="w-full p-5 bg-white rounded-2xl border-none text-xs font-black outline-none focus:ring-2 focus:ring-red-400 shadow-md uppercase italic italic italic"></div>{% endif %}<form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST" class="italic italic"><button class="w-full btn-medical py-6 rounded-[3rem] font-black text-3xl shadow-2xl shadow-blue-200 hover:scale-105 transition-all uppercase italic italic italic">Confirmar Compromiso</button></form></div></div>{% endblock %}""",
    'review.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-24 px-4 text-center uppercase italic italic italic"><div class="bg-white p-16 rounded-[4.5rem] shadow-2xl border border-slate-100 italic italic italic"><h2 class="text-3xl font-black mb-12 tracking-tighter italic uppercase leading-none italic italic italic">Auditar <br><span class="text-emerald-500 text-2xl italic italic">Donante.</span></h2><form method="POST" class="space-y-8 italic italic italic"><select name="estrellas" class="w-full p-5 bg-slate-50 rounded-2xl border-none font-black text-brand text-xl text-center outline-none italic italic italic"><option value="5">★★★★★ Excelente</option><option value="4">★★★★ Bueno</option><option value="3">★★★ Regular</option><option value="2">★★ Malo</option><option value="1">★ Fraude</option></select><textarea name="comentario" placeholder="Experiencia..." required rows="4" class="w-full p-6 bg-slate-50 rounded-[2rem] border-none outline-none font-bold text-sm focus:ring-2 focus:ring-emerald-400 shadow-inner italic uppercase italic italic italic"></textarea><button class="w-full bg-emerald-500 text-white py-6 rounded-[3rem] font-black text-2xl shadow-2xl shadow-emerald-100 uppercase italic transition-all hover:scale-105 italic italic italic">Publicar Score</button></form></div></div>{% endblock %}""",
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-16 px-4 uppercase italic italic italic"><div class="bg-white p-16 rounded-[4rem] shadow-2xl border border-slate-50 italic italic italic"><h2 class="text-4xl font-black text-slate-900 mb-10 tracking-tighter italic italic italic">Cédula de <span class="text-brand italic italic italic">Registro.</span></h2><form method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-6 italic italic italic"><input name="nombre" placeholder="Nombre completo" required class="col-span-1 md:col-span-2 p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase italic italic italic"><select name="tipo_sangre" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner italic italic italic"><option value="">TIPO SANGRE</option><option>O+</option><option>O-</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option></select><input name="telefono" placeholder="WhatsApp" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase italic italic"><input name="email" type="email" placeholder="Email" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase italic italic"><input name="ubicacion" placeholder="Ciudad" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase italic italic"><input name="password" type="password" placeholder="Passphrase" required class="col-span-1 md:col-span-2 p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-widest italic italic italic"><div class="col-span-1 md:col-span-2 flex items-center gap-4 bg-slate-50 p-6 rounded-3xl border border-slate-100 shadow-inner italic italic"><input type="checkbox" required class="w-6 h-6 rounded-lg text-brand border-slate-200 shadow-sm italic italic"><p class="text-[9px] font-black text-slate-400 uppercase tracking-widest italic leading-relaxed italic italic">Acepto tratamiento de datos LFPDPPP y confirmo uso ético TechPulse.</p></div><button class="col-span-1 md:col-span-2 w-full btn-medical py-6 rounded-[3rem] font-black text-2xl mt-8 shadow-2xl shadow-blue-100 italic uppercase italic italic italic">Activar Nodo</button></form></div></div>{% endblock %}""",
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-24 px-4 text-center uppercase italic italic italic"><div class="bg-white p-16 rounded-[5rem] shadow-2xl border border-slate-100 relative overflow-hidden shadow-blue-50/50 italic italic italic"><div class="w-24 h-24 bg-blue-50 text-brand rounded-[2rem] flex items-center justify-center mx-auto mb-12 shadow-inner rotate-6 italic italic italic"><i class="fas fa-fingerprint text-4xl italic italic"></i></div><h2 class="text-5xl font-black mb-12 tracking-tighter italic text-slate-800 uppercase leading-none italic italic italic">Validar <br>Acceso.</h2><form method="POST" class="space-y-6 italic italic italic"><input name="email" type="email" placeholder="USER ID" required class="w-full p-6 bg-slate-50 rounded-3xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-widest italic italic italic"><input name="password" type="password" placeholder="PASSPHRASE" required class="w-full p-6 bg-slate-50 rounded-3xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-widest italic italic italic"><button class="w-full btn-medical py-7 rounded-[3.5rem] font-black text-3xl mt-10 shadow-2xl shadow-blue-200 uppercase tracking-tighter italic italic italic italic">Ingresar</button></form></div></div>{% endblock %}""",
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-20 px-4 text-center uppercase italic italic italic italic"><div class="relative inline-block mb-12 italic italic italic"><div class="w-48 h-48 bg-brand text-white text-8xl font-black rounded-[4rem] flex items-center justify-center mx-auto shadow-2xl border-[12px] border-white ring-2 ring-slate-100 italic shadow-blue-100 italic italic italic italic">{{ current_user.nombre[0] | upper }}</div><div class="absolute -bottom-2 -right-2 bg-emerald-500 w-14 h-14 rounded-2xl flex items-center justify-center text-white border-4 border-white shadow-xl rotate-12 italic italic"><i class="fas fa-certificate text-xl italic italic"></i></div></div><h2 class="text-6xl font-black text-slate-900 mb-2 tracking-tighter uppercase italic leading-none italic italic italic italic">{{ current_user.nombre }}</h2><p class="text-brand font-black uppercase tracking-[0.4em] text-[10px] mb-16 italic italic italic italic">Nodo Verificado {{ current_user.tipo_sangre }}</p><div class="grid grid-cols-1 md:grid-cols-3 gap-8 text-left italic italic italic">{% for label, icon, val in [('Canal', 'fa-mobile-screen', current_user.telefono), ('Email', 'fa-envelope-open', current_user.email), ('Ubicación', 'fa-map-location-dot', current_user.ubicacion)] %}<div class="bg-white p-10 rounded-[3rem] shadow-sm border border-slate-100 flex flex-col items-center text-center group hover:border-brand transition-all italic italic italic"><i class="fas {{ icon }} text-slate-100 text-3xl mb-5 group-hover:text-brand transition-colors italic italic italic"></i><p class="text-[9px] text-slate-300 font-black uppercase mb-2 tracking-[0.2em] italic italic italic italic italic">{{ label }}</p><p class="font-black text-slate-800 text-xs break-words tracking-tighter uppercase italic italic italic italic">{{ val }}</p></div>{% endfor %}</div><div class="mt-24 italic italic italic"><a href="{{ url_for('logout') }}" class="text-red-300 font-black text-[9px] uppercase tracking-[0.4em] hover:text-red-500 transition-all underline decoration-red-50 font-bold italic italic italic italic">Cerrar Sesión Operativa</a></div></div>{% endblock %}""",
    'chat.html': """{% extends "base.html" %}{% block content %}<div class="max-w-4xl mx-auto py-8 px-4 h-[80vh] flex flex-col uppercase italic italic italic italic"><div class="bg-white rounded-[4rem] shadow-2xl flex flex-col flex-1 overflow-hidden border border-slate-100 animate-in zoom-in-95 duration-700 shadow-blue-50/50 italic italic italic"><div class="bg-brand p-10 text-white flex justify-between items-center shadow-lg relative z-10 italic italic italic"><div class="flex items-center gap-6 italic italic italic"><div class="w-16 h-16 rounded-[1.5rem] bg-white/20 flex items-center justify-center font-black text-2xl shadow-inner italic italic italic">LL</div><div><h3 class="font-black leading-none text-2xl tracking-tighter italic uppercase italic italic italic">Línea Coordinación</h3><p class="text-[10px] text-blue-50 uppercase tracking-[0.2em] mt-3 font-black animate-pulse italic italic italic">Encriptación End-to-End Activa</p></div></div><a href="{{ url_for('dashboard') }}" class="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center hover:bg-white/20 transition-all shadow-inner italic italic italic italic"><i class="fas fa-times text-xl italic italic italic"></i></a></div><div class="flex-1 overflow-y-auto p-12 space-y-10 bg-slate-50/50 custom-scrollbar italic italic italic italic italic" id="chat-box"></div><div class="p-10 bg-white border-t border-slate-100 italic italic italic"><form onsubmit="event.preventDefault(); send();" class="flex gap-6 italic italic italic"><input id="msg-input" placeholder="Coordina entrega..." class="flex-1 p-6 bg-slate-100 rounded-[2rem] border-none outline-none focus:ring-2 focus:ring-brand font-black text-sm shadow-inner uppercase tracking-tighter italic italic italic italic italic"><button class="bg-brand text-white w-20 h-20 rounded-[2rem] shadow-2xl shadow-blue-200 hover:scale-110 transition-transform flex items-center justify-center shadow-brand/20 italic italic italic italic"><i class="fas fa-paper-plane text-2xl italic italic italic"></i></button></form></div></div></div><script>const socket = io(); const room = "{{ solicitud.id_solicitud }}"; const user = "{{ current_user.nombre }}"; socket.emit('join', {room: room}); socket.on('nuevo_mensaje', function(data){ const box = document.getElementById('chat-box'); const isMe = data.user === user; const d = document.createElement('div'); d.className = `flex ${isMe ? 'justify-end':'justify-start'}`; d.innerHTML = `<div class="${isMe?'bg-brand text-white rounded-l-[2rem] rounded-tr-[2rem] shadow-2xl shadow-blue-100':'bg-white text-slate-700 rounded-r-[2rem] rounded-tl-[2rem] shadow-sm border border-slate-200'} px-8 py-5 max-w-[85%] animate-in fade-in slide-in-from-bottom-4 italic italic"><p class="text-[9px] font-black uppercase mb-3 ${isMe?'text-blue-100':'text-slate-300'} tracking-widest italic italic">${data.user}</p><p class="text-sm font-black leading-relaxed tracking-tight uppercase italic italic italic">${data.msg}</p></div>`; box.appendChild(d); box.scrollTop = box.scrollHeight; }); function send(){ const i = document.getElementById('msg-input'); if(i.value.trim()){ socket.emit('enviar_mensaje', {msg: i.value, room: room}); i.value=''; } }</script>{% endblock %}"""
})

# ==========================================
# 4. RUTAS Y FUNCIONES DE CONTROL
# ==========================================
@login_manager.user_loader
def load_user(user_id): return Usuario.query.get(int(user_id))

@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if Usuario.query.filter_by(email=request.form['email']).first():
            flash("Identidad ya persistida en la red TechPulse.", "error")
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
        flash("Acceso denegado. Protocolo fallido.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        img = request.files.get('imagen')
        rect = request.files.get('receta')
        cad = request.form.get('fecha_caducidad')
        urg = True if request.form.get('urgente') else False
        img_url = "https://via.placeholder.com/400"
        rect_url = None
        if img: img_url = cloudinary.uploader.upload(img)['secure_url']
        if rect: rect_url = cloudinary.uploader.upload(rect)['secure_url']
        
        cat = request.form['categoria']
        status = 'Verificado' if cat not in ['Medicamento', 'Sangre'] else 'Pendiente'
        
        if cat == 'Medicamento' and not rect:
            flash("Error legal: Se requiere receta física obligatoria.", "error")
            return redirect(url_for('publicar'))
        
        cad_date = datetime.strptime(cad, '%Y-%m-%d').date() if cad else None
        
        p = Publicacion(
            id_proveedor=current_user.id_usuario,
            nombre=request.form['nombre'],
            categoria=cat,
            tipo_publicacion=request.form['tipo_publicacion'],
            precio=float(request.form.get('precio', 0) or 0),
            imagen_url=img_url,
            receta_url=rect_url,
            direccion_exacta=request.form.get('direccion_manual', 'Nodo Geográfico Proyectado'),
            latitud=float(request.form.get('lat', 19.4326)),
            longitud=float(request.form.get('lng', -99.1332)),
            fecha_caducidad=cad_date,
            urgente=urg,
            estado=status
        )
        db.session.add(p)
        db.session.commit()
        flash("Recurso emitido bajo protocolo de seguridad.", "success")
        return redirect(url_for('dashboard'))
    return render_template('publish.html')

@app.route('/validar_publicacion/<int:id>', methods=['POST'])
@login_required
def validar_publicacion(id):
    if current_user.email != 'admin@lifelink.com': return redirect(url_for('index'))
    p = Publicacion.query.get_or_404(id)
    p.estado = 'Verificado'
    db.session.commit()
    flash(f"Publicación auditada satisfactoriamente.", "success")
    return redirect(url_for('dashboard'))

@app.route('/calificar_solicitud/<int:id>', methods=['GET', 'POST'])
@login_required
def calificar_solicitud(id):
    s = Solicitud.query.get_or_404(id)
    if s.id_solicitante != current_user.id_usuario: return redirect(url_for('index'))
    if request.method == 'POST':
        r = Resena(id_solicitud=s.id_solicitud, id_evaluador=current_user.id_usuario, id_evaluado=s.publicacion.id_proveedor, estrellas=int(request.form['estrellas']), comentario=request.form['comentario'])
        s.estatus = 'Finalizado'
        db.session.add(r)
        db.session.commit()
        flash("Evaluación enviada. Gracias por fortalecer la red.", "success")
        return redirect(url_for('dashboard'))
    return render_template('review.html', solicitud=s)

@app.route('/borrar_publicacion/<int:id>', methods=['POST'])
@login_required
def borrar_publicacion(id):
    p = Publicacion.query.get_or_404(id)
    if p.id_proveedor == current_user.id_usuario or current_user.email == 'admin@lifelink.com':
        db.session.delete(p)
        db.session.commit()
        flash("Recurso retirado de la red global.", "success")
    return redirect(url_for('dashboard'))

@app.route('/buscar')
def buscar():
    q = request.args.get('q', '')
    today = date.today()
    res = Publicacion.query.filter(
        Publicacion.nombre.contains(q), 
        Publicacion.estado == 'Verificado',
        db.or_(Publicacion.fecha_caducidad == None, Publicacion.fecha_caducidad >= today)
    ).all()
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
    s = Solicitud(id_solicitante=current_user.id_usuario, id_publicacion=p.id_oferta_insumo, hospital_destino=request.form.get('hospital', 'Nodo de Entrega Particular'))
    db.session.add(s)
    db.session.commit()
    flash("Certificado emitido. Coordinar entrega vía chat.", "success")
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id_usuario).all()
    pub_ids = [p.id_oferta_insumo for p in pubs]
    sols = Solicitud.query.filter(Solicitud.id_publicacion.in_(pub_ids)).all() if pub_ids else []
    mis_p = Solicitud.query.filter_by(id_solicitante=current_user.id_usuario).all()
    
    stats = {
        'total_usuarios': Usuario.query.count(),
        'total_publicaciones': Publicacion.query.count(),
        'total_tickets': MensajeSoporte.query.count()
    } if current_user.email == 'admin@lifelink.com' else {}
    
    tickets = MensajeSoporte.query.all() if current_user.email == 'admin@lifelink.com' else []
    pendientes = Publicacion.query.filter_by(estado='Pendiente').all() if current_user.email == 'admin@lifelink.com' else []
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols, tickets_admin=tickets, mis_pedidos=mis_p, pubs_pendientes=pendientes, stats=stats)

@app.route('/chat/<int:id_solicitud>')
@login_required
def chat(id_solicitud):
    s = Solicitud.query.get_or_404(id_solicitud)
    if current_user.id_usuario not in [s.id_solicitante, s.publicacion.id_proveedor]: return redirect(url_for('index'))
    return render_template('chat.html', solicitud=s)

@app.route('/perfil')
@login_required
def perfil(): return render_template('perfil.html')

@app.route('/soporte')
def soporte(): return render_template('soporte.html')

@app.route('/enviar_soporte', methods=['POST'])
@login_required
def enviar_soporte():
    t = MensajeSoporte(id_usuario=current_user.id_usuario, asunto=request.form['asunto'], mensaje=request.form['mensaje'])
    db.session.add(t)
    db.session.commit()
    flash("Reporte enviado a la división jurídica de TechPulse.", "success")
    return redirect(url_for('soporte'))

@socketio.on('join')
def on_join(data): join_room(data['room'])

@socketio.on('enviar_mensaje')
def handle_msg(data): emit('nuevo_mensaje', {'msg': data['msg'], 'user': current_user.nombre}, room=data['room'])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Usuario.query.filter_by(email='admin@lifelink.com').first():
            db.session.add(Usuario(nombre="TechPulse Admin", email="admin@lifelink.com", password_hash=generate_password_hash("admin123"), telefono="0000000000", tipo_sangre="N/A", ubicacion="HQ México"))
            db.session.commit()
    socketio.run(app, debug=False)
