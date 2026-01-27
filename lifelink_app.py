import eventlet
# Parcheo obligatorio para estabilidad en Render
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
        :root { --brand-blue: #0ea5e9; --brand-dark: #0369a1; }
        .bg-brand { background-color: var(--brand-blue); }
        .text-brand { color: var(--brand-blue); }
        .btn-medical { background-color: var(--brand-blue); color: white; transition: all 0.3s; border-radius: 0.75rem; }
        .btn-medical:hover { background-color: var(--brand-dark); transform: translateY(-1px); }
        #map { height: 350px; width: 100%; border-radius: 1rem; z-index: 10; border: 1px solid #e2e8f0; }
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
    </style>
</head>
<body class="bg-slate-50 flex flex-col min-h-screen font-sans text-slate-900">
    <nav class="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center gap-6">
                    <a href="/" class="flex items-center gap-2">
                        <div class="bg-brand p-1.5 rounded-lg">
                             <svg width="20" height="20" viewBox="0 0 100 100" fill="none" stroke="white" stroke-width="10">
                                <path d="M10 50 L30 50 L40 20 L60 80 L70 50 L90 50" stroke-linecap="round" stroke-linejoin="round"/>
                             </svg>
                        </div>
                        <span class="font-bold text-xl tracking-tight text-slate-800 uppercase italic">LifeLink</span>
                    </a>
                    <div class="hidden md:flex gap-6">
                        <a href="{{ url_for('buscar') }}" class="text-xs font-black text-slate-400 hover:text-brand transition uppercase tracking-widest">Explorar</a>
                        {% if current_user.is_authenticated %}
                        <a href="{{ url_for('publicar') }}" class="text-xs font-black text-slate-400 hover:text-brand transition uppercase tracking-widest">Publicar</a>
                        <a href="{{ url_for('dashboard') }}" class="text-xs font-black text-slate-400 hover:text-brand transition uppercase tracking-widest">Panel</a>
                        {% endif %}
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    {% if current_user.is_authenticated %}
                        <div class="flex items-center gap-3">
                            <span class="text-[10px] font-black text-slate-400 hidden sm:block uppercase">{{ current_user.nombre }}</span>
                            <a href="{{ url_for('perfil') }}" class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center text-brand font-black border border-blue-100 italic">{{ current_user.nombre[0] | upper }}</a>
                        </div>
                    {% else %}
                        <a href="{{ url_for('login') }}" class="text-xs font-black text-slate-400 uppercase">Ingresar</a>
                        <a href="{{ url_for('registro') }}" class="btn-medical px-5 py-2 text-xs font-black uppercase shadow-md">Unirse</a>
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
                <div class="p-3 rounded-lg {% if category == 'error' %}bg-red-50 text-red-700 border-red-100{% else %}bg-emerald-50 text-emerald-700 border-emerald-100{% endif %} flex items-center gap-3 border text-xs font-black uppercase">
                  <i class="fas fa-info-circle"></i> {{ message }}
                </div>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="py-10 bg-white border-t border-slate-100 text-center">
        <p class="text-[9px] text-slate-300 font-bold uppercase tracking-[0.3em]">LifeLink • TechPulse Solutions • 2026</p>
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
            <div class="sm:text-center lg:col-span-6 lg:text-left">
                <h1 class="text-6xl font-black text-slate-900 tracking-tighter sm:text-7xl leading-none mb-8 uppercase italic">
                    CONECTANDO <br><span class="text-brand">VIDAS.</span>
                </h1>
                <p class="text-xl text-slate-400 max-w-lg leading-relaxed mb-12 font-medium italic">
                    Plataforma de coordinación para donación altruista de sangre, medicamentos y equipo médico con validación técnica.
                </p>
                <div class="flex flex-wrap gap-5 sm:justify-center lg:justify-start">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-12 py-5 font-black text-lg shadow-2xl flex items-center gap-4 uppercase italic">
                        <i class="fas fa-search"></i> Explorar Red
                    </a>
                </div>
            </div>
            <div class="mt-16 lg:mt-0 lg:col-span-6 flex justify-center">
                <div class="relative w-full max-w-md">
                    <div class="absolute inset-0 bg-brand rounded-[3rem] rotate-3 opacity-5"></div>
                    <div class="relative bg-white p-4 rounded-[3rem] shadow-2xl border-8 border-slate-50 overflow-hidden">
                        <!-- IMAGEN DE ALTA DISPONIBILIDAD -->
                        <img class="w-full h-[550px] rounded-[2rem] object-cover" src="https://images.unsplash.com/photo-1584515933487-779824d29309?q=80&w=1000&auto=format&fit=crop" alt="LifeLink Medical">
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
            <h1 class="text-5xl font-black text-slate-900 tracking-tighter uppercase italic leading-none">Mi <span class="text-brand">Panel.</span></h1>
            <p class="text-[10px] font-black text-slate-400 uppercase tracking-widest mt-2 italic">Rating Actual: {{ current_user.rating_promedio|round(1) }} ★</p>
        </div>
        <a href="{{ url_for('publicar') }}" class="btn-medical px-8 py-4 text-xs font-black uppercase tracking-widest shadow-xl">Nueva Publicación</a>
    </div>

    {% if current_user.email == 'admin@lifelink.com' %}
    <div class="mb-16 bg-slate-900 p-10 rounded-[3rem] text-white shadow-2xl relative overflow-hidden">
        <h3 class="text-xl font-black mb-8 uppercase italic tracking-widest"><i class="fas fa-shield-halved text-brand mr-3"></i> Auditoría Admin</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            <div class="bg-white/5 p-6 rounded-2xl border border-white/10 text-center">
                <p class="text-3xl font-black text-brand">{{ stats.total_usuarios }}</p>
                <p class="text-[8px] font-bold uppercase text-slate-500">Usuarios</p>
            </div>
            <div class="bg-white/5 p-6 rounded-2xl border border-white/10 text-center">
                <p class="text-3xl font-black text-emerald-400">{{ stats.total_publicaciones }}</p>
                <p class="text-[8px] font-bold uppercase text-slate-500">Insumos</p>
            </div>
            <div class="bg-white/5 p-6 rounded-2xl border border-white/10 text-center">
                <p class="text-3xl font-black text-amber-400">{{ stats.total_tickets }}</p>
                <p class="text-[8px] font-bold uppercase text-slate-500">Tickets</p>
            </div>
        </div>
    </div>
    {% endif %}

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <div class="lg:col-span-2 space-y-10">
             <h4 class="text-[10px] font-black text-slate-300 uppercase tracking-[0.3em] italic">Transferencias Activas</h4>
             {% for s in solicitudes_recibidas %}
             <div class="bg-white p-8 rounded-[2.5rem] border border-slate-100 shadow-xl flex flex-col md:flex-row justify-between items-center group">
                <div>
                    <span class="text-[8px] font-black bg-blue-50 text-brand px-3 py-1 rounded-full uppercase border border-blue-100">{{ s.estatus }}</span>
                    <h5 class="font-black text-slate-800 text-2xl tracking-tighter uppercase italic mt-2">{{ s.publicacion.nombre }}</h5>
                    <p class="text-[10px] text-slate-400 font-bold uppercase italic mt-1 italic">Solicitante: {{ s.solicitante.nombre }}</p>
                </div>
                <a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="btn-medical px-6 py-3 text-[10px] font-black uppercase tracking-widest mt-4 md:mt-0 shadow-lg italic">Chat Coordinación</a>
             </div>
             {% else %}
             <div class="p-12 text-center bg-white rounded-[2.5rem] border-2 border-dashed border-slate-100">
                <p class="text-xs font-black text-slate-300 uppercase italic">Sin solicitudes entrantes</p>
             </div>
             {% endfor %}
        </div>

        <div class="space-y-10">
            <h4 class="text-[10px] font-black text-slate-300 uppercase tracking-[0.3em] italic">Mi Inventario</h4>
            {% for p in publicaciones %}
            <div class="bg-white p-5 rounded-[2rem] border border-slate-100 shadow-sm flex items-center gap-4">
                <img src="{{ p.imagen_url }}" class="w-12 h-12 rounded-xl object-cover grayscale">
                <div class="flex-1 min-w-0">
                    <p class="text-[11px] font-black text-slate-800 truncate uppercase italic">{{ p.nombre }}</p>
                    <span class="text-[8px] font-black uppercase {% if p.estado == 'Verificado' %}text-emerald-500 bg-emerald-50{% else %}text-amber-500 bg-amber-50{% endif %} px-2 py-0.5 rounded-lg border border-current italic">{{ p.estado }}</span>
                </div>
                <form action="{{ url_for('borrar_publicacion', id=p.id_oferta_insumo) }}" method="POST">
                    <button class="text-slate-200 hover:text-red-500 transition-colors"><i class="fas fa-trash-alt"></i></button>
                </form>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
"""

# ==========================================
# 2. LÓGICA DE SERVIDOR Y MODELOS (LIMPIOS)
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
        resenas = Resena.query.filter_by(id_evaluado=self.id_usuario).all()
        if not resenas: return 5.0
        return sum([r.estrellas for r in resenas]) / len(resenas)

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
    estado = db.Column(db.String(20), default='Verificado') 
    proveedor = db.relationship('Usuario', backref='publicaciones')

class Solicitud(db.Model):
    __tablename__ = 'solicitudes'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('insumos.id_oferta_insumo'))
    estatus = db.Column(db.String(50), default='En Proceso') 
    solicitante = db.relationship('Usuario', backref='solicitudes_enviadas')
    publicacion = db.relationship('Publicacion', backref='solicitudes_recibidas')

class Resena(db.Model):
    __tablename__ = 'resenas'
    id_resena = db.Column(db.Integer, primary_key=True)
    id_solicitud = db.Column(db.Integer, db.ForeignKey('solicitudes.id_solicitud'))
    id_evaluado = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    estrellas = db.Column(db.Integer)

class MensajeSoporte(db.Model):
    __tablename__ = 'soporte_tickets'
    id_ticket = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    asunto = db.Column(db.String(150))
    mensaje = db.Column(db.Text)

# Cargador de Plantillas (ORDENADO)
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'dashboard.html': dashboard_template,
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-24 px-4 text-center"><div class="bg-white p-12 rounded-[3rem] shadow-2xl border border-slate-100"><h2 class="text-4xl font-black mb-10 tracking-tighter uppercase italic leading-none italic">Acceder al <br><span class="text-brand italic">Nodo.</span></h2><form method="POST" class="space-y-5"><input name="email" type="email" placeholder="CORREO ELECTRÓNICO" required class="w-full p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase italic"><input name="password" type="password" placeholder="CONTRASEÑA" required class="w-full p-5 bg-slate-50 rounded-2xl border-none font-black text-xs outline-none focus:ring-2 focus:ring-brand shadow-inner uppercase italic"><button class="w-full btn-medical py-5 rounded-[2rem] font-black text-2xl mt-6 shadow-xl uppercase italic">Ingresar</button></form></div></div>{% endblock %}""",
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-16 px-4 uppercase italic font-black"><div class="bg-white p-12 rounded-[3rem] shadow-2xl border border-slate-50 italic"><h2 class="text-4xl font-black text-slate-900 mb-10 tracking-tighter italic italic">Cédula de <span class="text-brand italic italic">Registro.</span></h2><form method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-5 italic italic"><input name="nombre" placeholder="Nombre completo" required class="col-span-1 md:col-span-2 p-5 bg-slate-50 rounded-2xl border-none text-xs shadow-inner italic"><select name="tipo_sangre" required class="p-5 bg-slate-50 rounded-2xl border-none text-[10px] shadow-inner italic"><option value="">TIPO SANGRE</option><option>O+</option><option>O-</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option></select><input name="telefono" placeholder="WhatsApp" required class="p-5 bg-slate-50 rounded-2xl border-none text-xs shadow-inner italic"><input name="email" type="email" placeholder="Email" required class="p-5 bg-slate-50 rounded-2xl border-none text-xs shadow-inner italic"><input name="ubicacion" placeholder="Ciudad" required class="p-5 bg-slate-50 rounded-2xl border-none text-xs shadow-inner italic"><input name="password" type="password" placeholder="Contraseña" required class="col-span-1 md:col-span-2 p-5 bg-slate-50 rounded-2xl border-none text-xs shadow-inner italic"><button class="col-span-1 md:col-span-2 w-full btn-medical py-6 rounded-[2rem] font-black text-2xl mt-6 shadow-xl italic">Activar Nodo</button></form></div></div>{% endblock %}""",
    'search.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-12 px-4 uppercase italic font-black"><h2 class="text-4xl font-black mb-10 tracking-tighter uppercase italic italic leading-none">Explorar <span class="text-brand">Red Médica.</span></h2><div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-10">{% for item in resultados %}<div class="bg-white rounded-[2.5rem] border border-slate-100 shadow-sm overflow-hidden hover:shadow-2xl transition-all duration-700 group relative italic"><img src="{{ item.imagen_url }}" class="w-full h-64 object-cover group-hover:scale-105 transition-transform duration-700 grayscale group-hover:grayscale-0"><div class="p-8 italic"><h3 class="font-black text-slate-800 text-2xl tracking-tighter uppercase italic mb-1">{{ item.nombre }}</h3><p class="text-[10px] text-brand font-black uppercase mb-6 italic">{{ item.categoria }}</p><div class="flex justify-between items-center"><span class="text-2xl font-black text-slate-900 tracking-tighter italic">{% if item.tipo_publicacion == 'Venta' %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span><a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="w-12 h-12 bg-blue-50 text-brand rounded-2xl flex items-center justify-center hover:bg-brand hover:text-white transition-all shadow-md"><i class="fas fa-arrow-right text-lg"></i></a></div></div></div>{% endfor %}</div></div>{% endblock %}""",
    'publish.html': """{% extends "base.html" %}{% block content %}<div class="max-w-4xl mx-auto py-12 px-4 uppercase font-black italic"><div class="bg-white rounded-[3rem] shadow-2xl p-12 border border-slate-50 shadow-blue-50/50"><h2 class="text-3xl font-black text-slate-900 mb-10 tracking-tighter italic italic italic">Nueva <span class="text-brand italic italic italic">Publicación.</span></h2><form method="POST" enctype="multipart/form-data" class="space-y-10 italic"><div class="grid grid-cols-1 md:grid-cols-2 gap-8"><div class="space-y-6"><div><label class="block text-[10px] text-slate-400 mb-2 italic">Foto del Insumo</label><input type="file" name="imagen" required class="text-[10px] italic"></div><div><label class="block text-[10px] text-slate-400 mb-2 italic">Nombre del Insumo</label><input name="nombre" placeholder="Ej: Bolsa Sangre O+" required class="w-full p-4 bg-slate-50 rounded-2xl border-none text-xs shadow-inner italic"></div></div><div class="space-y-6"><div><label class="block text-[10px] text-slate-400 mb-2 italic">Categoría</label><select name="categoria" class="w-full p-4 bg-slate-50 rounded-2xl border-none text-xs shadow-inner italic"><option value="Sangre">Sangre</option><option value="Medicamento">Medicamento</option><option value="Equipo">Equipo</option></select></div><div><label class="block text-[10px] text-slate-400 mb-2 italic">Tipo de Publicación</label><select name="tipo_publicacion" class="w-full p-4 bg-slate-50 rounded-2xl border-none text-xs shadow-inner italic"><option value="Donacion">Donación</option><option value="Venta">Venta</option></select></div></div></div><button type="submit" class="w-full btn-medical py-6 rounded-[2rem] font-black text-3xl shadow-xl italic">Publicar en la Red</button></form></div></div>{% endblock %}""",
    'checkout.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-24 px-4 text-center uppercase italic font-black"><div class="bg-white p-12 rounded-[4rem] shadow-2xl border border-slate-100"><h2 class="text-4xl font-black mb-10 tracking-tighter italic">Solicitud de <br><span class="text-brand">Insumo.</span></h2><div class="bg-slate-50 p-10 rounded-[3rem] mb-10 shadow-inner"><img src="{{ pub.imagen_url }}" class="w-40 h-40 rounded-3xl mx-auto mb-6 shadow-xl"><h3 class="font-black text-2xl">{{ pub.nombre }}</h3><p class="text-xs text-brand mt-2">{{ pub.categoria }}</p></div><form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST"><button class="w-full btn-medical py-6 rounded-[2rem] font-black text-3xl shadow-xl italic">Confirmar Solicitud</button></form></div></div>{% endblock %}""",
    'chat.html': """{% extends "base.html" %}{% block content %}<div class="max-w-3xl mx-auto py-8 px-4 h-[75vh] flex flex-col uppercase font-black italic"><div class="bg-white rounded-[3rem] shadow-2xl flex flex-col flex-1 overflow-hidden border border-slate-100 shadow-blue-50/50"><div class="bg-brand p-8 text-white flex justify-between items-center"><h3 class="font-black text-xl italic uppercase">Línea de Coordinación</h3><a href="{{ url_for('dashboard') }}" class="text-white/70"><i class="fas fa-times"></i></a></div><div class="flex-1 overflow-y-auto p-10 space-y-6 bg-slate-50/50" id="chat-box"></div><div class="p-8 bg-white border-t border-slate-100"><form onsubmit="event.preventDefault(); send();" class="flex gap-4"><input id="msg-input" placeholder="Escribe un mensaje..." class="flex-1 p-5 bg-slate-100 rounded-2xl border-none outline-none text-xs italic shadow-inner"><button class="bg-brand text-white px-8 py-5 rounded-2xl shadow-lg"><i class="fas fa-paper-plane"></i></button></form></div></div></div><script>const socket = io(); const room = "{{ solicitud.id_solicitud }}"; const user = "{{ current_user.nombre }}"; socket.emit('join', {room: room}); socket.on('nuevo_mensaje', function(data){ const box = document.getElementById('chat-box'); const d = document.createElement('div'); d.className = `flex ${data.user === user ? 'justify-end' : 'justify-start'}`; d.innerHTML = `<div class="${data.user === user ? 'bg-brand text-white' : 'bg-white text-slate-800 border'} p-4 rounded-2xl text-xs font-black shadow-sm italic uppercase"><p class="text-[8px] opacity-60 mb-1">${data.user}</p><p>${data.msg}</p></div>`; box.appendChild(d); box.scrollTop = box.scrollHeight; }); function send(){ const i = document.getElementById('msg-input'); if(i.value.trim()){ socket.emit('enviar_mensaje', {msg: i.value, room: room}); i.value=''; } }</script>{% endblock %}""",
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-20 px-4 text-center uppercase font-black italic"><div class="w-40 h-40 bg-brand text-white text-7xl font-black rounded-[3rem] flex items-center justify-center mx-auto shadow-2xl italic border-8 border-white mb-8">{{ current_user.nombre[0] | upper }}</div><h2 class="text-5xl font-black text-slate-900 mb-2 tracking-tighter uppercase italic">{{ current_user.nombre }}</h2><p class="text-brand text-[10px] mb-12 italic uppercase">Nodo Verificado: {{ current_user.tipo_sangre }}</p><div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-left italic"><div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 italic"><p class="text-[8px] text-slate-300 uppercase italic">Email</p><p class="text-xs font-black">{{ current_user.email }}</p></div><div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 italic"><p class="text-[8px] text-slate-300 uppercase italic">Canal</p><p class="text-xs font-black">{{ current_user.telefono }}</p></div></div><a href="{{ url_for('logout') }}" class="inline-block mt-16 text-red-300 font-bold uppercase text-[10px] italic">Finalizar Sesión</a></div>{% endblock %}"""
})

# ==========================================
# 3. RUTAS Y LÓGICA DE CONTROL (CORREGIDAS)
# ==========================================
@login_manager.user_loader
def load_user(user_id): return Usuario.query.get(int(user_id))

@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if Usuario.query.filter_by(email=request.form['email']).first():
            flash("Identidad ya registrada en la red.", "error")
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
        flash("Acceso denegado. Datos inválidos.", "error")
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        img = request.files.get('imagen')
        img_url = "https://via.placeholder.com/400"
        if img: img_url = cloudinary.uploader.upload(img)['secure_url']
        
        p = Publicacion(
            id_proveedor=current_user.id_usuario,
            nombre=request.form['nombre'],
            categoria=request.form['categoria'],
            tipo_publicacion=request.form['tipo_publicacion'],
            imagen_url=img_url,
            estado='Verificado'
        )
        db.session.add(p)
        db.session.commit()
        flash("Recurso publicado con éxito.", "success")
        return redirect(url_for('dashboard'))
    return render_template('publish.html')

@app.route('/buscar')
def buscar():
    # Simplificado para evitar el Internal Server Error
    res = Publicacion.query.filter_by(estado='Verificado').all()
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
    flash("Certificado emitido. Coordinar entrega vía chat.", "success")
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id_usuario).all()
    pub_ids = [p.id_oferta_insumo for p in pubs]
    sols = Solicitud.query.filter(Solicitud.id_publicacion.in_(pub_ids)).all() if pub_ids else []
    
    stats = {
        'total_usuarios': Usuario.query.count(),
        'total_publicaciones': Publicacion.query.count(),
        'total_tickets': MensajeSoporte.query.count()
    } if current_user.email == 'admin@lifelink.com' else {}
    
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols, stats=stats)

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
    socketio.run(app, debug=False)
