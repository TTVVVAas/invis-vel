import cv2
import numpy as np
import json
import yaml
import os
from datetime import datetime
from flask import Flask, render_template, Response, request, jsonify, redirect, url_for, session, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
import cv2
import threading
import time
import os
import json
import logging
from logging.handlers import RotatingFileHandler
import yaml
from werkzeug.security import generate_password_hash, check_password_hash
from ultralytics import YOLO
from alerts import get_alert_manager
from recording_utils import (
    get_recordings_base_path, get_recording_path_for_date,
    ensure_recording_directory_exists, generate_recording_filename,
    get_all_recordings, get_recordings_by_year_month, get_recordings_by_date,
    format_file_size, parse_recording_filename
)

app = Flask(__name__)
from config import *
app.secret_key = SECRET_KEY

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

users = {
    'admin': User('1', 'admin', generate_password_hash('admin123'))
}

@login_manager.user_loader
def load_user(user_id):
    for user in users.values():
        if user.id == user_id:
            return user
    return None

class CameraStream:
    def __init__(self, rtsp_url=None):
        self.rtsp_url = rtsp_url or 'rtsp://usuario:senha@ip_da_camera:554/stream'
        self.cap = None
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)
        self.motion_detected = False
        self.person_detected = False
        self.last_detection_time = 0
        self.detection_cooldown = 2  # segundos
        
        try:
            self.yolo_model = YOLO('yolov8n.pt')
            logger.info("YOLOv8 carregado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao carregar YOLOv8: {e}")
            self.yolo_model = None
        
        self.start_stream()
    
    def start_stream(self):
        if self.cap is None or not self.cap.isOpened():
            try:
                self.cap = cv2.VideoCapture(self.rtsp_url)
                if self.cap.isOpened():
                    logger.info("Conexão RTSP estabelecida com sucesso")
                    self.running = True
                    threading.Thread(target=self.update_frame, daemon=True).start()
                else:
                    logger.error("Falha ao conectar com a câmera RTSP")
            except Exception as e:
                logger.error(f"Erro ao iniciar stream: {e}")
    
    def update_frame(self):
        while self.running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = self.process_frame(frame)
                else:
                    logger.warning("Frame não recebido, tentando reconectar...")
                    self.reconnect()
            else:
                self.reconnect()
            time.sleep(0.033)  # ~30 FPS
    
    def reconnect(self):
        try:
            if self.cap:
                self.cap.release()
            time.sleep(2)
            self.cap = cv2.VideoCapture(self.rtsp_url)
            if self.cap.isOpened():
                logger.info("Reconexão bem-sucedida")
            else:
                logger.error("Falha na reconexão")
        except Exception as e:
            logger.error(f"Erro ao reconectar: {e}")
    
    def process_frame(self, frame):
        current_time = time.time()
        
        # Detecção de movimento
        fg_mask = self.background_subtractor.apply(frame)
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        motion_detected_now = False
        person_detected_now = False
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:  # Área mínima para considerar movimento
                motion_detected_now = True
                
                # Detecção de pessoa com YOLOv8
                if self.yolo_model and (current_time - self.last_detection_time) > self.detection_cooldown:
                    try:
                        results = self.yolo_model(frame, conf=0.5, classes=[0])  # Classe 0 = pessoa
                        if len(results[0].boxes) > 0:
                            person_detected_now = True
                            self.last_detection_time = current_time
                            
                            # Desenhar caixas delimitadoras
                            for box in results[0].boxes:
                                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                                cv2.putText(frame, 'Pessoa', (int(x1), int(y1)-10), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                            
                            # Salvar imagem de alerta
                            self.save_alert_image(frame)
                            break
                    except Exception as e:
                        logger.error(f"Erro na detecção YOLO: {e}")
        
        self.motion_detected = motion_detected_now
        self.person_detected = person_detected_now
        
        # Adicionar informações na tela
        status_text = "Status: "
        if self.person_detected:
            status_text += "PESSOA DETECTADA"
            color = (0, 0, 255)
        elif self.motion_detected:
            status_text += "MOVIMENTO DETECTADO"
            color = (0, 255, 255)
        else:
            status_text += "MONITORANDO"
            color = (0, 255, 0)
        
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.putText(frame, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Enviar frame para gravação se estiver ativada
        alert_manager = get_alert_manager()
        alert_manager.recorder.write_frame(frame)
        
        return frame
    
    def save_alert_image(self, frame):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"alerts/alerta_{timestamp}.jpg"
            cv2.imwrite(filename, frame)
            logger.info(f"Imagem de alerta salva: {filename}")
            
            # Disparar alerta completo
            alert_manager = get_alert_manager()
            alert_manager.trigger_alert(frame, "person", "Câmera Principal")
            
        except Exception as e:
            logger.error(f"Erro ao salvar imagem de alerta: {e}")
    
    def get_frame(self):
        with self.lock:
            if self.frame is not None:
                _, buffer = cv2.imencode('.jpg', self.frame)
                return buffer.tobytes()
        return None
    
    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()

# Inicializar câmera (configurar URL RTSP aqui)
camera = CameraStream('rtsp://usuario:senha@ip_da_camera:554/stream')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = users.get(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Credenciais inválidas')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

def generate_frames():
    while True:
        frame = camera.get_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.1)

@app.route('/video_feed')
@login_required
def video_feed():
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
@login_required
def status():
    alert_manager = get_alert_manager()
    alert_stats = alert_manager.get_alert_stats()
    
    return jsonify({
        'motion_detected': camera.motion_detected,
        'person_detected': camera.person_detected,
        'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        'alert_stats': alert_stats
    })

@app.route('/alerts')
@login_required
def view_alerts():
    """Exibir alertas salvos"""
    alerts_dir = 'alerts'
    alerts = []
    
    try:
        if os.path.exists(alerts_dir):
            for filename in sorted(os.listdir(alerts_dir), reverse=True):
                if filename.endswith('.jpg'):
                    filepath = os.path.join(alerts_dir, filename)
                    stat = os.stat(filepath)
                    
                    # Extrair data/hora do nome do arquivo
                    try:
                        # Formato: alerta_YYYYMMDD_HHMMSS.jpg
                        parts = filename.replace('alerta_', '').replace('.jpg', '').split('_')
                        date_str = parts[0]
                        time_str = parts[1]
                        
                        date_formatted = f"{date_str[6:8]}/{date_str[4:6]}/{date_str[0:4]}"
                        time_formatted = f"{time_str[0:2]}:{time_str[2:4]}:{time_str[4:6]}"
                        
                        alerts.append({
                            'filename': filename,
                            'date': date_formatted,
                            'time': time_formatted,
                            'size': f"{stat.st_size / 1024:.1f} KB"
                        })
                    except:
                        alerts.append({
                            'filename': filename,
                            'date': 'Desconhecida',
                            'time': 'Desconhecida',
                            'size': f"{stat.st_size / 1024:.1f} KB"
                        })
    except Exception as e:
        logger.error(f"Erro ao listar alertas: {e}")
    
    return render_template('alerts.html', alerts=alerts[:50])  # Limitar a 50 alertas

@app.route('/alerts/<filename>')
@login_required
def serve_alert_image(filename):
    """Servir imagem de alerta"""
    try:
        # Validar nome do arquivo para segurança
        if not filename.startswith('alerta_') or not filename.endswith('.jpg'):
            return "Arquivo inválido", 400
        
        filepath = os.path.join('alerts', filename)
        if os.path.exists(filepath):
            return send_file(filepath, mimetype='image/jpeg')
        else:
            return "Imagem não encontrada", 404
    except Exception as e:
        logger.error(f"Erro ao servir imagem de alerta: {e}")
        return "Erro ao acessar imagem", 500

@app.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    if request.method == 'POST':
        new_url = request.form.get('rtsp_url')
        if new_url:
            camera.rtsp_url = new_url
            camera.stop()
            camera.start_stream()
            return jsonify({'status': 'success', 'message': 'Configuração atualizada'})
    
    return jsonify({'rtsp_url': camera.rtsp_url})

# ===== ROTAS DE CONFIGURAÇÕES =====
@app.route('/settings')
@login_required
def settings():
    """Painel de configurações do sistema"""
    return render_template('settings.html', config=get_config_data())

@app.route('/api/config', methods=['GET'])
@login_required
def get_config():
    """API: Obter configurações atuais"""
    return jsonify(get_config_data())

@app.route('/api/config', methods=['POST'])
@login_required
def update_config():
    """API: Atualizar configurações"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dados inválidos'}), 400
        
        # Atualizar configurações (simplificado - apenas algumas chaves)
        if 'camera' in data:
            CAMERA.update(data['camera'])
        if 'motion_detection' in data:
            MOTION_DETECTION.update(data['motion_detection'])
        if 'yolo' in data:
            YOLO.update(data['yolo'])
        if 'telegram' in data:
            TELEGRAM.update(data['telegram'])
        if 'recording' in data:
            RECORDING.update(data['recording'])
        
        return jsonify({'status': 'success', 'message': 'Configurações atualizadas'})
    except Exception as e:
        logger.error(f"Erro ao atualizar configurações: {e}")
        return jsonify({'error': 'Erro ao atualizar configurações'}), 500

@app.route('/api/config/export/<format>')
@login_required
def export_config(format):
    """Exportar configurações em JSON ou YAML"""
    try:
        config_data = get_config_data()
        
        if format == 'json':
            return Response(
                json.dumps(config_data, indent=2, ensure_ascii=False),
                mimetype='application/json',
                headers={'Content-Disposition': 'attachment; filename=config.json'}
            )
        elif format == 'yaml':
            return Response(
                yaml.dump(config_data, allow_unicode=True, default_flow_style=False),
                mimetype='text/yaml',
                headers={'Content-Disposition': 'attachment; filename=config.yaml'}
            )
        else:
            return jsonify({'error': 'Formato não suportado'}), 400
    except Exception as e:
        logger.error(f"Erro ao exportar configurações: {e}")
        return jsonify({'error': 'Erro ao exportar configurações'}), 500

@app.route('/api/config/import', methods=['POST'])
@login_required
def import_config():
    """Importar configurações de JSON ou YAML"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        # Ler arquivo
        content = file.read().decode('utf-8')
        
        # Detectar formato e processar
        if file.filename.endswith('.json'):
            config_data = json.loads(content)
        elif file.filename.endswith(('.yaml', '.yml')):
            config_data = yaml.safe_load(content)
        else:
            return jsonify({'error': 'Formato de arquivo não suportado'}), 400
        
        # Aplicar configurações (com validação básica)
        if isinstance(config_data, dict):
            # Atualizar configurações globais (exemplo simplificado)
            if 'camera' in config_data:
                CAMERA.update(config_data['camera'])
            # Adicionar mais atualizações conforme necessário
            
            return jsonify({'status': 'success', 'message': 'Configurações importadas com sucesso'})
        else:
            return jsonify({'error': 'Formato de configuração inválido'}), 400
            
    except json.JSONDecodeError:
        return jsonify({'error': 'Arquivo JSON inválido'}), 400
    except yaml.YAMLError:
        return jsonify({'error': 'Arquivo YAML inválido'}), 400
    except Exception as e:
        logger.error(f"Erro ao importar configurações: {e}")
        return jsonify({'error': 'Erro ao importar configurações'}), 500

# ===== API REST PARA DADOS =====
@app.route('/api/alerts')
@login_required
def api_alerts():
    """API: Listar alertas"""
    try:
        alerts_dir = 'alerts'
        alerts = []
        
        if os.path.exists(alerts_dir):
            for filename in sorted(os.listdir(alerts_dir), reverse=True):
                if filename.endswith('.jpg'):
                    filepath = os.path.join(alerts_dir, filename)
                    stat = os.stat(filepath)
                    
                    # Extrair data/hora do nome do arquivo
                    try:
                        parts = filename.replace('alerta_', '').replace('.jpg', '').split('_')
                        if len(parts) >= 2:
                            date_str = parts[0]
                            time_str = parts[1]
                            
                            alerts.append({
                                'filename': filename,
                                'date': f"{date_str[6:8]}/{date_str[4:6]}/{date_str[0:4]}",
                                'time': f"{time_str[0:2]}:{time_str[2:4]}:{time_str[4:6]}",
                                'size': stat.st_size,
                                'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                                'url': url_for('serve_alert_image', filename=filename)
                            })
                    except:
                        alerts.append({
                            'filename': filename,
                            'date': 'Desconhecida',
                            'time': 'Desconhecida',
                            'size': stat.st_size,
                            'size_formatted': f"{stat.st_size / 1024:.1f} KB",
                            'url': url_for('serve_alert_image', filename=filename)
                        })
        
        return jsonify({
            'total': len(alerts),
            'alerts': alerts[:50]  # Limitar a 50 alertas
        })
    except Exception as e:
        logger.error(f"Erro ao obter alertas via API: {e}")
        return jsonify({'error': 'Erro ao obter alertas'}), 500

@app.route('/api/recordings')
@login_required
def api_recordings():
    """API: Listar gravações"""
    try:
        # Obter parâmetros opcionais de data
        year = request.args.get('year')
        month = request.args.get('month')
        day = request.args.get('day')
        
        if year and month and day:
            # Listar vídeos de um dia específico
            recordings = get_recordings_by_date(year, month, day)
        elif year and month:
            # Listar dias disponíveis em um mês
            recordings = get_recordings_by_year_month(year, month)
        elif year:
            # Listar meses disponíveis em um ano
            recordings = get_recordings_by_year(year)
        else:
            # Listar todos os vídeos organizados por data
            recordings = get_all_recordings()
        
        return jsonify(recordings)
    
    except Exception as e:
        logger.error(f"Erro ao listar gravações: {e}")
        return jsonify([])

def get_recordings_by_year(year):
    """Obter lista de meses com gravações em um ano"""
    recordings = []
    base_path = get_recordings_base_path()
    year_path = os.path.join(base_path, year)
    
    if os.path.exists(year_path):
        for month in sorted(os.listdir(year_path)):
            month_path = os.path.join(year_path, month)
            if os.path.isdir(month_path):
                # Contar quantos vídeos existem neste mês
                video_count = 0
                for day in os.listdir(month_path):
                    day_path = os.path.join(month_path, day)
                    if os.path.isdir(day_path):
                        video_count += len([f for f in os.listdir(day_path) if f.endswith('.mp4')])
                
                if video_count > 0:
                    recordings.append({
                        'type': 'month',
                        'year': year,
                        'month': month,
                        'video_count': video_count,
                        'path': f"{year}/{month}"
                    })
    
    return recordings

def get_recordings_by_year_month(year, month):
    """Obter lista de dias com gravações em um mês específico"""
    recordings = []
    base_path = get_recordings_base_path()
    month_path = os.path.join(base_path, year, month)
    
    if os.path.exists(month_path):
        for day in sorted(os.listdir(month_path)):
            day_path = os.path.join(month_path, day)
            if os.path.isdir(day_path):
                video_files = [f for f in os.listdir(day_path) if f.endswith('.mp4')]
                if video_files:
                    recordings.append({
                        'type': 'day',
                        'year': year,
                        'month': month,
                        'day': day,
                        'video_count': len(video_files),
                        'path': f"{year}/{month}/{day}"
                    })
    
    return recordings

@app.route('/api/recordings/download/<path:filepath>')
@login_required
def download_recording(filepath):
    """Fazer download de um vídeo específico"""
    try:
        # Construir caminho completo
        base_path = get_recordings_base_path()
        full_path = os.path.join(base_path, filepath)
        
        # Verificar se o arquivo existe
        if not os.path.exists(full_path):
            return jsonify({'error': 'Arquivo não encontrado'}), 404
        
        # Verificar se é um arquivo .mp4
        if not filepath.endswith('.mp4'):
            return jsonify({'error': 'Tipo de arquivo inválido'}), 400
        
        # Verificar se o caminho está dentro da pasta de gravações
        real_base = os.path.realpath(base_path)
        real_file = os.path.realpath(full_path)
        if not real_file.startswith(real_base):
            return jsonify({'error': 'Acesso não autorizado'}), 403
        
        # Enviar arquivo
        return send_file(full_path, as_attachment=True, download_name=os.path.basename(filepath))
    
    except Exception as e:
        logger.error(f"Erro ao fazer download da gravação: {e}")
        return jsonify({'error': 'Erro ao fazer download'}), 500

@app.route('/api/system/status')
@login_required
def api_system_status():
    """API: Status completo do sistema"""
    try:
        alert_manager = get_alert_manager()
        alert_stats = alert_manager.get_alert_stats()
        
        # Informações do sistema
        import psutil
        
        system_info = {
            'camera': {
                'connected': camera.connected if hasattr(camera, 'connected') else False,
                'rtsp_url': camera.rtsp_url if hasattr(camera, 'rtsp_url') else 'N/A'
            },
            'detection': {
                'motion_enabled': MOTION_DETECTION['enabled'],
                'yolo_enabled': True,  # Sempre ativo se o modelo estiver carregado
                'confidence': YOLO['confidence']
            },
            'alerts': alert_stats,
            'system': {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_free': psutil.disk_usage('.').free // (1024**3),  # GB
                'uptime': time.time() - start_time if 'start_time' in globals() else 0
            },
            'config': {
                'telegram_enabled': TELEGRAM['enabled'],
                'recording_enabled': RECORDING['enabled']
            }
        }
        
        return jsonify(system_info)
    except Exception as e:
        logger.error(f"Erro ao obter status do sistema: {e}")
        return jsonify({'error': 'Erro ao obter status do sistema'}), 500

# Função auxiliar para obter dados de configuração
def get_config_data():
    """Obter configurações atuais para exibição"""
    return {
        'camera': CAMERA,
        'motion_detection': MOTION_DETECTION,
        'yolo': YOLO,
        'system': SYSTEM,
        'security': SECURITY,
        'telegram': TELEGRAM,
        'recording': RECORDING,
        'ip_whitelist': IP_WHITELIST,
        'schedule': SCHEDULE,
        'logging': LOGGING,
        'performance': PERFORMANCE
    }

if __name__ == '__main__':
    # Criar diretórios necessários
    os.makedirs('alerts', exist_ok=True)
    os.makedirs('recordings', exist_ok=True)
    
    # Baixar modelo YOLOv8 se não existir
    if not os.path.exists('yolov8n.pt'):
        logger.info("Baixando modelo YOLOv8n...")
        try:
            model = YOLO('yolov8n.pt')
            logger.info("Modelo YOLOv8n baixado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao baixar modelo YOLOv8: {e}")
    
    logger.info("Iniciando servidor Flask...")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)