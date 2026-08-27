import os
import datetime
from datetime import timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vettag_telemetry_secure_key")

# Definir la zona horaria oficial de Ecuador (UTC-5)
ZONA_HORARIA_ECUADOR = timezone(timedelta(hours=-5))

# Estructura de credenciales dinámicas en memoria
DATOS_USUARIO = {
    "usuario": None,
    "clave": None,
    "fecha_ultimo_cambio": None
}

# Historial de recetas e ID autoincremental
HISTORIAL_DOSIS = []
PROXIMO_ID_DOSIS = 1

def obtener_hora_ecuador():
    """Devuelve la fecha y hora actual en la zona horaria de Ecuador (UTC-5)."""
    return datetime.datetime.now(ZONA_HORARIA_ECUADOR)

def requiere_cambio_clave():
    """Verifica si han transcurrido 30 días o más desde la última actualización."""
    if not DATOS_USUARIO["fecha_ultimo_cambio"]:
        return False
    hoy = obtener_hora_ecuador().date()
    dias_transcurridos = (hoy - DATOS_USUARIO["fecha_ultimo_cambio"]).days
    return dias_transcurridos >= 30

def login_required(f):
    """Protege las rutas que requieren sesión activa."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('usuario_autenticado'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def evaluar_estado_clinico(temp, bpm, arnes_puesto):
    """Evalúa el estado del paciente según las lecturas recibidas."""
    if not arnes_puesto or (temp == 0 and bpm == 0):
        return {
            "salud_mascota": "Arnés Desconectado",
            "badge_class": "bg-secondary",
            "mensaje": "El arnés no detecta lecturas activas. Dispositivo en espera de señal física."
        }
    
    if temp > 39.2 and bpm > 140:
        return {
            "salud_mascota": "Estado Crítico",
            "badge_class": "bg-danger",
            "mensaje": "Alerta de Hipertermia severa y Taquicardia. Requiere atención inmediata."
        }
    elif temp > 39.2:
        return {
            "salud_mascota": "Fiebre Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Temperatura elevada por encima de 39.2°C."
        }
    elif temp < 37.5:
        return {
            "salud_mascota": "Hipotermia Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Temperatura por debajo del rango fisiológico normal."
        }
    elif bpm > 140:
        return {
            "salud_mascota": "Taquicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Frecuencia cardíaca acelerada."
        }
    elif bpm < 60:
        return {
            "salud_mascota": "Bradicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Frecuencia cardíaca por debajo del nivel basal."
        }
    else:
        return {
            "salud_mascota": "Estado Normal",
            "badge_class": "bg-success",
            "mensaje": "Constantes vitales estables."
        }

@app.route('/')
def inicio():
    # Lo primero que ve el usuario al escanear el QR o entrar al enlace
    return render_template('logotipo.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not DATOS_USUARIO["usuario"]:
        return redirect(url_for('cambiar_credenciales'))

    if session.get('usuario_autenticado'):
        return redirect(url_for('panel_medico'))

    if request.method == 'POST':
        usuario_ingresado = request.form.get('usuario', '').strip()
        clave_ingresada = request.form.get('clave', '').strip()

        if usuario_ingresado == DATOS_USUARIO["usuario"] and clave_ingresada == DATOS_USUARIO["clave"]:
            session['usuario_autenticado'] = True
            session['usuario'] = usuario_ingresado
            
            if requiere_cambio_clave():
                flash("Han transcurrido 30 días. Por seguridad actualice sus datos.", "warning")
                return redirect(url_for('cambiar_credenciales'))
                
            return redirect(url_for('panel_medico'))
        else:
            flash("Credenciales incorrectas.", "danger")

    return render_template('login.html')

@app.route('/cambiar_credenciales', methods=['GET', 'POST'])
def cambiar_credenciales():
    if request.method == 'POST':
        nuevo_usuario = request.form.get('nuevo_usuario', '').strip()
        nueva_clave = request.form.get('nueva_clave', '').strip()

        if nuevo_usuario and nueva_clave:
            DATOS_USUARIO["usuario"] = nuevo_usuario
            DATOS_USUARIO["clave"] = nueva_clave
            DATOS_USUARIO["fecha_ultimo_cambio"] = obtener_hora_ecuador().date()
            
            session['usuario_autenticado'] = True
            session['usuario'] = nuevo_usuario
            
            flash("Credenciales guardadas exitosamente.", "success")
            return redirect(url_for('panel_medico'))
        else:
            flash("Ingrese datos válidos.", "warning")

    return render_template('cambiar_credenciales.html')

@app.route('/medico')
@login_required
def panel_medico():
    return render_template('medico.html')

@app.route('/api/telemetria', methods=['GET'])
@login_required
def api_telemetria():
    """Limpia los datos a 0 para modo en espera (standby)."""
    temp = 0.0
    bpm = 0
    pechera = False
    ahora = obtener_hora_ecuador()
    
    diag = evaluar_estado_clinico(temp, bpm, pechera)
    
    return jsonify({
        "temperatura": temp,
        "ritmo_cardiaco": bpm,
        "pechera_puesta": pechera,
        "actividad": {"estado": "En espera"},
        "ultima_actualizacion": ahora.strftime("%H:%M:%S"),
        "diagnostico": diag,
        "gps": {
            "valido": False,
            "latitud": -1.3458,
            "longitud": -80.4285
        }
    })

@app.route('/api/guardar_dosis', methods=['POST'])
@login_required
def guardar_dosis():
    global PROXIMO_ID_DOSIS
    data = request.get_json() or {}
    
    peso = float(data.get('peso', 0.0))
    dosis_mg_kg = float(data.get('dosis_mg_kg', 0.0))
    concentracion = float(data.get('concentracion', 1.0))
    
    volumen_ml = round((peso * dosis_mg_kg) / concentracion, 2) if concentracion > 0 else 0.0
    fecha_registro = obtener_hora_ecuador().strftime("%Y-%m-%d %H:%M")

    nuevo_registro = {
        "id": PROXIMO_ID_DOSIS,
        "fecha": fecha_registro,
        "paciente": data.get('paciente', 'Desconocido'),
        "peso": peso,
        "propietario": data.get('propietario', 'N/A'),
        "telefono": data.get('telefono', 'N/A'),
        "correo": data.get('correo', 'N/A'),
        "direccion": data.get('direccion', 'N/A'),
        "farmaco": data.get('farmaco', 'N/A'),
        "dosis_mg_kg": dosis_mg_kg,
        "concentracion": concentracion,
        "volumen_ml": volumen_ml,
        "sugerencias": data.get('sugerencias', 'Sin observaciones.')
    }
    
    HISTORIAL_DOSIS.append(nuevo_registro)
    PROXIMO_ID_DOSIS += 1
    
    return jsonify({"status": "success", "id": nuevo_registro["id"]}), 201

@app.route('/api/historial_dosis', methods=['GET'])
@login_required
def obtener_historial_dosis():
    return jsonify(HISTORIAL_DOSIS)

@app.route('/api/eliminar_dosis/<int:id_dosis>', methods=['DELETE'])
@login_required
def eliminar_dosis(id_dosis):
    global HISTORIAL_DOSIS
    HISTORIAL_DOSIS = [item for item in HISTORIAL_DOSIS if item['id'] != id_dosis]
    return jsonify({"status": "success", "deleted_id": id_dosis})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('.', 'manifest.json')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
