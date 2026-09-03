import os
import json
import requests
import sys
from telethon.sync import TelegramClient

raw_api_id = os.environ.get('TELEGRAM_API_ID', '').strip()
API_HASH = os.environ.get('TELEGRAM_API_HASH', '').strip()
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()

if not raw_api_id or not API_HASH or not BOT_TOKEN:
    print("❌ ERROR: Faltan uno o más Secrets (TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN).")
    sys.exit(1)

try:
    API_ID = int(raw_api_id)
except ValueError:
    print(f"❌ ERROR: TELEGRAM_API_ID debe ser un número entero. Valor recibido: '{raw_api_id}'")
    sys.exit(1)

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

def resubir_a_gofile(file_path):
    try:
        resp_server = requests.get("https://api.gofile.io/servers", timeout=10).json()
        if resp_server.get('status') != 'ok':
            print("❌ GoFile no devolvió un servidor disponible.")
            return None
        server = resp_server['data']['servers'][0]['name']
        
        print(f"Subiendo archivo a GoFile (Servidor: {server})...")
        with open(file_path, 'rb') as f:
            upload_url = f"https://{server}.gofile.io/contents/uploadfile"
            resp = requests.post(upload_url, files={'file': f}, timeout=600).json()
            
        if resp.get('status') == 'ok':
            return resp['data']['downloadPage']
        print(f"❌ Error devuelto por GoFile: {resp}")
        return None
    except Exception as e:
        print(f"❌ Error en la subida a GoFile: {e}")
        return None

def main():
    if not os.path.exists('juegos.json'):
        print("❌ No se encontró el archivo juegos.json")
        sys.exit(1)

    with open('juegos.json', 'r', encoding='utf-8') as f:
        juegos = json.load(f)

    cambios = False

    try:
        with TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN) as client:
            for juego in juegos:
                url_actual = juego.get('enlace_descarga', '')
                print(f"🔍 Verificando: {juego['titulo']}...")

                if not comprobar_enlace(url_actual):
                    print(f"⚠️ Enlace caído o no existente para '{juego['titulo']}'. Descargando de Telegram...")
                    try:
                        chat_id = int(juego['telegram_channel_id'])
                        msg_id = int(juego['telegram_message_id'])
                        
                        entity = client.get_entity(chat_id)
                        message = client.get_messages(entity, ids=msg_id)
                        
                        if message and message.media:
                            temp_path = f"temp_{juego['id']}.rar"
                            print("⬇️ Descargando archivo desde Telegram...")
                            client.download_media(message, file=temp_path)
                            
                            nuevo_enlace = resubir_a_gofile(temp_path)

                            if os.path.exists(temp_path):
                                os.remove(temp_path)

                            if nuevo_enlace:
                                print(f"✅ ¡Resubido con éxito! Nuevo enlace: {nuevo_enlace}")
                                juego['enlace_descarga'] = nuevo_enlace
                                cambios = True
                            else:
                                print("❌ No se pudo obtener el nuevo enlace de GoFile.")
                        else:
                            print(f"❌ No se encontró el mensaje {msg_id} o no contiene un archivo multimedia.")
                    except Exception as e:
                        print(f"❌ Error al procesar '{juego['titulo']}': {e}")
    except Exception as e:
        print(f"❌ Error de conexión con Telegram: {e}")
        sys.exit(1)

    if cambios:
        with open('juegos.json', 'w', encoding='utf-8') as f:
            json.dump(juegos, f, indent=2, ensure_ascii=False)
        print("💾 Base de datos juegos.json actualizada.")

if __name__ == '__main__':
    main()
