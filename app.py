
import os
import datetime

from datetime import timezone, timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory
)


# ==========================================================
# CONFIGURACIÓN FLASK
# ==========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "vettag_telemetry_secure_key"
)


# ==========================================================
# ZONA HORARIA ECUADOR
# ==========================================================

ZONA_HORARIA_ECUADOR = timezone(
    timedelta(hours=-5)
)


# ==========================================================
# CREDENCIALES
# ==========================================================

DATOS_USUARIO = {
    "usuario": None,
    "clave": None,
    "fecha_ultimo_cambio": None
}


# ==========================================================
# HISTORIAL DE DOSIS
# ==========================================================

HISTORIAL_DOSIS = []

PROXIMO_ID_DOSIS = 1


# ==========================================================
# ESTADO ACTUAL DE TELEMETRÍA
# ==========================================================

estado_telemetria_actual = {

    "ritmo_cardiaco": 0,

    "temperatura": 0.0,

    "acx": 0.0,

    "acy": 0.0,

    "acz": 0.0,

    "actividad": {
        "estado": "En espera de sensor",
        "icono": "⏳"
    },

    "conectado": False,

    "ultima_actualizacion": "---"
}


# ==========================================================
# HORA ECUADOR
# ==========================================================

def obtener_hora_ecuador():

    return datetime.datetime.now(
        ZONA_HORARIA_ECUADOR
    )


# ==========================================================
# CAMBIO DE CLAVE
# ==========================================================

def requiere_cambio_clave():

    fecha = DATOS_USUARIO.get(
        "fecha_ultimo_cambio"
    )

    if not fecha:
        return False

    hoy = obtener_hora_ecuador().date()

    dias_transcurridos = (
        hoy - fecha
    ).days

    return dias_transcurridos >= 30


# ==========================================================
# LOGIN REQUIRED
# ==========================================================

def login_required(f):

    @wraps(f)
    def decorated_function(
        *args,
        **kwargs
    ):

        if not session.get(
            "usuario_autenticado"
        ):

            return redirect(
                url_for("login")
            )

        return f(
            *args,
            **kwargs
        )

    return decorated_function


# ==========================================================
# DIAGNÓSTICO CLÍNICO
# ==========================================================

def evaluar_estado_clinico(
    temp,
    bpm
):

    # Sin datos
    if temp == 0 and bpm == 0:

        return {

            "salud_mascota":
                "Sin datos",

            "badge_class":
                "bg-secondary",

            "mensaje":
                "Esperando datos del ESP32."
        }


    # Temperatura elevada
    if temp > 39.2 and bpm > 140:

        return {

            "salud_mascota":
                "Estado Crítico",

            "badge_class":
                "bg-danger",

            "mensaje":
                "Alerta de hipertermia severa "
                "y taquicardia."
        }


    elif temp > 39.2:

        return {

            "salud_mascota":
                "Fiebre Detectada",

            "badge_class":
                "bg-warning text-dark",

            "mensaje":
                "Temperatura corporal elevada."
        }


    # IMPORTANTE:
    # temperatura 0 significa
    # sensor todavía no instalado.
    elif temp > 0 and temp < 37.5:

        return {

            "salud_mascota":
                "Temperatura Baja",

            "badge_class":
                "bg-warning text-dark",

            "mensaje":
                "Temperatura corporal por "
                "debajo del rango establecido."
        }


    # Ritmo cardíaco
    elif bpm > 140:

        return {

            "salud_mascota":
                "Taquicardia",

            "badge_class":
                "bg-warning text-dark",

            "mensaje":
                "Frecuencia cardíaca elevada."
        }


    elif bpm > 0 and bpm < 60:

        return {

            "salud_mascota":
                "Bradicardia",

            "badge_class":
                "bg-warning text-dark",

            "mensaje":
                "Frecuencia cardíaca baja."
        }


    else:

        return {

            "salud_mascota":
                "Estado Normal",

            "badge_class":
                "bg-success",

            "mensaje":
                "Constantes vitales estables."
        }


# ==========================================================
# INICIO
# ==========================================================

@app.route("/")
def inicio():

    return render_template(
        "logotipo.html"
    )


# ==========================================================
# LOGIN
# ==========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if not DATOS_USUARIO["usuario"]:

        return redirect(
            url_for(
                "cambiar_credenciales"
            )
        )


    if session.get(
        "usuario_autenticado"
    ):

        return redirect(
            url_for("panel_medico")
        )


    if request.method == "POST":

        usuario_ingresado = request.form.get(
            "usuario",
            ""
        ).strip()

        clave_ingresada = request.form.get(
            "password"
        )

        if clave_ingresada is None:

            clave_ingresada = request.form.get(
                "clave",
                ""
            )

        clave_ingresada = clave_ingresada.strip()


        if (
            usuario_ingresado
            == DATOS_USUARIO["usuario"]

            and

            clave_ingresada
            == DATOS_USUARIO["clave"]
        ):

            session[
                "usuario_autenticado"
            ] = True

            session[
                "usuario"
            ] = usuario_ingresado


            if requiere_cambio_clave():

                flash(
                    "Han transcurrido 30 días. "
                    "Por seguridad actualice sus credenciales.",
                    "warning"
                )

                return redirect(
                    url_for(
                        "cambiar_credenciales"
                    )
                )


            return redirect(
                url_for("panel_medico")
            )


        else:

            flash(
                "Credenciales incorrectas.",
                "danger"
            )


    return render_template(
        "login.html"
    )


# ==========================================================
# CAMBIAR CREDENCIALES
# ==========================================================

@app.route(
    "/cambiar_credenciales",
    methods=["GET", "POST"]
)
def cambiar_credenciales():

    if request.method == "POST":

        nuevo_usuario = request.form.get(
            "nuevo_usuario",
            ""
        ).strip()

        nueva_clave = request.form.get(
            "nueva_clave",
            ""
        ).strip()


        if not nuevo_usuario:

            flash(
                "Debe ingresar un usuario.",
                "danger"
            )

            return render_template(
                "cambiar_credenciales.html"
            )


        if not nueva_clave:

            flash(
                "Debe ingresar una contraseña.",
                "danger"
            )

            return render_template(
                "cambiar_credenciales.html"
            )


        DATOS_USUARIO[
            "usuario"
        ] = nuevo_usuario

        DATOS_USUARIO[
            "clave"
        ] = nueva_clave

        DATOS_USUARIO[
            "fecha_ultimo_cambio"
        ] = obtener_hora_ecuador().date()


        session[
            "usuario_autenticado"
        ] = True

        session[
            "usuario"
        ] = nuevo_usuario


        flash(
            "Credenciales guardadas exitosamente.",
            "success"
        )


        return redirect(
            url_for("panel_medico")
        )


    return render_template(
        "cambiar_credenciales.html"
    )


# ==========================================================
# PANEL MÉDICO
# ==========================================================

@app.route("/medico")
@login_required
def panel_medico():

    return render_template(
        "medico.html"
    )


# ==========================================================
# RECIBIR TELEMETRÍA DEL ESP32
# ==========================================================

@app.route(
    "/api/actualizar_telemetria",
    methods=["POST"]
)
def actualizar_telemetria():

    global estado_telemetria_actual

    try:

        data = request.get_json(
            silent=True
        )


        if not data:

            return jsonify({

                "status":
                    "error",

                "mensaje":
                    "JSON vacío o inválido"

            }), 400


        # ==================================================
        # TEMPERATURA
        # ==================================================

        if "temperatura" in data:

            estado_telemetria_actual[
                "temperatura"
            ] = float(
                data["temperatura"]
            )


        # ==================================================
        # RITMO CARDÍACO
        # ==================================================

        if "ritmo_cardiaco" in data:

            estado_telemetria_actual[
                "ritmo_cardiaco"
            ] = int(
                float(
                    data["ritmo_cardiaco"]
                )
            )


        # ==================================================
        # ACELERÓMETRO X
        # ==================================================

        if "acx" in data:

            estado_telemetria_actual[
                "acx"
            ] = float(
                data["acx"]
            )


        # ==================================================
        # ACELERÓMETRO Y
        # ==================================================

        if "acy" in data:

            estado_telemetria_actual[
                "acy"
            ] = float(
                data["acy"]
            )


        # ==================================================
        # ACELERÓMETRO Z
        # ==================================================

        if "acz" in data:

            estado_telemetria_actual[
                "acz"
            ] = float(
                data["acz"]
            )


        # ==================================================
        # ACTIVIDAD
        # ==================================================

        actividad = str(
            data.get(
                "actividad",
                "En Reposo"
            )
        )


        if actividad == "En Reposo":

            icono = "🟢"

        elif actividad == "En Movimiento":

            icono = "🟡"

        elif actividad == "Movimiento Intenso":

            icono = "🔴"

        else:

            icono = "⚪"


        estado_telemetria_actual[
            "actividad"
        ] = {

            "estado":
                actividad,

            "icono":
                icono
        }


        # ==================================================
        # CONEXIÓN
        # ==================================================

        estado_telemetria_actual[
            "conectado"
        ] = True


        estado_telemetria_actual[
            "ultima_actualizacion"
        ] = obtener_hora_ecuador().strftime(
            "%H:%M:%S"
        )


        # ==================================================
        # CONSOLA
        # ==================================================

        print()
        print("================================")
        print("       TELEMETRÍA RECIBIDA")
        print("================================")

        print(
            "Temperatura:",
            estado_telemetria_actual[
                "temperatura"
            ],
            "°C"
        )

        print(
            "Ritmo cardíaco:",
            estado_telemetria_actual[
                "ritmo_cardiaco"
            ],
            "BPM"
        )

        print(
            "Actividad:",
            actividad
        )

        print(
            "ACX:",
            estado_telemetria_actual[
                "acx"
            ]
        )

        print(
            "ACY:",
            estado_telemetria_actual[
                "acy"
            ]
        )

        print(
            "ACZ:",
            estado_telemetria_actual[
                "acz"
            ]
        )

        print(
            "Hora:",
            estado_telemetria_actual[
                "ultima_actualizacion"
            ]
        )

        print("================================")
        print()


        # ==================================================
        # RESPUESTA ESP32
        # ==================================================

        return jsonify({

            "status":
                "success",

            "mensaje":
                "Telemetría recibida correctamente",

            "temperatura":
                estado_telemetria_actual[
                    "temperatura"
                ],

            "ritmo_cardiaco":
                estado_telemetria_actual[
                    "ritmo_cardiaco"
                ],

            "actividad":
                estado_telemetria_actual[
                    "actividad"
                ]

        }), 200


    except (ValueError, TypeError) as e:

        print(
            "ERROR EN LOS DATOS:",
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "mensaje":
                "Los datos enviados tienen "
                "un formato incorrecto.",

            "detalle":
                str(e)

        }), 400


    except Exception as e:

        print(
            "ERROR TELEMETRÍA:",
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "mensaje":
                "Error interno del servidor.",

            "detalle":
                str(e)

        }), 500


# ==========================================================
# ENVIAR TELEMETRÍA AL MÉDICO
# ==========================================================

@app.route(
    "/api/telemetria",
    methods=["GET"]
)
@login_required
def api_telemetria():

    temp = estado_telemetria_actual.get(
        "temperatura",
        0.0
    )

    bpm = estado_telemetria_actual.get(
        "ritmo_cardiaco",
        0
    )

    actividad = estado_telemetria_actual.get(
        "actividad",
        {
            "estado":
                "En espera de sensor",

            "icono":
                "⏳"
        }
    )

    conectado = estado_telemetria_actual.get(
        "conectado",
        False
    )

    ultima_actualizacion = (
        estado_telemetria_actual.get(
            "ultima_actualizacion",
            "---"
        )
    )


    diagnostico = evaluar_estado_clinico(
        temp,
        bpm
    )


    return jsonify({

        "temperatura":
            temp,

        "ritmo_cardiaco":
            bpm,

        "actividad":
            actividad,

        "diagnostico":
            diagnostico,

        "conectado":
            conectado,

        "ultima_actualizacion":
            ultima_actualizacion,

        "acx":
            estado_telemetria_actual.get(
                "acx",
                0.0
            ),

        "acy":
            estado_telemetria_actual.get(
                "acy",
                0.0
            ),

        "acz":
            estado_telemetria_actual.get(
                "acz",
                0.0
            )

    })


# ==========================================================
# GUARDAR DOSIS
# ==========================================================

@app.route(
    "/api/guardar_dosis",
    methods=["POST"]
)
@login_required
def guardar_dosis():

    global PROXIMO_ID_DOSIS

    try:

        data = request.get_json(
            silent=True
        ) or {}


        peso = float(
            data.get(
                "peso",
                0
            )
        )

        dosis_mg_kg = float(
            data.get(
                "dosis_mg_kg",
                0
            )
        )

        concentracion = float(
            data.get(
                "concentracion",
                0
            )
        )


        if peso <= 0:

            return jsonify({

                "status":
                    "error",

                "mensaje":
                    "El peso debe ser mayor que 0."

            }), 400


        if dosis_mg_kg <= 0:

            return jsonify({

                "status":
                    "error",

                "mensaje":
                    "La dosis debe ser mayor que 0."

            }), 400


        if concentracion <= 0:

            return jsonify({

                "status":
                    "error",

                "mensaje":
                    "La concentración debe ser mayor que 0."

            }), 400


        volumen_ml = round(
            (
                peso *
                dosis_mg_kg
            ) / concentracion,
            2
        )


        nuevo_registro = {

            "id":
                PROXIMO_ID_DOSIS,

            "fecha":
                obtener_hora_ecuador().strftime(
                    "%Y-%m-%d %H:%M"
                ),

            "paciente":
                data.get(
                    "paciente",
                    "Desconocido"
                ),

            "peso":
                peso,

            "propietario":
                data.get(
                    "propietario",
                    "N/A"
                ),

            "telefono":
                data.get(
                    "telefono",
                    "N/A"
                ),

            "correo":
                data.get(
                    "correo",
                    "N/A"
                ),

            "direccion":
                data.get(
                    "direccion",
                    "N/A"
                ),

            "farmaco":
                data.get(
                    "farmaco",
                    "N/A"
                ),

            "dosis_mg_kg":
                dosis_mg_kg,

            "concentracion":
                concentracion,

            "volumen_ml":
                volumen_ml,

            "sugerencias":
                data.get(
                    "sugerencias",
                    "Sin observaciones."
                )
        }


        HISTORIAL_DOSIS.append(
            nuevo_registro
        )

        PROXIMO_ID_DOSIS += 1


        return jsonify({

            "status":
                "success",

            "mensaje":
                "Dosis guardada correctamente.",

            "id":
                nuevo_registro["id"],

            "volumen_ml":
                volumen_ml

        }), 201


    except (ValueError, TypeError) as e:

        return jsonify({

            "status":
                "error",

            "mensaje":
                "Los datos de la dosis no son válidos.",

            "detalle":
                str(e)

        }), 400


    except Exception as e:

        print(
            "ERROR GUARDANDO DOSIS:",
            str(e)
        )

        return jsonify({

            "status":
                "error",

            "mensaje":
                "Error interno al guardar la dosis.",

            "detalle":
                str(e)

        }), 500


# ==========================================================
# HISTORIAL DE DOSIS
# ==========================================================

@app.route(
    "/api/historial_dosis",
    methods=["GET"]
)
@login_required
def obtener_historial_dosis():

    return jsonify(
        HISTORIAL_DOSIS
    )


# ==========================================================
# ELIMINAR DOSIS
# ==========================================================

@app.route(
    "/api/eliminar_dosis/<int:id_dosis>",
    methods=["DELETE"]
)
@login_required
def eliminar_dosis(id_dosis):

    global HISTORIAL_DOSIS


    cantidad_antes = len(
        HISTORIAL_DOSIS
    )


    HISTORIAL_DOSIS = [

        item

        for item in HISTORIAL_DOSIS

        if item["id"] != id_dosis
    ]


    if len(HISTORIAL_DOSIS) < cantidad_antes:

        return jsonify({

            "status":
                "success",

            "mensaje":
                "Registro eliminado correctamente.",

            "deleted_id":
                id_dosis

        })


    return jsonify({

        "status":
            "error",

        "mensaje":
            "No se encontró el registro."

    }), 404


# ==========================================================
# LOGOUT
# ==========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ==========================================================
# MANIFEST
# ==========================================================

@app.route("/manifest.json")
def serve_manifest():

    return send_from_directory(
        ".",
        "manifest.json"
    )


# ==========================================================
# EJECUTAR
# ==========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        debug=False,
        host="0.0.0.0",
        port=port
    )

