import asyncio
import json
import os
import subprocess
import sys
import requests
from telethon import TelegramClient

# --- CONFIGURACIÓN Y VARIABLES DE ENTORNO ---
API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GOFILE_TOKEN = os.environ.get("GOFILE_API_TOKEN")

JSON_FILE = "juegos.json"


def guardar_progreso_y_push(data):
  """Guarda el progreso en juegos.json y realiza un git push inmediato a GitHub."""
  try:
    with open(JSON_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, ensure_ascii=False, indent=2)
    print("💾 'juegos.json' actualizado localmente.")

    subprocess.run(
        ["git", "config", "--global", "user.name", "github-actions[bot]"],
        check=False,
    )
    subprocess.run(
        [
            "git",
            "config",
            "--global",
            "user.email",
            "github-actions[bot]@users.noreply.github.com",
        ],
        check=False,
    )
    subprocess.run(["git", "add", JSON_FILE], check=False)

    commit_res = subprocess.run(
        [
            "git",
            "commit",
            "-m",
            "Auto: Guardado de parte completada en GoFile",
        ],
        capture_output=True,
        text=True,
    )

    if "nothing to commit" not in commit_res.stdout:
      subprocess.run(
          ["git", "pull", "origin", "main", "--rebase"], check=False
      )
      subprocess.run(["git", "push"], check=False)
      print("🚀 Progreso guardado y subido a GitHub exitosamente.")
    else:
      print("ℹ️ Sin cambios nuevos que commitear.")
  except Exception as e:
    print(f"⚠️ Error al realizar el push a GitHub: {e}")


def obtener_servidor_gofile():
  """Obtiene el servidor activo de GoFile."""
  try:
    resp = requests.get("https://api.gofile.io/servers").json()
    if resp.get("status") == "ok":
      servers = resp["data"]["servers"]
      if servers:
        return servers[0]["name"]
  except Exception as e:
    print(f"⚠️ Error al consultar servidores GoFile: {e}")
  return "store1"


def subir_a_gofile(filepath, folder_id=None):
  """Subo el archivo a GoFile.

  Si recibe folder_id, lo mete en esa misma carpeta.
  """
  server = obtener_servidor_gofile()
  url = f"https://{server}.gofile.io/contents/uploadfile"

  payload = {}
  if GOFILE_TOKEN:
    payload["token"] = GOFILE_TOKEN
  if folder_id:
    payload["folderId"] = folder_id

  print(
      f"📤 Subiendo '{filepath}' a GoFile (Servidor: {server}, CarpetalD:"
      f" {folder_id or 'Nueva'})..."
  )

  with open(filepath, "rb") as f:
    files = {"file": f}
    response = requests.post(url, files=files, data=payload, timeout=3600)

  res_json = response.json()
  if res_json.get("status") == "ok":
    data = res_json["data"]
    download_page = data.get("downloadPage")
    parent_folder = data.get("parentFolder") or data.get("folderId")
    return download_page, parent_folder
  else:
    raise Exception(f"GoFile devolvió error: {res_json}")


async def procesar_juego(client, juego, todos_los_juegos):
  titulo = juego.get("titulo") or juego.get("nombre") or "Juego"
  channel_id_raw = juego.get("telegram_channel_id")
  msg_ids = juego.get("telegram_message_id")
  folder_id = juego.get("gofile_folder_id")

  if not channel_id_raw or not msg_ids:
    return

  channel_id = int(channel_id_raw)
  es_lista = isinstance(msg_ids, list)
  lista_msg_ids = list(msg_ids) if es_lista else [msg_ids]

  if not lista_msg_ids:
    print(f"✅ '{titulo}' ya no tiene partes pendientes.")
    return

  print(
      f"\n🎮 Procesando '{titulo}' - Partes pendientes:"
      f" {len(lista_msg_ids)}"
  )

  while lista_msg_ids:
    msg_id = lista_msg_ids[0]
    print(
        f"\n📥 Descargando mensaje ID {msg_id} de Telegram (Canal:"
        f" {channel_id})..."
    )

    archivo_local = None
    try:
      message = await client.get_messages(channel_id, ids=msg_id)
      if not message or not message.media:
        print(f"❌ Mensaje ID {msg_id} sin archivo adjunto. Omitiendo...")
        lista_msg_ids.pop(0)
        juego["telegram_message_id"] = lista_msg_ids if es_lista else None
        guardar_progreso_y_push(todos_los_juegos)
        continue

      def callback_progreso(downloaded, total):
        pct = (downloaded / total) * 100
        mb_down = downloaded / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        print(
            f"\r⬇️ Progreso descarga Telegram: {pct:.1f}% ({mb_down:.1f} /"
            f" {mb_total:.1f} MB)",
            end="",
        )

      archivo_local = await client.download_media(
          message, progress_callback=callback_progreso
      )
      print("\n✅ Descarga de Telegram finalizada.")

      # Subida a GoFile (usando folder_id si existe)
      download_page, parent_folder = subir_a_gofile(archivo_local, folder_id)

      # Guardar el enlace de la carpeta única
      if not juego.get("enlace_descarga"):
        juego["enlace_descarga"] = download_page
      if not juego.get("gofile_folder_id") and parent_folder:
        juego["gofile_folder_id"] = parent_folder
        folder_id = parent_folder

      # Eliminar el ID procesado
      lista_msg_ids.pop(0)
      juego["telegram_message_id"] = lista_msg_ids if es_lista else None

      print(
          f"✨ Parte subida con éxito. Enlace único de carpeta:"
          f" {juego['enlace_descarga']}"
      )

      # Commit y push a GitHub inmediatamente
      guardar_progreso_y_push(todos_los_juegos)

    except Exception as e:
      print(f"\n❌ Error durante el procesamiento de la parte {msg_id}: {e}")
      print("🛑 Proceso detenido para mantener a salvo las partes subidas.")
      break
    finally:
      # Eliminar archivo local para liberar los 2 GB inmediatamente
      if archivo_local and os.path.exists(archivo_local):
        os.remove(archivo_local)
        print(f"🗑️ Archivo local '{archivo_local}' eliminado.")


async def main():
  if not os.path.exists(JSON_FILE):
    print(f"❌ No se encontró el archivo {JSON_FILE}")
    sys.exit(1)

  with open(JSON_FILE, "r", encoding="utf-8") as f:
    juegos = json.load(f)

  # Cliente con configuración reforzada contra desconexiones de red
  client = TelegramClient(
      "sesion_bot",
      int(API_ID),
      API_HASH,
      request_retries=15,
      connection_retries=15,
      timeout=60,
  )

  await client.start(bot_token=BOT_TOKEN)
  print("🤖 Cliente de Telegram iniciado.")

  for juego in juegos:
    msg_ids = juego.get("telegram_message_id")
    tiene_pendientes = (
        bool(msg_ids) if isinstance(msg_ids, list) else (msg_ids is not None)
    )

    if tiene_pendientes:
      await procesar_juego(client, juego, juegos)

  await client.disconnect()
  print("\n🎉 Proceso completado con éxito.")


if __name__ == "__main__":
  asyncio.run(main())
   main()
