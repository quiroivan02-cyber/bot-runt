from flask import Flask, render_template, jsonify, Response
from flask_socketio import SocketIO
import subprocess
import os
import sys
import threading
import csv
import io

import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'runt-bot-dev')
socketio = SocketIO(app, cors_allowed_origins="*")

bot_process = None
bot_running = False


def get_sheet():
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
    ]
    credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    sheet_name = os.getenv('SHEET_NAME', 'Consultas RUNT')
    creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open(sheet_name)
    return spreadsheet, spreadsheet.sheet1


def get_sheet_payload():
    spreadsheet, sheet = get_sheet()
    values = sheet.get_all_values()
    headers = values[0] if values else []
    rows = []

    for raw_row in values[1:]:
        if not any(cell.strip() for cell in raw_row):
            continue

        normalized = raw_row + [''] * max(0, len(headers) - len(raw_row))
        rows.append({
            header: normalized[index] if index < len(normalized) else ''
            for index, header in enumerate(headers)
        })

    processed_rows = [
        row for row in rows
        if any(str(row.get(header, '')).strip() for header in headers[2:])
    ]

    return {
        'sheet_name': os.getenv('SHEET_NAME', 'Consultas RUNT'),
        'spreadsheet_url': getattr(spreadsheet, 'url', ''),
        'columns': headers,
        'rows': rows,
        'summary': {
            'total': len(rows),
            'processed': len(processed_rows),
            'pending': max(len(rows) - len(processed_rows), 0),
            'soat_vigente': sum(1 for row in rows if str(row.get('soat_estado', '')).upper() == 'VIGENTE'),
            'rtm_vigente': sum(1 for row in rows if str(row.get('rtm_estado', '')).upper() == 'VIGENTE'),
        },
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ejecutar', methods=['POST'])
def ejecutar_bot():
    global bot_process, bot_running
    
    if bot_running:
        return jsonify({'error': 'Bot ya está ejecutándose'}), 400
    
    try:
        bot_running = True
        
        def run_bot():
            global bot_process, bot_running
            
            socketio.emit('log', {'mensaje': '🚀 Iniciando bot RUNT...', 'tipo': 'info'})
            
            bot_process = subprocess.Popen(
                [sys.executable, 'runt_automation.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env={
                    **os.environ,
                    'HEADLESS': os.getenv('HEADLESS', 'true'),
                }
            )
            
            for line in iter(bot_process.stdout.readline, ''):
                if line:
                    socketio.emit('log', {'mensaje': line.strip(), 'tipo': 'info'})
            
            exit_code = bot_process.wait()
            bot_running = False
            
            if exit_code == 0:
                socketio.emit('log', {'mensaje': '✅ Bot finalizado', 'tipo': 'success'})
            else:
                socketio.emit('log', {'mensaje': f'⚠️ Bot finalizó con código {exit_code}', 'tipo': 'warning'})
            socketio.emit('bot_finished')
        
        thread = threading.Thread(target=run_bot)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True})
        
    except Exception as e:
        bot_running = False
        socketio.emit('log', {'mensaje': f'❌ Error: {str(e)}', 'tipo': 'error'})
        return jsonify({'error': str(e)}), 500

@app.route('/detener', methods=['POST'])
def detener_bot():
    global bot_process, bot_running
    
    if bot_process and bot_running:
        bot_process.terminate()
        bot_running = False
        socketio.emit('log', {'mensaje': '🛑 Bot detenido', 'tipo': 'warning'})
        return jsonify({'success': True})
    
    return jsonify({'error': 'No hay bot ejecutándose'}), 400

@app.route('/estado')
def estado():
    sheet_ok = False
    rows_count = 0
    sheet_error = None

    try:
        payload = get_sheet_payload()
        sheet_ok = True
        rows_count = len(payload['rows'])
    except Exception as e:
        sheet_error = str(e)

    return jsonify({
        'ejecutando': bot_running,
        'resultados_disponibles': rows_count > 0,
        'sheet_ok': sheet_ok,
        'sheet_error': sheet_error,
        'registros': rows_count,
    })

@app.route('/descargar')
def descargar():
    try:
        payload = get_sheet_payload()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=payload['columns'])
    writer.writeheader()
    writer.writerows(payload['rows'])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=resultados_runt_google_sheet.csv'},
    )

@app.route('/resultados')
def ver_resultados():
    try:
        return jsonify(get_sheet_payload())
    except Exception as e:
        return jsonify({'error': str(e), 'rows': [], 'columns': [], 'summary': {}}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes', 'si', 'sí')
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)
