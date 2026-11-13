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
import json
import os
import re
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


APP_ID = "936619743392459"  # x-ig-app-id publico del sitio web de Instagram


def _api(username):
    """Endpoint JSON de Instagram. Devuelve estado, o None si no concluye."""
    url = ("https://www.instagram.com/api/v1/users/web_profile_info/"
           f"?username={username}")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "x-ig-app-id": APP_ID,
        "Accept": "application/json",
        "Accept-Language": "es-MX,es;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8", "ignore"))
        user = (data.get("data") or {}).get("user")
        return "activada" if user else "desactivada"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "desactivada"
        return None   # 401/429/otros: no concluye, pasamos al metodo HTML
    except Exception:
        return None


def revisar(username):
    """Devuelve: 'activada', 'desactivada', 'bloqueado' o 'desconocido'.

    Regla de oro: solo dice 'activada' si CONFIRMA el perfil real.
    Si no esta seguro, dice 'desconocido' (nunca inventa 'activada').
    """
    # 1) Primero el endpoint JSON (mas confiable). Si no concluye, HTML.
    v = _api(username)
    if v is not None:
        return v

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
    u = username.lower()

    # --- Extraer el og:title (el HTML lo trae aunque entre un bot) ---
    og = ""
    m = re.search(r'<meta[^>]*og:title[^>]*>', html, re.I)
    if m:
        c = re.search(r'content="([^"]*)"', m.group(0), re.I)
        if c:
            og = c.group(1).lower()

    # 1) PERFIL REAL: el og:title de un perfil activo trae el usuario.
    #    Ej: "Nombre (@0.rcii) * Instagram photos and videos"
    if u in og and "instagram" in og:
        return "activada"

    # 2) NO DISPONIBLE: textos tipicos de cuenta desactivada / eliminada.
    marcadores_no = [
        "profile isn't available",
        "profile isn’t available",
        "page isn't available",
        "page isn’t available",
        "this page isn't available",
        "the profile may have been removed",
        "no esta disponible",
        "no está disponible",
        "page not found",
    ]
    if any(x in bajo for x in marcadores_no):
        return "desactivada"

    # 3) og:title generico (sin el usuario) tambien apunta a no disponible.
    if og.strip() in ("instagram", "login * instagram", "login • instagram"):
        return "desactivada"

    # 4) No se pudo confirmar nada (muro de login, pagina rara, etc.)
    return "desconocido"


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
