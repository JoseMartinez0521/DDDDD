#!/usr/bin/env python3
"""
Monitor del estado de una cuenta de Instagram.

Revisa si el perfil publico esta disponible o no y registra en un CSV
CADA VEZ QUE CAMBIA de estado (activada / desactivada), con fecha y hora
de la zona de Mexico (UTC-6).

Dos modos de uso:
  python3 monitor_instagram.py          -> se queda corriendo en bucle
  python3 monitor_instagram.py --once   -> revisa una sola vez y termina
                                           (este es el que se usa en la nube)
"""

import csv
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# ---------------- Configuracion ----------------
# Puedes poner el usuario aqui, o con la variable de entorno IG_USER.
USERNAME = os.environ.get("IG_USER", "0.rcii")  # <-- sin la @
INTERVALO_MIN = 20                 # cada cuantos minutos revisar (modo bucle)
ARCHIVO_LOG = "estado_cuenta.csv"
TZ = timezone(timedelta(hours=-6))  # America/Mexico_City
# ------------------------------------------------

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")


def ahora():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def revisar(username):
    """Devuelve: 'activada', 'desactivada', 'bloqueado' o 'desconocido'."""
    url = f"https://www.instagram.com/{username}/"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept-Language": "es-MX,es;q=0.9"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            html = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "desactivada"   # perfil no disponible / no existe
        if e.code == 429:
            return "bloqueado"     # Instagram nos esta limitando
        return "desconocido"
    except Exception:
        return "desconocido"

    bajo = html.lower()

    # Senales de "no disponible"
    if ("isn't available" in bajo
            or "no esta disponible" in bajo
            or "no está disponible" in bajo
            or "page not found" in bajo):
        return "desactivada"

    # Senales de perfil real
    if (f'"username":"{username.lower()}"' in bajo
            or f"@{username.lower()}" in bajo
            or ('og:title' in bajo and username.lower() in bajo)):
        return "activada"

    # Muro de inicio de sesion: no se puede saber con certeza
    if "accounts/login" in bajo or "loginform" in bajo:
        return "desconocido"

    return "activada"


def ultimo_estado(archivo):
    """Ultimo estado valido (activada/desactivada) guardado en el log."""
    if not os.path.exists(archivo):
        return None
    with open(archivo, newline="", encoding="utf-8") as f:
        filas = list(csv.reader(f))
    for fila in reversed(filas):
        if len(fila) >= 3 and fila[2] in ("activada", "desactivada"):
            return fila[2]
    return None


def registrar(archivo, estado):
    nuevo = not os.path.exists(archivo)
    with open(archivo, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fecha_hora", "usuario", "estado"])
        w.writerow([ahora(), USERNAME, estado])


def un_chequeo():
    estado = revisar(USERNAME)
    prev = ultimo_estado(ARCHIVO_LOG)
    marca = ahora()
    # Solo anotamos cambios reales; 'bloqueado'/'desconocido' no cuentan
    if estado in ("activada", "desactivada") and estado != prev:
        registrar(ARCHIVO_LOG, estado)
        print(f"[{marca}] CAMBIO -> {estado.upper()}")
    else:
        print(f"[{marca}] {estado} (sin cambio)")


def main():
    if USERNAME == "nombre_de_usuario":
        print("Falta poner el usuario: edita USERNAME o usa IG_USER=...")
        sys.exit(1)

    if "--once" in sys.argv:
        un_chequeo()
        return

    print(f"Vigilando @{USERNAME} cada {INTERVALO_MIN} min. Ctrl+C para parar.")
    while True:
        try:
            un_chequeo()
        except KeyboardInterrupt:
            print("\nDetenido.")
            break
        except Exception as e:
            print(f"[{ahora()}] error: {e}")
        time.sleep(INTERVALO_MIN * 60)


if __name__ == "__main__":
    main()
