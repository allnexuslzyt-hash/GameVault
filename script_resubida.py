importar os
importar json
solicitudes importantes
desde teletón.sync importar Cliente de Telegram

API_ID = int(os.environ.get('TELEGRAM_API_ID', 0))
API_HASH = sistema operativo.environ.get('TELEGRAM_API_HASH', '')
BOT_TOKEN = sistema operativo.environ.get('TELEGRAM_BOT_TOKEN', '')

def compromiso_enlace(url):
    si no hay URL o "gofile.io" no en url:
        retorno Falso
    intentar:
        content_id = url.dividir('/')[-1]
        api_url = f"https://api.gofile.io/contents/{contenido_id}"
        r = solicitudes.get(api_url, tiempo de espera=10)
        si r.código_estado == 200:
            retorno r.json().get('estado') == 'esta bien'
        retorno Falso
    excepto Excelencia como e:
        imprimir(f"Error comprando URL: {e}")
        retorno Falso

def resubir_a_gofile(ruta_archivo):
    intentar:
        resp_server = solicitudes.get("https://api.gofile.io/servers", tiempo de espera=10).json()
        si resp_servidor.get('estado') != 'esta bien':
            retorno Ninguno
        servidor = resp_server['datos']['servidores'][0]['nombre']
        
        con abierto(ruta_archivo, 'rb') como f:
            upload_url = f"https://{servidor}.gofile.io/contents/uploadfile"
            resp = solicitudes.post(upload_url, archivos={'archivo': f}, tiempo de espera=600).json()
            
        si resp.get('estado') == 'esta bien':
            retorno resp['datos']['descargarPágina']
        retorno Ninguno
    excepto Excelencia como e:
        imprimir(f"Error subiendo a GoFile: {e}")
        retorno Ninguno

def principal():
    si no os.camino.existir('juegos.json'):
        retorno

    con abierto('juegos.json', 'r', codificación='utf-8') como f:
        juegos = json.load(f)

    cambios = Falso

    con Cliente de Telegrama('bot_sesión', API_ID, API_HASH).comer(bot_token=BOT_TOKEN) como cliente:
        para juego en juegos:
            url_actual = juego.get('enlace_descarga', '')
            imprimir(f"Verificando: {juego['típulo']}...")

            si no compromiso_enlace(url_actual):
                imprimir(f"⚠️ Enlace hecho o no existente para {juego['típulo']}. Resubiendo...")
                intentar:
                    chat_id = int(juego['id_canal_telegrama'])
                    msg_id = int(juego['id_mensaje_telegrama'])
                    mensaje = cliente.obtener_mensajes(id_chat, ids=id_msg)
                    
                    si mensaje:
                        temp_path = f"temp_{juego['id']}.rar"
                        cliente.descargar_media(mensaje, archivo=temp_path)
                        nuevo_enlace = resubir_a_gofile(temp_ruta)

                        si os.camino.existir(temp_ruta):
                            os.eliminatorio(temp_ruta)

                        si nuevo_enlace:
                            juego['enlace_descarga'] = nuevo_enlace
                            cambios = Verdaddero
                excepto Excelencia como e:
                    imprimir(f"Error en {juego['típulo']}: {e}")

    si cambios:
        con abierto('juegos.json', 'w', codificación='utf-8') como f:
            json.volcar(juegos, f, sangría=2, asegurar_ascii=Falso)

si __nombre__ == '__principal__':
    principal()
