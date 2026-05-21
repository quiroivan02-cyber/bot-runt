from flask import Flask, render_template, jsonify, send_file
from flask_socketio import SocketIO
import subprocess
import os
import sys
import threading
import pandas as pd

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'runt-bot-dev')
socketio = SocketIO(app, cors_allowed_origins="*")

bot_process = None
bot_running = False

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
    return jsonify({
        'ejecutando': bot_running,
        'resultados_disponibles': os.path.exists('resultados_runt.csv')
    })

@app.route('/descargar')
def descargar():
    if os.path.exists('resultados_runt.csv'):
        return send_file('resultados_runt.csv', as_attachment=True)
    return jsonify({'error': 'No hay resultados'}), 404

@app.route('/resultados')
def ver_resultados():
    if os.path.exists('resultados_runt.csv'):
        df = pd.read_csv('resultados_runt.csv')
        return jsonify(df.to_dict('records'))
    return jsonify([])

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes', 'si', 'sí')
    socketio.run(app, host='0.0.0.0', port=port, debug=debug)
