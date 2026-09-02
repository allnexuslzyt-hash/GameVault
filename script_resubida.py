import os
import json
import requests
from telethon.sync import TelegramClient

API_ID = int(os.environ.get('TELEGRAM_API_ID', 0))
API_HASH = os.environ.get('TELEGRAM_API_HASH', '')

def comprobar_enlace(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=10)
        return r.status_code == 200
    except:
        return False

def resubir_a_gofile(file_path):
    try:
        server = requests.get("https://api.gofile.io/getServer").json()['data']['server']
        with open(file_path, 'rb') as f:
            resp = requests.post(f"https://{server}.gofile.io/uploadFile", files={'file': f}).json()
        return resp['data']['downloadPage']
    except Exception as e:
        print(f"Error subiendo a GoFile: {e}")
        return None

def main():
    if not os.path.exists('juegos.json'):
        return

    with open('juegos.json', 'r', encoding='utf-8') as f:
        juegos = json.load(f)

    cambios = False

    for juego in juegos:
        url_actual = juego.get('enlace_descarga', '')
        print(f"Verificando {juego['titulo']}...")

        if not comprobar_enlace(url_actual):
            print(f"⚠️ Enlace caído para {juego['titulo']}. Resubiendo...")
            
            with TelegramClient('bot_session', API_ID, API_HASH) as client:
                chat_id = int(juego['telegram_channel_id'])
                msg_id = int(juego['telegram_message_id'])
                message = client.get_messages(chat_id, ids=msg_id)
                
                temp_path = f"temp_{juego['id']}.7z"
                client.download_media(message, file=temp_path)

                nuevo_enlace = resubir_a_gofile(temp_path)

                if os.path.exists(temp_path):
                    os.remove(temp_path)

                if nuevo_enlace:
                    juego['enlace_descarga'] = nuevo_enlace
                    cambios = True

    if cambios:
        with open('juegos.json', 'w', encoding='utf-8') as f:
            json.dump(juegos, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
