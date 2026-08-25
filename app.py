import os
import datetime
import random
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vettag_telemetry_secure_key")

# Sistema de credenciales en memoria (Inicia dinámico)
DATOS_USUARIO = {
    "usuario": None,
    "clave": None,
    "fecha_ultimo_cambio": None
}

# Base de datos en memoria para el historial de prescripciones
HISTORIAL_DOSIS = []
PROXIMO_ID_DOSIS = 1

def requiere_cambio_clave():
    """Verifica si han transcurrido 30 días o más desde la última actualización."""
    if not DATOS_USUARIO["fecha_ultimo_cambio"]:
        return False
    dias_transcurridos = (datetime.date.today() - DATOS_USUARIO["fecha_ultimo_cambio"]).days
    return dias_transcurridos >= 30

def login_required(f):
    """Protege las rutas del sistema."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('usuario_autenticado'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def evaluar_estado_clinico(temp, bpm, arnes_puesto):
    """Calcula el diagnóstico según constantes vitales del paciente."""
    if not arnes_puesto:
        return {
            "salud_mascota": "Arnés Desconectado",
            "badge_class": "bg-danger",
            "mensaje": "El arnés capacitivo no detecta contacto. Verifique la sujeción del dispositivo."
        }
    
    if temp > 39.2 and bpm > 140:
        return {
            "salud_mascota": "Estado Crítico",
            "badge_class": "bg-danger",
            "mensaje": "Alerta de Hipertermia severa y Taquicardia. Requiere intervención médica inmediata."
        }
    elif temp > 39.2:
        return {
            "salud_mascota": "Fiebre Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Temperatura corporal elevada por encima del rango normal (37.5°C - 39.2°C)."
        }
    elif temp < 37.5:
        return {
            "salud_mascota": "Hipotermia Detectada",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Temperatura corporal por debajo del límite seguro. Mantener abrigado."
        }
    elif bpm > 140:
        return {
            "salud_mascota": "Taquicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Frecuencia cardíaca acelerada por encima de los valores basales en reposo."
        }
    elif bpm < 60:
        return {
            "salud_mascota": "Bradicardia",
            "badge_class": "bg-warning text-dark",
            "mensaje": "Frecuencia cardíaca anormalmente baja. Se sugiere monitoreo de pulso."
        }
    else:
        return {
            "salud_mascota": "Estado Normal",
            "badge_class": "bg-success",
            "mensaje": "Constantes vitales dentro de rangos fisiológicos estables."
        }

@app.route('/')
def inicio():
    """Ruta principal."""
    if session.get('usuario_autenticado'):
        return redirect(url_for('panel_medico'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Maneja el acceso o la creación inicial de credenciales."""
    # Si aún no se han configurado credenciales, permite registrar la primera
    if not DATOS_USUARIO["usuario"]:
        return redirect(url_for('cambiar_credenciales'))

    if request.method == 'POST':
        usuario_ingresado = request.form.get('usuario', '').strip()
        clave_ingresada = request.form.get('clave', '').strip()

        if usuario_ingresado == DATOS_USUARIO["usuario"] and clave_ingresada == DATOS_USUARIO["clave"]:
            session['usuario_autenticado'] = True
            session['usuario'] = usuario_ingresado
            
            if requiere_cambio_clave():
                flash("Han transcurrido 30 días. Debe actualizar sus credenciales.", "warning")
                return redirect(url_for('cambiar_credenciales'))
                
            return redirect(url_for('panel_medico'))
        else:
            flash("Credenciales incorrectas.", "danger")

    return render_template('login.html')

@app.route('/cambiar_credenciales', methods=['GET', 'POST'])
def cambiar_credenciales():
    """Permite guardar las credenciales iniciales o actualizarlas."""
    if request.method == 'POST':
        nuevo_usuario = request.form.get('nuevo_usuario', '').strip()
        nueva_clave = request.form.get('nueva_clave', '').strip()

        if nuevo_usuario and nueva_clave:
            DATOS_USUARIO["usuario"] = nuevo_usuario
            DATOS_USUARIO["clave"] = nueva_clave
            DATOS_USUARIO["fecha_ultimo_cambio"] = datetime.date.today()
            
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
    """Ruta protegida del visor telemétrico."""
    return render_template('medico.html')

@app.route('/api/telemetria', methods=['GET'])
@login_required
def api_telemetria():
    """Lectura de datos en tiempo real."""
    temp = round(random.uniform(37.0, 39.8), 1)
    bpm = random.randint(70, 150)
    pechera = random.choice([True, True, True, False])
    actividades = ["Reposo", "Caminando", "Corriendo", "Agitado"]
    
    diag = evaluar_estado_clinico(temp, bpm, pechera)
    
    return jsonify({
        "temperatura": temp,
        "ritmo_cardiaco": bpm,
        "pechera_puesta": pechera,
        "actividad": {"estado": random.choice(actividades)},
        "ultima_actualizacion": datetime.datetime.now().strftime("%H:%M:%S"),
        "diagnostico": diag,
        "gps": {
            "valido": True,
            "latitud": -1.3458 + random.uniform(-0.001, 0.001),
            "longitud": -80.4285 + random.uniform(-0.001, 0.001)
        }
    })

@app.route('/api/guardar_dosis', methods=['POST'])
@login_required
def guardar_dosis():
    """Guarda la prescripción en el historial."""
    global PROXIMO_ID_DOSIS
    data = request.get_json() or {}
    
    peso = float(data.get('peso', 0.0))
    dosis_mg_kg = float(data.get('dosis_mg_kg', 0.0))
    concentracion = float(data.get('concentracion', 1.0))
    
    volumen_ml = round((peso * dosis_mg_kg) / concentracion, 2) if concentracion > 0 else 0.0

    nuevo_registro = {
        "id": PROXIMO_ID_DOSIS,
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)