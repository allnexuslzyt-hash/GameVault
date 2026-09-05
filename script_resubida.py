import asyncio
import json
import os
import subprocess
import sys
import time
import requests
from telethon import TelegramClient
from telethon.sessions import StringSession

print("🚀 Iniciando script_resubida.py (Con ScraperAPI Anti-Cloudflare y Auto-Padding)...", flush=True)

# --- CONFIGURACIÓN Y VARIABLES DE ENTORNO ---
API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOFILE_TOKEN = os.environ.get("GOFILE_API_TOKEN")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION_STRING", "")
SCRAPER_KEY = os.environ.get("SCRAPERAPI_KEY")

JSON_FILE = "juegos.json"

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

if not API_ID or not API_HASH or not BOT_TOKEN:
    print("❌ ERROR CRÍTICO: Faltan variables de entorno de Telegram en GitHub Secrets.", flush=True)
    sys.exit(1)


def guardar_progreso_y_push(data):
    """Guarda el progreso en juegos.json y realiza un git push inmediato a GitHub."""
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("💾 'juegos.json' actualizado localmente.", flush=True)

        subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
        subprocess.run(["git", "add", JSON_FILE], check=False)

        commit_res = subprocess.run(
            ["git", "commit", "-m", "Auto: Estado de resubida actualizado"],
            capture_output=True, text=True
        )

        if "nothing to commit" not in commit_res.stdout:
            subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=False)
            subprocess.run(["git", "push"], check=False)
            print("🚀 Progreso guardado y subido a GitHub exitosamente.", flush=True)
        else:
            print("ℹ️ Sin cambios nuevos que commitear.", flush=True)
    except Exception as e:
        print(f"⚠️ Error al realizar el push a GitHub: {e}", flush=True)


def es_enlace_valido(juego):
    """
    VERIFICACIÓN CON SCRAPERAPI:
    Consulta la API de GoFile a través del proxy de ScraperAPI para evitar los bloqueos de Cloudflare.
    Solo marca como caducado (False) si GoFile confirma al 100% que la carpeta NO existe o está VACÍA.
    Ante cualquier fallo de red o duda, conserva el enlace (True) por seguridad.
    """
    folder_id = juego.get("gofile_folder_id")
    titulo = juego.get("titulo") or juego.get("nombre") or "Juego"

    if not folder_id:
        print(f"🆕 '{titulo}' no tiene carpeta asociada. Se programará para subir...", flush=True)
        return False

    gofile_url = f"https://api.gofile.io/contents/{folder_id}"
    
    if SCRAPER_KEY:
        api_url = f"http://api.scraperapi.com?api_key={SCRAPER_KEY}&url={gofile_url}"
    else:
        api_url = gofile_url

    headers = HEADERS_BASE.copy()
    if GOFILE_TOKEN:
        headers["Authorization"] = f"Bearer {GOFILE_TOKEN}"

    try:
        res = requests.get(api_url, headers=headers, timeout=25)

        if res.status_code == 404:
            print(f"🚨 BORRADO CONFIRMADO (404): '{titulo}' ya no existe en GoFile.", flush=True)
            return False

        if res.status_code == 200:
            try:
                data = res.json()
                status = data.get("status")

                if status == "ok":
                    children = data.get("data", {}).get("children", {})
                    if children:
                        print(f"✅ VÁLIDO: '{titulo}' existe con {len(children)} archivo(s) activo(s).", flush=True)
                        return True
                    else:
                        print(f"🚨 BORRADO CONFIRMADO: La carpeta de '{titulo}' está VACÍA.", flush=True)
                        return False

                if status in ["error-notFound", "error-notFoundOrNotAuthorized"]:
                    print(f"🚨 BORRADO CONFIRMADO (API '{status}'): '{titulo}' fue eliminado.", flush=True)
                    return False

            except Exception:
                print(f"⚠️ Respuesta no-JSON para '{titulo}'. CONSERVANDO ENLACE por seguridad.", flush=True)
                return True

        print(f"⚠️ Respuesta inusual HTTP {res.status_code} para '{titulo}'. CONSERVANDO ENLACE.", flush=True)
        return True

    except Exception as e:
        print(f"⚠️ Error de conexión al consultar '{titulo}' ({e}). CONSERVANDO ENLACE.", flush=True)
        return True


def obtener_servidor_gofile():
    """Obtiene el servidor de carga activo de GoFile."""
    headers = HEADERS_BASE.copy()
    if GOFILE_TOKEN:
        headers["Authorization"] = f"Bearer {GOFILE_TOKEN}"

    try:
        resp = requests.get("https://api.gofile.io/servers", headers=headers, timeout=10).json()
        if resp.get("status") == "ok":
            servers = resp.get("data", {}).get("servers", [])
            if servers:
                return servers[0]["name"]
    except Exception as e:
        print(f"⚠️ Error al consultar servidores GoFile: {e}", flush=True)
    return "store1"


def subir_a_gofile(filepath, folder_id=None, max_reintentos=5):
    """Subo el archivo a GoFile vinculado a tu cuenta personal."""
    for intento in range(1, max_reintentos + 1):
        server = obtener_servidor_gofile()
        url = f"https://{server}.gofile.io/contents/uploadfile"

        payload = {}
        if GOFILE_TOKEN:
            payload["token"] = GOFILE_TOKEN
        if folder_id:
            payload["folderId"] = folder_id

        print(f"📤 Intento {intento}/{max_reintentos}: Subiendo '{filepath}' a tu GoFile...", flush=True)

        try:
            with open(filepath, "rb") as f:
                files = {"file": f}
                response = requests.post(url, files=files, data=payload, headers=HEADERS_BASE, timeout=3600)

            if response.status_code == 200:
                res_json = response.json()
                if res_json.get("status") == "ok":
                    data = res_json["data"]
                    download_page = data.get("downloadPage")
                    parent_folder = data.get("parentFolder") or data.get("folderId")
                    return download_page, parent_folder
                else:
                    print(f"⚠️ GoFile devolvió error en intento {intento}: {res_json}", flush=True)
            else:
                print(f"⚠️ Servidor GoFile devolvió HTTP {response.status_code} en intento {intento}.", flush=True)

        except Exception as e:
            print(f"⚠️ Error durante la subida en intento {intento}: {e}", flush=True)

        if intento < max_reintentos:
            tiempo_espera = 15 * intento
            print(f"⏳ Esperando {tiempo_espera}s antes de reintentar...", flush=True)
            time.sleep(tiempo_espera)

    raise Exception(f"Incapaz de subir '{filepath}' a GoFile tras {max_reintentos} intentos.")


async def procesar_juego(client, juego, todos_los_juegos):
    titulo = juego.get("titulo") or juego.get("nombre") or "Juego"
    channel_id_raw = juego.get("telegram_channel_id")
    msg_ids = juego.get("telegram_message_id")
    folder_id = juego.get("gofile_folder_id")

    if not channel_id_raw or msg_ids is None:
        return

    channel_id = int(channel_id_raw)
    es_lista = isinstance(msg_ids, list)
    lista_msg_ids = list(msg_ids) if es_lista else [msg_ids]

    if not lista_msg_ids:
        print(f"✅ '{titulo}' no tiene partes pendientes.", flush=True)
        return

    print(f"\n🎮 Procesando '{titulo}'...", flush=True)

    while lista_msg_ids:
        msg_id = lista_msg_ids[0]
        print(f"\n📥 Descargando mensaje ID {msg_id} de Telegram (Canal: {channel_id})...", flush=True)

        archivo_local = None
        ultimo_porcentaje = -1

        try:
            message = await client.get_messages(channel_id, ids=msg_id)
            if not message or not message.media:
                print(f"❌ Mensaje ID {msg_id} sin archivo adjunto. Omitiendo...", flush=True)
                lista_msg_ids.pop(0)
                if es_lista:
                    juego["telegram_message_id"] = lista_msg_ids
                guardar_progreso_y_push(todos_los_juegos)
                continue

            def callback_progreso(downloaded, total):
                nonlocal ultimo_porcentaje
                pct = int((downloaded / total) * 100)
                if pct % 10 == 0 and pct != ultimo_porcentaje:
                    mb_down = downloaded / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    print(f"⬇️ Descarga Telegram: {pct}% ({mb_down:.1f} / {mb_total:.1f} MB)", flush=True)
                    ultimo_porcentaje = pct

            archivo_local = await client.download_media(message, progress_callback=callback_progreso)
            print("✅ Descarga de Telegram finalizada.", flush=True)

            download_page, parent_folder = subir_a_gofile(archivo_local, folder_id)

            juego["enlace_descarga"] = download_page
            juego["gofile_folder_id"] = parent_folder
            folder_id = parent_folder

            lista_msg_ids.pop(0)
            if es_lista:
                juego["telegram_message_id"] = lista_msg_ids

            print(f"✨ Parte subida con éxito: {juego['enlace_descarga']}", flush=True)

            guardar_progreso_y_push(todos_los_juegos)

        except Exception as e:
            print(f"\n❌ Error en la parte {msg_id}: {e}", flush=True)
            print("🛑 Proceso detenido para mantener a salvo las partes subidas.", flush=True)
            break
        finally:
            if archivo_local and os.path.exists(archivo_local):
                os.remove(archivo_local)
                print(f"🗑️ Archivo local '{archivo_local}' eliminado.", flush=True)


async def main():
    if not os.path.exists(JSON_FILE):
        print(f"❌ No se encontró el archivo {JSON_FILE}", flush=True)
        sys.exit(1)

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            juegos = json.load(f)
    except Exception as e:
        print(f"❌ Error al leer '{JSON_FILE}': {e}", flush=True)
        sys.exit(1)

    try:
        api_id_int = int(API_ID)
    except ValueError:
        print(f"❌ ERROR: TELEGRAM_API_ID inválido.", flush=True)
        sys.exit(1)

    # --- CORRECCIÓN AUTOMÁTICA DE FORMATO Y PADDING ---
    session_str = SESSION_STRING.strip().strip("'").strip('"') if SESSION_STRING else ""
    if session_str:
        missing_padding = len(session_str) % 4
        if missing_padding:
            session_str += '=' * (4 - missing_padding)
        session_obj = StringSession(session_str)
        print("🔑 Cargando sesión desde TELEGRAM_SESSION_STRING (Padding corregido)...", flush=True)
    else:
        session_obj = "sesion_bot"
        print("⚠️ No se detectó SESSION_STRING. Usando sesión por defecto...", flush=True)

    client = TelegramClient(session_obj, api_id_int, API_HASH, request_retries=15, connection_retries=15, timeout=60)
    
    await client.start(bot_token=BOT_TOKEN)
    print("🤖 Cliente de Telegram iniciado correctamente.", flush=True)

    for juego in juegos:
        titulo = juego.get("titulo") or juego.get("nombre") or "Juego"
        msg_ids = juego.get("telegram_message_id")

        if es_enlace_valido(juego):
            continue

        print(f"⚠️ Preparando resubida de '{titulo}'...", flush=True)
        
        if msg_ids is None:
            print(f"❌ '{titulo}' no tiene telegram_message_id configurado.", flush=True)
            continue

        juego["enlace_descarga"] = ""
        juego["gofile_folder_id"] = ""

        await procesar_juego(client, juego, juegos)

    await client.disconnect()
    print("\n🎉 Proceso completado con éxito.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
