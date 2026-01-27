import eventlet
# Parcheo de seguridad para Render
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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root { --brand: #0ea5e9; }
        .bg-brand { background-color: var(--brand); }
        .text-brand { color: var(--brand); }
        .btn-medical { background-color: var(--brand); color: white; transition: all 0.3s; border-radius: 0.5rem; font-weight: 800; }
        .btn-medical:hover { background-color: #0369a1; transform: translateY(-1px); }
    </style>
</head>
<body class="bg-slate-50 flex flex-col min-h-screen font-sans text-slate-900 uppercase font-bold italic">
    <nav class="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 h-16 flex justify-between items-center">
            <a href="/" class="flex items-center gap-2">
                <div class="bg-brand p-1.5 rounded-lg shadow-md">
                     <svg width="20" height="20" viewBox="0 0 100 100" fill="none" stroke="white" stroke-width="10">
                        <path d="M10 50 L30 50 L40 20 L60 80 L70 50 L90 50" stroke-linecap="round" stroke-linejoin="round"/>
                     </svg>
                </div>
                <span class="font-black text-xl tracking-tighter text-slate-800">LifeLink</span>
            </a>
            <div class="flex items-center gap-6">
                <a href="{{ url_for('buscar') }}" class="text-[10px] text-slate-400 hover:text-brand transition tracking-widest">Explorar</a>
                {% if current_user.is_authenticated %}
                <a href="{{ url_for('dashboard') }}" class="text-[10px] text-slate-400 hover:text-brand transition tracking-widest">Panel</a>
                <a href="{{ url_for('logout') }}" class="text-[10px] text-red-400 tracking-widest">Salir</a>
                {% else %}
                <a href="{{ url_for('login') }}" class="text-[10px] text-slate-400 tracking-widest">Entrar</a>
                <a href="{{ url_for('registro') }}" class="btn-medical px-4 py-2 text-[10px] tracking-widest shadow-md">Unirse</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <main class="flex-grow">
        {% with messages = get_flashed_messages() %}
          {% if messages %}
            {% for message in messages %}
              <div class="max-w-4xl mx-auto mt-4 px-4">
                <div class="p-3 rounded-lg bg-blue-50 text-blue-700 border border-blue-100 text-[10px]">
                   {{ message }}
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
    <div class="max-w-7xl mx-auto px-4 w-full">
        <div class="lg:grid lg:grid-cols-12 lg:gap-12 items-center">
            <div class="sm:text-center lg:col-span-6 lg:text-left">
                <h1 class="text-6xl font-black text-slate-900 tracking-tighter sm:text-7xl leading-[0.9] mb-8 uppercase italic">
                    CONECTANDO <br><span class="text-brand">VIDAS.</span>
                </h1>
                <p class="text-xl text-slate-400 max-w-lg leading-relaxed mb-10 font-medium italic italic">
                    Plataforma inteligente para la gestión de donaciones de sangre, medicamentos y equipo médico.
                </p>
                <div class="flex flex-wrap gap-5 sm:justify-center lg:justify-start">
                    <a href="{{ url_for('buscar') }}" class="btn-medical px-12 py-5 font-black text-lg shadow-2xl">
                        Explorar Red
                    </a>
                </div>
            </div>
            <div class="mt-16 lg:mt-0 lg:col-span-6 flex justify-center">
                <div class="relative w-full max-w-md">
                    <div class="absolute inset-0 bg-brand rounded-[3rem] rotate-3 opacity-5"></div>
                    <div class="relative bg-white p-4 rounded-[3rem] shadow-2xl border-8 border-slate-50 overflow-hidden">
                        <img class="w-full h-[550px] rounded-[2rem] object-cover" src="https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&q=80&w=1000" alt="LifeLink Medical">
                    </div>
                </div>
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
app.config['SECRET_KEY'] = 'lifelink_2026_reset_force_key'

# Obtener URL de base de datos (PostgreSQL de Render o SQLite local)
uri = os.environ.get('DATABASE_URL', 'sqlite:///lifelink_reset.db')
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    def get_id(self): return str(self.id)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_proveedor = db.Column(db.Integer, db.ForeignKey('user.id'))
    nombre = db.Column(db.String(100), nullable=False)
    categoria = db.Column(db.String(50))
    imagen_url = db.Column(db.String(500))

# Cargador de Plantillas
app.jinja_loader = jinja2.DictLoader({
    'base.html': base_template,
    'home.html': home_template,
    'login.html': """{% extends "base.html" %}{% block content %}<div class="max-w-md mx-auto py-24 px-4 text-center font-black uppercase"><div class="bg-white p-12 rounded-[3rem] shadow-2xl border border-slate-100 italic"><h2>Ingresar</h2><form method="POST" class="space-y-5"><input name="email" type="email" placeholder="CORREO" required class="w-full p-4 bg-slate-50 rounded-xl border-none outline-none shadow-inner"><input name="password" type="password" placeholder="CONTRASEÑA" required class="w-full p-4 bg-slate-50 rounded-xl border-none outline-none shadow-inner"><button class="w-full btn-medical py-5 rounded-[2rem] font-black text-2xl mt-4 italic uppercase">Ingresar</button></form></div></div>{% endblock %}""",
    'register.html': """{% extends "base.html" %}{% block content %}<div class="max-w-xl mx-auto py-16 px-4 uppercase font-black italic"><div class="bg-white p-12 rounded-[3rem] shadow-2xl border border-slate-100 text-center"><h2>Registro</h2><form method="POST" class="space-y-4"><input name="nombre" placeholder="NOMBRE COMPLETO" required class="w-full p-4 bg-slate-50 rounded-xl border-none shadow-inner"><input name="email" type="email" placeholder="CORREO" required class="w-full p-4 bg-slate-50 rounded-xl border-none shadow-inner"><input name="password" type="password" placeholder="CONTRASEÑA" required class="w-full p-4 bg-slate-50 rounded-xl border-none shadow-inner"><button class="w-full btn-medical py-6 rounded-[2rem] text-xl uppercase shadow-xl">Unirse</button></form></div></div>{% endblock %}""",
    'dashboard.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-20 px-4 text-center font-black uppercase"><h1>Mi Panel</h1><p class="mt-4 text-slate-400 italic">Bienvenido Nodo: {{ current_user.nombre }}</p></div>{% endblock %}""",
    'search.html': """{% extends "base.html" %}{% block content %}<div class="max-w-7xl mx-auto py-20 px-4 text-center font-black uppercase"><h1>Buscador Activo</h1><p class="mt-4 text-slate-400 italic">Sistema de base de datos reiniciado con éxito.</p></div>{% endblock %}"""
})

# ==========================================
# 3. RUTAS DE CONTROL
# ==========================================
@login_manager.user_loader
def load_user(user_id): return User.query.get(int(user_id))

@app.route('/')
def index(): return render_template('home.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        if User.query.filter_by(email=request.form['email']).first():
            flash("Correo ya registrado.")
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
        flash("Datos incorrectos.")
    return render_template('login.html')

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('index'))

@app.route('/buscar')
def buscar(): return render_template('search.html')

@app.route('/dashboard')
@login_required
def dashboard(): return render_template('dashboard.html')

if __name__ == '__main__':
    with app.app_context():
        # ESTO ES LO QUE ARREGLA EL ERROR 500: Borra todo lo viejo y crea lo nuevo.
        # Solo lo ejecutamos una vez para limpiar el desastre anterior.
        db.drop_all() 
        db.create_all()
        print("BASE DE DATOS REINICIADA Y LIMPIA.")
    app.run(debug=False)
