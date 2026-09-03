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

def comprobar_enlace(url):
    """Comprueba directamente si la página web de GoFile está activa sin depender de su API"""
    if not url or "gofile.io" not in url:
        return False
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
    try:
        resp_server = requests.get("https://api.gofile.io/servers", timeout=15).json()
        if resp_server.get('status') == 'ok':
            return resp_server['data']['servers'][0]['name']
    except Exception as e:
        registrar_log(f"Error obteniendo servidor GoFile: {e}")
    return None

def subir_archivo_gofile(server, file_path, folder_id=None, retries=3):
    """Sube un archivo a GoFile con reintentos automáticos y manejo seguro de respuestas HTML/JSON"""
    upload_url = f"https://{server}.gofile.io/contents/uploadfile"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for intento in range(1, retries + 1):
        try:
            data = {}
            if folder_id:
                data['folderId'] = folder_id

            with open(file_path, 'rb') as f:
                resp_raw = requests.post(upload_url, files={'file': f}, data=data, headers=headers, timeout=1800)

            if resp_raw.status_code == 200:
                try:
                    resp = resp_raw.json()
                    if resp.get('status') == 'ok':
                        return resp['data']
                    else:
                        registrar_log(f"  ⚠️ Intento {intento}/{retries}: GoFile devolvió error interno: {resp}")
                except Exception:
                    registrar_log(f"  ⚠️ Intento {intento}/{retries}: Respuesta no es JSON válido (servidor sobrecargado).")
            else:
                registrar_log(f"  ⚠️ Intento {intento}/{retries}: Código HTTP {resp_raw.status_code} de GoFile.")

        except Exception as e:
            registrar_log(f"  ⚠️ Intento {intento}/{retries} falló con excepción: {e}")

        if intento < retries:
            registrar_log(f"  🔄 Esperando 10 segundos antes del reintento {intento + 1}...")
            time.sleep(10)

    return None

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
                registrar_log(f"🟢 Estado: Enlace activo y funcional.")
                continue

            registrar_log(f"⚠️ Estado: Enlace caído o inexistente. Iniciando resubida...")

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
                if not server:
                    registrar_log("❌ No se pudo obtener un servidor activo de GoFile.")
                    continue

                folder_id = None
                nuevo_enlace = None

                for i, msg_id in enumerate(msg_ids, start=1):
                    registrar_log(f"  └─ Procesando parte {i}/{len(msg_ids)} (Mensaje ID: {msg_id})...")
                    message = client.get_messages(chat_id, ids=msg_id)

                    if message:
                        temp_path = f"temp_{juego['id']}_part{i}.rar"
                        client.download_media(message, file=temp_path)

                        upload_data = subir_archivo_gofile(server, temp_path, folder_id)

                        if os.path.exists(temp_path):
                            os.remove(temp_path)

                        if upload_data:
                            if not folder_id:
                                folder_id = upload_data.get('parentFolder')
                                nuevo_enlace = upload_data.get('downloadPage')
                        else:
                            registrar_log(f"❌ Fallaron todos los intentos para la parte {i}. Abortando resubida de {titulo}.")
                            nuevo_enlace = None
                            break
                    else:
                        registrar_log(f"❌ No se encontró el mensaje ID {msg_id} en Telegram.")
                        nuevo_enlace = None
                        break

                if nuevo_enlace:
                    juego['enlace_descarga'] = nuevo_enlace
                    cambios = True
                    registrar_log(f"🔄 Resultado: Resubido con éxito.")
                    registrar_log(f"🔗 Nuevo enlace carpeta: {nuevo_enlace}")

            except Exception as e:
                registrar_log(f"❌ Error al procesar '{titulo}': {e}")

    registrar_log("\n" + "─"*45)
    if cambios:
        with open('juegos.json', 'w', encoding='utf-8') as f:
            json.dump(juegos, f, indent=2, ensure_ascii=False)
        registrar_log("💾 Cambios de enlaces guardados en juegos.json.")
    else:
        registrar_log("✨ Todos los enlaces están operativos. No se requirieron cambios.")

if __name__ == '__main__':
    main()
