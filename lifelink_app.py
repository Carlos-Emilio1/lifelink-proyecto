import eventlet
# Parcheo obligatorio para estabilidad de WebSockets en Render
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
# 1. DEFINICIÓN DE TODAS LAS PLANTILLAS (Strings)
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
        .btn-medical { background-color: var(--brand); color: white; transition: all 0.2s; border-radius: 0.5rem; font-weight: 700; text-transform: uppercase; }
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
                         <svg width="20" height="20" viewBox="0 0 100 100" fill="none" stroke="white" stroke-width="12">
                            <path d="M10 50 L30 50 L40 20 L60 80 L70 50 L90 50" stroke-linecap="round" stroke-linejoin="round"/>
                         </svg>
                    </div>
                    <span class="font-black text-lg tracking-tighter text-slate-800">LifeLink</span>
                </a>
                <div class="hidden md:flex gap-6">
                    <a href="{{ url_for('buscar') }}" class="text-[10px] text-slate-400 hover:text-brand transition">Explorar</a>
                    {% if current_user.is_authenticated %}
                    <a href="{{ url_for('publicar') }}" class="text-[10px] text-slate-400 hover:text-brand transition">Publicar</a>
                    <a href="{{ url_for('dashboard') }}" class="text-[10px] text-slate-400 hover:text-brand transition">Gestión</a>
                    {% endif %}
                </div>
            </div>
            <div class="flex items-center gap-3">
                {% if current_user.is_authenticated %}
                    <div class="flex items-center gap-3 bg-slate-50 p-1 pr-4 rounded-xl border border-slate-100">
                        <a href="{{ url_for('perfil') }}" class="w-8 h-8 rounded-lg bg-brand text-white flex items-center justify-center font-black text-xs italic shadow-blue-100 shadow-sm">{{ current_user.nombre[0] | upper }}</a>
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
    <footer class="py-8 bg-white border-t border-slate-100">
        <div class="max-w-7xl mx-auto px-4 flex flex-col items-center gap-4">
            <div class="flex gap-6">
                <a href="{{ url_for('politicas') }}" class="text-[8px] text-slate-400 hover:text-brand tracking-widest uppercase">Privacidad</a>
                <a href="{{ url_for('reglas') }}" class="text-[8px] text-slate-400 hover:text-brand tracking-widest uppercase">Reglas de la Red</a>
                <a href="{{ url_for('soporte') }}" class="text-[8px] text-slate-400 hover:text-brand tracking-widest uppercase">Soporte Técnico</a>
            </div>
            <p class="text-[8px] text-slate-300 tracking-[0.2em]">LifeLink • TechPulse Solutions • 2026</p>
        </div>
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
                    Plataforma inteligente de coordinación para insumos médicos, medicamentos y donaciones de sangre con validación técnica profesional.
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
            <h1 class="text-5xl font-black text-slate-900 tracking-tighter leading-none italic uppercase">Mi <span class="text-brand">Panel.</span></h1>
            <p class="text-[9px] font-black text-slate-400 tracking-[0.3em] mt-2">BIENVENIDO NODO: {{ current_user.nombre }}</p>
        </div>
        <a href="{{ url_for('publicar') }}" class="btn-medical px-8 py-3 text-[10px] shadow-lg">Nueva Publicación</a>
    </div>

    {% if stats %}
    <div class="mb-16 bg-slate-900 p-10 rounded-[3rem] text-white shadow-xl">
        <h3 class="text-lg font-black mb-8 italic uppercase tracking-widest text-brand"><i class="fas fa-shield-halved mr-3"></i> Auditoría de Red TechPulse</h3>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 text-center mb-10">
            <div class="bg-white/5 p-6 rounded-2xl border border-white/10">
                <p class="text-3xl font-black text-brand">{{ stats.total_usuarios }}</p>
                <p class="text-[8px] text-slate-500 mt-1 uppercase">Nodos Activos</p>
            </div>
            <div class="bg-white/5 p-6 rounded-2xl border border-white/10">
                <p class="text-3xl font-black text-emerald-400">{{ stats.total_publicaciones }}</p>
                <p class="text-[8px] text-slate-500 mt-1 uppercase">Recursos en Red</p>
            </div>
            <div class="bg-white/5 p-6 rounded-2xl border border-white/10">
                <p class="text-3xl font-black text-amber-400">{{ stats.total_tickets }}</p>
                <p class="text-[8px] text-slate-500 mt-1 uppercase">Tickets Soporte</p>
            </div>
        </div>
        
        {% if tickets %}
        <div class="border-t border-white/5 pt-8">
            <h4 class="text-[9px] text-slate-400 mb-4 uppercase italic">Últimos mensajes de ayuda:</h4>
            {% for t in tickets %}
            <div class="bg-white/5 p-3 rounded-lg text-[8px] mb-2 flex justify-between items-center border border-white/5 italic">
                <p><span class="text-brand">DE: {{ t.usuario.nombre }}</span> | {{ t.mensaje }}</p>
                <span class="text-slate-500">{{ t.fecha.strftime('%H:%M') }}</span>
            </div>
            {% endfor %}
        </div>
        {% endif %}
    </div>
    {% endif %}

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-12">
        <div class="space-y-8">
            <h4 class="text-[10px] text-slate-300 tracking-[0.3em] uppercase italic">Peticiones de tus recursos (Vendedor)</h4>
            {% for s in solicitudes_recibidas %}
            <div class="bg-white p-8 rounded-[3rem] border border-slate-100 shadow-md flex justify-between items-center group">
                <div>
                    <span class="text-[8px] font-black bg-blue-50 text-brand px-3 py-1 rounded-full border border-blue-100 uppercase">{{ s.estatus }}</span>
                    <h5 class="font-black text-slate-800 text-2xl tracking-tighter mt-3 uppercase italic">{{ s.publicacion.nombre }}</h5>
                    <p class="text-[9px] text-slate-400 mt-1">INTERESADO: {{ s.solicitante.nombre }}</p>
                </div>
                <a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="btn-medical px-6 py-3 text-[9px] shadow-sm">Coordinar</a>
            </div>
            {% else %}
            <p class="text-slate-200 text-[10px]">Sin actividad entrante.</p>
            {% endfor %}
        </div>

        <div class="space-y-8">
            <h4 class="text-[10px] text-slate-300 tracking-[0.3em] uppercase italic">Tus solicitudes activas (Comprador)</h4>
            {% for s in solicitudes_enviadas %}
            <div class="bg-white p-8 rounded-[3rem] border border-slate-100 shadow-md flex justify-between items-center">
                <div>
                    <span class="text-[8px] font-black bg-emerald-50 text-emerald-500 px-3 py-1 rounded-full border border-emerald-100 uppercase italic">Pendiente</span>
                    <h5 class="font-black text-slate-800 text-2xl tracking-tighter mt-3 uppercase italic">{{ s.publicacion.nombre }}</h5>
                    <p class="text-[9px] text-slate-400 mt-1">NODO DONANTE: {{ s.publicacion.proveedor.nombre }}</p>
                </div>
                <a href="{{ url_for('chat', id_solicitud=s.id_solicitud) }}" class="btn-medical px-6 py-3 text-[9px] shadow-sm bg-emerald-500 hover:bg-emerald-600">Hablar</a>
            </div>
            {% else %}
            <p class="text-slate-200 text-[10px]">No has solicitado recursos.</p>
            {% endfor %}
        </div>
    </div>
</div>
{% endblock %}
"""

checkout_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-2xl mx-auto py-20 px-4 text-center italic">
    <div class="bg-white p-12 rounded-[4rem] shadow-2xl border border-slate-100 uppercase font-black italic">
        <h2 class="text-4xl mb-10 tracking-tighter italic leading-none">Validación de <br><span class="text-brand italic">Solicitud.</span></h2>
        
        <div class="bg-slate-50 p-8 rounded-[3rem] mb-10 border border-slate-100">
            <img src="{{ pub.imagen_url }}" class="w-40 h-40 rounded-3xl mx-auto mb-6 object-cover shadow-xl border-4 border-white">
            <h3 class="text-2xl text-slate-800 uppercase">{{ pub.nombre }}</h3>
            <p class="text-[10px] text-brand mt-1 tracking-widest">{{ pub.categoria }}</p>
        </div>

        <form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST" class="space-y-8 text-left italic">
            <div class="space-y-4">
                <label class="block text-[10px] text-slate-400 tracking-widest uppercase">Elegir método de transacción:</label>
                
                <label class="flex items-center p-5 bg-slate-50 rounded-2xl cursor-pointer hover:border-brand border-2 border-transparent transition-all">
                    <input type="radio" name="metodo_pago" value="Tarjeta" required class="w-4 h-4 text-brand">
                    <span class="ml-4 text-xs font-black uppercase">Tarjeta Bancaria (Pasarela TechPulse)</span>
                </label>

                <label class="flex items-center p-5 bg-slate-50 rounded-2xl cursor-pointer hover:border-brand border-2 border-transparent transition-all">
                    <input type="radio" name="metodo_pago" value="Efectivo" class="w-4 h-4 text-brand">
                    <span class="ml-4 text-xs font-black uppercase">Efectivo (Contra entrega física)</span>
                </label>
            </div>

            <button class="w-full btn-medical py-6 rounded-[2.5rem] font-black text-2xl shadow-xl shadow-blue-100 mt-6 italic">Certificar Solicitud</button>
        </form>
    </div>
</div>
{% endblock %}
"""

reglas_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-3xl mx-auto py-16 px-4 uppercase font-black italic">
    <h2 class="text-3xl font-black mb-8 italic">Reglas de la <span class="text-brand">Red.</span></h2>
    <div class="bg-white p-10 rounded-[3rem] border border-slate-100 text-[10px] leading-relaxed space-y-8 shadow-sm">
        <div>
            <p class="text-brand mb-2">1. VALIDACIÓN OBLIGATORIA</p>
            <p class="text-slate-500">CADA INSUMO PUBLICADO DEBE SER REAL Y CONTAR CON EVIDENCIA FOTOGRÁFICA LEGIBLE. LA PUBLICACIÓN DE INFORMACIÓN FALSA RESULTARÁ EN BAJA DEFINITIVA DEL NODO.</p>
        </div>
        <div>
            <p class="text-brand mb-2">2. COORDINACIÓN DIRECTA</p>
            <p class="text-slate-500">LAS TRANSFERENCIAS DEBEN COORDINARSE SIEMPRE DENTRO DEL CHAT OFICIAL DE LIFELINK PARA GARANTIZAR LA SEGURIDAD Y AUDITORÍA DE AMBAS PARTES.</p>
        </div>
        <div>
            <p class="text-brand mb-2">3. ALTRUISMO Y PRECIOS JUSTOS</p>
            <p class="text-slate-500">LIFELINK PRIORIZA LAS DONACIONES. EN CASO DE VENTA, LOS PRECIOS DEBEN SER DE RECUPERACIÓN Y NO ESPECULATIVOS POR EMERGENCIAS.</p>
        </div>
    </div>
</div>
{% endblock %}
"""

politicas_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-3xl mx-auto py-16 px-4 uppercase font-black italic">
    <h2 class="text-3xl font-black mb-8 italic">Privacidad <span class="text-brand">Médica.</span></h2>
    <div class="bg-white p-10 rounded-[3rem] border border-slate-100 text-[10px] leading-relaxed space-y-8 shadow-sm">
        <div>
            <p class="text-brand mb-2">PROTECCIÓN DE DATOS SENSIBLES</p>
            <p class="text-slate-500">SUS DATOS DE SALUD, UBICACIÓN Y TIPO DE SANGRE SON ENCRIPTADOS BAJO EL PROTOCOLO LIFELINK. TECHPULSE NO COMPARTE ESTA INFORMACIÓN CON TERCEROS AJENOS A LA RED.</p>
        </div>
        <div>
            <p class="text-brand mb-2">USO DE EVIDENCIA</p>
            <p class="text-slate-500">LAS IMÁGENES DE INSUMOS SE ALMACENAN EN SERVIDORES SEGUROS ÚNICAMENTE PARA FINES DE VERIFICACIÓN MÉDICA Y LOGÍSTICA DE ENTREGA.</p>
        </div>
    </div>
</div>
{% endblock %}
"""

soporte_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-md mx-auto py-20 px-4 text-center uppercase font-black italic">
    <h2 class="text-3xl italic leading-none">Soporte <span class="text-brand italic">Técnico.</span></h2>
    <p class="text-[9px] text-slate-400 mt-4 tracking-widest italic">¿Problemas con una transferencia o el mapa?</p>
    <form method="POST" class="mt-10 space-y-6">
        <textarea name="msg" placeholder="Describe el problema de forma detallada..." required class="w-full p-5 bg-white border border-slate-100 rounded-3xl text-[10px] h-32 outline-none shadow-inner italic uppercase"></textarea>
        <button class="w-full btn-medical py-5 rounded-2xl text-xl shadow-lg italic">Enviar Reporte</button>
    </form>
</div>
{% endblock %}
"""

# ==========================================
# 2. LÓGICA DE SERVIDOR Y MODELOS
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'lifelink_final_master_v5_fix'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lifelink.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    __tablename__ = 'users_master_final_fix'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    tipo_sangre = db.Column(db.String(10))
    ubicacion = db.Column(db.String(100))
    password_hash = db.Column(db.String(255), nullable=False)
    def get_id(self): return str(self.id)

class Publicacion(db.Model):
    __tablename__ = 'items_master_final_fix'
    id_oferta_insumo = db.Column(db.Integer, primary_key=True)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('users_master_final_fix.id'))
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    tipo_publicacion = db.Column(db.String(50))
    precio = db.Column(db.Float, default=0.0)
    imagen_url = db.Column(db.String(500))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    direccion_text = db.Column(db.String(500))
    proveedor = db.relationship('User', backref='items')

class Solicitud(db.Model):
    __tablename__ = 'orders_master_final_fix'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('users_master_final_fix.id'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('items_master_final_fix.id_oferta_insumo'))
    metodo_pago = db.Column(db.String(50))
    estatus = db.Column(db.String(50), default='En Coordinación')
    solicitante = db.relationship('User', backref='solicitudes_enviadas')
    publicacion = db.relationship('Publicacion', backref='solicitudes_recibidas')

class Ticket(db.Model):
    __tablename__ = 'tickets_soporte'
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('users_master_final_fix.id'))
    mensaje = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('User', backref='tickets')

# CARGADOR DE PLANTILLAS CORREGIDO (Sin errores de NameError)
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'dashboard.html': dashboard_template,
    'checkout.html': checkout_template,
    'reglas.html': reglas_template,
    'politicas.html': politicas_template,
    'soporte.html': soporte_template,
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-20 px-4 text-center font-black uppercase italic"><div class="bg-white p-12 rounded-[3rem] shadow-xl border"><h2>Acceso</h2><form method="POST" class="mt-8 space-y-4"><input name="email" type="email" placeholder="CORREO" required class="w-full p-4 bg-slate-50 rounded-xl border-none text-xs"><input name="password" type="password" placeholder="CONTRASEÑA" required class="w-full p-4 bg-slate-50 rounded-xl border-none text-xs"><button class="w-full btn-medical py-4 rounded-xl text-lg mt-4">Entrar</button></form></div></div>{% endblock %}""",
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-12 px-4 uppercase font-black italic"><div class="bg-white p-10 rounded-[3rem] shadow-xl border border-slate-50"><h2>Registro Nodo</h2><form method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8"><input name="nombre" placeholder="NOMBRE" required class="md:col-span-2 p-4 bg-slate-50 rounded-xl border-none text-xs shadow-inner"><select name="tipo_sangre" required class="p-4 bg-slate-50 rounded-xl border-none text-[9px] shadow-inner"><option value="">SANGRE</option><option>O+</option><option>O-</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option></select><input name="telefono" placeholder="WHATSAPP" required class="p-4 bg-slate-50 rounded-xl border-none text-xs shadow-inner"><input name="ubicacion" placeholder="CIUDAD" required class="p-4 bg-slate-50 rounded-xl border-none text-xs shadow-inner"><input name="email" type="email" placeholder="CORREO" required class="p-4 bg-slate-50 rounded-xl border-none text-xs shadow-inner"><input name="password" type="password" placeholder="CONTRASEÑA" required class="md:col-span-2 p-4 bg-slate-50 rounded-xl border-none text-xs shadow-inner"><button class="md:col-span-2 w-full btn-medical py-5 rounded-xl text-lg shadow-lg">Unirse</button></form></div></div>{% endblock %}""",
    'publish.html': """{% extends "base.html" %}{% block content %}<div class="max-w-4xl mx-auto py-10 px-4 uppercase font-black italic"><div class="bg-white rounded-[3rem] shadow-xl p-10 border border-slate-50"><h2>PUBLICAR</h2><form method="POST" enctype="multipart/form-data" class="space-y-8"><div class="grid grid-cols-1 md:grid-cols-2 gap-10"><div><label class="block text-[8px] text-slate-400 mb-2 italic uppercase">Foto del Recurso</label><input type="file" name="imagen" accept="image/*" required class="text-[8px]"></div><div class="space-y-4"><div><label class="block text-[8px] text-slate-400 mb-1 italic">NOMBRE</label><input name="nombre" placeholder="BOLSA SANGRE O-" required class="w-full p-4 bg-slate-50 rounded-xl border-none text-xs shadow-inner"></div><div class="grid grid-cols-2 gap-4"><div><select name="categoria" class="w-full p-4 bg-slate-50 rounded-xl border-none text-[8px] shadow-inner"><option value="Sangre">Sangre</option><option value="Medicamento">Farmacia</option><option value="Equipo">Insumo</option></select></div><div><select name="tipo_publicacion" id="tp" onchange="const p=document.getElementById('pr'); if(this.value==='Donacion'){p.value='0.00';p.disabled=true;}else{p.disabled=false;}" class="w-full p-4 bg-slate-50 rounded-xl border-none text-[8px] shadow-inner"><option value="Donacion">Donación</option><option value="Venta">Venta</option></select></div></div><input id="pr" name="precio" type="number" step="0.01" value="0.00" disabled class="w-full p-4 bg-slate-100 rounded-xl border-none text-xs shadow-inner"></div></div><div id="map"></div><input type="hidden" id="lt" name="lat"><input type="hidden" id="lg" name="lng"><input type="text" id="dir" name="dir" readonly placeholder="UBICACIÓN EN MAPA" class="w-full p-3 bg-blue-50/50 rounded-xl border-none text-[8px] text-brand italic"><button class="w-full btn-medical py-5 rounded-xl text-xl shadow-lg">Certificar</button></form></div></div><script>var map=L.map('map').setView([19.4326,-99.1332],12); L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map); var m; map.on('click',function(e){ if(m)map.removeLayer(m); m=L.marker(e.latlng).addTo(map); document.getElementById('lt').value=e.latlng.lat; document.getElementById('lg').value=e.latlng.lng; fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${e.latlng.lat}&lon=${e.latlng.lng}`).then(r=>r.json()).then(d=>{ document.getElementById('dir').value=d.display_name; }); });</script>{% endblock %}""",
    'search.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-12 px-4 uppercase font-black italic"><h2>EXPLORAR RED</h2><div class="grid md:grid-cols-3 gap-8 mt-10">{% for item in resultados %}<div class="bg-white rounded-[2.5rem] border border-slate-100 shadow-sm overflow-hidden hover:shadow-xl transition-all group"><img src="{{ item.imagen_url }}" class="w-full h-48 object-cover grayscale group-hover:grayscale-0 transition-all duration-500"><div class="p-6"><h3 class="text-xl tracking-tighter">{{ item.nombre }}</h3><p class="text-[8px] text-brand mt-1 italic">{{ item.categoria }}</p><div class="flex justify-between items-center mt-6"><span class="text-2xl font-black">{% if item.precio > 0 %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span><a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="text-brand"><i class="fas fa-arrow-right text-xl"></i></a></div></div></div>{% endfor %}</div></div>{% endblock %}""",
    'chat.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-6 h-[75vh] flex flex-col uppercase font-black italic"><div class="bg-brand p-6 text-white rounded-t-3xl flex justify-between items-center shadow-lg relative z-10"><p class="text-[10px] uppercase">Línea de Coordinación</p><a href="{{ url_for('dashboard') }}"><i class="fas fa-times text-xs"></i></a></div><div id="chat-box" class="flex-1 bg-white border-x p-8 overflow-y-auto custom-scrollbar space-y-6"></div><div class="p-6 bg-white border rounded-b-3xl flex gap-3 shadow-xl"><input id="mi" placeholder="..." class="flex-1 p-4 bg-slate-50 rounded-2xl border-none text-[10px] outline-none italic"><button onclick="send()" class="bg-brand text-white w-12 h-12 rounded-2xl flex items-center justify-center shadow-xl hover:scale-110 transition-transform"><i class="fas fa-paper-plane"></i></button></div></div><script>const s=io(); const r="{{ solicitud.id_solicitud }}"; const u="{{ current_user.nombre }}"; s.emit('join',{room:r}); s.on('nuevo_mensaje',function(d){ const box=document.getElementById('chat-box'); const isMe=d.user===u; const div=document.createElement('div'); div.className=`flex ${isMe?'justify-end':'justify-start'}`; div.innerHTML=`<div class="${isMe?'bg-brand text-white':'bg-slate-100 text-slate-700'} p-4 rounded-2xl max-w-[85%] text-[9px] shadow-sm italic"><p class="font-black mb-1 opacity-50 uppercase">${d.user}</p><p class="uppercase font-bold">${d.msg}</p></div>`; box.appendChild(div); box.scrollTop=box.scrollHeight; }); function send(){ const i=document.getElementById('mi'); if(i.value.trim()){ s.emit('enviar_mensaje',{msg:i.value,room:r}); i.value=''; } }</script>{% endblock %}""",
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-16 px-4 text-center uppercase italic font-black"><div class="w-32 h-32 bg-brand text-white text-5xl font-black rounded-[2.5rem] flex items-center justify-center mx-auto shadow-xl mb-8 border-[8px] border-white ring-2 ring-slate-100 italic">{{ current_user.nombre[0] | upper }}</div><h2>{{ current_user.nombre }}</h2><p class="text-brand text-[8px] tracking-widest mt-2 uppercase">NODO VERIFICADO {{ current_user.tipo_sangre }}</p><div class="grid grid-cols-2 gap-4 text-left mt-10"><div class="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm"><p class="text-[7px] text-slate-300 uppercase mb-1">Email</p><p class="text-xs uppercase">{{ current_user.email }}</p></div><div class="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm"><p class="text-[7px] text-slate-300 uppercase mb-1">Ubicación</p><p class="text-xs uppercase">{{ current_user.ubicacion }}</p></div></div></div>{% endblock %}"""
})

# --- ASEGURAR TABLAS Y ADMIN ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@lifelink.com').first():
        admin = User(nombre="ADMINISTRADOR MAESTRO", email="admin@lifelink.com", telefono="0000000000", tipo_sangre="AB+", ubicacion="NODO CENTRAL", password_hash=generate_password_hash("admin123"))
        db.session.add(admin); db.session.commit()

# ==========================================
# 3. RUTAS DE CONTROL
# ==========================================
@login_manager.user_loader
def load_user(u_id): return User.query.get(int(u_id))

@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if User.query.filter_by(email=request.form['email']).first(): flash("Correo ya registrado.")
        else:
            u = User(nombre=request.form['nombre'], email=request.form['email'], telefono=request.form['telefono'], tipo_sangre=request.form['tipo_sangre'], ubicacion=request.form['ubicacion'], password_hash=generate_password_hash(request.form['password']))
            db.session.add(u); db.session.commit(); login_user(u); return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = User.query.filter_by(email=request.form['email']).first()
        if u and check_password_hash(u.password_hash, request.form['password']): login_user(u); return redirect(url_for('dashboard'))
        flash("Acceso denegado.")
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/buscar')
def buscar(): return render_template('search.html', resultados=Publicacion.query.all())

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id).all()
    p_ids = [x.id_oferta_insumo for x in pubs]
    s_recibidas = Solicitud.query.filter(Solicitud.id_publicacion.in_(p_ids)).all() if p_ids else []
    s_enviadas = Solicitud.query.filter_by(id_solicitante=current_user.id).all()
    stats, tickets = None, None
    if current_user.email == 'admin@lifelink.com':
        stats = {'total_usuarios': User.query.count(), 'total_publicaciones': Publicacion.query.count(), 'total_tickets': Ticket.query.count()}
        tickets = Ticket.query.order_by(Ticket.fecha.desc()).limit(5).all()
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=s_recibidas, solicitudes_enviadas=s_enviadas, stats=stats, tickets=tickets)

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        img = request.files.get('imagen')
        img_url = "https://via.placeholder.com/400"
        if img: img_url = cloudinary.uploader.upload(img)['secure_url']
        p = Publicacion(id_proveedor=current_user.id, nombre=request.form['nombre'], categoria=request.form['categoria'], tipo_publicacion=request.form['tipo_publicacion'], precio=float(request.form.get('precio', 0) or 0), imagen_url=img_url, latitud=float(request.form.get('lat', 19.4)), longitud=float(request.form.get('lng', -99.1)), direccion_text=request.form.get('dir', ''))
        db.session.add(p); db.session.commit(); flash("Recurso Certificado."); return redirect(url_for('dashboard'))
    return render_template('publish.html')

@app.route('/confirmar_compra/<int:id>')
@login_required
def confirmar_compra(id): return render_template('checkout.html', pub=Publicacion.query.get_or_404(id))

@app.route('/procesar_transaccion/<int:id>', methods=['POST'])
@login_required
def procesar_transaccion(id):
    s = Solicitud(id_solicitante=current_user.id, id_publicacion=id, metodo_pago=request.form.get('metodo_pago'))
    db.session.add(s); db.session.commit(); flash("Solicitud Certificada."); return redirect(url_for('dashboard'))

@app.route('/chat/<int:id_solicitud>')
@login_required
def chat(id_solicitud): return render_template('chat.html', solicitud=Solicitud.query.get_or_404(id_solicitud))

@app.route('/borrar_publicacion/<int:id>', methods=['POST'])
@login_required
def borrar_publicacion(id):
    p = Publicacion.query.get_or_404(id)
    if p.id_proveedor == current_user.id: db.session.delete(p); db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/soporte', methods=['GET', 'POST'])
@login_required
def soporte():
    if request.method == 'POST':
        t = Ticket(id_usuario=current_user.id, mensaje=request.form['msg']); db.session.add(t); db.session.commit(); flash("Reporte enviado."); return redirect(url_for('dashboard'))
    return render_template('soporte.html')

@app.route('/politicas')
def politicas(): return render_template('politicas.html')

@app.route('/reglas')
def reglas(): return render_template('reglas.html')

@app.route('/perfil')
@login_required
def perfil(): return render_template('perfil.html')

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
@socketio.on('join')
def on_join(d): join_room(d['room'])
@socketio.on('enviar_mensaje')
def handle_m(d): emit('nuevo_mensaje', {'msg': d['msg'], 'user': current_user.nombre}, room=d['room'])

if __name__ == '__main__':
    socketio.run(app, debug=False)
