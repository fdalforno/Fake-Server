from flask import Flask, request, jsonify, make_response, render_template,Response
import requests
import argparse
import logging
import json
from pprint import pformat
import uuid
import os

# Configura il logging
logging.basicConfig(level=logging.DEBUG)

def read_json_config(file_path):
    if not os.path.exists(file_path):
        logging.error(f"File '{file_path}' non trovato.")
        raise FileNotFoundError(f"File '{file_path}' non trovato.")

    with open(file_path, 'r') as file:
        config = json.load(file)
    logging.info(f"File '{file_path}' caricato correttamente.")
    return config

app = Flask(__name__)


def _send_fake_respone(response):
    content_type = response["type"]
    code = response["code"]
    file_name = response["file"]
    
    if not os.path.exists(file_name):
        logging.error(f"File '{file_name}' non trovato.")
        abort(404, description=f"File '{file_name}' non trovato.")
        
    with open(file_name, 'r') as file:
        file_content = file.read()


    return file_content,code,{'Content-Type': content_type}


def _send_relay_response(request):
    # ref. https://stackoverflow.com/a/36601467/248616
    try:
        res = requests.request(
            method          = request.method,
            url             = request.url.replace(request.host_url, f'{API_HOST}/'),
            headers         = {k:v for k,v in request.headers if k.lower() != 'host'}, # exclude 'host' header
            data            = request.get_data(),
            cookies         = request.cookies,
            allow_redirects = False,
        )
    except requests.exceptions.ConnectionError as conn_err:
        return jsonify({'error': 'Connection error occurred', 'message': str(conn_err)}), 500
    except requests.exceptions.Timeout as timeout_err:
        return jsonify({'error': 'Timeout error occurred', 'message': str(timeout_err)}), 500
    except requests.exceptions.RequestException as req_err:
        return jsonify({'error': 'An error occurred', 'message': str(req_err)}), 500

    #NOTE we here exclude all "hop-by-hop headers" defined by RFC 2616 section 13.5.1 ref. https://www.rfc-editor.org/rfc/rfc2616#section-13.5.1
    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection'] 
    headers          = [
        (k,v) for k,v in res.raw.headers.items()
        if k.lower() not in excluded_headers
    ]
   
    response = Response(res.content, res.status_code, headers)
    return response



@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def handle_request(path):

    raw_request = request.get_data()

    try:
        string_request = raw_request.decode('utf-8')
    except UnicodeDecodeError as unicode:
        logging.info(f"Per la chiamata {path} non sono riuscito a decodificare la raw_request")
        string_request = "UNDECODED"

    # Dump delle informazioni della richiesta
    request_data = {
        'url':request.url,
        'endpoint':request.endpoint,
        'cookies': request.cookies,
        'method': request.method,
        'path': path,
        'headers': dict(request.headers),
        'args': request.args.to_dict(),
        'form': request.form.to_dict(),
        'json': request.get_json(silent=True),
        'data': string_request,
        'files': {}
    }
  
     # Gestione dei file caricati
    for file_key in request.files:
        file = request.files[file_key]
        file_info = {
            'filename': file.filename,
            'content_type': file.content_type,
            'size': len(file.read())
        }
        file.seek(0)  # Reset del puntatore del file
        request_data['files'][file_key] = file_info


    if not os.path.exists(folder):
        os.makedirs(folder)

    unique_filename = f"{uuid.uuid4()}"
    file_path = os.path.join(folder, unique_filename)

    logging.info(f"Per la chiamata {path} creo il file {file_path}")

    # Scrivere i dati della richiesta su un file
    with open(f"{file_path}.json", 'w') as f:
        json.dump(request_data, f, indent=4)


    if path in config_data:
        response = config_data[path]
        logging.info(f"Per il path {path} creo una risposta fake {response}")
        resp = _send_fake_respone(response)
        print(resp)
        return resp
    else:
        if not path:
            return render_template('configure.html', config=config_data)
        else:
            logging.info(f"Path {path} non configurato restituisco la chiamata in relay dal server {API_HOST}")
            return _send_relay_response(request)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Start an fake server.')
    parser.add_argument('--port', type=int, default=8080, help='Port to run the server on')
    parser.add_argument('--config', type=str, default='config.json', help='Config file for fake response')
    parser.add_argument('--folder', type=str, default='dump', help='Dump folder')
    parser.add_argument('--debug', type=bool, default=False, help='Debug configuration')
    parser.add_argument('--relay', type=str, required=True, help='Destination server')
    args = parser.parse_args()

    config_data = read_json_config(args.config)
    folder = args.folder
    API_HOST = args.relay

    app.run(debug=args.debug,port=args.port)