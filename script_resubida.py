principal(principalimportar os
importar json
importar solicitudes
importar sys
desde teletón.sync importar Cliente de Telegram

raw_api_id = sistema operativo.environ.get('TELEGRAM_API_ID', '').tira()
API_HASH = sistema operativo.environ.get('TELEGRAM_API_HASH', '').tira()
BOT_TOKEN = sistema operativo.environ.get('TELEGRAM_BOT_TOKEN', '').tira()

si no raw_api_id o no API_HASH o no BOT_TOKEN:
    imprimir("❌ ERROR: Faltan uno o más Secretos (TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN).")
    sys.salida(1)

intentar:
    API_ID = int(raw_api_id)
excepto Error de valor:
    imprimir(f"❌ ERROR: TELEGRAM_API_ID debe ser un número entero. Valor recibido: '{raw_api_id}'")
    sys.salida(1)

def compromiso_enlace(url):
    si no url o "gofile.io" no en url:
        retorno Falso
    intentar:
        content_id = url.dividir('/')[-1]
        api_url = f"https://api.gofile.io/contents/{contenido_id}"
        r = solicitudes.get(api_url, tiempo de espera=10)
        si r.código_estado == 200:
            retorno r.json().get('estado') == 'está bien'
        retorno Falso
    excepto Excepción como e:
        imprimir(f"Error comprando URL: {e}")
        retorno Falso

def resubir_a_gofile(ruta_archivo):
    intentar:
        resp_server = solicitudes.get("https://api.gofile.io/servers", tiempo de espera=10).json()
        si resp_servidor.get('estado') != 'está bien':
            imprimir("❌ GoFile no desarrolló un servidor disponible.")
            retorno Ninguno
        servidor = resp_server['datos']['servidores'][0]['nombre']
        
        imprimir(f"Subiendo archivo a GoFile (Servidor: {servidor})...")
        con abierto(ruta_archivo, 'rb') como f:
            upload_url = f"https://{servidor}.gofile.io/contents/uploadfile"
            resp = solicitudes.post(upload_url, archivos={'archivo': f}, tiempo de espera=600).json()
            
        si resp.get('estado') == 'está bien':
            retorno resp['datos']['descargarPágina']
        imprimir(f"❌ Error devuelo por GoFile: {resp}")
        retorno Ninguno
    excepto Excepción como e:
        imprimir(f"❌ Error en la subida a GoFile: {e}")
        retorno Ninguno

def principal():
    si no os.camino.existe('juegos.json'):
        imprimir("❌ No se encontró el archivo juegos.json")
        sys.salida(1)

    con abierto('juegos.json', 'r', codificación='utf-8') como f:
        juegos = json.load(f)

    cambios = Falso

    intentar:
        con Cliente de Telegram('bot_sesión', API_ID, API_HASH).comenzar(bot_token=BOT_TOKEN) como cliente:
            para juego en juegos:
                url_actual = juego.get('enlace_descarga', '')
                imprimir(f"🔍 Verificando: {juego['título']}...")

                si no compromiso_enlace(url_actual):
                    imprimir(f"⚠️ Enlace hecho o no existente para '{juego['título']}'. Descargando de Telegram...")
                    intentar:
                        chat_id = int(juego['id_canal_telegrama'])
                        msg_id = int(juego['id_mensaje_telegrama'])
                        
                        entidad = cliente.obtener_entidad(chat_id)
                        mensaje = cliente.obtener_mensajes(entidad, ids=msg_id)
                        
                        si mensaje y mensaje.medios:
                            temp_path = f"temp_{juego['id']}.rar"
                            imprimir("⬇️ Descargando archivo desde Telegram...")
                            cliente.descargar_media(mensaje, archivo=temp_path)
                            
                            nuevo_enlace = resubir_a_gofile(temp_ruta)

                            si os.camino.existe(temp_ruta):
                                os.eliminar(temp_ruta)

                            si nuevo_enlace:
                                imprimir(f"✅ ¡Resubido con Éxito! Nuevo enlace: {nuevo_enlace}")
                                juego['enlace_descarga'] = nuevo_enlace
                                cambios = Verdadero
                            else:
                                imprimir("❌ No se puede obtener el nuevo enlace de GoFile.")
                        else:
                            imprimir(f"❌ No se encontró el mensaje {msg_id} o no contiene un archivo multimedia.")
                    excepto Excepción como e:
                        imprimir(f"❌ Error al procesar '{juego['título']}': {e}")
    excepto Excepción como e:
        imprimir(f"❌ Error de conexión con Telegram: {e}")
        sys.salida(1)

    si cambios:
        con abierto('juegos.json', 'w', codificación='utf-8') como f:
            json.volcar(juegos, f, sangría=2, asegurar_ascii=Falso)
        imprimir("💾 Base de datos juegos.json actualizada.")

si __nombre__ == '__principal__':
    principal()
