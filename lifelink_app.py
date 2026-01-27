import os
import logging
# import base64 (Ya no se usa base64 local, usaremos Cloudinary)
import jinja2
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
# NUEVOS IMPORTS PARA RENDER
from flask_socketio import SocketIO, emit, join_room
import cloudinary
import cloudinary.uploader

# --- CONFIGURACIÓN TÉCNICA ---
from flask import cli
cli.show_server_banner = lambda *_: None 

# --- CONFIGURACIÓN CLOUDINARY (Imágenes) ---
# En Render, estas se configuran en "Environment Variables"
cloudinary.config(
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', 'pon_tu_cloud_name_aqui_si_es_local'),
  api_key = os.environ.get('CLOUDINARY_API_KEY', 'pon_tu_api_key'),
  api_secret = os.environ.get('CLOUDINARY_API_SECRET', 'pon_tu_api_secret'),
  secure = True
)

# ==========================================
# 1. PLANTILLAS HTML (FRONTEND)
# ==========================================

base_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LifeLink - TechPulse</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <!-- Socket.IO Cliente -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    
    <style>
        .bg-brand { background-color: #6B21A8; }
        .text-brand { color: #6B21A8; }
        .btn-primary { background-color: #6B21A8; color: white; padding: 0.5rem 1rem; border-radius: 0.375rem; transition: background 0.3s; }
        .btn-primary:hover { background-color: #581c87; }
        #map { height: 300px; width: 100%; border-radius: 0.5rem; margin-top: 1rem; z-index: 0; }
        .chat-float { position: fixed; bottom: 20px; right: 20px; z-index: 1000; }
        .sold-out-overlay { position: absolute; inset: 0; background: rgba(255,255,255,0.85); display: flex; align-items: center; justify-content: center; z-index: 10; border-radius: 0.5rem; }
        .sold-badge { background: #DC2626; color: white; font-weight: bold; padding: 0.5rem 1.5rem; transform: rotate(-12deg); border: 4px solid white; box-shadow: 0 4px 6px rgba(0,0,0,0.1); font-size: 1.25rem; }
        .product-img { width: 100%; height: 200px; object-fit: cover; border-radius: 0.5rem; }
    </style>
</head>
<body class="bg-gray-50 flex flex-col min-h-screen">
    <nav class="bg-white shadow-md sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16">
                <div class="flex items-center">
                    <a href="/" class="flex-shrink-0 flex items-center gap-2 group">
                        <div class="bg-brand text-white p-2 rounded-lg group-hover:bg-purple-900 transition">
                            <i class="fa-solid fa-heart-pulse text-2xl"></i>
                        </div>
                        <div class="flex flex-col">
                            <span class="font-bold text-xl text-gray-800 leading-none">LifeLink</span>
                            <span class="text-xs text-brand font-semibold tracking-wider">BY TECHPULSE</span>
                        </div>
                    </a>
                    <div class="hidden sm:ml-8 sm:flex sm:space-x-8">
                        <a href="{{ url_for('buscar') }}" class="text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 border-transparent hover:border-brand text-sm font-medium transition">Buscar</a>
                        {% if current_user.is_authenticated %}
                        <a href="{{ url_for('publicar') }}" class="text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 border-transparent hover:border-brand text-sm font-medium transition">Publicar</a>
                        <a href="{{ url_for('dashboard') }}" class="text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 border-transparent hover:border-brand text-sm font-medium transition">Mi Panel</a>
                        <a href="{{ url_for('mis_pedidos') }}" class="text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 border-transparent hover:border-brand text-sm font-medium transition">Mis Pedidos</a>
                        <a href="{{ url_for('perfil') }}" class="text-gray-900 inline-flex items-center px-1 pt-1 border-b-2 border-transparent hover:border-brand text-sm font-medium transition">Mi Perfil</a>
                        {% endif %}
                    </div>
                </div>
                <div class="flex items-center">
                    {% if current_user.is_authenticated %}
                        <div class="flex items-center">
                            <span class="text-gray-700 mr-3 text-sm hidden md:block font-medium">Hola, {{ current_user.nombre.split()[0] }}</span>
                            <div class="h-9 w-9 rounded-full bg-purple-100 border-2 border-brand flex items-center justify-center text-brand font-bold mr-4 cursor-default shadow-sm">
                                {{ current_user.nombre[0] | upper }}
                            </div>
                            <a href="{{ url_for('logout') }}" class="text-gray-400 hover:text-red-600 transition" title="Cerrar Sesión"><i class="fa-solid fa-sign-out-alt text-xl"></i></a>
                        </div>
                    {% else %}
                        <a href="{{ url_for('login') }}" class="text-gray-600 font-medium hover:text-brand mr-4 transition">Ingresar</a>
                        <a href="{{ url_for('registro') }}" class="btn-primary shadow-lg transform hover:scale-105 transition">Registrarse</a>
                    {% endif %}
                </div>
            </div>
        </div>
    </nav>
    <main class="flex-grow">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="max-w-7xl mx-auto mt-4 px-4">
              {% for category, message in messages %}
                <div class="p-4 mb-4 text-sm text-white rounded-lg shadow-md flex items-center {% if category == 'error' %}bg-red-500{% else %}bg-green-500{% endif %}" role="alert">
                  <i class="fas {% if category == 'error' %}fa-exclamation-circle{% else %}fa-check-circle{% endif %} mr-3 text-lg"></i> 
                  <span>{{ message }}</span>
                </div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <div class="chat-float">
        <a href="{{ url_for('soporte') }}" class="bg-blue-600 text-white p-4 rounded-full shadow-lg hover:bg-blue-700 transition flex items-center justify-center w-14 h-14 transform hover:scale-110 ring-4 ring-blue-200" title="Soporte Técnico 24/7">
            <i class="fas fa-headset text-2xl"></i>
        </a>
    </div>
    <footer class="bg-gray-900 text-white mt-12 border-t border-gray-800">
        <div class="max-w-7xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
            <p class="text-center text-gray-500 text-xs">&copy; 2026 TechPulse - LifeLink Project. Todos los derechos reservados.</p>
        </div>
    </footer>
</body>
</html>
"""

# ... (home_template, register_template, login_template, dashboard_template, mis_pedidos_template, checkout_template, perfil_template IGUALES AL ANTERIOR) ...
# Pongo aquí solo los que cambian drásticamente: PUBLISH y CHAT

home_template = """
{% extends "base.html" %}
{% block content %}
<div class="relative bg-white overflow-hidden">
    <div class="max-w-7xl mx-auto">
        <div class="relative z-10 pb-8 bg-white sm:pb-16 md:pb-20 lg:max-w-2xl lg:w-full lg:pb-28 xl:pb-32">
            <main class="mt-10 mx-auto max-w-7xl px-4 sm:mt-12 sm:px-6 md:mt-16 lg:mt-20 lg:px-8 xl:mt-28">
                <div class="sm:text-center lg:text-left">
                    <h1 class="text-4xl tracking-tight font-extrabold text-gray-900 sm:text-5xl md:text-6xl">
                        <span class="block xl:inline">Conectando esperanza</span>
                        <span class="block text-brand">salvando vidas.</span>
                    </h1>
                    <p class="mt-3 text-base text-gray-500 sm:mt-5 sm:text-lg sm:max-w-xl sm:mx-auto md:mt-5 md:text-xl lg:mx-0">
                        La plataforma inteligente que conecta a donantes y receptores de insumos médicos y sangre en tiempo real.
                    </p>
                    <div class="mt-5 sm:mt-8 sm:flex sm:justify-center lg:justify-start">
                        <div class="rounded-md shadow">
                            <a href="{{ url_for('buscar') }}" class="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-brand hover:bg-purple-800 md:py-4 md:text-lg transition transform hover:scale-105 shadow-lg">
                                <i class="fas fa-search mr-2"></i> Buscar Ayuda
                            </a>
                        </div>
                        <div class="mt-3 sm:mt-0 sm:ml-3">
                            <a href="{{ url_for('registro') }}" class="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-brand bg-purple-100 hover:bg-purple-200 md:py-4 md:text-lg transition transform hover:scale-105 shadow-md">
                                <i class="fas fa-hand-holding-heart mr-2"></i> Quiero Donar
                            </a>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    </div>
    <div class="lg:absolute lg:inset-y-0 lg:right-0 lg:w-1/2">
        <img class="h-56 w-full object-cover sm:h-72 md:h-96 lg:w-full lg:h-full" src="https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?ixlib=rb-1.2.1&auto=format&fit=crop&w=1350&q=80" alt="Médicos trabajando">
    </div>
</div>
{% endblock %}
"""

register_template = """
{% extends "base.html" %}
{% block content %}
<div class="min-h-full flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gray-50">
    <div class="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg border border-gray-100">
        <div>
            <div class="flex justify-center"><i class="fas fa-heart-pulse text-5xl text-brand animate-pulse"></i></div>
            <h2 class="mt-4 text-center text-3xl font-extrabold text-gray-900">Únete a LifeLink</h2>
        </div>
        <form class="mt-8 space-y-4" action="{{ url_for('registro') }}" method="POST">
            <div class="rounded-md shadow-sm space-y-3">
                <input name="nombre" type="text" required class="appearance-none rounded relative block w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-brand sm:text-sm" placeholder="Nombre Completo">
                <input name="email" type="email" required pattern="[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$" class="appearance-none rounded relative block w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-brand sm:text-sm" placeholder="usuario@ejemplo.com">
                <input name="password" type="password" required class="appearance-none rounded relative block w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-brand sm:text-sm" placeholder="Contraseña">
                <input name="direccion" type="text" class="appearance-none rounded relative block w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-brand sm:text-sm" placeholder="Dirección">
                <div class="grid grid-cols-2 gap-4">
                    <select name="rol" class="block w-full px-3 py-2 border border-gray-300 bg-white rounded sm:text-sm"><option value="Solicitante">Solicitante</option><option value="Donante">Donante</option><option value="Ambos">Ambos</option></select>
                    <select name="id_tipo_sangre" class="block w-full px-3 py-2 border border-gray-300 bg-white rounded sm:text-sm"><option value="">N/A</option>{% for ts in tipos_sangre %}<option value="{{ ts.id_tipo_sangre }}">{{ ts.grupo }}{{ ts.factor_rh }}</option>{% endfor %}</select>
                </div>
            </div>
            <div><button type="submit" class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-brand hover:bg-purple-800 transition">Registrarse</button></div>
        </form>
    </div>
</div>
{% endblock %}
"""

login_template = """
{% extends "base.html" %}
{% block content %}
<div class="min-h-full flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gray-50">
    <div class="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg border border-gray-100">
        <div>
            <div class="flex justify-center"><i class="fas fa-user-circle text-5xl text-brand"></i></div>
            <h2 class="mt-4 text-center text-3xl font-extrabold text-gray-900">Bienvenido</h2>
        </div>
        <form class="mt-8 space-y-6" action="{{ url_for('login') }}" method="POST">
            <div class="rounded-md shadow-sm space-y-4">
                <input name="email" type="email" required class="appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-brand sm:text-sm" placeholder="Correo Electrónico">
                <input name="password" type="password" required class="appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 focus:outline-none focus:ring-brand sm:text-sm" placeholder="Contraseña">
            </div>
            <div><button type="submit" class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-brand hover:bg-purple-800 transition">Iniciar Sesión</button></div>
        </form>
    </div>
</div>
{% endblock %}
"""

dashboard_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
    <h1 class="text-3xl font-bold text-gray-900 mb-6">Panel de Gestión</h1>
    <div class="bg-white shadow overflow-hidden sm:rounded-md mb-8">
        <div class="px-4 py-5 border-b border-gray-200 bg-gray-50"><h3 class="text-lg leading-6 font-medium text-gray-900">Solicitudes Recibidas</h3></div>
        <ul class="divide-y divide-gray-200">
             {% for sol in solicitudes_recibidas %}
            <li class="px-4 py-4 sm:px-6 hover:bg-gray-50 transition">
                <div class="md:flex md:justify-between md:items-center">
                    <div class="mb-4 md:mb-0">
                        <p class="text-sm font-bold text-brand">Pedido #{{ sol.id_solicitud }} - {{ sol.publicacion.nombre }}</p>
                        <p class="text-xs text-gray-500">Cliente: {{ sol.solicitante.nombre }}</p>
                        <p class="mt-2"><span class="px-2 py-1 rounded text-xs font-bold bg-gray-100 text-gray-800">{{ sol.estado }}</span></p>
                        {% if sol.fecha_entrega %}<p class="text-xs text-blue-600 mt-1 font-bold">Entrega: {{ sol.fecha_entrega }}</p>{% endif %}
                    </div>
                    <div class="flex flex-col space-y-2">
                        <a href="{{ url_for('chat', id_solicitud=sol.id_solicitud) }}" class="bg-indigo-500 text-white px-3 py-1 rounded text-xs hover:bg-indigo-600 text-center"><i class="fas fa-comments"></i> Chat</a>
                        {% if sol.estado == 'Pendiente' %}
                            <form action="{{ url_for('actualizar_estado_pedido', id=sol.id_solicitud) }}" method="POST" class="flex flex-col gap-2">
                                <input type="datetime-local" name="fecha_entrega" required class="border rounded text-xs p-1">
                                <button type="submit" name="accion" value="programar" class="bg-blue-600 text-white px-3 py-1 rounded text-xs hover:bg-blue-700">Programar</button>
                            </form>
                        {% elif sol.estado == 'Procesando' %}
                            <form action="{{ url_for('actualizar_estado_pedido', id=sol.id_solicitud) }}" method="POST">
                                <button type="submit" name="accion" value="completar" class="bg-green-600 text-white px-3 py-1 rounded text-xs hover:bg-green-700 w-full">Entregado</button>
                            </form>
                        {% endif %}
                    </div>
                </div>
            </li>
            {% else %}<li class="px-4 py-8 text-center text-gray-500">No tienes pedidos pendientes.</li>{% endfor %}
        </ul>
    </div>
    <h2 class="text-2xl font-bold text-gray-900 mb-4">Mis Insumos</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {% for pub in publicaciones %}
        <div class="bg-white overflow-hidden shadow rounded-lg border-l-4 {% if pub.tipo_publicacion == 'Venta' %}border-blue-500{% else %}border-green-500{% endif %} relative">
            <div class="p-4">
                <img src="{{ pub.imagen_url }}" class="product-img mb-2 shadow-sm" onerror="this.src='https://via.placeholder.com/300?text=No+Image'">
                {% if pub.estado != 'Disponible' %}
                <div class="absolute inset-0 bg-white bg-opacity-80 flex items-center justify-center z-10 rounded-lg">
                    <span class="bg-red-600 text-white font-bold px-4 py-2 rounded text-sm transform -rotate-12 shadow-xl">{{ pub.estado }}</span>
                </div>
                {% endif %}
                <h3 class="text-lg font-bold text-gray-900 truncate">{{ pub.nombre }}</h3>
                <p class="text-sm text-gray-500">{{ pub.tipo_publicacion }}</p>
                <form action="{{ url_for('eliminar_publicacion', id_publicacion=pub.id_oferta_insumo) }}" method="POST" onsubmit="return confirm('¿Eliminar?');" class="mt-3 text-right">
                    <button class="text-red-500 hover:text-red-700 text-xs font-bold uppercase tracking-wide transition"><i class="fas fa-trash"></i> Eliminar</button>
                </form>
            </div>
        </div>
        {% else %}<p class="text-gray-500 col-span-3 text-center py-8 bg-white rounded-lg shadow">No has publicado nada aún.</p>{% endfor %}
    </div>
</div>
{% endblock %}
"""

mis_pedidos_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
    <h1 class="text-3xl font-bold text-gray-900 mb-6">Mis Pedidos</h1>
    <div class="bg-white shadow overflow-hidden sm:rounded-md">
        <ul class="divide-y divide-gray-200">
            {% for pedido in pedidos %}
            <li class="px-4 py-4 sm:px-6 hover:bg-gray-50 transition">
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="text-lg font-bold text-gray-900">{{ pedido.publicacion.nombre }}</h3>
                        <p class="text-sm text-gray-500">Vendedor: {{ pedido.publicacion.proveedor.nombre }}</p>
                        <div class="mt-2"><span class="px-2 py-1 rounded text-xs font-bold bg-gray-100 text-gray-800">{{ pedido.estado }}</span></div>
                        {% if pedido.fecha_entrega %}
                        <div class="mt-2 p-2 bg-blue-50 rounded border border-blue-100"><p class="text-sm text-blue-800"><i class="fas fa-clock mr-1"></i> <strong>Entrega:</strong> {{ pedido.fecha_entrega }}</p></div>
                        {% endif %}
                    </div>
                    <div><a href="{{ url_for('chat', id_solicitud=pedido.id_solicitud) }}" class="bg-brand text-white px-4 py-2 rounded-md hover:bg-purple-800 text-sm shadow transition"><i class="fas fa-comments"></i> Chat</a></div>
                </div>
            </li>
            {% else %}<li class="px-4 py-8 text-center text-gray-500">No has realizado ninguna compra o solicitud.</li>{% endfor %}
        </ul>
    </div>
</div>
{% endblock %}
"""

checkout_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-2xl mx-auto py-10 px-4 sm:px-6">
    <div class="bg-white shadow-xl rounded-lg overflow-hidden">
        <div class="px-6 py-4 bg-gray-50 border-b border-gray-200"><h3 class="text-lg font-bold text-gray-900">Confirmar Pedido</h3></div>
        <div class="p-6">
            <div class="flex items-center mb-6 bg-purple-50 p-4 rounded-lg">
                <img src="{{ pub.imagen_url }}" class="w-16 h-16 rounded object-cover mr-4 shadow-sm" onerror="this.src='https://via.placeholder.com/150'">
                <div class="flex-1"><h4 class="text-xl font-bold text-gray-900">{{ pub.nombre }}</h4><p class="text-sm text-gray-600">{{ pub.proveedor.nombre }}</p></div>
                <div class="text-right"><p class="text-2xl font-bold text-brand">{% if pub.tipo_publicacion == 'Venta' %} ${{ pub.precio }} {% else %} $0.00 {% endif %}</p></div>
            </div>
            <form action="{{ url_for('procesar_transaccion', id=pub.id_oferta_insumo) }}" method="POST">
                <h4 class="font-medium text-gray-900 mb-3">Datos de Entrega</h4>
                <div class="mb-6"><input type="text" name="direccion_envio" required value="{{ current_user.ubicacion or '' }}" class="w-full border border-gray-300 rounded p-3 focus:ring-brand focus:border-brand" placeholder="Dirección completa"></div>
                {% if pub.tipo_publicacion == 'Venta' %}
                <h4 class="font-medium text-gray-900 mb-3">Método de Pago</h4>
                <div class="space-y-4 mb-6">
                    <div class="border p-4 rounded flex items-center cursor-pointer hover:border-brand transition"><input type="radio" name="metodo_pago" value="Tarjeta" checked class="mr-3"><span class="font-medium">Tarjeta</span><div class="ml-auto text-gray-400 text-xl"><i class="fab fa-cc-visa"></i></div></div>
                    <div class="bg-gray-50 p-4 rounded space-y-3 border border-gray-200"><input type="text" placeholder="Número de Tarjeta" class="w-full border border-gray-300 rounded p-2"><div class="grid grid-cols-2 gap-4"><input type="text" placeholder="MM/AA" class="border border-gray-300 rounded p-2"><input type="text" placeholder="CVC" class="border border-gray-300 rounded p-2"></div></div>
                    <div class="border p-4 rounded flex items-center cursor-pointer hover:border-brand transition"><input type="radio" name="metodo_pago" value="Efectivo" class="mr-3"><span class="font-medium">Efectivo (Contra Entrega)</span></div>
                </div>
                {% else %}<input type="hidden" name="metodo_pago" value="Donación">{% endif %}
                <button type="submit" class="w-full bg-brand text-white py-3 px-4 rounded-md font-bold hover:bg-purple-800 shadow-lg transition transform hover:-translate-y-0.5">Confirmar</button>
            </form>
        </div>
    </div>
</div>
{% endblock %}
"""

perfil_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-3xl mx-auto py-10 px-4 sm:px-6">
    <div class="bg-white shadow rounded-lg overflow-hidden">
        <div class="bg-brand px-4 py-5 sm:px-6">
            <h3 class="text-lg leading-6 font-medium text-white">Editar Perfil</h3>
            <p class="mt-1 max-w-2xl text-sm text-purple-200">Mantén tu información actualizada.</p>
        </div>
        <div class="p-6">
            <form action="{{ url_for('editar_perfil') }}" method="POST">
                <div class="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-6">
                    <div class="sm:col-span-3">
                        <label class="block text-sm font-medium text-gray-700">Nombre</label>
                        <input type="text" name="nombre" value="{{ current_user.nombre }}" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 sm:text-sm">
                    </div>
                    <div class="sm:col-span-3">
                        <label class="block text-sm font-medium text-gray-700">Email</label>
                        <input type="email" name="email" value="{{ current_user.email }}" readonly class="mt-1 block w-full border border-gray-300 bg-gray-100 rounded-md shadow-sm py-2 px-3 sm:text-sm">
                    </div>
                    <div class="sm:col-span-6">
                        <label class="block text-sm font-medium text-gray-700">Dirección</label>
                        <input type="text" name="ubicacion" value="{{ current_user.ubicacion or '' }}" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 sm:text-sm">
                    </div>
                    <div class="sm:col-span-3">
                        <label class="block text-sm font-medium text-gray-700">Teléfono</label>
                        <input type="text" name="telefono" value="{{ current_user.telefono or '' }}" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 sm:text-sm">
                    </div>
                </div>
                <div class="mt-6 flex justify-end">
                    <button type="submit" class="bg-brand text-white px-4 py-2 rounded-md hover:bg-purple-800 transition">Guardar</button>
                </div>
            </form>
        </div>
    </div>
    <div class="mt-8 bg-white shadow rounded-lg overflow-hidden">
        <div class="px-4 py-5 sm:px-6 border-b border-gray-200"><h3 class="text-lg leading-6 font-medium text-gray-900">Historial</h3></div>
        <ul class="divide-y divide-gray-200">
            {% for hist in historial %}
            <li class="px-4 py-4 sm:px-6"><div class="flex justify-between"><span class="text-sm font-medium text-gray-900">{{ hist.publicacion.nombre }}</span><span class="text-xs text-gray-500">{{ hist.fecha_solicitud.strftime('%d/%m/%Y') }}</span></div><p class="text-xs text-gray-500">Estado: {{ hist.estado }}</p></li>
            {% else %}<li class="px-4 py-4 text-sm text-gray-500 text-center">Sin actividad reciente.</li>{% endfor %}
        </ul>
    </div>
</div>
{% endblock %}
"""

# HTML DEL CHAT (Con SocketIO Client para Render)
chat_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-2xl mx-auto py-10 px-4 sm:px-6">
    <div class="bg-white shadow-xl rounded-lg overflow-hidden flex flex-col h-[600px]">
        <div class="px-6 py-4 bg-brand text-white flex justify-between items-center">
            <div><h3 class="text-lg font-bold"><i class="fas fa-comments mr-2"></i> Chat</h3></div>
            <span class="text-xs bg-purple-700 px-2 py-1 rounded">En Vivo</span>
        </div>
        <div class="flex-1 p-6 overflow-y-auto bg-gray-50 space-y-4" id="chat-box">
            <div class="text-center text-xs text-gray-400 my-4">--- Inicio de la conversación ---</div>
        </div>
        <div class="p-4 bg-white border-t border-gray-200">
            <form class="flex gap-2" onsubmit="event.preventDefault(); enviarMensaje();">
                <input type="text" id="msg-input" class="flex-1 border border-gray-300 rounded-full px-4 py-2 focus:outline-none focus:border-brand" placeholder="Escribe un mensaje...">
                <button type="submit" class="bg-brand text-white rounded-full p-2 w-10 h-10 hover:bg-purple-800 flex items-center justify-center transition"><i class="fas fa-paper-plane"></i></button>
            </form>
        </div>
    </div>
</div>
<script>
    // Inicializar SocketIO
    var socket = io();
    var room = "{{ solicitud.id_solicitud }}"; // Room único por pedido

    // Unirse al room al cargar
    socket.emit('join', {room: room});

    // Escuchar nuevos mensajes
    socket.on('nuevo_mensaje', function(data) {
        const chatBox = document.getElementById('chat-box');
        const isMe = data.user === "{{ current_user.nombre }}";
        const msgDiv = document.createElement('div');
        msgDiv.className = isMe ? 'flex justify-end' : 'flex justify-start';
        
        // Estilos diferentes si soy yo o el otro
        const bubbleColor = isMe ? 'bg-purple-100 border-purple-200' : 'bg-white border-gray-200';
        
        msgDiv.innerHTML = `
            <div class="${bubbleColor} border rounded-lg py-2 px-4 max-w-[80%] shadow-sm">
                <p class="text-xs text-gray-500 mb-1">${data.user}</p>
                <p class="text-sm text-gray-800">${data.msg}</p>
                <span class="text-xs text-gray-400 block text-right mt-1">Ahora</span>
            </div>
        `;
        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    });

    function enviarMensaje() {
        const input = document.getElementById('msg-input');
        const text = input.value;
        if(!text) return;
        
        // Enviar al servidor
        socket.emit('enviar_mensaje', {msg: text, room: room});
        input.value = '';
    }
</script>
{% endblock %}
"""

# CAMBIOS EN PUBLISH PARA SUBIR FOTO REAL A CLOUDINARY
publish_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
    <div class="bg-white shadow px-4 py-5 sm:rounded-lg sm:p-6">
        <h2 class="text-2xl font-bold mb-6">Publicar Insumo</h2>
        <form action="{{ url_for('publicar') }}" method="POST" enctype="multipart/form-data" class="space-y-6">
            <!-- INPUT DE ARCHIVO REAL -->
            <div>
                <label class="block text-sm font-medium text-gray-700">Foto del Insumo (Subir Archivo)</label>
                <input type="file" name="imagen" accept="image/*" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3">
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div><label class="block text-sm font-medium text-gray-700">Nombre</label><input type="text" name="nombre" required class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3"></div>
                <div><label class="block text-sm font-medium text-gray-700">Categoría</label><select name="categoria" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3"><option value="Medicamento">Medicamento</option><option value="Ortopedico">Ortopédico</option><option value="Sangre">Sangre</option><option value="Equipo">Equipo Médico</option></select></div>
            </div>
            
            <div><label class="block text-sm font-medium text-gray-700">Descripción</label><textarea name="descripcion" rows="3" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3"></textarea></div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label class="block text-sm font-medium text-gray-700">Tipo</label>
                    <select id="tipo" name="tipo_publicacion" onchange="document.getElementById('sec-precio').classList.toggle('hidden', this.value !== 'Venta')" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3">
                        <option value="Donacion">Donación</option>
                        <option value="Venta">Venta</option>
                    </select>
                </div>
                <div id="sec-precio" class="hidden">
                    <label class="block text-sm font-medium text-gray-700">Precio</label>
                    <input type="number" name="precio" placeholder="0.00" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3">
                </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6"><div><label class="block text-sm font-medium text-gray-700">Disponibilidad</label><select name="es_unico" class="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3"><option value="1">Único (Se agota)</option><option value="0">Múltiple</option></select></div></div>

            <!-- Mapa simplificado -->
            <div><label class="block text-sm font-medium text-gray-700 mb-2">Ubicación</label><div id="map"></div><input type="hidden" id="lat" name="lat"><input type="hidden" id="lng" name="lng"></div>
            <script>
                window.onload = function() {
                    var map = L.map('map').setView([19.4326, -99.1332], 13);
                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: 'OSM' }).addTo(map);
                    var marker;
                    map.on('click', function(e) {
                        if(marker) map.removeLayer(marker);
                        marker = L.marker(e.latlng).addTo(map);
                        document.getElementById('lat').value = e.latlng.lat;
                        document.getElementById('lng').value = e.latlng.lng;
                    });
                }
            </script>

            <div class="flex items-center"><input id="es_urgente" name="es_urgente" type="checkbox" class="h-4 w-4 text-brand rounded"><label for="es_urgente" class="ml-2 block text-sm text-red-600 font-bold">Urgente</label></div>
            <div class="flex justify-end"><button type="submit" class="bg-brand text-white px-4 py-2 rounded hover:bg-purple-800">Publicar</button></div>
        </form>
    </div>
</div>
{% endblock %}
"""

search_template = """
{% extends "base.html" %}
{% block content %}
<div class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
    <div class="bg-white p-6 shadow rounded-lg mb-6">
        <h1 class="text-2xl font-bold text-gray-900 mb-4">Encuentra lo que necesitas</h1>
        <form action="{{ url_for('buscar') }}" method="GET" class="grid grid-cols-1 md:grid-cols-4 gap-4">
            <input type="text" name="q" class="md:col-span-2 border border-gray-300 rounded-md p-2" placeholder="Ej: Silla de ruedas...">
            <select name="categoria" class="border border-gray-300 rounded-md p-2"><option value="">Categorías</option><option value="Medicamento">Medicamento</option><option value="Ortopedico">Ortopédico</option><option value="Sangre">Sangre</option></select>
            <button type="submit" class="bg-brand text-white rounded-md p-2 hover:bg-purple-800 md:col-start-4">Buscar</button>
        </form>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div class="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {% for item in resultados %}
            <div class="bg-white shadow rounded-lg p-4 border-t-4 {% if item.tipo_publicacion=='Donacion' %}border-green-500{% else %}border-blue-500{% endif %} hover:shadow-lg transition relative">
                {% if item.estado != 'Disponible' %}<div class="sold-out-overlay"><span class="sold-badge">AGOTADO</span></div>{% endif %}
                
                <!-- IMAGEN DESDE CLOUDINARY O URL -->
                <img src="{{ item.imagen_url }}" class="product-img mb-3 shadow-sm" onerror="this.src='https://via.placeholder.com/300?text=No+Image'">
                
                <div class="flex justify-between items-start"><h3 class="text-lg font-bold text-gray-900 truncate">{{ item.nombre }}</h3>{% if item.es_urgente %}<span class="bg-red-100 text-red-800 text-xs px-2 py-1 rounded font-bold animate-pulse">URGENTE</span>{% endif %}</div>
                <p class="text-gray-600 text-sm mt-1 h-10 overflow-hidden">{{ item.descripcion }}</p>
                <div class="mt-2 flex items-center justify-between"><span class="font-bold {% if item.tipo_publicacion=='Venta' %}text-blue-600{% else %}text-green-600{% endif %}">{% if item.tipo_publicacion=='Venta' %}${{ item.precio }}{% else %}Donación{% endif %}</span><span class="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">{{ item.categoria }}</span></div>
                <div class="mt-4">
                    {% if current_user.is_authenticated %}
                        {% if item.estado == 'Disponible' %}<a href="{{ url_for('confirmar_compra', id=item.id_oferta_insumo) }}" class="block w-full text-center py-2 px-4 rounded text-white font-medium transition shadow {% if item.tipo_publicacion=='Venta' %}bg-blue-600 hover:bg-blue-700{% else %}bg-green-600 hover:bg-green-700{% endif %}">{% if item.tipo_publicacion=='Venta' %}Comprar{% else %}Solicitar{% endif %}</a>
                        {% else %}<button disabled class="block w-full text-center py-2 px-4 rounded text-gray-500 bg-gray-200 font-medium cursor-not-allowed">No Disponible</button>{% endif %}
                    {% else %}<a href="{{ url_for('login') }}" class="block w-full text-center text-sm text-brand hover:underline">Inicia sesión</a>{% endif %}
                </div>
            </div>
            {% else %}<div class="col-span-2 py-12 text-center text-gray-500">No hay resultados.</div>{% endfor %}
        </div>
        <div class="lg:col-span-1 hidden lg:block">
            <div class="bg-white p-4 shadow rounded-lg sticky top-24"><h3 class="font-bold text-gray-700 mb-2 border-b pb-2">Mapa</h3><div id="map" style="height: 400px;"></div><script>var map = L.map('map').setView([19.4326, -99.1332], 12);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: 'OSM' }).addTo(map);{% for item in resultados %}{% if item.latitud and item.longitud and item.estado == 'Disponible' %}L.marker([{{ item.latitud }}, {{ item.longitud }}]).addTo(map).bindPopup("<b>{{ item.nombre }}</b>");{% endif %}{% endfor %}</script></div>
        </div>
    </div>
</div>
{% endblock %}
"""

# ==========================================
# 2. CONFIGURACIÓN
# ==========================================
app = Flask(__name__)
# SECRET KEY DESDE ENV
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'techpulse_lifelink_secret_key_2025')

# DB CONFIG (Render PostgreSQL o SQLite Local)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///lifelink.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# INICIAR SOCKETIO
socketio = SocketIO(app, cors_allowed_origins="*")

app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'register.html': register_template,
    'login.html': login_template,
    'dashboard.html': dashboard_template,
    'publish.html': publish_template,
    'search.html': search_template,
    'checkout.html': checkout_template,
    'perfil.html': perfil_template,
    'chat.html': chat_template,
    'mis_pedidos.html': mis_pedidos_template,
    'soporte.html': soporte_template
})

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==========================================
# 3. MODELOS
# ==========================================
class TipoSangre(db.Model):
    __tablename__ = 'tipos_sangre'
    id_tipo_sangre = db.Column(db.Integer, primary_key=True)
    grupo = db.Column(db.String(3), nullable=False)
    factor_rh = db.Column(db.String(1), nullable=False)

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(50))
    ubicacion = db.Column(db.String(255))
    telefono = db.Column(db.String(20))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    id_tipo_sangre = db.Column(db.Integer, db.ForeignKey('tipos_sangre.id_tipo_sangre'))
    tipo_sangre = db.relationship('TipoSangre', backref='usuarios')
    def get_id(self): return str(self.id_usuario)

class Publicacion(db.Model):
    __tablename__ = 'insumos_ofertas'
    id_oferta_insumo = db.Column(db.Integer, primary_key=True)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    tipo_publicacion = db.Column(db.String(50))
    categoria = db.Column(db.String(50))
    precio = db.Column(db.Float, default=0.0)
    formas_pago = db.Column(db.String(255))
    direccion = db.Column(db.String(255))
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)
    estado = db.Column(db.String(20), default='Disponible')
    es_urgente = db.Column(db.Boolean, default=False)
    es_unico = db.Column(db.Boolean, default=True)
    imagen_url = db.Column(db.String(500)) 
    fecha_publicacion = db.Column(db.DateTime, default=datetime.utcnow)
    proveedor = db.relationship('Usuario', backref='publicaciones')

class Solicitud(db.Model):
    __tablename__ = 'solicitudes_contacto'
    id_solicitud = db.Column(db.Integer, primary_key=True)
    id_solicitante = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    id_publicacion = db.Column(db.Integer, db.ForeignKey('insumos_ofertas.id_oferta_insumo'))
    estado = db.Column(db.String(20), default='Pendiente') 
    direccion_envio = db.Column(db.String(255))
    metodo_pago = db.Column(db.String(50))
    fecha_entrega = db.Column(db.String(50))
    fecha_solicitud = db.Column(db.DateTime, default=datetime.utcnow)
    
    solicitante = db.relationship('Usuario', backref='solicitudes_enviadas')
    publicacion = db.relationship('Publicacion', backref='solicitudes_recibidas')

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ==========================================
# 4. RUTAS Y LÓGICA
# ==========================================
@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    tipos = TipoSangre.query.all()
    if request.method == 'POST':
        email = request.form.get('email')
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash('Error: Email inválido.', 'error')
            return render_template('register.html', tipos_sangre=tipos)
        if Usuario.query.filter_by(email=email).first():
            flash('Correo ya registrado.', 'error')
            return redirect(url_for('registro'))
        
        new_user = Usuario(nombre=request.form.get('nombre'), email=email, password_hash=generate_password_hash(request.form.get('password')), rol=request.form.get('rol'), ubicacion=request.form.get('direccion'), id_tipo_sangre=request.form.get('id_tipo_sangre') or None)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('register.html', tipos_sangre=tipos)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = Usuario.query.filter_by(email=request.form.get('email')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Credenciales incorrectas.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    pubs = Publicacion.query.filter_by(id_proveedor=current_user.id_usuario).all()
    pub_ids = [p.id_oferta_insumo for p in pubs]
    sols = Solicitud.query.filter(Solicitud.id_publicacion.in_(pub_ids)).order_by(Solicitud.fecha_solicitud.desc()).all() if pub_ids else []
    return render_template('dashboard.html', publicaciones=pubs, solicitudes_recibidas=sols)

@app.route('/mis_pedidos')
@login_required
def mis_pedidos():
    pedidos = Solicitud.query.filter_by(id_solicitante=current_user.id_usuario).order_by(Solicitud.fecha_solicitud.desc()).all()
    return render_template('mis_pedidos.html', pedidos=pedidos)

@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    historial = Solicitud.query.join(Publicacion).filter(Publicacion.id_proveedor == current_user.id_usuario, Solicitud.estado == 'Completada').all()
    return render_template('perfil.html', historial=historial)

@app.route('/editar_perfil', methods=['POST'])
@login_required
def editar_perfil():
    current_user.nombre = request.form.get('nombre')
    current_user.ubicacion = request.form.get('ubicacion')
    current_user.telefono = request.form.get('telefono')
    db.session.commit()
    flash('Perfil actualizado.', 'success')
    return redirect(url_for('perfil'))

@app.route('/publicar', methods=['GET', 'POST'])
@login_required
def publicar():
    if request.method == 'POST':
        precio = request.form.get('precio')
        
        # SUBIDA A CLOUDINARY (Lógica Real)
        img_file = request.files.get('imagen')
        img_url = "https://via.placeholder.com/400x300?text=Sin+Imagen" # Fallback
        
        if img_file:
            try:
                # Sube la imagen y obtiene la URL segura
                upload_result = cloudinary.uploader.upload(img_file)
                img_url = upload_result['secure_url']
            except Exception as e:
                print(f"Error Cloudinary: {e}")
                # Si falla (ej. en local sin internet), usa una genérica
                img_url = "https://via.placeholder.com/400x300?text=Error+Subida"

        pub = Publicacion(
            id_proveedor=current_user.id_usuario,
            nombre=request.form.get('nombre'),
            descripcion=request.form.get('descripcion'),
            tipo_publicacion=request.form.get('tipo_publicacion'),
            categoria=request.form.get('categoria'),
            precio=float(precio) if precio else 0.0,
            formas_pago=request.form.get('formas_pago'),
            direccion=request.form.get('direccion'),
            latitud=float(request.form.get('lat')) if request.form.get('lat') else 19.4326,
            longitud=float(request.form.get('lng')) if request.form.get('lng') else -99.1332,
            es_urgente=bool(request.form.get('es_urgente')),
            es_unico=bool(int(request.form.get('es_unico'))),
            imagen_url=img_url # Guarda la URL de Cloudinary
        )
        db.session.add(pub)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('publish.html')

@app.route('/eliminar_publicacion/<int:id_publicacion>', methods=['POST'])
@login_required
def eliminar_publicacion(id_publicacion):
    pub = Publicacion.query.get_or_404(id_publicacion)
    if pub.id_proveedor != current_user.id_usuario: return redirect(url_for('dashboard'))
    Solicitud.query.filter_by(id_publicacion=id_publicacion).delete()
    db.session.delete(pub)
    db.session.commit()
    flash('Publicación eliminada.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/actualizar_estado_pedido/<int:id>', methods=['POST'])
@login_required
def actualizar_estado_pedido(id):
    sol = Solicitud.query.get_or_404(id)
    if sol.publicacion.id_proveedor != current_user.id_usuario: return redirect(url_for('dashboard'))
    accion = request.form.get('accion')
    if accion == 'programar':
        sol.estado = 'Procesando'
        sol.fecha_entrega = request.form.get('fecha_entrega').replace('T', ' ')
        flash('Pedido en camino.', 'success')
    elif accion == 'completar':
        sol.estado = 'Completada'
        flash('Pedido entregado.', 'success')
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/chat/<int:id_solicitud>')
@login_required
def chat(id_solicitud):
    sol = Solicitud.query.get_or_404(id_solicitud)
    if current_user.id_usuario not in [sol.id_solicitante, sol.publicacion.id_proveedor]:
        flash("Acceso denegado.", "error")
        return redirect(url_for('dashboard'))
    return render_template('chat.html', solicitud=sol)

@app.route('/soporte')
@login_required
def soporte(): return render_template('soporte.html')

@app.route('/buscar')
def buscar():
    q = request.args.get('q')
    cat = request.args.get('categoria')
    ts = request.args.get('tipo_sangre')
    query = Publicacion.query
    if q: query = query.filter(Publicacion.nombre.like(f"%{q}%") | Publicacion.descripcion.like(f"%{q}%"))
    if cat: query = query.filter_by(categoria=cat)
    if ts: query = query.join(Usuario).filter(Usuario.id_tipo_sangre == ts)
    return render_template('search.html', resultados=query.order_by(Publicacion.es_urgente.desc()).all(), tipos_sangre=TipoSangre.query.all())

@app.route('/confirmar_compra/<int:id>', methods=['GET'])
@login_required
def confirmar_compra(id):
    pub = Publicacion.query.get_or_404(id)
    return render_template('checkout.html', pub=pub)

@app.route('/procesar_transaccion/<int:id>', methods=['POST'])
@login_required
def procesar_transaccion(id):
    pub = Publicacion.query.get_or_404(id)
    if pub.es_unico and pub.estado != 'Disponible':
        flash('Producto no disponible.', 'error')
        return redirect(url_for('buscar'))
    
    sol = Solicitud(id_solicitante=current_user.id_usuario, id_publicacion=pub.id_oferta_insumo, estado='Pendiente', direccion_envio=request.form.get('direccion_envio'), metodo_pago=request.form.get('metodo_pago'))
    if pub.es_unico: pub.estado = 'Reservado'
    db.session.add(sol)
    db.session.commit()
    flash('Pedido realizado.', 'success')
    
    # Notificar al room del chat (OPCIONAL, si quisieras notificar en tiempo real)
    # socketio.emit('nueva_notificacion', {'msg': f'Nueva compra de {pub.nombre}'}, room=str(pub.id_proveedor))
    
    return redirect(url_for('mis_pedidos'))

# 5. EVENTOS SOCKET.IO
@socketio.on('enviar_mensaje')
def handle_message(data):
    room = data['room']
    msg = data['msg']
    emit('nuevo_mensaje', {'msg': msg, 'user': current_user.nombre}, room=room)

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Crear Tipos Sangre si no existen
        if not TipoSangre.query.first():
            for g, rh in [('A','+'),('A','-'),('B','+'),('B','-'),('O','+'),('O','-'),('AB','+'),('AB','-')]:
                db.session.add(TipoSangre(grupo=g, factor_rh=rh))
            db.session.commit()

    print("--- LIFELINK SERVER (RENDER READY) ---")
    socketio.run(app, debug=False)