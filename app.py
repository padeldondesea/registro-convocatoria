from flask import Flask, render_template, request, redirect, url_for, session, make_response, jsonify
import secrets
import json
from urllib.parse import quote
from datetime import datetime
import logging  # Importar el módulo logging

# Configurar el logging (¡MUY IMPORTANTE PARA DEPURAR!)
logging.basicConfig(level=logging.DEBUG,  # Nivel de detalle (DEBUG es el más detallado)
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',  # Formato del log (incluye nombre de archivo y línea)
                    filename='app.log',  # Guardar los logs en un archivo
                    filemode='a')  # Añadir al archivo, no sobreescribir

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
ADMIN_KEY = "5202"

def cargar_participantes():
    try:
        with open("lista_participantes.txt", "r", encoding="utf-8") as f:
            return [linea.strip() for linea in f]
    except FileNotFoundError:
        logging.warning("lista_participantes.txt no encontrado.")  # Log si el archivo no existe
        return []

def guardar_registro(nombre):
    logging.info(f"Guardando registro para: {nombre}")  # INFO: Más claro que DEBUG
    with open("registros.txt", "a", encoding="utf-8") as f:
        f.write(nombre + "\n")

def obtener_registrados():
    try:
        with open("registros.txt", "r", encoding="utf-8") as f:
            registrados = [linea.strip() for linea in f]
            logging.debug(f"Registrados obtenidos: {registrados}")  # Log de los registrados
            return registrados
    except FileNotFoundError:
        logging.warning("registros.txt no encontrado.")  # Log si el archivo no existe
        return []

def eliminar_registro(nombre):
    registrados = obtener_registrados()
    if nombre in registrados:
        registrados.remove(nombre)
        with open("registros.txt", "w", encoding="utf-8") as f:
            f.writelines(jugador + "\n" for jugador in registrados)
        logging.info(f"Participante '{nombre}' eliminado de registrados.")  # INFO
        mover_de_espera_a_registrados()  # Llama a la función correcta *después*
    else:
        logging.warning(f"Intento de eliminar '{nombre}', pero no está en registrados.")  # Log si el nombre no existe

def guardar_en_espera(nombre):
    logging.info(f"Guardando en espera a: {nombre}")  # INFO
    with open("lista_espera.txt", "a", encoding="utf-8") as f:
        f.write(nombre + "\n")

def obtener_lista_espera():
    try:
        with open("lista_espera.txt", "r", encoding="utf-8") as f:
            lista_espera = [linea.strip() for linea in f]
            logging.debug(f"Lista de espera obtenida: {lista_espera}")  # Log de la lista de espera
            return lista_espera
    except FileNotFoundError:
        logging.warning("lista_espera.txt no encontrado.")  # Log si el archivo no existe
        return []

def eliminar_de_espera(nombre):
    lista_espera = obtener_lista_espera()
    if nombre in lista_espera:
        lista_espera.remove(nombre)
        with open("lista_espera.txt", "w", encoding="utf-8") as f:
            f.writelines(jugador + "\n" for jugador in lista_espera)
        logging.info(f"Participante '{nombre}' eliminado de la lista de espera.")  # INFO
    else:
        logging.warning(f"Intento de eliminar '{nombre}' de la lista de espera, pero no está.")

def mover_de_espera_a_registrados():
    """Mueve participantes de espera a registrados SI HAY ESPACIO."""
    configuracion = cargar_configuracion()
    registrados = obtener_registrados()
    lista_espera = obtener_lista_espera()
    total_participantes = int(configuracion["total_participantes"])

    logging.debug(f"mover_de_espera_a_registrados: Antes - Registrados: {registrados}, Espera: {lista_espera}, Total: {total_participantes}")  # Log

    while len(registrados) < total_participantes and lista_espera:
        primer_en_espera = lista_espera.pop(0)  # Saca del PRINCIPIO
        guardar_registro(primer_en_espera)  # Lo añade a registrados
        registrados = obtener_registrados()  # ACTUALIZA la lista de registrados

    # Reescribe la lista de espera *DESPUÉS* del bucle
    with open("lista_espera.txt", "w", encoding="utf-8") as f:
        f.writelines(jugador + "\n" for jugador in lista_espera)

    logging.debug(f"mover_de_espera_a_registrados: Después - Registrados: {registrados}, Espera: {lista_espera}")  # Log

def mover_de_registrados_a_espera(configuracion):
    """Mueve participantes de registrados a espera SI SE REDUCE EL TOTAL."""
    registrados = obtener_registrados()
    lista_espera = obtener_lista_espera()
    total_participantes = int(configuracion["total_participantes"])

    logging.debug(f"mover_de_registrados_a_espera: Antes - Registrados: {registrados}, Espera: {lista_espera}, Nuevo total: {total_participantes}")  # Log

    while len(registrados) > total_participantes:
        jugador_a_mover = registrados.pop()  # Saca del FINAL
        lista_espera.insert(0, jugador_a_mover)  # Inserta al PRINCIPIO de la espera

    # Reescribe *AMBOS* archivos *DESPUÉS* del bucle
    with open("registros.txt", "w", encoding="utf-8") as f:
        f.writelines(jugador + "\n" for jugador in registrados)
    with open("lista_espera.txt", "w", encoding="utf-8") as f:
        f.writelines(jugador + "\n" for jugador in lista_espera)

    logging.debug(f"mover_de_registrados_a_espera: Después - Registrados: {registrados}, Espera: {lista_espera}")  # Log

def cargar_configuracion():
    try:
        with open("configuracion.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            logging.debug(f"Configuración cargada: {config}")  # Log
            if "comentarios" not in config:
                config["comentarios"] = ""  # Valor por defecto
            return config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error al cargar configuración: {e}. Devolviendo configuración por defecto.")  # Log
        return {
            "torneo": "",
            "lugar": "",
            "fecha": "",
            "hora": "",
            "num_canchas": "",
            "bloques": "",
            "total_participantes": "0",
            "comentarios": ""  # <---  Valor por defecto!
        }

def guardar_configuracion(config):
    logging.debug(f"Guardando configuración: {config}")  # Log
    with open("configuracion.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


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
        'comentarios': configuracion['comentarios'],  # Incluir comentarios
    }
    logging.debug(f"datos_convocatoria: Devolviendo datos: {datos}")  # Log
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
    error = None

    if request.method == "POST":
        # --- 1. Obtener el total de participantes ANTERIOR ---
        total_participantes_anterior = int(configuracion["total_participantes"])

        # --- 2. Guardar los nuevos valores (INCLUYENDO el nuevo total) ---
        configuracion["torneo"] = request.form.get("torneo")
        configuracion["lugar"] = request.form.get("lugar")
        configuracion["fecha"] = request.form.get("fecha")
        configuracion["hora"] = request.form.get("hora")
        configuracion["num_canchas"] = request.form.get("num_canchas")
        configuracion["bloques"] = request.form.get("bloques")
        # --- Obtener y validar comentarios ---
        comentarios = request.form.get("comentarios")
        if comentarios and len(comentarios) > 1000:
            error = "Los comentarios no pueden exceder los 1000 caracteres."
        else:
            configuracion["comentarios"] = comentarios  # Guardar los comentarios

        nuevo_total = request.form.get("total_participantes")
        if nuevo_total:
            try:
                nuevo_total = int(nuevo_total)
                if 4 <= nuevo_total <= 80:
                    configuracion["total_participantes"] = str(nuevo_total)  # Guardar como cadena
                else:
                    error = "El total de participantes debe estar entre 4 y 80."
            except ValueError:
                error = "El total de participantes debe ser un número."

        # --- 3. Guardar la configuración *ANTES* de mover jugadores ---
        guardar_configuracion(configuracion)

        # --- 4. Mover jugadores SOLO SI el total ha cambiado ---
        if nuevo_total is not None and nuevo_total < total_participantes_anterior:
            logging.debug(f"config (POST): Reduciendo total.  Anterior: {total_participantes_anterior}, Nuevo: {nuevo_total}")  # Log
            mover_de_registrados_a_espera(configuracion)  # Mueve si se redujo
        elif nuevo_total is not None and nuevo_total > total_participantes_anterior:
            logging.debug(f"config (POST): Aumentando total. Anterior: {total_participantes_anterior}, Nuevo: {nuevo_total}")  # Log
            mover_de_espera_a_registrados()  # Intenta llenar si se amplió

        return redirect(url_for("index"))


    # --- Formateo para el GET ---
    try:
        fecha_obj = datetime.strptime(configuracion["fecha"], '%Y-%m-%d')
        fecha_formateada = fecha_obj.strftime('%d-%m-%Y')
        hora_obj = datetime.strptime(configuracion["hora"], '%H:%M')
        hora_formateada = hora_obj.strftime('%I:%M %p')

    except ValueError as e:
        error = f"Error al formatear fecha/hora: {e}"
        fecha_formateada = ""
        hora_formateada = ""

    logging.debug(f"config (GET): Renderizando config.html.  Configuración: {configuracion}")  # Log
    return render_template("config.html", configuracion=configuracion,
                           fecha_formateada=fecha_formateada, hora_formateada=hora_formateada, error=error)

@app.route("/deseleccionar", methods=["POST"])
def deseleccionar():
    if not session.get('admin_logged_in'):
        return redirect(url_for("admin"))

    nombre_a_eliminar = request.form.get("nombre_eliminar")
    if nombre_a_eliminar:
        eliminar_registro(nombre_a_eliminar)
        mover_de_espera_a_registrados()
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
    app.run(debug=True)