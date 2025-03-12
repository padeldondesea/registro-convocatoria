from flask import Flask, render_template, request, redirect, url_for, session, make_response
import secrets
import json
from urllib.parse import quote  # ¡Importante! Para codificar la URL


app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
ADMIN_KEY = "5202"
# MAX_REGISTROS_POR_DISPOSITIVO = 1  # Ya no se usa


def cargar_participantes():
    try:
        with open("lista_participantes.txt", "r", encoding="utf-8") as f:
            participantes = [linea.strip() for linea in f]
            return participantes
    except FileNotFoundError:
        return []

def guardar_registro(nombre):
    with open("registros.txt", "a", encoding="utf-8") as f:
        f.write(nombre + "\n")

def obtener_registrados():
    try:
        with open("registros.txt", "r", encoding="utf-8") as f:
            registrados = [linea.strip() for linea in f]
            return registrados
    except FileNotFoundError:
        return []

def eliminar_registro(nombre):
    registrados = obtener_registrados()
    if nombre in registrados:
        registrados.remove(nombre)
        with open("registros.txt", "w", encoding="utf-8") as f:
            for r in registrados:
                f.write(r + "\n")
        # Intenta mover a alguien de la lista de espera a la de registrados
        mover_de_espera_a_registrados()

def guardar_en_espera(nombre):
    with open("lista_espera.txt", "a", encoding="utf-8") as f:
        f.write(nombre + "\n")

def obtener_lista_espera():
    try:
        with open("lista_espera.txt", "r", encoding="utf-8") as f:
            lista_espera = [linea.strip() for linea in f]
            return lista_espera
    except FileNotFoundError:
        return []
def eliminar_de_espera(nombre):
    lista_espera = obtener_lista_espera()
    if nombre in lista_espera:
        lista_espera.remove(nombre)
        with open("lista_espera.txt", "w", encoding="utf-8") as f:
            for r in lista_espera:
                f.write(r + "\n")

def mover_de_espera_a_registrados():
    """Mueve al primer participante de la lista de espera a la lista de registrados (si hay espacio)."""
    configuracion = cargar_configuracion()
    registrados = obtener_registrados()
    lista_espera = obtener_lista_espera()

    if len(registrados) < int(configuracion["total_participantes"]) and lista_espera:
        primer_en_espera = lista_espera.pop(0)  # Obtiene y elimina el primero
        guardar_registro(primer_en_espera)
        with open("lista_espera.txt", "w", encoding="utf-8") as f: # Reescribe la lista de espera
             for r in lista_espera:
                f.write(r + "\n")


def cargar_configuracion():
    try:
        with open("configuracion.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "torneo": "",
            "lugar": "",
            "fecha": "",
            "hora": "",
            "num_canchas": "",
            "bloques": "",
            "total_participantes": "0"
        }

def guardar_configuracion(config):
    with open("configuracion.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)

def generar_texto_convocatoria():
    """Genera el texto completo de la convocatoria para WhatsApp."""
    configuracion = cargar_configuracion()
    registrados = obtener_registrados()
    lista_espera = obtener_lista_espera()

    texto = f"Registro para la Convocatoria de Juego\n\n"
    texto += f"Torneo: {configuracion['torneo']}\n"
    texto += f"Lugar: {configuracion['lugar']}\n"
    texto += f"Fecha: {configuracion['fecha']}\n"
    texto += f"Hora: {configuracion['hora']}\n"
    texto += f"Nº de canchas: {configuracion['num_canchas']}\n"
    texto += f"Bloques: {configuracion['bloques']}\n"
    texto += f"Total de Participantes: {configuracion['total_participantes']}\n\n"

    texto += "Lista de participantes registrados:\n"
    if registrados:
        for i, nombre in enumerate(registrados):
            texto += f"{i+1}. {nombre}\n"
    else:
        texto += "Todavía no hay ningún participante en la lista.\n"

    texto += "\nLista de Espera:\n"
    if lista_espera:
        for i, nombre in enumerate(lista_espera):
            texto += f"{i+1}. {nombre}\n"
    else:
        texto += "La lista de espera está vacía.\n"

    return texto

@app.route("/", methods=["GET", "POST"])
def index():
    participantes = cargar_participantes()
    registrados = obtener_registrados()
    lista_espera = obtener_lista_espera()  # Obtener la lista de espera
    configuracion = cargar_configuracion()
    total_participantes = int(configuracion["total_participantes"])
    disponibles = [p for p in participantes if p not in registrados and p not in lista_espera] # Disponibles sin estar en espera
    mensaje = None

    if request.method == "POST":
        nombre_seleccionado = request.form.get("participante")
        if nombre_seleccionado and nombre_seleccionado in disponibles:
            if len(registrados) < total_participantes:
                guardar_registro(nombre_seleccionado)
            else:
                # Si ya están completos los registros, añadir a la lista de espera
                guardar_en_espera(nombre_seleccionado)
                mensaje = "¡Estás en lista de espera!"  # Mensaje opcional

            return redirect(url_for("index"))

    return render_template("index.html", participantes=disponibles, registrados=registrados,
                           num_registrados=len(registrados), configuracion=configuracion,
                           admin_logged_in=session.get('admin_logged_in'), mensaje=mensaje,
                           lista_espera=lista_espera, num_espera=len(lista_espera))  # Pasar lista_espera y su longitud


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

    if request.method == "POST":
        configuracion["torneo"] = request.form.get("torneo")
        configuracion["lugar"] = request.form.get("lugar")
        configuracion["fecha"] = request.form.get("fecha")
        configuracion["hora"] = request.form.get("hora")
        configuracion["num_canchas"] = request.form.get("num_canchas")
        configuracion["bloques"] = request.form.get("bloques")

        nuevo_total = request.form.get("total_participantes")
        if nuevo_total:
            try:
                nuevo_total = int(nuevo_total)
                if 4 <= nuevo_total <= 80 and nuevo_total % 4 == 0:
                    configuracion["total_participantes"] = str(nuevo_total)
                else:
                    pass

            except ValueError:
                pass
        guardar_configuracion(configuracion)
        # Después de cambiar el total, intenta mover gente de espera a registrados
        mover_de_espera_a_registrados()

        return redirect(url_for("index"))

    return render_template("config.html", configuracion=configuracion)

@app.route("/deseleccionar", methods=["POST"])
def deseleccionar():
    if not session.get('admin_logged_in'):
        return redirect(url_for("admin"))

    nombre_a_eliminar = request.form.get("nombre_eliminar")
    if nombre_a_eliminar:
        eliminar_registro(nombre_a_eliminar)  # Ya incluye mover_de_espera_a_registrados()
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

@app.route("/texto_convocatoria")
def texto_convocatoria():
    """Devuelve el texto de la convocatoria (sin HTML)."""
    texto = generar_texto_convocatoria()
    return texto, 200, {'Content-Type': 'text/plain; charset=utf-8'}

if __name__ == "__main__":
    app.run(debug=True)