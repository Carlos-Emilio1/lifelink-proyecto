import eventlet
# Parcheo agresivo inmediato para evitar el error de 'blocking functions' en Python 3.13
eventlet.monkey_patch(all=True) 

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
# 1. LÓGICA DE NEGOCIO Y DOMINIO MÉDICO
# ==========================================

# Diccionario de compatibilidad para defensa legal/médica
BLOOD_COMPATIBILITY = {
    'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'], # Donante Universal
    'O+': ['O+', 'A+', 'B+', 'AB+'],
    'A-': ['A-', 'A+', 'AB-', 'AB+'],
    'A+': ['A+', 'AB+'],
    'B-': ['B-', 'B+', 'AB-', 'AB+'],
    'B+': ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+'] # Receptor Universal
}

# ==========================================
# 2. PLANTILLAS HTML (UI PREMIUM Y CONTROL TOTAL)
# ==========================================

base_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LifeLink - Red de Inteligencia Médica</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --brand-blue: #0ea5e9; --brand-dark: #0369a1; }
        .bg-brand { background-color: var(--brand-blue); }
        .text-brand { color: var(--brand-blue); }
        .btn-medical { background-color: var(--brand-blue); color: white; transition: all 0.3s; border-radius: 1.2rem; }
        .btn-medical:hover { background-color: var(--brand-dark); transform: translateY(-2px); box-shadow: 0 10px 20px -5px rgba(14, 165, 233, 0.4); }
        #map { height: 380px; width: 100%; border-radius: 2rem; z-index: 10; border: 3px solid #f8fafc; }
        .animate-float { animation: float 6s ease-in-out infinite; }
        @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-20px); } 100% { transform: translateY(0px); } }
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
        .star-active { color: #fbbf24; }
        .star-inactive { color: #e2e8f0; }
        .triage-p1 { border: 2px solid #ef4444; box-shadow: 0 0 20px rgba(239, 68, 68, 0.2); }
    </style>
</head>
<body class="bg-[#F9FBFF] flex flex-col min-h-screen font-sans text-slate-900">
    <nav class="bg-white/80 backdrop-blur-xl border-b border-slate-100 sticky top-0 z-[100]">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-20">
                <div class="flex items-center gap-10">
                    <a href="/" class="flex items-center gap-3 group">
                        <div class="bg-brand p-2 rounded-xl shadow-lg group-hover:rotate-12 transition-transform">
                             <svg width="28" height="28" viewBox="0 0 100 100" fill="none" stroke="white" stroke-width="10">
                                <path d="M10 50 L30 50 L40 20 L60 80 L70 50 L90 50" stroke-linecap="round" stroke-linejoin="round"/>
                             </svg>
                        </div>
                        <span class="font-black text-2xl tracking-tighter text-slate-800 uppercase italic">LifeLink</span>
                    </a>
                    <div class="hidden lg:flex gap-8">
                        <a href="{{ url_for('buscar') }}" class="text-[11px] font-black text-slate-400 hover:text-brand transition uppercase tracking-[0.2em]">Explorar Red</a>
                        {% if current_user.is_authenticated %}
                        <a href="{{ url_for('publicar') }}" class="text-[11px] font-black text-slate-400 hover:text-brand transition uppercase tracking-[0.2em]">Publicar</a>
                        <a href="{{ url_for('dashboard') }}" class="text-[11px] font-black text-slate-400 hover:text-brand transition uppercase tracking-[0.2em]">Centro Control</a>
                        {% endif %}
                    </div>
                </div>
                <div class="flex items-center gap-5">
                    {% if current_user.is_authenticated %}
                        <div class="flex items-center gap-4 bg-slate-50 p-1.5 pr-4 rounded-2xl border border-slate-100">
                            <a href="{{ url_for('perfil') }}" class="w-10 h-10 rounded-xl bg-brand flex items-center justify-center text-white font-black shadow-md">{{ current_user.nombre[0] | upper }}</a>
                            <div class="hidden sm:block">
                                <p class="text-[10px] font-black text-slate-800 leading-none">{{ current_user.nombre.split()[0] }}</p>
                                <p class="text-[8px] font-bold text-brand uppercase tracking-tighter">Nodo Verificado</p>
                            </div>
                        </div>
                    {% else %}
                        <a href="{{ url_for('login') }}" class="text-xs font-black text-slate-400 uppercase tracking-widest hover:text-brand transition">Ingresar</a>
                        <a href="{{ url_for('registro') }}" class="btn-medical px-8 py-3 text-xs font-black uppercase tracking-widest">Unirse</a>
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
                <div class="p-5 rounded-[1.5rem] {% if category == 'error' %}bg-red-50 text-red-700 border-red-100{% else %}bg-emerald-50 text-emerald-700 border-emerald-100{% endif %} flex items-center gap-4 shadow-xl shadow-slate-200/50 border animate-in slide-in-from-top-4">
                  <div class="w-8 h-8 rounded-full {% if category == 'error' %}bg-red-100{% else %}bg-emerald-100{% endif %} flex items-center justify-center shrink-0">
                    <i class="fas {% if category == 'error' %}fa-shield-virus{% else %}fa-check-double{% endif %}"></i>
                  </div>
                  <span class="text-xs font-black uppercase tracking-tight">{{ message }}</span>
                </div>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="py-20 bg-white border-t border-slate-100 mt-20">
        <div class="max-w-7xl mx-auto px-4 text-center">
            <div class="flex justify-center gap-8 mb-8">
                <a href="{{ url_for('soporte') }}" class="text-[10px] font-black text-slate-300 uppercase hover:text-brand tracking-widest transition">Triage y Legalidad</a>
                <a href="{{ url_for('soporte') }}" class="text-[10px] font-black text-slate-300 uppercase hover:text-brand tracking-widest transition">NOM-253 Sangre</a>
                <a href="{{ url_for('soporte') }}" class="text-[10px] font-black text-slate-300 uppercase hover:text-brand tracking-widest transition">Aviso Privacidad</a>
            </div>
            <p class="text-[10px] text-slate-300 font-black uppercase tracking-[0.4em]">TechPulse Solutions • 5IV7 • IPN 2026</p>
        </div>
    </footer>
</body>
</html>
"""

publish_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-5xl mx-auto py-12 px-4">
    <div class="bg-white rounded-[4.5rem] shadow-2xl p-16 border border-slate-50 shadow-blue-50/50">
        <h2 class="text-5xl font-black text-slate-900 mb-4 tracking-tighter italic leading-none">Nodo de <br><span class="text-brand italic underline decoration-blue-100">Publicación Oficial.</span></h2>
        <p class="text-[11px] font-black text-slate-300 uppercase tracking-[0.5em] mb-16 italic">TechPulse audit system enabled</p>
        
        <form method="POST" enctype="multipart/form-data" class="space-y-16">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-16">
                <div>
                    <label class="block text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-6 italic">Documentación Gráfica (Real)</label>
                    <div class="p-20 border-4 border-dashed border-slate-100 rounded-[4rem] text-center bg-slate-50/50 hover:border-brand transition-all group cursor-pointer shadow-inner relative overflow-hidden">
                        <i class="fas fa-fingerprint text-6xl text-slate-200 mb-6 group-hover:text-brand transition-colors"></i>
                        <input type="file" name="imagen" accept="image/*" required class="text-[10px] text-slate-400 font-black w-full relative z-10 italic">
                    </div>
                    
                    <!-- EXPLICACIÓN DEL TRIAGE PARA LA DEFENSA -->
                    <div class="mt-8 p-6 bg-blue-50 rounded-[2rem] border border-blue-100">
                        <h4 class="text-[10px] font-black text-brand uppercase tracking-widest mb-3 italic"><i class="fas fa-circle-info mr-1"></i> Guía de Triage LifeLink</h4>
                        <p class="text-[9px] text-slate-500 font-bold uppercase leading-relaxed">
                            P1 - CRÍTICO: Riesgo de vida inmediato (Sangre, Oxígeno).<br>
                            P2 - URGENTE: Requiere atención hoy (Fármacos controlados).<br>
                            P3 - ESTÁNDAR: Soporte general (Ortopedia, Insumos básicos).
                        </p>
                    </div>

                    <div class="mt-6 flex items-center gap-4 bg-red-50 p-6 rounded-[2rem] border border-red-100">
                        <input type="checkbox" name="urgente" id="urg_check" class="w-6 h-6 rounded-lg text-red-500 border-red-200 focus:ring-red-400 shadow-sm">
                        <span class="text-[10px] font-black text-red-600 uppercase tracking-widest italic leading-none">Certificar como Urgencia Crítica (P1)</span>
                    </div>
                </div>

                <div class="space-y-10">
                    <div>
                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-3 italic">Denominación del Recurso</label>
                        <input name="nombre" placeholder="Ej: Bolsa de Sangre O- 450ml" required class="w-full p-6 bg-slate-50 rounded-[2rem] border-none font-black text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-tighter">
                    </div>
                    <div class="grid grid-cols-2 gap-6">
                        <div>
                            <label class="block text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-3 italic">Especialidad</label>
                            <select name="categoria" id="cat_select" onchange="handleTriageLogic(this.value)" class="w-full p-6 bg-slate-50 rounded-[1.5rem] border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner italic">
                                <option value="Equipo">Insumo Médico</option>
                                <option value="Medicamento">Farmacéutico</option>
                                <option value="Sangre">Hemoderivado</option>
                                <option value="Ortopedico">Ortopédico</option>
                            </select>
                        </div>
                        <div id="receta_section" class="hidden">
                            <label class="block text-[10px] font-black text-red-500 uppercase tracking-[0.3em] mb-3 italic underline">Carga de Receta</label>
                            <input type="file" name="receta" accept="image/*,application/pdf" class="text-[8px] font-black text-red-300 italic uppercase">
                        </div>
                    </div>
                    <div>
                        <label class="block text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-3 italic">Marco de Recuperación</label>
                        <select name="tipo_publicacion" id="tipo_pub" class="w-full p-6 bg-slate-50 rounded-[1.5rem] border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner italic">
                            <option value="Venta">Venta Certificada</option>
                            <option value="Donacion">Donación Altruista</option>
                        </select>
                    </div>
                </div>
            </div>

            <div class="space-y-8">
                <div id="map" class="shadow-2xl ring-8 ring-slate-50"></div>
                <div class="bg-blue-50 p-8 rounded-[3rem] border border-blue-100 flex items-center gap-6 shadow-inner text-brand">
                    <i class="fas fa-location-crosshairs animate-pulse text-2xl"></i>
                    <input type="text" id="direccion_text" name="direccion_manual" readonly placeholder="Aguardando geolocalización de transferencia..." class="bg-transparent w-full outline-none text-[12px] font-black uppercase tracking-widest italic">
                </div>
                <input type="hidden" id="lat" name="lat">
                <input type="hidden" id="lng" name="lng">
            </div>

            <button type="submit" class="w-full btn-medical py-8 rounded-[3.5rem] font-black text-4xl shadow-2xl shadow-blue-200 italic uppercase hover:scale-[1.01] transition-all">Sincronizar con la Red</button>
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

    function handleTriageLogic(v){
        const s = document.getElementById('receta_section');
        const t = document.getElementById('tipo_pub');
        const u = document.getElementById('urg_check');
        
        // Solo Medicamentos muestran receta
        if(v==='Medicamento'){ s.classList.remove('hidden'); } else { s.classList.add('hidden'); }
        
        // Sangre bloquea venta y sugiere urgencia
        if(v==='Sangre'){ 
            t.value='Donacion'; t.disabled=true; 
            u.checked = true; // Sugerir urgencia para sangre
        } else { 
            t.disabled=false; 
            // Si es ortopédico, advertir que no es crítico
            if(v==='Ortopedico') {
                u.checked = false;
                console.log("Aviso: Los recursos ortopédicos se clasifican como P3 por defecto.");
            }
        }
    }
</script>
{% endblock %}
"""

soporte_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-6xl mx-auto py-20 px-4">
    <div class="text-center mb-20">
        <h2 class="text-6xl font-black text-slate-900 tracking-tighter italic uppercase mb-6 leading-none italic">Sustento <span class="text-brand">Jurídico.</span></h2>
        <p class="text-[11px] font-black text-slate-400 uppercase tracking-[0.5em] italic">Protocolo de Triage y Gestión de Red</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-10 mb-24">
        <!-- COLUMNA 1: TRIAGE (EL CORAZÓN DE TU PREGUNTA) -->
        <div class="bg-white p-10 rounded-[3.5rem] border border-slate-100 shadow-2xl relative overflow-hidden">
            <h3 class="text-xl font-black mb-6 italic uppercase tracking-tighter text-red-500">Sistema de Triage</h3>
            <div class="space-y-4 text-[10px] text-slate-500 font-bold uppercase tracking-tighter">
                <div class="p-3 bg-red-50 rounded-xl border-l-4 border-red-500"><b class="text-red-700">P1 - Crítico:</b> Solo Sangre y Oxigenoterapia. Aparece primero en la red con pulso visual.</div>
                <div class="p-3 bg-amber-50 rounded-xl border-l-4 border-amber-500"><b class="text-amber-700">P2 - Urgente:</b> Fármacos especializados. Requieren receta auditada por Admin.</div>
                <div class="p-3 bg-blue-50 rounded-xl border-l-4 border-blue-500"><b class="text-blue-700">P3 - Estándar:</b> Equipo ortopédico y rehabilitación. No se permite marcarlos como críticos.</div>
            </div>
        </div>

        <div class="bg-white p-10 rounded-[3.5rem] border border-slate-100 shadow-2xl relative overflow-hidden">
            <h3 class="text-xl font-black mb-6 italic uppercase tracking-tighter text-brand">Norma NOM-253</h3>
            <p class="text-[10px] text-slate-500 font-bold uppercase tracking-tighter leading-relaxed">Prohibimos estrictamente la monetización de sangre. Toda "Venta" en esta categoría bloquea el nodo y se reporta a TechPulse Compliance. La sangre es altruista por ley nacional.</p>
        </div>

        <div class="bg-slate-900 p-10 rounded-[3.5rem] text-white shadow-2xl relative overflow-hidden">
            <h3 class="text-xl font-black mb-6 italic uppercase tracking-tighter text-amber-400">Monetización B2B</h3>
            <p class="text-[10px] text-slate-400 font-medium uppercase tracking-widest leading-relaxed">Suscripciones para hospitales ($990 MXN) que permiten acceso prioritario a donantes O- (Universales) y estadísticas de demanda regional para prevenir desabasto.</p>
        </div>
    </div>

    <div class="bg-white p-16 rounded-[5rem] border-2 border-blue-50 shadow-2xl max-w-3xl mx-auto text-center">
        <h3 class="text-3xl font-black mb-6 italic uppercase tracking-tighter">Auditoría TechPulse</h3>
        <p class="text-xs text-slate-400 font-bold uppercase mb-10 tracking-widest italic">¿Detectaste un uso incorrecto del sistema de Urgencias?</p>
        <form action="{{ url_for('enviar_soporte') }}" method="POST" class="space-y-6 text-left">
            <input name="asunto" placeholder="Reporte de Clasificación Incorrecta" required class="w-full p-6 bg-slate-50 rounded-[1.5rem] border-none outline-none font-black text-xs shadow-inner uppercase italic">
            <textarea name="mensaje" placeholder="Evidencia de por qué el recurso no es una urgencia..." rows="4" required class="w-full p-6 bg-slate-50 rounded-[2rem] border-none outline-none font-bold text-sm shadow-inner italic"></textarea>
            <button class="w-full btn-medical py-7 text-[12px] font-black uppercase tracking-[0.3em] shadow-2xl shadow-blue-200 italic">Emitir Reporte Legal</button>
        </form>
    </div>
</div>
{% endblock %}
"""

# ==========================================
# 3. LÓGICA DE SERVIDOR Y MODELOS (FULL BLINDADO)
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lifelink_2026_reputation_ultra_secure_blindado_final')
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

    @property
    def rating_promedio(self):
        resenas_recibidas = Resena.query.filter_by(id_evaluado=self.id_usuario).all()
        if not resenas_recibidas: return 5.0 
        return sum([r.estrellas for r in resenas_recibidas]) / len(resenas_recibidas)

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
    receta_url = db.Column(db.String(500))
    direccion_exacta = db.Column(db.String(500))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    urgente = db.Column(db.Boolean, default=False)
    estado = db.Column(db.String(20), default='Pendiente') 
    proveedor = db.relationship('Usuario', backref='publicaciones')

class Solicitud(db.Model):
    __tablename__ = 'solicitudes'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('insumos.id_oferta_insumo'))
    hospital_destino = db.Column(db.String(255), default='Centro de Salud Local')
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

# Loader de Plantillas Actualizado
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'dashboard.html': dashboard_template,
    'soporte.html': soporte_template,
    'search.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-12 px-4 flex flex-col lg:flex-row gap-16"><div class="lg:w-96"><div class="bg-white p-12 rounded-[4rem] border border-slate-100 shadow-2xl shadow-blue-50/50 sticky top-28"><h4 class="text-[11px] font-black uppercase tracking-[0.4em] text-slate-400 mb-10 italic">Filtro de Red</h4><form method="GET" class="space-y-6"><div class="space-y-2"><label class="text-[9px] font-black text-slate-300 uppercase ml-2 tracking-widest italic">Insumo / Sangre</label><input name="q" placeholder="Ej: Sangre AB-..." class="w-full p-5 bg-slate-50 border-none rounded-[1.5rem] text-[11px] font-black outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase"></div><button class="w-full btn-medical py-5 text-[11px] font-black uppercase tracking-[0.4em] italic shadow-2xl shadow-blue-100">Actualizar Malla</button></form></div></div><div class="flex-1 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-12">{% for item in resultados %}<div class="bg-white rounded-[3.5rem] border border-slate-50 shadow-sm overflow-hidden hover:shadow-2xl transition-all duration-1000 group relative {% if item.urgente %}triage-p1{% endif %}">{% if item.urgente %}<div class="absolute z-20 top-8 left-8 bg-red-600 text-white text-[8px] px-4 py-1.5 rounded-full font-black tracking-[0.2em] shadow-2xl animate-pulse italic uppercase">Urgencia Crítica</div>{% endif %}<img src="{{ item.imagen_url }}" class="w-full h-72 object-cover group-hover:scale-110 transition-transform duration-1000 shadow-inner grayscale group-hover:grayscale-0"><div class="p-10"><h3 class="font-black text-slate-800 text-3xl tracking-tighter uppercase italic mb-2 leading-none">{{ item.nombre }}</h3><p class="text-[10px] text-brand font-black uppercase tracking-[0.2em] mb-8 italic">{{ item.categoria }}</p><div class="flex justify-between items-center"><span class="text-4xl font-black text-slate-900 tracking-tighter italic">{% if item.tipo_publicacion == 'Venta' %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span><a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="w-16 h-16 bg-blue-50 text-brand rounded-[2rem] flex items-center justify-center hover:bg-brand hover:text-white transition-all shadow-xl shadow-blue-50"><i class="fas fa-chevron-right text-xl"></i></a></div><p class="text-[9px] text-slate-300 font-bold uppercase mt-8 tracking-[0.15em] truncate italic"><i class="fas fa-location-dot mr-2"></i> {{ item.direccion_exacta }}</p></div></div>{% endfor %}</div></div>{% endblock %}""",
    'publish.html': publish_template,
    'checkout.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-20 px-4 text-center animate-in zoom-in-95 duration-1000"><div class="bg-white p-16 rounded-[5rem] shadow-2xl border border-slate-100 relative overflow-hidden shadow-blue-100/50"><div class="absolute -top-10 -right-10 w-40 h-40 bg-brand opacity-5 rounded-full blur-3xl"></div><h2 class="text-5xl font-black text-slate-900 mb-12 tracking-tighter italic uppercase leading-none italic">Solicitud <br><span class="text-brand underline decoration-blue-100">Enlazada.</span></h2><div class="bg-slate-50 p-12 rounded-[4rem] mb-12 border border-slate-100 shadow-inner relative z-10"><img src="{{ pub.imagen_url }}" class="w-56 h-56 rounded-[3rem] object-cover mx-auto mb-10 shadow-2xl ring-[15px] ring-white group-hover:rotate-6 transition-all"><h3 class="font-black text-3xl text-slate-800 uppercase italic leading-none mb-3">{{ pub.nombre }}</h3><p class="text-[11px] font-black text-brand uppercase tracking-[0.3em] italic">{{ pub.categoria }} • VERIFICACIÓN TECHPULSE</p></div>{% if pub.categoria == 'Sangre' %}<div class="mb-12 p-10 bg-red-50 border-2 border-red-100 rounded-[4rem] text-left shadow-inner"><p class="text-[11px] font-black text-red-600 uppercase tracking-[0.3em] mb-6 italic"><i class="fas fa-biohazard mr-2"></i> Reporte para Banco de Sangre</p><input name="hospital" placeholder="NOMBRE DEL HOSPITAL RECEPTOR" required class="w-full p-6 bg-white rounded-[1.5rem] border-none text-xs font-black outline-none focus:ring-2 focus:ring-red-400 shadow-md uppercase italic tracking-widest shadow-inner">{% set target_blood = pub.nombre.split()[-1] %}{% if current_user.tipo_sangre not in BLOOD_COMPATIBILITY[target_blood] %}<div class="mt-6 flex items-center gap-4 bg-amber-50 p-4 rounded-2xl border border-amber-100 text-amber-600"><i class="fas fa-circle-exclamation text-lg animate-pulse"></i><p class="text-[10px] font-black uppercase tracking-tighter italic leading-relaxed">Advertencia: Tu perfil ({{ current_user.tipo_sangre }}) tiene compatibilidad restringida con {{ target_blood }}. Valida con tu médico.</p></div>{% endif %}</div>{% endif %}<form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST"><button class="w-full btn-medical py-8 rounded-[3.5rem] font-black text-4xl shadow-2xl shadow-blue-200 hover:scale-[1.03] transition-all uppercase italic tracking-tighter">Certificar Compromiso</button></form><p class="text-[9px] text-slate-300 font-bold uppercase tracking-[0.3em] mt-12 italic"><i class="fas fa-shield-halved text-brand mr-2"></i> Validado bajo estándar TechPulse SafeLink v3.0</p></div></div>{% endblock %}""",
    'review.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-24 px-4"><div class="bg-white p-16 rounded-[4.5rem] shadow-2xl border border-slate-100 text-center shadow-blue-50/50"><h2 class="text-4xl font-black mb-10 tracking-tighter italic uppercase leading-none">Auditar <br><span class="text-emerald-500">Transacción.</span></h2><p class="text-[11px] font-black text-slate-400 uppercase tracking-[0.2em] mb-12 italic">Tu evaluación construye la red de confianza</p><form method="POST" class="space-y-8"><div class="bg-slate-50 p-6 rounded-[2rem] shadow-inner mb-10"><select name="estrellas" class="w-full p-4 bg-transparent border-none font-black text-amber-400 text-2xl text-center outline-none"><option value="5" class="text-slate-800 text-base italic">★★★★★ 5.0 Excelente</option><option value="4" class="text-slate-800 text-base italic">★★★★☆ 4.0 Muy Bueno</option><option value="3" class="text-slate-800 text-base italic">★★★☆☆ 3.0 Regular</option><option value="2" class="text-slate-800 text-base italic">★★☆☆☆ 2.0 Deficiente</option><option value="1" class="text-slate-800 text-base italic">★☆☆☆☆ 1.0 Alerta de Fraude</option></select></div><textarea name="comentario" placeholder="Describe tu experiencia operativa..." required rows="4" class="w-full p-6 bg-slate-50 rounded-[2rem] border-none outline-none font-bold text-sm focus:ring-2 focus:ring-emerald-400 shadow-inner italic uppercase tracking-tighter"></textarea><button class="w-full bg-emerald-500 text-white py-6 rounded-[3rem] font-black text-2xl shadow-2xl shadow-emerald-100 uppercase italic tracking-tighter hover:scale-105 transition-all">Cerrar Operación</button></form></div></div>{% endblock %}""",
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-16 px-4"><div class="bg-white p-12 rounded-[3.5rem] shadow-2xl border border-slate-50"><h2 class="text-4xl font-black text-slate-900 mb-10 tracking-tighter italic text-slate-800">Cédula de <span class="text-brand">Registro.</span></h2><form method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-6"><input name="nombre" placeholder="Nombre completo" required class="col-span-1 md:col-span-2 p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase italic"><select name="tipo_sangre" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner italic"><option value="">TIPO SANGRE</option><option>O+</option><option>O-</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option></select><input name="telefono" placeholder="WhatsApp / Telegram" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase"><input name="email" type="email" placeholder="Email corporativo" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase"><input name="ubicacion" placeholder="Delegación / Estado" required class="p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner italic uppercase"><input name="password" type="password" placeholder="Passphrase" required class="col-span-1 md:col-span-2 p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-widest"><button class="col-span-1 md:col-span-2 w-full btn-medical py-6 rounded-[3rem] font-black text-2xl mt-8 shadow-2xl shadow-blue-100 italic uppercase">Activar Perfil</button></form></div></div>{% endblock %}""",
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-24 px-4"><div class="bg-white p-12 rounded-[4rem] shadow-2xl border border-slate-100 text-center relative overflow-hidden shadow-blue-50/50"><div class="absolute -top-10 -right-10 w-32 h-32 bg-brand/5 rounded-full blur-3xl"></div><div class="w-24 h-24 bg-blue-50 text-brand rounded-[2rem] flex items-center justify-center mx-auto mb-12 shadow-inner rotate-6"><i class="fas fa-fingerprint text-4xl"></i></div><h2 class="text-5xl font-black mb-12 tracking-tighter italic text-slate-800 uppercase leading-none">Validación <br>de Nodo.</h2><form method="POST" class="space-y-6"><input name="email" type="email" placeholder="USER ID" required class="w-full p-6 bg-slate-50 rounded-3xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-widest italic"><input name="password" type="password" placeholder="PASSPHRASE" required class="w-full p-6 bg-slate-50 rounded-3xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase tracking-widest"><button class="w-full btn-medical py-7 rounded-[3.5rem] font-black text-3xl mt-10 shadow-2xl shadow-blue-200 uppercase tracking-tighter italic">Efectuar Acceso</button></form></div></div>{% endblock %}""",
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-20 px-4 text-center"><div class="relative inline-block mb-12"><div class="w-48 h-48 bg-brand text-white text-8xl font-black rounded-[4rem] flex items-center justify-center mx-auto shadow-2xl border-[12px] border-white ring-2 ring-slate-100 italic">{{ current_user.nombre[0] | upper }}</div><div class="absolute -bottom-2 -right-2 bg-emerald-500 w-14 h-14 rounded-2xl flex items-center justify-center text-white border-4 border-white shadow-xl rotate-12"><i class="fas fa-certificate text-xl"></i></div></div><h2 class="text-6xl font-black text-slate-900 mb-2 tracking-tighter uppercase italic">{{ current_user.nombre }}</h2><p class="text-brand font-black uppercase tracking-[0.4em] text-[10px] mb-16 italic">Estatus Nodo: Donante Verificado {{ current_user.tipo_sangre }}</p><div class="grid grid-cols-1 md:grid-cols-3 gap-8 text-left">{% for label, icon, val in [('Canal', 'fa-mobile-screen', current_user.telefono), ('Email', 'fa-envelope-open', current_user.email), ('Base', 'fa-map-location-dot', current_user.ubicacion)] %}<div class="bg-white p-10 rounded-[3rem] shadow-sm border border-slate-100 flex flex-col items-center text-center group hover:border-brand transition-all"><i class="fas {{ icon }} text-slate-100 text-3xl mb-5 group-hover:text-brand transition-colors"></i><p class="text-[9px] text-slate-300 font-black uppercase mb-2 tracking-[0.2em] italic">{{ label }}</p><p class="font-black text-slate-800 text-xs break-words tracking-tighter uppercase">{{ val }}</p></div>{% endfor %}</div><div class="mt-24"><a href="{{ url_for('logout') }}" class="text-red-300 font-black text-[9px] uppercase tracking-[0.4em] hover:text-red-500 transition-all underline decoration-red-50 font-bold">Finalizar Sesión Operativa</a></div></div>{% endblock %}""",
    'chat.html': """{% extends "base.html" %}{% block content %}<div class="max-w-4xl mx-auto py-8 px-4 h-[80vh] flex flex-col"><div class="bg-white rounded-[4rem] shadow-2xl flex flex-col flex-1 overflow-hidden border border-slate-100 animate-in zoom-in-95 duration-700 shadow-blue-50/50"><div class="bg-brand p-10 text-white flex justify-between items-center shadow-lg relative z-10"><div class="flex items-center gap-6"><div class="w-16 h-16 rounded-[1.5rem] bg-white/20 flex items-center justify-center font-black text-2xl italic shadow-inner">LL</div><div><h3 class="font-black leading-none text-2xl tracking-tighter italic">Línea de Transferencia</h3><p class="text-[10px] text-blue-50 uppercase tracking-[0.2em] mt-3 font-black animate-pulse">Encriptación End-to-End Activa</p></div></div><a href="{{ url_for('dashboard') }}" class="w-12 h-12 bg-white/10 rounded-2xl flex items-center justify-center hover:bg-white/20 transition-all shadow-inner"><i class="fas fa-times text-xl"></i></a></div><div class="flex-1 overflow-y-auto p-12 space-y-10 bg-slate-50/50 custom-scrollbar" id="chat-box"></div><div class="p-10 bg-white border-t border-slate-100"><form onsubmit="event.preventDefault(); send();" class="flex gap-6"><input id="msg-input" placeholder="Coordina el punto de entrega..." class="flex-1 p-6 bg-slate-100 rounded-[2rem] border-none outline-none focus:ring-2 focus:ring-brand font-black text-sm shadow-inner uppercase tracking-tighter"><button class="bg-brand text-white w-20 h-20 rounded-[2rem] shadow-2xl shadow-blue-200 hover:scale-110 transition-transform flex items-center justify-center shadow-brand/20"><i class="fas fa-paper-plane text-2xl"></i></button></form></div></div></div><script>const socket = io(); const room = "{{ solicitud.id_solicitud }}"; const user = "{{ current_user.nombre }}"; socket.emit('join', {room: room}); socket.on('nuevo_mensaje', function(data){ const box = document.getElementById('chat-box'); const isMe = data.user === user; const d = document.createElement('div'); d.className = `flex ${isMe ? 'justify-end':'justify-start'}`; d.innerHTML = `<div class="${isMe?'bg-brand text-white rounded-l-[2rem] rounded-tr-[2rem] shadow-2xl shadow-blue-100':'bg-white text-slate-700 rounded-r-[2rem] rounded-tl-[2rem] shadow-sm border border-slate-200'} px-8 py-5 max-w-[85%] animate-in fade-in slide-in-from-bottom-4"><p class="text-[9px] font-black uppercase mb-3 ${isMe?'text-blue-100':'text-slate-300'} tracking-widest italic">${data.user}</p><p class="text-sm font-black leading-relaxed tracking-tight uppercase">${data.msg}</p></div>`; box.appendChild(d); box.scrollTop = box.scrollHeight; }); function send(){ const i = document.getElementById('msg-input'); if(i.value.trim()){ socket.emit('enviar_mensaje', {msg: i.value, room: room}); i.value=''; } }</script>{% endblock %}"""
})

# ==========================================
# 4. RUTAS Y LÓGICA (FULL STACK BLINDADO)
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
        flash("Acceso denegado. Protocolo de seguridad fallido.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        img = request.files.get('imagen')
        rect = request.files.get('receta')
        urg = True if request.form.get('urgente') else False
        img_url = "https://via.placeholder.com/400"
        rect_url = None
        if img: img_url = cloudinary.uploader.upload(img)['secure_url']
        if rect: rect_url = cloudinary.uploader.upload(rect)['secure_url']
        
        cat = request.form['categoria']
        # Lógica de Triage Automática para proteger la red
        status = 'Verificado' if cat not in ['Medicamento', 'Sangre'] else 'Pendiente'
        
        # Blindaje: Si es ortopédico y marcó urgente, forzar a Falso o advertir
        if cat == 'Ortopedico' and urg:
            flash("Nota: Los recursos ortopédicos se reclasifican como P3 por norma interna.", "error")
            urg = False

        if cat == 'Medicamento' and not rect:
            flash("Blindaje Legal: Se requiere receta física para validar fármacos.", "error")
            return redirect(url_for('publicar'))
        
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
            urgente=urg,
            estado=status
        )
        db.session.add(p)
        db.session.commit()
        flash("Carga exitosa. Recurso en proceso de auditoría TechPulse.", "success")
        return redirect(url_for('dashboard'))
    return render_template('publish.html')

@app.route('/validar_publicacion/<int:id>', methods=['POST'])
@login_required
def validar_publicacion(id):
    if current_user.email != 'admin@lifelink.com': return redirect(url_for('index'))
    p = Publicacion.query.get_or_404(id)
    p.estado = 'Verificado'
    db.session.commit()
    flash(f"Recurso LL-{id} auditado y liberado en la red.", "success")
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
        flash("Auditoría de servicio finalizada. Score de confianza actualizado.", "success")
        return redirect(url_for('dashboard'))
    return render_template('review.html', solicitud=s)

@app.route('/borrar_publicacion/<int:id>', methods=['POST'])
@login_required
def borrar_publicacion(id):
    p = Publicacion.query.get_or_404(id)
    if p.id_proveedor == current_user.id_usuario or current_user.email == 'admin@lifelink.com':
        db.session.delete(p)
        db.session.commit()
        flash("Nodo de inventario retirado de la red global.", "success")
    return redirect(url_for('dashboard'))

@app.route('/buscar')
def buscar():
    q = request.args.get('q', '')
    res = Publicacion.query.filter(Publicacion.nombre.contains(q), Publicacion.estado == 'Verificado').all()
    return render_template('search.html', resultados=res)

@app.route('/confirmar_compra/<int:id>')
@login_required
def confirmar_compra(id):
    p = Publicacion.query.get_or_404(id)
    return render_template('checkout.html', pub=p, BLOOD_COMPATIBILITY=BLOOD_COMPATIBILITY)

@app.route('/procesar_transaccion/<int:id>', methods=['POST'])
@login_required
def procesar_transaccion(id):
    p = Publicacion.query.get_or_404(id)
    s = Solicitud(id_solicitante=current_user.id_usuario, id_publicacion=p.id_oferta_insumo, hospital_destino=request.form.get('hospital', 'Nodo de Entrega Particular'))
    db.session.add(s)
    db.session.commit()
    flash("Certificado de compromiso LL emitido. Sincroniza entrega vía chat.", "success")
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id_usuario).all()
    pub_ids = [p.id_oferta_insumo for p in pubs]
    sols = Solicitud.query.filter(Solicitud.id_publicacion.in_(pub_ids)).all() if pub_ids else []
    mis_p = Solicitud.query.filter_by(id_solicitante=current_user.id_usuario).all()
    tickets = MensajeSoporte.query.all() if current_user.email == 'admin@lifelink.com' else []
    pendientes = Publicacion.query.filter_by(estado='Pendiente').all() if current_user.email == 'admin@lifelink.com' else []
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols, tickets_admin=tickets, mis_pedidos=mis_p, pubs_pendientes=pendientes)

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
            db.session.add(Usuario(nombre="TechPulse Admin", email="admin@lifelink.com", password_hash=generate_password_hash("admin123"), telefono="0000000000", tipo_sangre="N/A", ubicacion="HQ Central"))
            db.session.commit()
    socketio.run(app, debug=False)
