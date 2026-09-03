import os
import json
import time
import requests
from telethon.sync import TelegramClient

API_ID = int(os.environ.get('TELEGRAM_API_ID', 0))
API_HASH = os.environ.get('TELEGRAM_API_HASH', '')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

REPORTE_PATH = 'reporte.txt'

def registrar_log(texto):
    """Imprime de forma inmediata en la consola de GitHub Actions y guarda el log en reporte.txt"""
    print(texto, flush=True)
    with open(REPORTE_PATH, 'a', encoding='utf-8') as f:
        f.write(texto + '\n')

class ProgresoDescarga:
    """Muestra el avance de descarga de Telegram en tramos de 10%"""
    def __init__(self):
        self.ultimo_porcentaje = -10

    def callback(self, downloaded, total):
        if not total:
            return
        porcentaje = int((downloaded / total) * 100)
        if porcentaje >= self.ultimo_porcentaje + 10:
            self.ultimo_porcentaje = porcentaje
            mb_descargados = downloaded / (1024 * 1024)
            mb_totales = total / (1024 * 1024)
            registrar_log(f"     ⬇️ Progreso descarga Telegram: {porcentaje}% ({mb_descargados:.1f} / {mb_totales:.1f} MB)")

def comprobar_enlace(url):
    """Comprueba si la página web de GoFile está activa"""
    if not url or "gofile.io" not in url:
        return False
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            texto_pagina = r.text.lower()
            if "error-notfound" in texto_pagina or "this content does not exist" in texto_pagina or "item not found" in texto_pagina:
                return False
            return True
        return False
    except Exception as e:
        registrar_log(f"Error comprobando URL ({url}): {e}")
        return False

def obtener_servidor_gofile():
    """Obtiene el servidor de subida activo en GoFile"""
    try:
        resp_server = requests.get("https://api.gofile.io/servers", timeout=15).json()
        if resp_server.get('status') == 'ok':
            return resp_server['data']['servers'][0]['name']
    except Exception as e:
        registrar_log(f"Error obteniendo servidor GoFile: {e}")
    return None

def obtener_token_gofile():
    """Obtiene un token de sesión anónima en GoFile"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.post("https://api.gofile.io/accounts", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get('status') == 'ok':
                return data['data']['token']
    except Exception as e:
        registrar_log(f"Error obteniendo token de GoFile: {e}")
    return None

def subir_archivo_gofile(server, file_path, token=None, folder_id=None, retries=3):
    """Sube un archivo a GoFile con reintentos"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    for intento in range(1, retries + 1):
        servidor_activo = server if intento == 1 else (obtener_servidor_gofile() or server)
        upload_url = f"https://{servidor_activo}.gofile.io/contents/uploadfile"

        try:
            data = {}
            if token:
                data['token'] = token
            if folder_id:
                data['folderId'] = folder_id

            registrar_log(f"     ⬆️ Subiendo a GoFile ({servidor_activo})...")
            
            with open(file_path, 'rb') as f:
                resp_raw = requests.post(upload_url, files={'file': f}, data=data, headers=headers, timeout=1800)

            if resp_raw.status_code == 200:
                try:
                    resp = resp_raw.json()
                    if resp.get('status') == 'ok':
                        return resp['data']
                    else:
                        registrar_log(f"  ⚠️ Intento {intento}/{retries}: GoFile devolvió error: {resp}")
                except Exception:
                    registrar_log(f"  ⚠️ Intento {intento}/{retries}: Respuesta no es JSON válido.")
            else:
                registrar_log(f"  ⚠️ Intento {intento}/{retries}: Código HTTP {resp_raw.status_code}.")

        except Exception as e:
            registrar_log(f"  ⚠️ Intento {intento}/{retries} falló con excepción: {e}")

        if intento < retries:
            registrar_log("  🔄 Esperando 10 segundos antes del reintento...")
            time.sleep(10)

    return None

def guardar_progreso_juegos(juegos):
    """Guarda inmediatamente el estado actual en juegos.json"""
    with open('juegos.json', 'w', encoding='utf-8') as f:
        json.dump(juegos, f, indent=2, ensure_ascii=False)

def main():
    if os.path.exists(REPORTE_PATH):
        os.remove(REPORTE_PATH)

    if not os.path.exists('juegos.json'):
        registrar_log("❌ No se encontró el archivo juegos.json.")
        return

    with open('juegos.json', 'r', encoding='utf-8') as f:
        juegos = json.load(f)

    cambios = False
    registrar_log("🤖 [Nexus Games] Reporte de Chequeo y Resubidas\n" + "─"*45)

    with TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN) as client:
        for juego in juegos:
            url_actual = juego.get('enlace_descarga', '')
            titulo = juego.get('titulo', 'Sin título')

            registrar_log(f"\n🔍 Verificando: {titulo}...")

            if comprobar_enlace(url_actual):
                registrar_log("🟢 Estado: Enlace activo y funcional.")
                continue

            registrar_log("⚠️ Estado: Enlace caído o inexistente. Iniciando/Reanudando resubida...")

            raw_msg_ids = juego.get('telegram_message_id')
            if isinstance(raw_msg_ids, list):
                msg_ids = [int(m) for m in raw_msg_ids]
            elif raw_msg_ids is not None:
                msg_ids = [int(raw_msg_ids)]
            else:
                registrar_log(f"❌ {titulo} no tiene telegram_message_id configurado.")
                continue

            try:
                chat_id = int(juego['telegram_channel_id'])
                server = obtener_servidor_gofile()
                token = obtener_token_gofile()

                if not server:
                    registrar_log("❌ No se pudo obtener un servidor activo de GoFile.")
                    continue

                folder_id = juego.get('gofile_folder_id', None)
                nuevo_enlace = juego.get('gofile_temp_link', None)
                partes_completadas = juego.get('partes_completadas', [])

                for i, msg_id in enumerate(msg_ids, start=1):
                    if i in partes_completadas:
                        registrar_log(f"  └─ Parte {i}/{len(msg_ids)} ya fue subida anteriormente. Omitiendo...")
                        continue

                    registrar_log(f"\n  └─ Procesando parte {i}/{len(msg_ids)} (Mensaje ID: {msg_id})...")
                    
                    if not client.is_connected():
                        client.connect()

                    message = client.get_messages(chat_id, ids=msg_id)

                    if message:
                        temp_path = f"temp_{juego['id']}_part{i}.rar"
                        registrar_log(f"     ⬇️ Descargando parte {i} desde Telegram...")
                        
                        progreso = ProgresoDescarga()
                        client.download_media(message, file=temp_path, progress_callback=progreso.callback)

                        upload_data = subir_archivo_gofile(server, temp_path, token=token, folder_id=folder_id)

                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                        if upload_data:
                            if not folder_id:
                                folder_id = upload_data.get('parentFolder')
                                nuevo_enlace = upload_data.get('downloadPage')
                                juego['gofile_folder_id'] = folder_id
                                juego['gofile_temp_link'] = nuevo_enlace

                            partes_completadas.append(i)
                            juego['partes_completadas'] = partes_completadas
                            guardar_progreso_juegos(juegos)
                            cambios = True

                            registrar_log(f"     ✅ Parte {i}/{len(msg_ids)} completada con éxito y guardada.")
                        else:
                            registrar_log(f"❌ Falló la subida para la parte {i}. Se reanudará en la siguiente ejecución.")
                            break
                    else:
                        registrar_log(f"❌ No se encontró el mensaje ID {msg_id} en Telegram.")
                        break

                    time.sleep(5)

                if len(partes_completadas) == len(msg_ids) and nuevo_enlace:
                    juego['enlace_descarga'] = nuevo_enlace
                    juego.pop('gofile_folder_id', None)
                    juego.pop('gofile_temp_link', None)
                    juego.pop('partes_completadas', None)
                    
                    guardar_progreso_juegos(juegos)
                    cambios = True
                    registrar_log(f"\n🔄 Resultado: Resubida completa del juego finalizada con éxito.")
                    registrar_log(f"🔗 Nuevo enlace final: {nuevo_enlace}")

            except Exception as e:
                registrar_log(f"❌ Error al procesar '{titulo}': {e}")

    registrar_log("\n" + "─"*45)
    if cambios:
        registrar_log("💾 Cambios e historial guardados en juegos.json.")
    else:
        registrar_log("✨ Todos los enlaces están operativos. No se requirieron cambios.")

if __name__ == '__main__':
    main()
