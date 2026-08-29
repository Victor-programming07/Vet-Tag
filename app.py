
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

import sqlite3

# ==========================================================

# CONFIGURACIÓN FLASK

# ==========================================================

app = Flask(**name**)

app.secret_key = os.environ.get(
"SECRET_KEY",
"vettag_telemetry_secure_key"
)

ZONA_HORARIA_ECUADOR = timezone(
timedelta(hours=-5)
)

# Base de datos persistente de Render.

# Render debe tener un disco persistente montado en /opt/render/project/src

# para conservarla entre reinicios.

DB_PATH = os.environ.get(
"DATABASE_PATH",
"vettag.db"
)

# ==========================================================

# BASE DE DATOS

# ==========================================================

def conectar_db():
conexion = sqlite3.connect(DB_PATH)
conexion.row_factory = sqlite3.Row
return conexion

def inicializar_db():

```
conexion = conectar_db()

cursor = conexion.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS credenciales (
        id INTEGER PRIMARY KEY,
        usuario TEXT NOT NULL,
        clave TEXT NOT NULL,
        fecha_ultimo_cambio TEXT NOT NULL
    )
""")

conexion.commit()
conexion.close()
```

def obtener_credenciales():

```
conexion = conectar_db()

cursor = conexion.cursor()

cursor.execute("""
    SELECT usuario, clave, fecha_ultimo_cambio
    FROM credenciales
    WHERE id = 1
""")

fila = cursor.fetchone()

conexion.close()

if fila is None:
    return None

return {
    "usuario": fila["usuario"],
    "clave": fila["clave"],
    "fecha_ultimo_cambio": datetime.date.fromisoformat(
        fila["fecha_ultimo_cambio"]
    )
}
```

def guardar_credenciales(usuario, clave):

```
fecha = obtener_hora_ecuador().date().isoformat()

conexion = conectar_db()

cursor = conexion.cursor()

cursor.execute("""
    INSERT INTO credenciales
    (id, usuario, clave, fecha_ultimo_cambio)
    VALUES (1, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        usuario = excluded.usuario,
        clave = excluded.clave,
        fecha_ultimo_cambio = excluded.fecha_ultimo_cambio
""", (
    usuario,
    clave,
    fecha
))

conexion.commit()
conexion.close()
```

# ==========================================================

# INICIALIZAR BASE DE DATOS

# ==========================================================

inicializar_db()

# ==========================================================

# HISTORIAL DE DOSIS

# ==========================================================

HISTORIAL_DOSIS = []

PROXIMO_ID_DOSIS = 1

# ==========================================================

# ESTADO ACTUAL DE TELEMETRÍA

# ==========================================================

estado_telemetria_actual = {

```
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
```

}

# ==========================================================

# HORA ECUADOR

# ==========================================================

def obtener_hora_ecuador():

```
return datetime.datetime.now(
    ZONA_HORARIA_ECUADOR
)
```

# ==========================================================

# CAMBIO DE CONTRASEÑA CADA 30 DÍAS

# ==========================================================

def requiere_cambio_clave():

```
datos = obtener_credenciales()

if not datos:
    return False

fecha = datos["fecha_ultimo_cambio"]

hoy = obtener_hora_ecuador().date()

dias_transcurridos = (
    hoy - fecha
).days

return dias_transcurridos >= 30
```

# ==========================================================

# PROTECCIÓN DE RUTAS

# ==========================================================

def login_required(f):

```
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
```

# ==========================================================

# DIAGNÓSTICO CLÍNICO

# ==========================================================

def evaluar_estado_clinico(
temp,
bpm
):

```
# No usamos pechera/Hall todavía.

if temp == 0 and bpm == 0:

    return {
        "salud_mascota":
            "Sin Conexión de Sensores",

        "badge_class":
            "bg-secondary",

        "mensaje":
            "A la espera de datos del ESP32."
    }


if temp > 39.2 and bpm > 140:

    return {
        "salud_mascota":
            "Estado Crítico",

        "badge_class":
            "bg-danger",

        "mensaje":
            "Alerta de hipertermia severa "
            "y taquicardia. Requiere "
            "atención médica inmediata."
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


# Como todavía no tienes sensor de temperatura,
# no se genera hipotermia cuando temp = 0.

elif temp > 0 and temp < 37.5:

    return {
        "salud_mascota":
            "Hipotermia Detectada",

        "badge_class":
            "bg-warning text-dark",

        "mensaje":
            "Temperatura corporal "
            "por debajo del rango normal."
    }


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
```

# ==========================================================

# INICIO

# ==========================================================

@app.route("/")
def inicio():

```
return render_template(
    "logotipo.html"
)
```

# ==========================================================

# LOGIN

# ==========================================================

@app.route(
"/login",
methods=["GET", "POST"]
)
def login():

```
datos = obtener_credenciales()

# ------------------------------------------------------
# PRIMERA CONFIGURACIÓN
# ------------------------------------------------------

if datos is None:

    return redirect(
        url_for(
            "cambiar_credenciales"
        )
    )


# ------------------------------------------------------
# USUARIO YA AUTENTICADO
# ------------------------------------------------------

if session.get(
    "usuario_autenticado"
):

    return redirect(
        url_for("panel_medico")
    )


# ------------------------------------------------------
# PROCESAR LOGIN
# ------------------------------------------------------

if request.method == "POST":

    usuario_ingresado = request.form.get(
        "usuario",
        ""
    ).strip()

    # Tu login.html utiliza "password".
    # También aceptamos "clave" por compatibilidad.

    clave_ingresada = request.form.get(
        "password"
    )

    if clave_ingresada is None:

        clave_ingresada = request.form.get(
            "clave",
            ""
        )

    clave_ingresada = clave_ingresada.strip()


    # --------------------------------------------------
    # VALIDACIÓN
    # --------------------------------------------------

    if (
        usuario_ingresado
        == datos["usuario"]
        and
        clave_ingresada
        == datos["clave"]
    ):

        session[
            "usuario_autenticado"
        ] = True

        session[
            "usuario"
        ] = usuario_ingresado


        # ------------------------------------------------
        # COMPROBAR LOS 30 DÍAS
        # ------------------------------------------------

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
            url_for(
                "panel_medico"
            )
        )


    else:

        flash(
            "Credenciales incorrectas.",
            "danger"
        )


return render_template(
    "login.html"
)
```

# ==========================================================

# CREAR / CAMBIAR CREDENCIALES

# ==========================================================

@app.route(
"/cambiar_credenciales",
methods=["GET", "POST"]
)
def cambiar_credenciales():

```
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


    # --------------------------------------------------
    # GUARDAR EN SQLITE
    # --------------------------------------------------

    guardar_credenciales(
        nuevo_usuario,
        nueva_clave
    )


    # --------------------------------------------------
    # ACTIVAR SESIÓN
    # --------------------------------------------------

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
        url_for(
            "panel_medico"
        )
    )


return render_template(
    "cambiar_credenciales.html"
)
```

# ==========================================================

# PANEL MÉDICO

# ==========================================================

@app.route("/medico")
@login_required
def panel_medico():


