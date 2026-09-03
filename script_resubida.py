import os
import json
import requests
from telethon.sync import TelegramClient

API_ID = int(os.environ.get('TELEGRAM_API_ID', 0))
API_HASH = os.environ.get('TELEGRAM_API_HASH', '')
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

def comprobar_enlace(url):
    if not url or "gofile.io" not in url:
        return False
    try:
        content_id = url.split('/')[-1]
        api_url = f"https://api.gofile.io/contents/{content_id}"
        r = requests.get(api_url, timeout=10)
        if r.status_code == 200:
            return r.json().get('status') == 'ok'
        return False
    except Exception as e:
        print(f"Error comprobando URL: {e}")
        return False

def obtener_servidor_gofile():
    try:
        resp_server = requests.get("https://api.gofile.io/servers", timeout=10).json()
        if resp_server.get('status') == 'ok':
            return resp_server['data']['servers'][0]['name']
    except Exception as e:
        print(f"Error obteniendo servidor GoFile: {e}")
    return None

def subir_archivo_gofile(server, file_path, folder_id=None):
    try:
        upload_url = f"https://{server}.gofile.io/contents/uploadfile"
        data = {}
        if folder_id:
            data['folderId'] = folder_id

        with open(file_path, 'rb') as f:
            resp = requests.post(upload_url, files={'file': f}, data=data, timeout=1200).json()

        if resp.get('status') == 'ok':
            return resp['data']
        else:
            print(f"Error respuesta GoFile: {resp}")
            return None
    except Exception as e:
        print(f"Error subiendo {file_path} a GoFile: {e}")
        return None

def main():
    if not os.path.exists('juegos.json'):
        return

    with open('juegos.json', 'r', encoding='utf-8') as f:
        juegos = json.load(f)

    cambios = False

    with TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN) as client:
        for juego in juegos:
            url_actual = juego.get('enlace_descarga', '')
            titulo = juego.get('titulo', 'Sin título')
            print(f"Verificando: {titulo}...")

            if not comprobar_enlace(url_actual):
                print(f"⚠️ Enlace caído o no existente para {titulo}. Resubiendo...")
                
                # Detectar si es un solo mensaje o una lista de partes
                raw_msg_ids = juego.get('telegram_message_id')
                if isinstance(raw_msg_ids, list):
                    msg_ids = [int(m) for m in raw_msg_ids]
                elif raw_msg_ids is not None:
                    msg_ids = [int(raw_msg_ids)]
                else:
                    print(f"❌ {titulo} no tiene telegram_message_id configurado.")
                    continue

                try:
                    chat_id = int(juego['telegram_channel_id'])
                    server = obtener_servidor_gofile()
                    if not server:
                        print("No se pudo obtener un servidor activo de GoFile.")
                        continue

                    folder_id = None
                    nuevo_enlace = None

                    for i, msg_id in enumerate(msg_ids, start=1):
                        print(f"  └─ Procesando parte {i}/{len(msg_ids)} (Mensaje ID: {msg_id})...")
                        message = client.get_messages(chat_id, ids=msg_id)
                        
                        if message:
                            temp_path = f"temp_{juego['id']}_part{i}.rar"
                            client.download_media(message, file=temp_path)
                            
                            # Subir la parte a GoFile (vinculándola a la misma carpeta)
                            upload_data = subir_archivo_gofile(server, temp_path, folder_id)

                            # Eliminar la parte del disco inmediatamente para liberar memoria
                            if os.path.exists(temp_path):
                                os.remove(temp_path)

                            if upload_data:
                                if not folder_id:
                                    folder_id = upload_data.get('parentFolder')
                                    nuevo_enlace = upload_data.get('downloadPage')
                            else:
                                print(f"❌ Falló la subida de la parte {i}. Abortando este juego.")
                                nuevo_enlace = None
                                break
                        else:
                            print(f"❌ No se encontró el mensaje ID {msg_id} en Telegram.")
                            nuevo_enlace = None
                            break

                    if nuevo_enlace:
                        juego['enlace_descarga'] = nuevo_enlace
                        cambios = True
                        print(f"✅ Juego resubido con éxito. Nueva carpeta: {nuevo_enlace}")

                except Exception as e:
                    print(f"❌ Error al procesar '{titulo}': {e}")

    if cambios:
        with open('juegos.json', 'w', encoding='utf-8') as f:
            json.dump(juegos, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
