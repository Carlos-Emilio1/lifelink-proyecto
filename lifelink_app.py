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
# 1. PLANTILLAS HTML (UI PREMIUM Y BLINDAJE LEGAL)
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
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
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
                        <span class="font-black text-xl tracking-tighter text-slate-800 uppercase italic">LifeLink</span>
                    </a>
                </div>
                <div class="flex items-center gap-6">
                    <div class="hidden md:flex gap-6">
                        <a href="{{ url_for('buscar') }}" class="text-xs font-black text-slate-500 hover:text-brand transition uppercase tracking-widest">Recursos</a>
                        {% if current_user.is_authenticated %}
                        <a href="{{ url_for('publicar') }}" class="text-xs font-black text-slate-500 hover:text-brand transition uppercase tracking-widest">Publicar</a>
                        <a href="{{ url_for('dashboard') }}" class="text-xs font-black text-slate-500 hover:text-brand transition uppercase tracking-widest">Mi Gestión</a>
                        {% endif %}
                    </div>
                    {% if current_user.is_authenticated %}
                        <div class="flex items-center gap-3">
                            <a href="{{ url_for('perfil') }}" class="w-10 h-10 rounded-2xl bg-blue-50 flex items-center justify-center text-brand font-black border border-blue-100 hover:bg-brand hover:text-white transition-all shadow-sm">{{ current_user.nombre[0] | upper }}</a>
                        </div>
                    {% else %}
                        <a href="{{ url_for('login') }}" class="text-xs font-black text-slate-400 uppercase tracking-widest">Ingresar</a>
                        <a href="{{ url_for('registro') }}" class="btn-medical px-6 py-2.5 text-xs font-black uppercase tracking-widest shadow-lg">Unirse</a>
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
                <div class="p-4 rounded-2xl {% if category == 'error' %}bg-red-50 text-red-700 border border-red-100{% else %}bg-emerald-50 text-emerald-700 border border-emerald-100{% endif %} flex items-center gap-3 shadow-sm border animate-in slide-in-from-top-2">
                  <i class="fas {% if category == 'error' %}fa-circle-xmark{% else %}fa-circle-check{% endif %}"></i>
                  <span class="text-sm font-bold">{{ message }}</span>
                </div>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="py-16 bg-white border-t border-slate-100 mt-20">
        <div class="max-w-7xl mx-auto px-4">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12 text-center md:text-left">
                <div class="col-span-1 md:col-span-2">
                    <span class="font-black text-2xl tracking-tighter text-slate-800 mb-4 block">LifeLink</span>
                    <p class="text-sm text-slate-400 leading-relaxed max-w-sm">Tecnología diseñada por TechPulse para la coordinación ética y segura de recursos médicos críticos en tiempo real.</p>
                </div>
                <div>
                    <h5 class="font-black text-[10px] uppercase tracking-[0.2em] text-slate-300 mb-4">Legalidad</h5>
                    <ul class="space-y-2 text-sm text-slate-500 font-bold">
                        <li><a href="{{ url_for('soporte') }}" class="hover:text-brand">Términos de Uso</a></li>
                        <li><a href="{{ url_for('soporte') }}" class="hover:text-brand">Privacidad (LFPDPPP)</a></li>
                        <li><a href="{{ url_for('soporte') }}" class="hover:text-brand">Bioética Médica</a></li>
                    </ul>
                </div>
                <div>
                    <h5 class="font-black text-[10px] uppercase tracking-[0.2em] text-slate-300 mb-4">Proyecto</h5>
                    <p class="text-[10px] text-slate-400 font-bold uppercase mb-1">Grupo 5IV7</p>
                    <p class="text-[10px] text-slate-400 font-bold uppercase mb-4">IPN CECyT 9</p>
                    <div class="flex justify-center md:justify-start gap-4 text-slate-400">
                        <i class="fab fa-github"></i>
                        <i class="fab fa-linkedin"></i>
                    </div>
                </div>
            </div>
            <div class="border-t border-slate-50 pt-8 text-center">
                <p class="text-[9px] text-slate-300 font-medium uppercase tracking-[0.3em]">LifeLink • TechPulse © 2026 • Prototipo de Alta Fidelidad</p>
            </div>
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
                <div class="inline-flex items-center px-4 py-2 rounded-2xl text-[10px] font-black bg-blue-50 text-brand uppercase tracking-widest mb-8 border border-blue-100 shadow-sm">
                    <span class="relative flex h-2 w-2 mr-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand opacity-75"></span><span class="relative inline-flex rounded-full h-2 w-2 bg-brand"></span></span>
                    Red Solidaria en Tiempo Real
                </div>
                <h1 class="text-6xl tracking-tighter font-black text-slate-900 sm:text-7xl leading-[1] mb-8">
                    La salud es una <span class="text-brand italic underline decoration-blue-200">red compartida.</span>
                </h1>
                <p class="text-lg text-slate-500 max-w-lg leading-relaxed mb-10 font-medium">
                    Gestiona donaciones de sangre, insumos médicos y equipos especializados con validación legal y logística integrada.
                </p>
                <div class="flex flex-wrap gap-5 sm:justify-center lg:justify-start">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-12 py-5 font-black text-lg shadow-2xl shadow-blue-200 flex items-center gap-3">
                        <i class="fas fa-hand-holding-medical"></i> Buscar Insumos
                    </a>
                    <a href="{{ url_for('registro') }}" class="bg-white border-2 border-slate-200 px-12 py-5 rounded-2xl font-black text-lg hover:border-brand transition shadow-sm">Unirse</a>
                </div>
            </div>
            <div class="mt-16 lg:mt-0 lg:col-span-6 flex justify-center">
                <div class="relative w-full max-w-md animate-float">
                    <div class="absolute inset-0 bg-blue-500 rounded-[3rem] rotate-3 opacity-5"></div>
                    <div class="relative bg-white p-5 rounded-[3rem] shadow-2xl border-8 border-slate-50 overflow-hidden">
                        <img class="w-full h-[550px] rounded-[2rem] object-cover hover:scale-105 transition-transform duration-700" src="https://images.unsplash.com/photo-1551076805-e1869033e561?q=80&w=1000&auto=format&fit=crop" alt="LifeLink Medical">
                        <div class="absolute bottom-10 left-10 right-10 bg-white/90 backdrop-blur p-4 rounded-2xl border border-white shadow-xl">
                            <div class="flex items-center gap-3">
                                <div class="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
                                <p class="text-[10px] font-black uppercase text-slate-700 tracking-tighter">Última donación: Hace 5 minutos en CDMX</p>
                            </div>
                        </div>
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
    <div class="mb-12">
        <h1 class="text-5xl font-black text-slate-900 tracking-tighter mb-2">Panel de <span class="text-brand">Gestión.</span></h1>
        <div class="flex gap-4">
            <span class="text-[10px] font-black uppercase bg-blue-50 text-brand px-3 py-1 rounded-full border border-blue-100 italic">{{ current_user.tipo_sangre }}</span>
            <span class="text-[10px] font-black uppercase bg-slate-100 text-slate-500 px-3 py-1 rounded-full">{{ current_user.ubicacion }}</span>
        </div>
    </div>

    {% if current_user.email == 'admin@lifelink.com' %}
    <div class="mb-12 bg-red-50 p-10 rounded-[2.5rem] border-2 border-red-100 shadow-sm">
        <h3 class="text-2xl font-black text-red-700 mb-6 flex items-center gap-3"><i class="fas fa-shield-halved"></i> Centro de Control Admin</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {% for ticket in tickets_admin %}<div class="bg-white p-6 rounded-3xl shadow-sm border border-red-50">
                <p class="text-[9px] font-black text-red-400 uppercase mb-2">Ticket #LL-{{ ticket.id_ticket }} • {{ ticket.usuario.nombre }}</p>
                <h5 class="font-black text-slate-800 text-sm mb-2">{{ ticket.asunto }}</h5>
                <p class="text-xs text-slate-500 mb-6 leading-relaxed">{{ ticket.mensaje }}</p>
                <a href="mailto:{{ ticket.usuario.email }}" class="inline-block bg-brand text-white px-6 py-2.5 rounded-xl text-[10px] font-black uppercase shadow-md">Atender vía Mail</a>
            </div>{% endfor %}
        </div>
    </div>
    {% endif %}

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <!-- SOLICITUDES QUE ME HICIERON -->
        <div class="lg:col-span-2 space-y-8">
            <div class="flex items-center justify-between">
                <h4 class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] flex items-center gap-3">
                    <i class="fas fa-inbox text-brand"></i> Bandeja de Coordinación
                </h4>
                <span class="text-[9px] font-black text-slate-300 uppercase italic">Revisa recetas antes de aceptar</span>
            </div>
            
            <div class="grid gap-6">
                {% for s in solicitudes_recibidas %}<div class="bg-white p-8 rounded-[2.5rem] shadow-sm border border-slate-100 flex flex-col md:flex-row justify-between items-center group hover:border-brand transition-all duration-300">
                    <div class="mb-4 md:mb-0">
                        <p class="text-[10px] font-black text-brand mb-1 uppercase tracking-widest">Pedido Activo #{{ s.id_solicitud }}</p>
                        <h5 class="font-black text-slate-800 text-xl">{{ s.publicacion.nombre }}</h5>
                        <p class="text-xs text-slate-400 mt-1">Interesado: <b>{{ s.solicitante.nombre }}</b> • {{ s.solicitante.telefono }}</p>
                        {% if s.hospital_destino != 'N/A' %}<p class="text-[10px] text-emerald-600 font-black mt-2 uppercase tracking-tighter italic">Destino: Hospital {{ s.hospital_destino }}</p>{% endif %}
                    </div>
                    <div class="flex gap-4 w-full md:w-auto">
                        <a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="flex-1 md:flex-none btn-medical px-8 py-3.5 text-[10px] font-black uppercase tracking-widest shadow-xl">Abrir Chat</a>
                    </div>
                </div>{% else %}<div class="p-20 text-center bg-white rounded-[3rem] border-4 border-dashed border-slate-50"><p class="text-slate-300 font-black uppercase text-xs tracking-widest">Sin solicitudes entrantes</p></div>{% endfor %}
            </div>

            <!-- MIS PEDIDOS (LAS COSAS QUE YO PEDI) -->
            <div class="pt-10 border-t border-slate-100">
                <h4 class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-8">Mis Requerimientos Realizados</h4>
                <div class="grid gap-4">
                    {% for s in mis_pedidos %}<div class="bg-slate-50 p-6 rounded-3xl border border-slate-100 flex justify-between items-center opacity-75 hover:opacity-100 transition-opacity">
                        <div class="flex items-center gap-4"><img src="{{ s.publicacion.imagen_url }}" class="w-12 h-12 rounded-2xl object-cover grayscale"><div class="text-sm font-black">{{ s.publicacion.nombre }}</div></div>
                        <a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="bg-white border border-slate-200 px-4 py-2 rounded-xl text-[10px] font-black text-slate-500 uppercase">Ver Chat</a>
                    </div>{% endfor %}
                </div>
            </div>
        </div>

        <!-- MIS PUBLICACIONES -->
        <div class="space-y-8">
            <h4 class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Mis Publicaciones Activas</h4>
            <div class="grid gap-4">
                {% for p in publicaciones %}<div class="bg-white p-5 rounded-[2rem] shadow-sm border border-slate-100 flex items-center gap-4 relative overflow-hidden group">
                    <img src="{{ p.imagen_url }}" class="w-16 h-16 rounded-2xl object-cover shadow-inner group-hover:scale-110 transition-transform">
                    <div class="flex-1 min-w-0">
                        <div class="text-sm font-black text-slate-800 truncate mb-1">{{ p.nombre }}</div>
                        <div class="flex items-center gap-2">
                            <span class="bg-blue-50 text-brand px-2 py-0.5 rounded-md text-[8px] font-black uppercase tracking-tighter">{{ p.estado }}</span>
                            <span class="text-[8px] font-black text-slate-300 uppercase tracking-widest">ID: LL-{{ p.id_oferta_insumo }}</span>
                        </div>
                    </div>
                    <form action="{{ url_for('borrar_publicacion', id=p.id_oferta_insumo) }}" method="POST">
                        <button type="submit" class="p-3 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-2xl transition-colors"><i class="fas fa-trash-can text-sm"></i></button>
                    </form>
                </div>{% else %}<p class="text-center text-slate-300 text-[10px] font-black uppercase py-10 tracking-widest">No has publicado nada</p>{% endfor %}
            </div>
            
            <div class="bg-brand p-8 rounded-[2.5rem] shadow-2xl shadow-blue-100 text-white relative overflow-hidden">
                <div class="absolute -top-10 -right-10 w-32 h-32 bg-white/10 rounded-full blur-2xl"></div>
                <h5 class="font-black text-lg mb-2 italic">¿Necesitas algo más?</h5>
                <p class="text-[10px] text-blue-100 font-bold mb-6 leading-relaxed uppercase tracking-tighter">Tu actividad ayuda a salvar vidas hoy.</p>
                <a href="{{ url_for('publicar') }}" class="block w-full bg-white text-brand py-4 rounded-2xl text-center text-[10px] font-black uppercase tracking-widest hover:scale-105 transition-transform shadow-lg">Nueva Publicación</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

# ==========================================
# 2. LÓGICA DE SERVIDOR Y MODELOS
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lifelink_2026_pro_secure_vfinal')
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
    receta_url = db.Column(db.String(500))
    direccion_exacta = db.Column(db.String(500))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    estado = db.Column(db.String(20), default='Disponible')
    proveedor = db.relationship('Usuario', backref='publicaciones')

class Solicitud(db.Model):
    __tablename__ = 'solicitudes'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('insumos.id_oferta_insumo'))
    hospital_destino = db.Column(db.String(255), default='N/A')
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
    'dashboard.html': dashboard_template,
    'soporte.html': """{% extends "base.html" %}{% block content %}<div class="max-w-5xl mx-auto py-16 px-4"><div class="text-center mb-16"><h2 class="text-5xl font-black text-slate-900 mb-4 tracking-tighter">Soporte y <span class="text-brand italic">Legalidad.</span></h2><p class="text-slate-500 font-bold uppercase text-[10px] tracking-widest">TechPulse Compliance Protocol</p></div><div class="grid grid-cols-1 md:grid-cols-2 gap-10 mb-20"><div class="bg-white p-10 rounded-[2.5rem] border border-slate-100 shadow-xl shadow-slate-100"><h3 class="text-2xl font-black mb-8 flex items-center gap-3"><i class="fas fa-scale-balanced text-brand"></i> Marco Normativo</h3><div class="space-y-6 text-sm text-slate-500 leading-relaxed font-medium"><p><b>1. Donación de Sangre:</b> En cumplimiento con la Norma Oficial Mexicana NOM-253-SSA1-2012, LifeLink prohíbe estrictamente la venta de sangre o tejidos. Nuestra plataforma es únicamente una red de coordinación altruista.</p><p><b>2. Medicamentos:</b> Para insumos controlados, el sistema actúa como repositorio de recetas para facilitar el cumplimiento de la Ley General de Salud.</p><p><b>3. Datos Personales:</b> Protegemos tu información bajo el estándar LFPDPPP.</p></div></div><div class="bg-slate-900 p-10 rounded-[2.5rem] text-white shadow-2xl"><h3 class="text-2xl font-black mb-8 flex items-center gap-3"><i class="fas fa-coins text-amber-400"></i> Modelo de Negocio</h3><ul class="space-y-6 text-sm text-slate-400"><li class="flex items-start gap-3"><div class="w-2 h-2 bg-amber-400 rounded-full mt-2"></div><div><b>Suscripciones Hospitalarias:</b> Bancos de sangre y clínicas pagan membresías para acceso a dashboards de donantes recurrentes.</div></li><li class="flex items-start gap-3"><div class="w-2 h-2 bg-brand rounded-full mt-2"></div><div><b>Logística Premium:</b> Alianzas con transportistas especializados para entregas de equipo pesado con un 5% de comisión.</div></li></ul></div></div><div class="bg-white p-12 rounded-[3rem] border border-blue-50 shadow-2xl"><h3 class="text-3xl font-black text-center mb-10 tracking-tighter">¿Problemas con un usuario?</h3><form action="{{ url_for('enviar_soporte') }}" method="POST" class="max-w-2xl mx-auto space-y-4"><input name="asunto" placeholder="Motivo del reporte" required class="w-full p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand"><textarea name="mensaje" placeholder="Detalles de la situación..." rows="5" required class="w-full p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand"></textarea><button class="w-full btn-medical py-5 text-[10px] font-black uppercase tracking-widest shadow-xl">Enviar a Revisión Legal</button></form></div></div>{% endblock %}""",
    'search.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-10 px-4"><div class="flex flex-col lg:flex-row gap-10"><div class="lg:w-80"><div class="bg-white p-8 rounded-[2rem] border border-slate-100 shadow-sm sticky top-24"><h4 class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-6">Filtrar Red</h4><form method="GET" class="space-y-4"><input name="q" placeholder="Ej: Sangre AB-..." class="w-full p-3.5 bg-slate-50 border-none rounded-2xl text-xs font-black outline-none focus:ring-2 focus:ring-brand"><button class="w-full btn-medical py-3.5 text-[10px] font-black uppercase tracking-widest shadow-md">Actualizar</button></form></div></div><div class="flex-1 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">{% for item in resultados %}<div class="bg-white rounded-[2.5rem] border border-slate-100 shadow-sm overflow-hidden hover:shadow-2xl transition-all duration-500 group relative">{% if item.receta_url %}<div class="absolute z-20 top-4 left-4 bg-red-500 text-white text-[7px] px-2 py-1 rounded-full font-black tracking-widest shadow-lg">RECETA OBLIGATORIA</div>{% endif %}<img src="{{ item.imagen_url }}" class="w-full h-56 object-cover group-hover:scale-105 transition-transform duration-700"><div class="p-8"><h3 class="font-black text-slate-800 text-xl tracking-tighter mb-1">{{ item.nombre }}</h3><p class="text-[9px] text-brand font-black uppercase tracking-[0.1em] mb-4 italic">{{ item.categoria }}</p><div class="flex justify-between items-center"><span class="text-2xl font-black text-slate-900 tracking-tighter">{% if item.tipo_publicacion == 'Venta' %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span><a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="w-12 h-12 bg-blue-50 text-brand rounded-2xl flex items-center justify-center hover:bg-brand hover:text-white transition-all shadow-sm"><i class="fas fa-chevron-right"></i></a></div><div class="mt-6 pt-4 border-t border-slate-50 flex items-center gap-2"><i class="fas fa-location-dot text-[10px] text-slate-300"></i><p class="text-[8px] text-slate-400 font-bold uppercase truncate">{{ item.direccion_exacta }}</p></div></div></div>{% endfor %}</div></div></div>{% endblock %}""",
    'publish.html': """{% extends "base.html" %}{% block content %}<div class="max-w-5xl mx-auto py-12 px-4"><div class="bg-white rounded-[3rem] shadow-2xl p-12 border border-slate-50"><h2 class="text-4xl font-black text-slate-900 mb-2 tracking-tighter">Alta de <span class="text-brand italic">Recurso.</span></h2><p class="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-10 italic">Asegúrate de que la información sea fidedigna</p><form method="POST" enctype="multipart/form-data" class="space-y-10"><div class="grid grid-cols-1 md:grid-cols-2 gap-12"><div class="space-y-6"><div><label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-3 italic">Fotografía Real</label><div class="p-10 border-4 border-dashed border-slate-100 rounded-[2.5rem] text-center bg-slate-50/50 hover:border-brand transition-all group cursor-pointer"><i class="fas fa-cloud-arrow-up text-4xl text-slate-200 mb-4 group-hover:text-brand transition-colors"></i><input type="file" name="imagen" accept="image/*" required class="text-[10px] text-slate-400 font-bold w-full"></div></div><div id="receta_section" class="hidden animate-in fade-in"><label class="block text-[10px] font-black text-red-400 uppercase tracking-widest mb-3 italic">Receta Médica Digital</label><div class="p-5 border-2 border-red-50 bg-red-50/20 rounded-2xl"><input type="file" name="receta" accept="image/*,application/pdf" class="text-[10px] text-red-300 font-bold"></div></div></div><div class="space-y-6"><div><label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Nombre del Insumo</label><input name="nombre" placeholder="Ej: Silla de ruedas motorizada" required class="w-full p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner"></div><div class="grid grid-cols-2 gap-4"><div><label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Categoría</label><select name="categoria" id="cat_select" onchange="toggleLegal(this.value)" class="w-full p-4 bg-slate-50 rounded-2xl border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand"><option value="Equipo">Equipo Médico</option><option value="Medicamento">Medicamento</option><option value="Sangre">Donación Sangre</option><option value="Ortopedico">Ortopédico</option></select></div><div><label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Precio ($)</label><input name="precio" id="precio_input" type="number" value="0" class="w-full p-4 bg-slate-50 rounded-2xl border-none font-black text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner"></div></div><div><label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Modalidad</label><select name="tipo_publicacion" id="tipo_pub" class="w-full p-4 bg-slate-50 rounded-2xl border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand"><option value="Venta">Recuperación (Venta)</option><option value="Donacion">Gratuito (Donación)</option></select></div></div></div><div class="space-y-4"><label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 italic">Ubicación Precisa de Entrega</label><div id="map"></div><div class="bg-blue-50 p-5 rounded-[2rem] border border-blue-100 flex items-center gap-4 shadow-sm"><i class="fas fa-location-crosshairs text-brand animate-pulse"></i><input type="text" id="direccion_text" name="direccion_manual" readonly placeholder="Haz clic en el mapa para geolocalizar..." class="bg-transparent w-full outline-none text-[10px] font-black text-brand uppercase tracking-tighter"></div><input type="hidden" id="lat" name="lat"><input type="hidden" id="lng" name="lng"></div><button type="submit" class="w-full btn-medical py-6 rounded-[2.5rem] font-black text-2xl shadow-2xl shadow-blue-200 hover:scale-[1.01] transition-transform">Confirmar Publicación</button></form></div></div><script>var map = L.map('map').setView([19.4326, -99.1332], 12);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);var marker;map.on('click', function(e) { if(marker) map.removeLayer(marker); marker = L.marker(e.latlng).addTo(map); document.getElementById('lat').value = e.latlng.lat; document.getElementById('lng').value = e.latlng.lng; fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${e.latlng.lat}&lon=${e.latlng.lng}`).then(r => r.json()).then(d => { document.getElementById('direccion_text').value = d.display_name; }); });function toggleLegal(v){const s = document.getElementById('receta_section');const p = document.getElementById('precio_input');const t = document.getElementById('tipo_pub');if(v==='Medicamento') s.classList.remove('hidden'); else s.classList.add('hidden');if(v==='Sangre'){ p.value=0; p.disabled=true; t.value='Donacion'; t.disabled=true; }else{ p.disabled=false; t.disabled=false; }}</script>{% endblock %}""",
    'checkout.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-20 px-4 text-center animate-in zoom-in-95 duration-500"><div class="bg-white p-12 rounded-[3.5rem] shadow-2xl border border-slate-50"><h2 class="text-4xl font-black text-slate-900 mb-10 tracking-tighter italic">Compromiso <span class="text-brand">LifeLink.</span></h2><div class="bg-slate-50 p-8 rounded-[2.5rem] mb-10 border border-slate-100"><img src="{{ pub.imagen_url }}" class="w-40 h-40 rounded-[2rem] object-cover mx-auto mb-6 shadow-2xl ring-4 ring-white"><h3 class="font-black text-2xl text-slate-800">{{ pub.nombre }}</h3><p class="text-[10px] font-black text-brand uppercase tracking-[0.2em] mt-2 italic">Ubicación detectada: {{ pub.direccion_exacta[:60] }}...</p></div>{% if pub.categoria == 'Sangre' %}<div class="mb-10 p-6 bg-red-50 border-2 border-red-100 rounded-[2rem] text-left"><p class="text-[10px] font-black text-red-600 uppercase tracking-widest mb-4 italic"><i class="fas fa-biohazard mr-2"></i> Protocolo de Donación Altruista</p><div class="space-y-5"><div><label class="block text-[9px] font-black text-slate-400 uppercase tracking-widest mb-1 italic">Hospital de Recepción</label><input name="hospital" placeholder="Banco de Sangre / Hospital Central" required class="w-full p-4 bg-white rounded-2xl border-none text-xs font-bold outline-none focus:ring-2 focus:ring-red-400 shadow-sm"></div></div></div>{% endif %}<form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST"><button class="w-full btn-medical py-6 rounded-[2.5rem] font-black text-2xl shadow-2xl shadow-blue-100 hover:scale-105 transition-transform uppercase tracking-tighter">Confirmar Solicitud</button></form><p class="text-[9px] text-slate-300 font-bold uppercase tracking-widest mt-8 flex items-center justify-center gap-2"><i class="fas fa-shield-halved"></i> Transacción Regulada por TechPulse Compliance</p></div></div>{% endblock %}""",
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-16 px-4"><div class="bg-white p-12 rounded-[3rem] shadow-2xl border border-slate-50"><h2 class="text-4xl font-black text-slate-900 mb-10 tracking-tighter italic">Registro <span class="text-brand">Médico.</span></h2><form method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-5"><input name="nombre" placeholder="Nombre Completo" required class="col-span-1 md:col-span-2 p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner"><select name="tipo_sangre" required class="p-4 bg-slate-50 rounded-2xl border-none font-black text-[10px] uppercase outline-none focus:ring-2 focus:ring-brand shadow-inner"><option value="">Tipo Sangre</option><option>O+</option><option>O-</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option></select><input name="telefono" placeholder="WhatsApp (10 dígitos)" required class="p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner"><input name="email" type="email" placeholder="Email institucional/personal" required class="p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner"><input name="ubicacion" placeholder="Delegación / Ciudad" required class="p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner"><input name="password" type="password" placeholder="Contraseña de acceso" required class="col-span-1 md:col-span-2 p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner"><button class="col-span-1 md:col-span-2 w-full btn-medical py-5 rounded-[2rem] font-black text-xl mt-6 shadow-2xl shadow-blue-100 italic">Crear Cuenta Segura</button></form></div></div>{% endblock %}""",
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-20 px-4 text-center"><div class="relative inline-block mb-10"><div class="w-40 h-40 bg-brand text-white text-7xl font-black rounded-[3rem] flex items-center justify-center mx-auto shadow-2xl border-[10px] border-white ring-1 ring-slate-100">{{ current_user.nombre[0] | upper }}</div><div class="absolute -bottom-2 -right-2 bg-emerald-500 w-12 h-12 rounded-2xl flex items-center justify-center text-white border-4 border-white shadow-lg" title="Verificado"><i class="fas fa-check-double text-lg"></i></div></div><h2 class="text-5xl font-black text-slate-900 mb-2 tracking-tighter uppercase italic">{{ current_user.nombre }}</h2><p class="text-brand font-black uppercase tracking-[0.3em] text-[10px] mb-12 italic">Estatus: Donante Universal {{ current_user.tipo_sangre }}</p><div class="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">{% for label, icon, val in [('Canal', 'fa-whatsapp', current_user.telefono), ('Email', 'fa-at', current_user.email), ('Base', 'fa-map-pin', current_user.ubicacion)] %}<div class="bg-white p-8 rounded-[2.5rem] shadow-sm border border-slate-100 flex flex-col items-center text-center"><i class="fas {{ icon }} text-slate-200 text-2xl mb-4"></i><p class="text-[9px] text-slate-300 font-black uppercase mb-1 tracking-widest">{{ label }}</p><p class="font-black text-slate-800 text-xs break-words">{{ val }}</p></div>{% endfor %}</div><div class="mt-20"><a href="{{ url_for('logout') }}" class="text-red-400 font-black text-[10px] uppercase tracking-[0.3em] hover:text-red-600 transition-colors underline decoration-red-100">Finalizar Sesión Segura</a></div></div>{% endblock %}""",
    'chat.html': """{% extends "base.html" %}{% block content %}<div class="max-w-4xl mx-auto py-8 px-4 h-[75vh] flex flex-col"><div class="bg-white rounded-[3rem] shadow-2xl flex flex-col flex-1 overflow-hidden border border-slate-100 animate-in zoom-in-95 duration-500"><div class="bg-brand p-8 text-white flex justify-between items-center shadow-lg relative z-10"><div class="flex items-center gap-5"><div class="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center font-black text-xl italic">LL</div><div><h3 class="font-black leading-none text-xl tracking-tighter italic">Línea de Coordinación</h3><p class="text-[10px] text-blue-100 uppercase tracking-widest mt-2 font-bold animate-pulse">Encriptación LifeLink Activa</p></div></div><a href="{{ url_for('dashboard') }}" class="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center hover:bg-white/20 transition-all"><i class="fas fa-times text-lg"></i></a></div><div class="flex-1 overflow-y-auto p-10 space-y-8 bg-slate-50/50 custom-scrollbar" id="chat-box"></div><div class="p-8 bg-white border-t border-slate-100"><form onsubmit="event.preventDefault(); send();" class="flex gap-5"><input id="msg-input" placeholder="Coordina la entrega aquí..." class="flex-1 p-5 bg-slate-100 rounded-[1.5rem] border-none outline-none focus:ring-2 focus:ring-brand font-bold text-sm shadow-inner"><button class="bg-brand text-white w-16 h-16 rounded-2xl shadow-2xl shadow-blue-200 hover:scale-110 transition-transform flex items-center justify-center"><i class="fas fa-paper-plane text-xl"></i></button></form></div></div></div><script>const socket = io(); const room = "{{ solicitud.id_solicitud }}"; const user = "{{ current_user.nombre }}"; socket.emit('join', {room: room}); socket.on('nuevo_mensaje', function(data){ const box = document.getElementById('chat-box'); const isMe = data.user === user; const d = document.createElement('div'); d.className = `flex ${isMe ? 'justify-end':'justify-start'}`; d.innerHTML = `<div class="${isMe?'bg-brand text-white rounded-l-[1.5rem] rounded-tr-[1.5rem] shadow-2xl shadow-blue-100':'bg-white text-slate-700 rounded-r-[1.5rem] rounded-tl-[1.5rem] shadow-sm border border-slate-200'} px-6 py-4 max-w-[85%] animate-in fade-in slide-in-from-bottom-3"><p class="text-[9px] font-black uppercase mb-2 ${isMe?'text-blue-100':'text-slate-300'} tracking-widest">${data.user}</p><p class="text-sm font-bold leading-relaxed tracking-tight">${data.msg}</p></div>`; box.appendChild(d); box.scrollTop = box.scrollHeight; }); function send(){ const i = document.getElementById('msg-input'); if(i.value.trim()){ socket.emit('enviar_mensaje', {msg: i.value, room: room}); i.value=''; } }</script>{% endblock %}""",
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-24 px-4"><div class="bg-white p-12 rounded-[3.5rem] shadow-2xl border border-slate-100 text-center"><div class="w-16 h-16 bg-blue-50 text-brand rounded-2xl flex items-center justify-center mx-auto mb-8 shadow-inner"><i class="fas fa-lock text-xl"></i></div><h2 class="text-4xl font-black mb-10 tracking-tighter italic text-slate-800">Acceso Seguro.</h2><form method="POST" class="space-y-5"><input name="email" type="email" placeholder="Correo electrónico" required class="w-full p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner"><input name="password" type="password" placeholder="Contraseña" required class="w-full p-4 bg-slate-50 rounded-2xl border-none font-bold text-sm outline-none focus:ring-2 focus:ring-brand shadow-inner"><button class="w-full btn-medical py-5 rounded-[2rem] font-black text-xl mt-6 shadow-2xl shadow-blue-100 uppercase tracking-tighter italic">Ingresar</button></form></div></div>{% endblock %}"""
})

# ==========================================
# 3. RUTAS Y LÓGICA (FULL STACK)
# ==========================================
@login_manager.user_loader
def load_user(user_id): return Usuario.query.get(int(user_id))

@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if Usuario.query.filter_by(email=request.form['email']).first():
            flash("Credenciales ya en uso en la red.", "error")
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
            flash("Bienvenido a la red LifeLink", "success")
            return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = Usuario.query.filter_by(email=request.form['email']).first()
        if u and check_password_hash(u.password_hash, request.form['password']):
            login_user(u)
            return redirect(url_for('dashboard'))
        flash("Datos de acceso incorrectos.", "error")
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
        if img: img_url = cloudinary.uploader.upload(img)['secure_url']
        if rect: rect_url = cloudinary.uploader.upload(rect)['secure_url']
        p = Publicacion(
            id_proveedor=current_user.id_usuario,
            nombre=request.form['nombre'],
            categoria=request.form['categoria'],
            tipo_publicacion=request.form['tipo_publicacion'],
            precio=float(request.form.get('precio', 0) or 0),
            imagen_url=img_url,
            receta_url=rect_url,
            direccion_exacta=request.form.get('direccion_manual', 'Ubicación Proyectada'),
            latitud=float(request.form.get('lat', 19.4326)),
            longitud=float(request.form.get('lng', -99.1332))
        )
        db.session.add(p)
        db.session.commit()
        flash("Publicación emitida con éxito bajo protocolo legal.", "success")
        return redirect(url_for('dashboard'))
    return render_template('publish.html')

@app.route('/borrar_publicacion/<int:id>', methods=['POST'])
@login_required
def borrar_publicacion(id):
    p = Publicacion.query.get_or_404(id)
    if p.id_proveedor == current_user.id_usuario:
        db.session.delete(p)
        db.session.commit()
        flash("Publicación retirada de la red.", "success")
    return redirect(url_for('dashboard'))

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
    s = Solicitud(
        id_solicitante=current_user.id_usuario, 
        id_publicacion=p.id_oferta_insumo,
        hospital_destino=request.form.get('hospital', 'N/A')
    )
    db.session.add(s)
    db.session.commit()
    flash("Protocolo de coordinación activado. Contacta al donante.", "success")
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id_usuario).all()
    pub_ids = [p.id_oferta_insumo for p in pubs]
    sols = Solicitud.query.filter(Solicitud.id_publicacion.in_(pub_ids)).all() if pub_ids else []
    mis_p = Solicitud.query.filter_by(id_solicitante=current_user.id_usuario).all()
    tickets = MensajeSoporte.query.all() if current_user.email == 'admin@lifelink.com' else []
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols, tickets_admin=tickets, mis_pedidos=mis_p)

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
    t = MensajeSoporte(id_usuario=current_user.id_usuario, asunto=request.form['asunto'], mensaje=request.form['mensaje'])
    db.session.add(t)
    db.session.commit()
    flash("Reporte enviado a la división legal de TechPulse.", "success")
    return redirect(url_for('soporte'))

@socketio.on('join')
def on_join(data): join_room(data['room'])

@socketio.on('enviar_mensaje')
def handle_msg(data): emit('nuevo_mensaje', {'msg': data['msg'], 'user': current_user.nombre}, room=data['room'])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Usuario.query.filter_by(email='admin@lifelink.com').first():
            db.session.add(Usuario(nombre="Admin TechPulse", email="admin@lifelink.com", password_hash=generate_password_hash("admin123"), telefono="0000000000", tipo_sangre="N/A", ubicacion="HQ"))
            db.session.commit()
    socketio.run(app, debug=False)
