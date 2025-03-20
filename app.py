import os
import sqlite3
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, make_response, jsonify
import json
from urllib.parse import quote
from datetime import datetime
import logging

# Configuración de logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s', filename='app.log', filemode='a')

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))
ADMIN_KEY = os.getenv("ADMIN_KEY")

# Función para conectar a SQLite
def get_db_connection():
    conn = sqlite3.connect('/home/sstenta/convocatoria.db')
    conn.row_factory = sqlite3.Row
    return conn

# Inicializar la base de datos
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS registrados (nombre TEXT PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS lista_espera (nombre TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

# Funciones para manejar participantes
def cargar_participantes():
    try:
        with open("lista_participantes.txt", "r", encoding="utf-8") as f:
            participantes = [linea.strip() for linea in f if linea.strip()]
            return sorted(participantes)  # Ordenar alfabéticamente
    except FileNotFoundError:
        logging.warning("lista_participantes.txt no encontrado.")
        return []

def guardar_participantes(participantes):
    with open("lista_participantes.txt", "w", encoding="utf-8") as f:
        for p in sorted(participantes):  # Ordenar alfabéticamente antes de guardar
            f.write(f"{p}\n")
    logging.info("Lista de participantes actualizada.")

def agregar_participante(nombre):
    participantes = cargar_participantes()
    if nombre and nombre.strip() and nombre not in participantes:
        participantes.append(nombre.strip())
        guardar_participantes(participantes)
        logging.info(f"Participante añadido: {nombre}")
    else:
        logging.warning(f"No se añadió '{nombre}': ya existe o está vacío.")

def editar_participante(nombre_viejo, nombre_nuevo):
    participantes = cargar_participantes()
    if nombre_viejo in participantes and nombre_nuevo and nombre_nuevo.strip() and nombre_nuevo not in participantes:
        participantes[participantes.index(nombre_viejo)] = nombre_nuevo.strip()
        guardar_participantes(participantes)
        logging.info(f"Participante editado: '{nombre_viejo}' -> '{nombre_nuevo}'")
    else:
        logging.warning(f"No se editó '{nombre_viejo}' a '{nombre_nuevo}': inválido o duplicado.")

def eliminar_participante(nombre):
    participantes = cargar_participantes()
    if nombre in participantes:
        participantes.remove(nombre)
        guardar_participantes(participantes)
        eliminar_registro(nombre)
        eliminar_de_espera(nombre)
        logging.info(f"Participante eliminado: {nombre}")
    else:
        logging.warning(f"Intento de eliminar '{nombre}', pero no existe.")

# Funciones para SQLite (sin cambios, solo se incluyen para completitud)
def guardar_registro(nombre):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO registrados (nombre) VALUES (?)", (nombre,))
        conn.commit()
        logging.info(f"Guardando registro para: {nombre}")
    except sqlite3.IntegrityError:
        logging.warning(f"Intento de registrar duplicado: {nombre}")
    conn.close()

def obtener_registrados():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT nombre FROM registrados")
    registrados = [row['nombre'] for row in c.fetchall()]
    conn.close()
    logging.debug(f"Registrados obtenidos: {registrados}")
    return registrados

def eliminar_registro(nombre):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM registrados WHERE nombre = ?", (nombre,))
    if c.rowcount > 0:
        conn.commit()
        logging.info(f"Participante '{nombre}' eliminado de registrados.")
        mover_de_espera_a_registrados()
    else:
        logging.warning(f"Intento de eliminar '{nombre}', pero no está en registrados.")
    conn.close()

def guardar_en_espera(nombre):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO lista_espera (nombre) VALUES (?)", (nombre,))
        conn.commit()
        logging.info(f"Guardando en espera a: {nombre}")
    except sqlite3.IntegrityError:
        logging.warning(f"Intento de añadir duplicado a espera: {nombre}")
    conn.close()

def obtener_lista_espera():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT nombre FROM lista_espera")
    lista_espera = [row['nombre'] for row in c.fetchall()]
    conn.close()
    logging.debug(f"Lista de espera obtenida: {lista_espera}")
    return lista_espera

def eliminar_de_espera(nombre):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM lista_espera WHERE nombre = ?", (nombre,))
    if c.rowcount > 0:
        conn.commit()
        logging.info(f"Participante '{nombre}' eliminado de la lista de espera.")
    else:
        logging.warning(f"Intento de eliminar '{nombre}' de la lista de espera, pero no está.")
    conn.close()

def mover_de_espera_a_registrados():
    configuracion = cargar_configuracion()
    registrados = obtener_registrados()
    lista_espera = obtener_lista_espera()
    total_participantes = int(configuracion["total_participantes"])
    logging.debug(f"mover_de_espera_a_registrados: Antes - Registrados: {registrados}, Espera: {lista_espera}, Total: {total_participantes}")
    conn = get_db_connection()
    c = conn.cursor()
    while len(registrados) < total_participantes and lista_espera:
        c.execute("SELECT nombre FROM lista_espera LIMIT 1")
        participante = c.fetchone()
        if participante:
            nombre = participante['nombre']
            c.execute("INSERT INTO registrados (nombre) VALUES (?)", (nombre,))
            c.execute("DELETE FROM lista_espera WHERE nombre = ?", (nombre,))
            conn.commit()
            registrados = obtener_registrados()
            lista_espera = obtener_lista_espera()
            logging.info(f"Movido de espera a registrados: {nombre}")
    conn.close()
    logging.debug(f"mover_de_espera_a_registrados: Después - Registrados: {registrados}, Espera: {lista_espera}")

def mover_de_registrados_a_espera(configuracion):
    registrados = obtener_registrados()
    lista_espera = obtener_lista_espera()
    total_participantes = int(configuracion["total_participantes"])
    logging.debug(f"mover_de_registrados_a_espera: Antes - Registrados: {registrados}, Espera: {lista_espera}, Nuevo total: {total_participantes}")
    conn = get_db_connection()
    c = conn.cursor()
    while len(registrados) > total_participantes:
        c.execute("SELECT nombre FROM registrados LIMIT 1 OFFSET ?", (total_participantes,))
        exceso = c.fetchone()
        if exceso:
            nombre = exceso['nombre']
            c.execute("DELETE FROM registrados WHERE nombre = ?", (nombre,))
            c.execute("INSERT INTO lista_espera (nombre) VALUES (?)", (nombre,))
            conn.commit()
            registrados = obtener_registrados()
            lista_espera = obtener_lista_espera()
            logging.info(f"Movido de registrados a espera: {nombre}")
    conn.close()
    logging.debug(f"mover_de_registrados_a_espera: Después - Registrados: {registrados}, Espera: {lista_espera}")

def vaciar_registrados():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM registrados")
    conn.commit()
    logging.info("Lista de registrados vaciada.")
    conn.close()

def vaciar_lista_espera():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM lista_espera")
    conn.commit()
    logging.info("Lista de espera vaciada.")
    conn.close()

def cargar_configuracion():
    try:
        with open("configuracion.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            logging.debug(f"Configuración cargada: {config}")
            if "comentarios" not in config:
                config["comentarios"] = ""
            return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error al cargar configuración: {e}. Devolviendo configuración por defecto.")
        return {
            "torneo": "",
            "lugar": "",
            "fecha": "",
            "hora": "",
            "num_canchas": "",
            "bloques": "",
            "total_participantes": "0",
            "comentarios": ""
        }

def guardar_configuracion(config):
    logging.debug(f"Guardando configuración: {config}")
    with open("configuracion.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

# Rutas
@app.route("/datos_convocatoria")
def datos_convocatoria():
    configuracion = cargar_configuracion()
    try:
        fecha_obj = datetime.strptime(configuracion["fecha"], '%Y-%m-%d')
        fecha_formateada = fecha_obj.strftime('%d-%m-%Y')
        hora_obj = datetime.strptime(configuracion["hora"], '%H:%M')
        hora_formateada = hora_obj.strftime('%I:%M %p')
    except ValueError:
        fecha_formateada = "Fecha inválida"
        hora_formateada = "Hora inválida"
    datos = {
        'torneo': configuracion['torneo'],
        'lugar': configuracion['lugar'],
        'fecha': fecha_formateada,
        'hora': hora_formateada,
        'num_canchas': configuracion['num_canchas'],
        'bloques': configuracion['bloques'],
        'total_participantes': configuracion['total_participantes'],
        'registrados': obtener_registrados(),
        'lista_espera': obtener_lista_espera(),
        'comentarios': configuracion['comentarios'],
    }
    logging.debug(f"datos_convocatoria: Devolviendo datos: {datos}")
    return jsonify(datos)

@app.route("/", methods=["GET", "POST"])
def index():
    participantes = cargar_participantes()
    registrados = obtener_registrados()
    lista_espera = obtener_lista_espera()
    configuracion = cargar_configuracion()
    total_participantes = int(configuracion["total_participantes"])
    disponibles = [p for p in participantes if p not in registrados and p not in lista_espera]
    mensaje = None
    error = None
    if request.method == "POST":
        nombre_seleccionado = request.form.get("participante")
        if nombre_seleccionado and nombre_seleccionado in disponibles:
            if len(registrados) < total_participantes:
                guardar_registro(nombre_seleccionado)
            else:
                guardar_en_espera(nombre_seleccionado)
                mensaje = "¡Estás en lista de espera!"
            return redirect(url_for("index"))
    try:
        fecha_obj = datetime.strptime(configuracion["fecha"], '%Y-%m-%d')
        fecha_formateada = fecha_obj.strftime('%d-%m-%Y')
        hora_obj = datetime.strptime(configuracion["hora"], '%H:%M')
        hora_formateada = hora_obj.strftime('%I:%M %p')
    except ValueError as e:
        error = f"Error al formatear: {e}"
        fecha_formateada = configuracion["fecha"]
        hora_formateada = configuracion["hora"]
    logging.debug(f"index: Renderizando index.html. Registrados: {registrados}, Espera: {lista_espera}")
    return render_template("index.html", participantes=disponibles, registrados=registrados,
                           num_registrados=len(registrados), configuracion=configuracion,
                           admin_logged_in=session.get('admin_logged_in'), mensaje=mensaje,
                           lista_espera=lista_espera, num_espera=len(lista_espera),
                           fecha_formateada=fecha_formateada, hora_formateada=hora_formateada,
                           error=error)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        clave = request.form.get("clave")
        if clave == ADMIN_KEY:
            session['admin_logged_in'] = True
            return redirect(url_for("index"))
        else:
            return render_template("admin_login.html", error=True)
    return render_template("admin_login.html", error=False)

@app.route("/config", methods=["GET", "POST"])
def config():
    if not session.get('admin_logged_in'):
        return redirect(url_for("admin"))
    configuracion = cargar_configuracion()
    participantes = cargar_participantes()  # Ya ordenados alfabéticamente
    error = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_participant":
            nuevo_participante = request.form.get("nuevo_participante")
            agregar_participante(nuevo_participante)
        elif action == "edit_participant":
            nombre_viejo = request.form.get("nombre_viejo")
            nombre_nuevo = request.form.get("nombre_nuevo")
            editar_participante(nombre_viejo, nombre_nuevo)
        elif action == "delete_participant":
            nombre = request.form.get("participante_eliminar")
            eliminar_participante(nombre)
        elif action == "clear_registrados":
            vaciar_registrados()
        elif action == "clear_lista_espera":
            vaciar_lista_espera()
        else:
            total_participantes_anterior = int(configuracion["total_participantes"])
            configuracion["torneo"] = request.form.get("torneo")
            configuracion["lugar"] = request.form.get("lugar")
            configuracion["fecha"] = request.form.get("fecha")
            configuracion["hora"] = request.form.get("hora")
            configuracion["num_canchas"] = request.form.get("num_canchas")
            configuracion["bloques"] = request.form.get("bloques")
            comentarios = request.form.get("comentarios")
            if comentarios and len(comentarios) > 1000:
                error = "Los comentarios no pueden exceder los 1000 caracteres."
            else:
                configuracion["comentarios"] = comentarios
            nuevo_total = request.form.get("total_participantes")
            if nuevo_total:
                try:
                    nuevo_total = int(nuevo_total)
                    if 4 <= nuevo_total <= 80:
                        configuracion["total_participantes"] = str(nuevo_total)
                    else:
                        error = "El total de participantes debe estar entre 4 y 80."
                except ValueError:
                    error = "El total de participantes debe ser un número."
            guardar_configuracion(configuracion)
            if nuevo_total is not None and nuevo_total < total_participantes_anterior:
                logging.debug(f"config (POST): Reduciendo total. Anterior: {total_participantes_anterior}, Nuevo: {nuevo_total}")
                mover_de_registrados_a_espera(configuracion)
            elif nuevo_total is not None and nuevo_total > total_participantes_anterior:
                logging.debug(f"config (POST): Aumentando total. Anterior: {total_participantes_anterior}, Nuevo: {nuevo_total}")
                mover_de_espera_a_registrados()
        return redirect(url_for("config"))
    try:
        fecha_obj = datetime.strptime(configuracion["fecha"], '%Y-%m-%d')
        fecha_formateada = fecha_obj.strftime('%d-%m-%Y')
        hora_obj = datetime.strptime(configuracion["hora"], '%H:%M')
        hora_formateada = hora_obj.strftime('%I:%M %p')
    except ValueError as e:
        error = f"Error al formatear fecha/hora: {e}"
        fecha_formateada = ""
        hora_formateada = ""
    logging.debug(f"config (GET): Renderizando config.html. Configuración: {configuracion}")
    return render_template("config.html", configuracion=configuracion, participantes=participantes,
                           fecha_formateada=fecha_formateada, hora_formateada=hora_formateada, error=error)

@app.route("/deseleccionar", methods=["POST"])
def deseleccionar():
    if not session.get('admin_logged_in'):
        return redirect(url_for("admin"))
    nombre_a_eliminar = request.form.get("nombre_eliminar")
    if nombre_a_eliminar:
        eliminar_registro(nombre_a_eliminar)
        return redirect(url_for("index"))

@app.route("/deseleccionar_espera", methods=["POST"])
def deseleccionar_espera():
    if not session.get('admin_logged_in'):
        return redirect(url_for("admin"))
    nombre_a_eliminar = request.form.get("nombre_eliminar_espera")
    if nombre_a_eliminar:
        eliminar_de_espera(nombre_a_eliminar)
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)