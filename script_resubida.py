importar os
principalimportar
importar solicitudes
desde teletón.sync importar Cliente de Telegram
desde teletón.sesiones importar Sesión de cadena

API_ID = int(os.environ.get('TELEGRAM_API_ID', 0))
API_HASH = sistema operativo.environ.get('TELEGRAM_API_HASH', '')
SESSION_STRING = os.environ.get('TELEGRAM_SESSION', '')

def compromiso_enlace(url):
    """Comprueba si el enlace de GoFile realmente contiene archivos."""
    si no url o "gofile.io" no en url:
        retorno Falso
    intentar:
        # Extraer el ID de la alfombra de la URL (ej: https://gofile.io/d/XYZ -> XYZ)
        content_id = url.dividir('/')[-1]
        api_url = f"https://api.gofile.io/contents/{contenido_id}"
        r = solicitudes.get(api_url, tiempo de espera=10)
        
        si r.código_estado == 200:
            datos = r.json()
            # Si el estado es 'ok', el enlace sigue activo
            retorno datos.get('estado') == 'está bien'
        retorno Falso
    excepto Excepción como e:
        imprimir(f"Error al comprar la URL {url}: {e}")
        retorno Falso

def resubir_a_gofile(ruta_archivo):
    """Obtiene servidor activo y sube el archivo a GoFile."""
    intentar:
        # Obtener servidor libre
        resp_server = solicitudes.get("https://api.gofile.io/servers", tiempo de espera=10).json()
        si resp_servidor.get('estado') != 'está bien':
            retorno Ninguno
        
        servidor = resp_server['datos']['servidores'][0]['nombre']
        
        # Subir archivo
        con abierto(ruta_archivo, 'rb') como f:
            upload_url = f"https://{servidor}.gofile.io/contents/uploadfile"
            resp = solicitudes.post(upload_url, archivos={'archivo': f}, tiempo de espera=300).json()
            
        si resp.get('estado') == 'está bien':
            retorno resp['datos']['descargarPágina']
        retorno Ninguno
    excepto Excepción como e:
        imprimir(f"Error subiendo a GoFile: {e}")
        retorno Ninguno

def principal():
    si no os.camino.existe('juegos.json'):
        imprimir("No se encontró el archivo juegos.json")
        retorno

    con abierto('juegos.json', 'r', codificación='utf-8') como f:
        juegos = json.load(f)

    cambios = Falso

    # Conectar un Telegram usando la StringSession
    con Cliente de Telegram(Sesión de cadena(CADENA_SESIÓN), API_ID, API_HASH) como cliente:
        para juego en juegos:
            url_actual = juego.get('enlace_descarga', '')
            imprimir(f"Verificando: {juego['título']}...")

            si no compromiso_enlace(url_actual):
                imprimir(f"⚠️ Enlace caído o no válido para {juego['título']}. Resubiendo desde Telegram...")
                
                intentar:
                    chat_id = int(juego['id_canal_telegrama'])
                    msg_id = int(juego['id_mensaje_telegrama'])
                    mensaje = cliente.obtener_mensajes(id_chat, ids=id_msg)
                    
                    si no mensaje:
                        imprimir(f"❌ No se encontró el mensaje ID {msg_id} en Telegrama.")
                        continuar

                    temp_path = f"temp_{juego['id']}.rar"
                    imprimir(f"Descargando de Telegram...")
                    cliente.descargar_media(mensaje, archivo=temp_path)

                    imprimir("Subiendo un GoFile...")
                    nuevo_enlace = resubir_a_gofile(temp_ruta)

                    si os.camino.existe(temp_ruta):
                        os.eliminar(temp_ruta)

                    si nuevo_enlace:
                        imprimir(f"✅ Nuevo enlace generado: {nuevo_enlace}")
                        juego['enlace_descarga'] = nuevo_enlace
                        cambios = Verdadero
                    else:
                        imprimir("❌ Falló la resubida a GoFile.")

                excepto Excepción como e:
                    imprimir(f"Error procesando {juego['título']}: {e}")

    si cambios:
        con abierto('juegos.json', 'w', codificación='utf-8') como f:
            json.volcar(juegos, f, sangría=2, asegurar_ascii=Falso)
        imprimir("💾 juegos.json actualizado correctamente.")
    else:
        imprimir("✨ Todos los enlaces están funcionando correctamente.")

si __nombre__ == '__principal__':
    principal()
