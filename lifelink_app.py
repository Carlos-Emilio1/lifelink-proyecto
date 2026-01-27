import os
import logging
import jinja2
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room
import cloudinary
import cloudinary.uploader

# --- CONFIGURACIÓN TÉCNICA ---
from flask import cli
cli.show_server_banner = lambda *_: None 

# --- CONFIGURACIÓN CLOUDINARY ---
cloudinary.config(
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
  api_key = os.environ.get('CLOUDINARY_API_KEY'),
  api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
  secure = True
)

# ==========================================
# 1. PLANTILLAS HTML (FRONTEND - ESTILO AZUL MÉDICO)
# ==========================================

base_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LifeLink - Gestión Médica Solidaria</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --brand-blue: #0284c7; --brand-dark: #0c4a6e; }
        .bg-brand { background-color: var(--brand-blue); }
        .text-brand { color: var(--brand-blue); }
        .border-brand { border-color: var(--brand-blue); }
        .btn-medical { background-color: var(--brand-blue); color: white; transition: all 0.3s; }
        .btn-medical:hover { background-color: var(--brand-dark); transform: translateY(-1px); }
        #map { height: 350px; width: 100%; border-radius: 0.75rem; z-index: 0; border: 2px solid #e2e8f0; }
        .product-card { transition: transform 0.2s; border-radius: 1rem; overflow: hidden; }
        .product-card:hover { transform: translateY(-5px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }
        .chat-dot { height: 8px; width: 8px; background-color: #10b981; border-radius: 50%; display: inline-block; margin-right: 5px; }
    </style>
</head>
<body class="bg-slate-50 flex flex-col min-h-screen font-sans">
    <nav class="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <a href="/" class="flex items-center gap-3">
                        <svg width="40" height="40" viewBox="0 0 100 100" class="text-brand">
                            <rect width="100" height="100" rx="20" fill="currentColor"/>
                            <path d="M20 50 L40 50 L45 35 L55 65 L60 50 L80 50" stroke="white" stroke-width="6" fill="none" stroke-linecap="round"/>
                            <circle cx="50" cy="50" r="10" fill="none" stroke="white" stroke-width="2" stroke-dasharray="4 2"/>
                        </svg>
                        <div class="flex flex-col">
                            <span class="font-black text-2xl tracking-tight text-slate-800 leading-none">LifeLink</span>
                            <span class="text-[10px] font-bold text-brand tracking-[0.2em] uppercase">Tecnología Médica</span>
                        </div>
                    </a>
                    <div class="hidden md:ml-10 md:flex md:space-x-8">
                        <a href="{{ url_for('buscar') }}" class="text-slate-600 hover:text-brand px-1 pt-1 text-sm font-semibold transition">Buscar Recursos</a>
                        {% if current_user.is_authenticated %}
                        <a href="{{ url_for('publicar') }}" class="text-slate-600 hover:text-brand px-1 pt-1 text-sm font-semibold transition">Publicar</a>
                        <a href="{{ url_for('dashboard') }}" class="text-slate-600 hover:text-brand px-1 pt-1 text-sm font-semibold transition">Gestión</a>
                        {% endif %}
                    </div>
                </div>
                <div class="flex items-center gap-4">
                    {% if current_user.is_authenticated %}
                        <a href="{{ url_for('perfil') }}" class="flex items-center gap-2 group">
                            <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-brand font-bold border border-blue-200">{{ current_user.nombre[0] | upper }}</div>
                            <span class="text-sm font-medium text-slate-700 group-hover:text-brand transition">{{ current_user.nombre.split()[0] }}</span>
                        </a>
                        <a href="{{ url_for('logout') }}" class="text-slate-400 hover:text-red-500 transition"><i class="fa-solid fa-right-from-bracket"></i></a>
                    {% else %}
                        <a href="{{ url_for('login') }}" class="text-slate-600 text-sm font-bold hover:text-brand">Ingresar</a>
                        <a href="{{ url_for('registro') }}" class="btn-medical px-5 py-2 rounded-full text-sm font-bold shadow-md">Registrarse</a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>
    <main class="flex-grow">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="max-w-4xl mx-auto mt-6 px-4">
              {% for category, message in messages %}
                <div class="p-4 rounded-xl border flex items-center gap-3 {% if category == 'error' %}bg-red-50 border-red-200 text-red-800{% else %}bg-emerald-50 border-emerald-200 text-emerald-800{% endif %} shadow-sm">
                  <i class="fas {% if category == 'error' %}fa-circle-xmark{% else %}fa-circle-check{% endif %}"></i>
                  <span class="text-sm font-medium">{{ message }}</span>
                </div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="bg-white border-t border-slate-200 py-8">
        <div class="max-w-7xl mx-auto px-4 text-center">
            <p class="text-slate-400 text-xs">© 2026 LifeLink Proyecto Aula - Equipo TechPulse. Uso Académico.</p>
        </div>
    </footer>
    <a href="{{ url_for('soporte') }}" class="fixed bottom-6 right-6 bg-brand text-white w-14 h-14 rounded-full shadow-2xl flex items-center justify-center hover:scale-110 transition-transform z-50">
        <i class="fas fa-headset text-xl"></i>
    </a>
</body>
</html>
"""

home_template = """
{% extends "base.html" %}
{% block content %}
<div class="relative bg-white pt-16 pb-32 overflow-hidden">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        <div class="lg:grid lg:grid-cols-12 lg:gap-8">
            <div class="sm:text-center md:max-w-2xl md:mx-auto lg:col-span-6 lg:text-left">
                <span class="inline-flex items-center px-3 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800 uppercase tracking-widest mb-4">
                    Proyecto Aula 5IV7
                </span>
                <h1 class="text-4xl tracking-tight font-extrabold text-slate-900 sm:text-5xl md:text-6xl">
                    Conectando <span class="text-brand">Recursos Médicos</span> con quienes más los necesitan.
                </h1>
                <p class="mt-3 text-base text-slate-500 sm:mt-5 sm:text-xl">
                    Una plataforma diseñada para agilizar la donación de sangre y la gestión de insumos médicos en tiempo real. 
                </p>
                <div class="mt-8 sm:max-w-lg sm:mx-auto sm:text-center lg:text-left lg:mx-0 flex flex-wrap gap-4">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-8 py-4 rounded-xl font-bold shadow-lg flex items-center gap-2">
                        <i class="fas fa-search"></i> Buscar Insumos
                    </a>
                    <a href="{{ url_for('registro') }}" class="bg-slate-100 text-slate-700 hover:bg-slate-200 px-8 py-4 rounded-xl font-bold transition shadow">
                        Unirse a la Red
                    </a>
                </div>
            </div>
            <div class="mt-12 relative sm:max-w-lg sm:mx-auto lg:mt-0 lg:max-w-none lg:mx-0 lg:col-span-6 lg:flex lg:items-center">
                <div class="relative mx-auto w-full rounded-3xl shadow-2xl overflow-hidden border-8 border-white">
                    <img class="w-full" src="https://images.unsplash.com/photo-1584036561566-baf8f5f1b144?auto=format&fit=crop&q=80&w=800" alt="Medicina">
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
<div class="max-w-3xl mx-auto py-10 px-4">
    <div class="bg-white shadow-xl rounded-2xl overflow-hidden border border-slate-100">
        <div class="bg-brand p-6 text-white text-center">
            <h2 class="text-2xl font-bold">Publicar Recurso</h2>
            <p class="text-blue-100 text-sm">Ayuda a la comunidad compartiendo lo que tienes.</p>
        </div>
        <form action="{{ url_for('publicar') }}" method="POST" enctype="multipart/form-data" class="p-8 space-y-6">
            <div class="space-y-2">
                <label class="block text-sm font-bold text-slate-700">Imagen del Insumo</label>
                <div class="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-slate-300 border-dashed rounded-xl hover:border-brand transition-colors cursor-pointer group">
                    <div class="space-y-1 text-center">
                        <i class="fas fa-cloud-upload-alt text-4xl text-slate-400 group-hover:text-brand transition-colors mb-2"></i>
                        <div class="flex text-sm text-slate-600">
                            <input type="file" name="imagen" accept="image/*" required class="w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-brand hover:file:bg-blue-100">
                        </div>
                        <p class="text-xs text-slate-500">PNG, JPG hasta 5MB</p>
                    </div>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label class="block text-sm font-bold text-slate-700">Nombre del Insumo</label>
                    <input type="text" name="nombre" required placeholder="Ej: Silla de ruedas, O+" class="mt-1 block w-full border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-brand focus:border-brand outline-none transition">
                </div>
                <div>
                    <label class="block text-sm font-bold text-slate-700">Categoría</label>
                    <select name="categoria" class="mt-1 block w-full border border-slate-300 rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-brand">
                        <option value="Medicamento">Medicamento</option>
                        <option value="Ortopedico">Ortopédico</option>
                        <option value="Sangre">Donación Sangre</option>
                        <option value="Equipo">Equipo Médico</option>
                    </select>
                </div>
            </div>

            <div>
                <label class="block text-sm font-bold text-slate-700">Descripción detallada</label>
                <textarea name="description" rows="3" required class="mt-1 block w-full border border-slate-300 rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-brand" placeholder="Estado del insumo, caducidad, etc..."></textarea>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label class="block text-sm font-bold text-slate-700">Tipo de Publicación</label>
                    <select name="tipo_publicacion" id="tipo_pub" onchange="togglePrecio(this.value)" class="mt-1 block w-full border border-slate-300 rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-brand">
                        <option value="Donacion">Donación Altruista</option>
                        <option value="Venta">Venta (Recuperación)</option>
                    </select>
                </div>
                <div id="price_container" class="hidden">
                    <label class="block text-sm font-bold text-slate-700">Precio ($ MXN)</label>
                    <input type="number" name="precio" value="0" class="mt-1 block w-full border border-slate-300 rounded-lg p-2.5 outline-none focus:ring-2 focus:ring-brand">
                </div>
            </div>

            <div>
                <label class="block text-sm font-bold text-slate-700 mb-2">Ubicación del Insumo</label>
                <div id="map"></div>
                <input type="hidden" id="lat" name="lat">
                <input type="hidden" id="lng" name="lng">
                <p class="text-xs text-slate-400 mt-2 italic"><i class="fas fa-info-circle"></i> Haz clic en el mapa para marcar el punto de entrega.</p>
            </div>

            <div class="pt-4">
                <button type="submit" class="w-full btn-medical py-4 rounded-xl font-bold shadow-xl text-lg">Publicar Ahora</button>
            </div>
        </form>
    </div>
</div>
<script>
    function togglePrecio(val) {
        document.getElementById('price_container').classList.toggle('hidden', val !== 'Venta');
    }
    window.onload = function() {
        var map = L.map('map').setView([19.4326, -99.1332], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
        var marker;
        map.on('click', function(e) {
            if(marker) map.removeLayer(marker);
            marker = L.marker(e.latlng).addTo(map);
            document.getElementById('lat').value = e.latlng.lat;
            document.getElementById('lng').value = e.latlng.lng;
        });
    }
</script>
{% endblock %}
"""

checkout_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-2xl mx-auto py-12 px-4">
    <div class="bg-white rounded-3xl shadow-2xl overflow-hidden border border-slate-200">
        <div class="p-8 border-b border-slate-100 flex items-center justify-between">
            <h2 class="text-2xl font-bold text-slate-800 italic">Checkout Seguro</h2>
            <div class="flex gap-2 text-2xl text-slate-300">
                <i class="fab fa-cc-visa"></i>
                <i class="fab fa-cc-mastercard"></i>
            </div>
        </div>
        <div class="p-8">
            <div class="flex items-center gap-6 bg-slate-50 p-6 rounded-2xl mb-8 border border-slate-100">
                <img src="{{ pub.imagen_url }}" class="w-24 h-24 rounded-xl object-cover shadow-sm">
                <div class="flex-1">
                    <h3 class="text-xl font-bold text-slate-900">{{ pub.nombre }}</h3>
                    <p class="text-sm text-slate-500">{{ pub.categoria }}</p>
                </div>
                <div class="text-right">
                    <p class="text-2xl font-black text-brand">{% if pub.tipo_publicacion == 'Venta' %} ${{ pub.precio }} {% else %} GRATIS {% endif %}</p>
                </div>
            </div>

            <form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST" class="space-y-6">
                <div>
                    <label class="block text-sm font-bold text-slate-700 mb-2">Dirección de Entrega</label>
                    <input type="text" name="direccion_envio" required value="{{ current_user.ubicacion or '' }}" class="w-full border border-slate-300 rounded-xl p-3 outline-none focus:ring-2 focus:ring-brand">
                </div>

                {% if pub.tipo_publicacion == 'Venta' %}
                <div class="space-y-4">
                    <label class="block text-sm font-bold text-slate-700">Datos de la Tarjeta (Simulación)</label>
                    <div class="relative">
                        <input type="text" placeholder="0000 0000 0000 0000" class="w-full border border-slate-300 rounded-xl p-4 outline-none focus:ring-2 focus:ring-brand font-mono">
                        <i class="fas fa-credit-card absolute right-4 top-4 text-slate-300"></i>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <input type="text" placeholder="MM/AA" class="border border-slate-300 rounded-xl p-4 outline-none focus:ring-2 focus:ring-brand text-center">
                        <input type="text" placeholder="CVC" class="border border-slate-300 rounded-xl p-4 outline-none focus:ring-2 focus:ring-brand text-center">
                    </div>
                </div>
                {% endif %}

                <button type="submit" class="w-full btn-medical py-5 rounded-2xl font-bold text-xl shadow-lg mt-4">
                    {% if pub.tipo_publicacion == 'Venta' %} Pagar y Solicitar {% else %} Confirmar Solicitud Gratis {% endif %}
                </button>
            </form>
            <p class="text-center text-xs text-slate-400 mt-6"><i class="fas fa-lock"></i> Conexión encriptada punto a punto.</p>
        </div>
    </div>
</div>
{% endblock %}
"""

chat_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto py-8 px-4 h-[80vh] flex flex-col">
    <div class="bg-white rounded-2xl shadow-xl border border-slate-200 flex flex-col flex-1 overflow-hidden">
        <div class="bg-brand p-4 text-white flex justify-between items-center shadow-md">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center font-bold">L</div>
                <div>
                    <h3 class="font-bold leading-none">Chat de Coordinación</h3>
                    <p class="text-[10px] text-blue-100 mt-1 uppercase tracking-tighter"><span class="chat-dot"></span>Pedido #{{ solicitud.id_solicitud }}</p>
                </div>
            </div>
            <a href="{{ url_for('dashboard') }}" class="text-white/80 hover:text-white"><i class="fas fa-times"></i></a>
        </div>
        
        <div class="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-50" id="chat-box">
            <div class="text-center"><span class="bg-slate-200 text-slate-500 text-[10px] px-3 py-1 rounded-full uppercase font-bold tracking-widest">Chat Seguro Iniciado</span></div>
        </div>

        <div class="p-4 bg-white border-t border-slate-100">
            <form id="msg-form" class="flex gap-3" onsubmit="event.preventDefault(); send();">
                <input type="text" id="msg-input" placeholder="Escribe un mensaje de coordinación..." class="flex-1 bg-slate-100 border-none rounded-2xl px-6 py-3 focus:ring-2 focus:ring-brand outline-none text-sm">
                <button type="submit" class="bg-brand text-white w-12 h-12 rounded-2xl shadow-lg hover:scale-105 transition-transform flex items-center justify-center">
                    <i class="fas fa-paper-plane"></i>
                </button>
            </form>
        </div>
    </div>
</div>
<script>
    const socket = io();
    const room = "{{ solicitud.id_solicitud }}";
    const user = "{{ current_user.nombre }}";

    socket.emit('join', {room: room});

    socket.on('nuevo_mensaje', function(data) {
        const box = document.getElementById('chat-box');
        const isMe = data.user === user;
        const div = document.createElement('div');
        div.className = `flex ${isMe ? 'justify-end' : 'justify-start'}`;
        
        div.innerHTML = `
            <div class="${isMe ? 'bg-blue-600 text-white rounded-l-2xl rounded-tr-2xl' : 'bg-white text-slate-800 rounded-r-2xl rounded-tl-2xl shadow-sm border border-slate-200'} px-4 py-2 max-w-[80%]">
                <p class="text-[10px] ${isMe ? 'text-blue-100' : 'text-slate-400'} font-bold mb-1">${data.user}</p>
                <p class="text-sm">${data.msg}</p>
            </div>
        `;
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    });

    function send() {
        const input = document.getElementById('msg-input');
        if(input.value.trim()){
            socket.emit('enviar_mensaje', {msg: input.value, room: room});
            input.value = '';
        }
    }
</script>
{% endblock %}
"""

soporte_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto py-16 px-4">
    <div class="bg-white shadow-2xl rounded-3xl p-10 border-t-8 border-brand">
        <div class="text-center mb-12">
            <i class="fas fa-headset text-6xl text-brand mb-4"></i>
            <h2 class="text-4xl font-black text-slate-800">Soporte Técnico</h2>
            <p class="text-slate-500 mt-2">¿Tienes algún problema con la plataforma? Estamos para servirte.</p>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
            <div class="bg-slate-50 p-6 rounded-2xl text-center border border-slate-100">
                <div class="w-12 h-12 bg-blue-100 text-brand rounded-full flex items-center justify-center mx-auto mb-4"><i class="fas fa-envelope"></i></div>
                <h4 class="font-bold text-slate-900">Email</h4>
                <p class="text-xs text-slate-500 mt-2">ayuda@lifelink.com</p>
            </div>
            <div class="bg-slate-50 p-6 rounded-2xl text-center border border-slate-100">
                <div class="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4"><i class="fab fa-whatsapp"></i></div>
                <h4 class="font-bold text-slate-900">WhatsApp</h4>
                <p class="text-xs text-slate-500 mt-2">+52 55 9876 5432</p>
            </div>
            <div class="bg-slate-50 p-6 rounded-2xl text-center border border-slate-100">
                <div class="w-12 h-12 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center mx-auto mb-4"><i class="fas fa-clock"></i></div>
                <h4 class="font-bold text-slate-900">Horario</h4>
                <p class="text-xs text-slate-500 mt-2">L-V 9:00 - 18:00</p>
            </div>
        </div>

        <div class="bg-blue-50 p-6 rounded-2xl border border-blue-100 text-sm text-blue-800 leading-relaxed">
            <h5 class="font-bold mb-2 flex items-center gap-2"><i class="fas fa-shield-halved"></i> Compromiso de Seguridad</h5>
            LifeLink es un proyecto escolar (5IV7). Toda la información y transacciones son simulaciones con fines de demostración técnica y académica. Nunca compartas datos bancarios reales.
        </div>
    </div>
</div>
{% endblock %}
"""

# ... (Templates de Login/Registro/Dashboard/Search/Perfil se mantienen con estilo azul similar) ...
# Aquí omito los repetitivos pero aseguro que el loader los tenga todos.

# ==========================================
# 2. CONFIGURACIÓN APP
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'lifelink_ultra_secret_2026')
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///lifelink.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

socketio = SocketIO(app, cors_allowed_origins="*")
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Loader de Plantillas
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'publish.html': publish_template,
    'checkout.html': checkout_template,
    'chat.html': chat_template,
    'soporte.html': soporte_template,
    # Estos deben estar definidos o tomados del historial anterior:
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto my-20 bg-white p-10 rounded-3xl shadow-xl border border-slate-200">
        <h2 class="text-3xl font-black text-slate-800 mb-8 text-center underline decoration-brand">Crear Cuenta</h2>
        <form method="POST" class="space-y-4">
            <input name="nombre" placeholder="Nombre Completo" required class="w-full p-3 rounded-xl border border-slate-300 outline-none focus:ring-2 focus:ring-brand">
            <input name="email" type="email" placeholder="Email" required class="w-full p-3 rounded-xl border border-slate-300 outline-none focus:ring-2 focus:ring-brand">
            <input name="password" type="password" placeholder="Contraseña" required class="w-full p-3 rounded-xl border border-slate-300 outline-none focus:ring-2 focus:ring-brand">
            <button class="w-full btn-medical py-3 rounded-xl font-bold shadow-lg">Unirse</button>
        </form></div>{% endblock %}""",
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto my-20 bg-white p-10 rounded-3xl shadow-xl border border-slate-200">
        <h2 class="text-3xl font-black text-slate-800 mb-8 text-center underline decoration-brand">Ingresar</h2>
        <form method="POST" class="space-y-4">
            <input name="email" type="email" placeholder="Email" required class="w-full p-3 rounded-xl border border-slate-300 outline-none focus:ring-2 focus:ring-brand">
            <input name="password" type="password" placeholder="Contraseña" required class="w-full p-3 rounded-xl border border-slate-300 outline-none focus:ring-2 focus:ring-brand">
            <button class="w-full btn-medical py-3 rounded-xl font-bold shadow-lg">Entrar</button>
        </form></div>{% endblock %}""",
    'search.html': """{% extends "base.html" %}{% block content %}
    <div class="max-w-7xl mx-auto py-10 px-4">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div class="md:col-span-1 space-y-6">
                <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 sticky top-24">
                    <h4 class="font-bold text-slate-800 mb-4">Filtrar</h4>
                    <form method="GET">
                        <input name="q" placeholder="Buscar..." class="w-full p-2 border border-slate-300 rounded-lg text-sm mb-4">
                        <select name="categoria" class="w-full p-2 border border-slate-300 rounded-lg text-sm mb-4"><option value="">Categoría</option><option>Sangre</option><option>Medicamento</option><option>Ortopedico</option></select>
                        <button class="w-full btn-medical py-2 rounded-lg text-sm font-bold shadow">Aplicar</button>
                    </form>
                </div>
            </div>
            <div class="md:col-span-3 grid grid-cols-1 sm:grid-cols-2 gap-6">
                {% for item in resultados %}
                <div class="product-card bg-white border border-slate-200 relative">
                    <img src="{{ item.imagen_url }}" class="w-full h-48 object-cover">
                    <div class="p-4">
                        <h3 class="font-bold text-slate-900 text-lg">{{ item.nombre }}</h3>
                        <p class="text-xs text-slate-400 mb-4">{{ item.categoria }}</p>
                        <div class="flex justify-between items-center">
                            <span class="text-brand font-black">{% if item.tipo_publicacion == 'Venta' %} ${{ item.precio }} {% else %} GRATIS {% endif %}</span>
                            <a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="bg-slate-100 hover:bg-brand hover:text-white p-2 rounded-lg transition"><i class="fas fa-chevron-right"></i></a>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>{% endblock %}""",
    'dashboard.html': """{% extends "base.html" %}{% block content %}<div class="max-w-6xl mx-auto py-10 px-4">
        <h1 class="text-3xl font-black text-slate-900 mb-10">Panel de Gestión</h1>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-10">
            <div class="bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden">
                <div class="bg-slate-100 p-4 font-bold text-slate-700">Solicitudes Recibidas</div>
                <div class="p-4 space-y-4">
                    {% for sol in solicitudes_recibidas %}<div class="flex justify-between items-center border-b pb-4">
                        <div><p class="font-bold text-slate-800">{{ sol.publicacion.nombre }}</p><p class="text-xs text-slate-400">De: {{ sol.solicitante.nombre }}</p></div>
                        <a href="{{ url_for('chat', id_solicitud=sol.id_solicitud) }}" class="btn-medical px-4 py-2 rounded-xl text-xs font-bold">Chat</a>
                    </div>{% else %}<p class="text-slate-400 text-center py-10">Sin solicitudes aún.</p>{% endfor %}
                </div>
            </div>
            <div class="bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden">
                <div class="bg-slate-100 p-4 font-bold text-slate-700">Mis Insumos</div>
                <div class="p-4 space-y-4">
                    {% for pub in publicaciones %}<div class="flex items-center gap-4">
                        <img src="{{ pub.imagen_url }}" class="w-12 h-12 rounded object-cover">
                        <div class="flex-1"><p class="font-bold text-slate-800">{{ pub.nombre }}</p></div>
                        <span class="text-[10px] bg-blue-100 text-brand px-2 py-1 rounded-full font-bold">{{ pub.estado }}</span>
                    </div>{% endfor %}
                </div>
            </div>
        </div>
    </div>{% endblock %}""",
    'perfil.html': """{% extends "base.html" %}{% block content %}<div class="max-w-2xl mx-auto py-20 text-center">
        <div class="w-24 h-24 bg-brand text-white text-4xl font-bold rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl border-4 border-white">{{ current_user.nombre[0] | upper }}</div>
        <h2 class="text-3xl font-black text-slate-900">{{ current_user.nombre }}</h2>
        <p class="text-slate-500 mb-10">{{ current_user.email }}</p>
        <div class="bg-white p-8 rounded-3xl shadow-sm border border-slate-200">
            <h4 class="font-bold text-slate-700 mb-4 border-b pb-2">Configuración</h4>
            <div class="space-y-4 text-left">
                <div class="flex justify-between"><span>Estatus:</span><span class="font-bold text-emerald-600">Verificado</span></div>
                <div class="flex justify-between"><span>Grupo:</span><span class="font-bold">5IV7</span></div>
            </div>
        </div>
    </div>{% endblock %}"""
})

# ==========================================
# 3. MODELOS DB
# ==========================================
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    ubicacion = db.Column(db.String(255))
    def get_id(self): return str(self.id_usuario)

class Publicacion(db.Model):
    __tablename__ = 'insumos_ofertas'
    id_oferta_insumo = db.Column(db.Integer, primary_key=True)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    tipo_publicacion = db.Column(db.String(50))
    categoria = db.Column(db.String(50))
    precio = db.Column(db.Float, default=0.0)
    imagen_url = db.Column(db.String(500))
    estado = db.Column(db.String(20), default='Disponible')
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    proveedor = db.relationship('Usuario', backref='publicaciones')

class Solicitud(db.Model):
    __tablename__ = 'solicitudes_contacto'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('insumos_ofertas.id_oferta_insumo'))
    estado = db.Column(db.String(20), default='Pendiente')
    solicitante = db.relationship('Usuario', backref='solicitudes_enviadas')
    publicacion = db.relationship('Publicacion', backref='solicitudes_recibidas')

@login_manager.user_loader
def load_user(user_id): return Usuario.query.get(int(user_id))

# ==========================================
# 4. RUTAS
# ==========================================
@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if Usuario.query.filter_by(email=request.form['email']).first():
            flash("Email ya registrado", "error")
        else:
            u = Usuario(nombre=request.form['nombre'], email=request.form['email'], password_hash=generate_password_hash(request.form['password']))
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
        flash("Credenciales inválidas", "error")
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
            precio=float(request.form.get('precio', 0)),
            imagen_url=img_url,
            latitud=float(request.form.get('lat', 19.4326)),
            longitud=float(request.form.get('lng', -99.1332))
        )
        db.session.add(p)
        db.session.commit()
        flash("¡Publicación exitosa!", "success")
        return redirect(url_for('dashboard'))
    return render_template('publish.html')

@app.route('/buscar')
def buscar():
    q = request.args.get('q', '')
    cat = request.args.get('categoria', '')
    res = Publicacion.query.filter(Publicacion.nombre.contains(q), Publicacion.categoria.contains(cat)).all()
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
    flash("Solicitud procesada con éxito", "success")
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id_usuario).all()
    pub_ids = [p.id_oferta_insumo for p in pubs]
    sols = Solicitud.query.filter(Solicitud.id_publicacion.in_(pub_ids)).all() if pub_ids else []
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols)

@app.route('/chat/<int:id_solicitud>')
@login_required
def chat(id_solicitud):
    s = Solicitud.query.get_or_404(id_solicitud)
    return render_template('chat.html', solicitud=s)

@app.route('/soporte')
def soporte(): return render_template('soporte.html')

@app.route('/perfil')
@login_required
def perfil(): return render_template('perfil.html')

# --- SOCKETIO EVENTS ---
@socketio.on('join')
def handle_join(data): join_room(data['room'])

@socketio.on('enviar_mensaje')
def handle_msg(data):
    emit('nuevo_mensaje', {'msg': data['msg'], 'user': current_user.nombre}, room=data['room'])

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    socketio.run(app, debug=False)
