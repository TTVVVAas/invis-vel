import json
import logging
import os
import time
import yaml
from datetime import datetime
from flask import Flask, render_template, Response, request, jsonify, redirect, url_for, session, send_file, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from ultralytics import YOLO as YOLOModel

from alerts import get_alert_manager
from recording_utils import (
    get_recordings_base_path, get_recording_path_for_date,
    ensure_recording_directory_exists, generate_recording_filename,
    get_all_recordings, get_recordings_by_year_month, get_recordings_by_date,
    format_file_size, parse_recording_filename
)
app = Flask(__name__)
from config import *
from config_loader import (
    get_cameras as load_cameras_from_store,
    update_camera as persist_camera_update
)
app.secret_key = SECRET_KEY

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
start_time = time.time()

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

users = {}

def refresh_user_store(username=None, password_hash=None):
    """Atualiza o dicionário de usuários com base nas configurações atuais."""
    username = username or SECURITY.get('username', 'admin')
    stored_hash = password_hash or SECURITY.get('password_hash')

    if not stored_hash:
        # Garante um hash padrão caso não exista (senha de fábrica)
        stored_hash = generate_password_hash('admin123')
        SECURITY['password_hash'] = stored_hash

    users.clear()
    users[username] = User('1', username, stored_hash)

refresh_user_store()

@login_manager.user_loader
def load_user(user_id):
    for user in users.values():
        if user.id == user_id:
            return user
    return None


from camera_manager import CameraManager

# Inicializar cameras (configuracoes vindas de config.py)
camera_manager = CameraManager()

CONFIG_SECTIONS = {
    'camera_defaults': CAMERA_DEFAULTS,
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


def get_camera_entries():
    """Retorna uma lista padronizada das câmeras configuradas."""
    return load_cameras_from_store()


def sanitize_security_payload(payload):
    updates = {}
    username = payload.get('username')
    if username:
        updates['username'] = username

    session_timeout = payload.get('session_timeout')
    if session_timeout is not None:
        try:
            updates['session_timeout'] = int(session_timeout)
        except (TypeError, ValueError):
            return None, 'Tempo de sessão inválido'

    max_attempts = payload.get('max_login_attempts')
    if max_attempts is not None:
        try:
            updates['max_login_attempts'] = int(max_attempts)
        except (TypeError, ValueError):
            return None, 'Máximo de tentativas inválido'

    new_password = payload.get('new_password')
    confirm_password = payload.get('confirm_password')
    if new_password:
        if not confirm_password or new_password != confirm_password:
            return None, 'As senhas não conferem'
        updates['password_hash'] = generate_password_hash(new_password)

    return updates, None


def prepare_config_payload(data):
    processed = {}
    if not isinstance(data, dict):
        return processed, None

    for key in CONFIG_SECTIONS.keys():
        section = data.get(key)
        if isinstance(section, dict):
            processed[key] = section

    if 'security' in processed:
        updates, error = sanitize_security_payload(processed['security'])
        if error:
            return None, error
        if updates:
            processed['security'] = updates
        else:
            processed.pop('security', None)

    return processed, None


def apply_configuration_updates(payload):
    changed = set()
    for key, target in CONFIG_SECTIONS.items():
        section = payload.get(key)
        if isinstance(section, dict):
            target.update(section)
            changed.add(key)
    return changed


def handle_config_side_effects(changed_sections):
    if {'camera_defaults', 'motion_detection', 'yolo'} & changed_sections:
        camera_manager.apply_config()
    if {'recording', 'telegram'} & changed_sections:
        get_alert_manager().refresh_from_config()
    if 'security' in changed_sections:
        refresh_user_store()

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

@app.route('/camsmonteiro')
@app.route('/welcome')
def camsmonteiro_welcome():
    """Página de boas-vindas especial para camsmonteiro.ddns.net"""
    return render_template('camsmonteiro_welcome.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/recordings')
@login_required
def recordings():
    return render_template('recordings.html')

@app.route('/')
@login_required
def index():
    return render_template('index.html', cameras=get_camera_entries())


@app.route('/video_feed')
@login_required
def default_video_feed():
    camera_id = request.args.get('camera_id')
    stream = camera_manager.get_stream(camera_id) if camera_id else camera_manager.get_default_stream()
    if not stream:
        abort(404)
    return Response(stream.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video_feed/<camera_id>')
@login_required
def video_feed(camera_id):
    stream = camera_manager.get_stream(camera_id)
    if not stream:
        abort(404)
    return Response(stream.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
@login_required
def status():
    alert_manager = get_alert_manager()
    alert_stats = alert_manager.get_alert_stats()
    camera_statuses = camera_manager.get_all_statuses()
    camera_list = list(camera_statuses.values())

    def aggregate(field):
        return any(status.get(field) for status in camera_list)

    def sum_field(field):
        return sum(status.get(field, 0) for status in camera_list)

    ai_last_ts = 0
    for status in camera_list:
        ts = status.get('last_inference_ts') or 0
        if ts and ts > ai_last_ts:
            ai_last_ts = ts

    ai_last_timestamp = datetime.fromtimestamp(ai_last_ts).strftime("%d/%m/%Y %H:%M:%S") if ai_last_ts else None
    total_detections = sum(status.get('detection_count', 0) for status in camera_list)
    avg_fps = 0.0
    if camera_list:
        fps_sum = sum(float(status.get('frame_rate') or 0) for status in camera_list)
        avg_fps = round(fps_sum / len(camera_list), 2)

    return jsonify({
        'cameras': camera_list,
        'motion_detected': aggregate('motion_detected'),
        'person_detected': aggregate('person_detected'),
        'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        'alert_stats': alert_stats,
        'motion_count': sum_field('motion_events'),
        'person_count': sum_field('person_events'),
        'alert_count': alert_stats.get('total_alerts', 0),
        'camera_connected': all(status.get('connected') for status in camera_list) if camera_list else False,
        'is_recording': alert_stats.get('is_recording'),
        'ai_last_timestamp': ai_last_timestamp,
        'total_detections': total_detections,
        'avg_fps': avg_fps
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
        camera_id = request.form.get('camera_id')
        new_url = request.form.get('rtsp_url')
        if camera_id and new_url:
            updated = camera_manager.update_camera(camera_id, {'rtsp_url': new_url})
            if updated:
                return jsonify({'status': 'success', 'camera': updated})
        return jsonify({'error': 'Camera ou URL invalida'}), 400

    return jsonify({'cameras': get_camera_entries()})


@app.route('/api/cameras', methods=['GET'])
@login_required
def api_list_cameras():
    return jsonify({'cameras': get_camera_entries()})


@app.route('/api/cameras', methods=['POST'])
@login_required
def api_add_camera():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    rtsp_url = (data.get('rtsp_url') or data.get('rtsp') or '').strip()
    camera_id = (data.get('id') or data.get('camera_id') or '').strip() or None
    enabled = bool(data.get('enabled', True))

    if not name or not rtsp_url:
        return jsonify({'error': 'Nome e RTSP são obrigatórios'}), 400

    payload = {
        'id': camera_id,
        'name': name,
        'rtsp_url': rtsp_url,
        'enabled': enabled
    }
    try:
        new_camera = camera_manager.add_camera(payload)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    return jsonify({'status': 'success', 'camera': new_camera}), 201


@app.route('/api/cameras/<camera_id>', methods=['PUT'])
@login_required
def api_update_camera(camera_id):
    data = request.get_json() or {}
    payload = {}

    name = data.get('name')
    if name is not None:
        payload['name'] = name.strip()

    rtsp_url = data.get('rtsp_url') or data.get('rtsp')
    if rtsp_url is not None:
        payload['rtsp_url'] = rtsp_url.strip()

    if 'enabled' in data:
        payload['enabled'] = bool(data['enabled'])

    if not payload:
        return jsonify({'error': 'Nenhuma alteração fornecida'}), 400

    updated = camera_manager.update_camera(camera_id, payload)
    if not updated:
        return jsonify({'error': 'Câmera não encontrada'}), 404

    return jsonify({'status': 'success', 'camera': updated})


@app.route('/api/cameras/<camera_id>', methods=['DELETE'])
@login_required
def api_delete_camera(camera_id):
    success = camera_manager.delete_camera(camera_id)
    if not success:
        return jsonify({'error': 'Câmera não encontrada'}), 404
    return jsonify({'status': 'success'})
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
        data = request.get_json() or {}
        processed_payload, error = prepare_config_payload(data)
        if error:
            return jsonify({'error': error}), 400
        if not processed_payload:
            return jsonify({'error': 'Nenhuma configuração válida fornecida'}), 400

        changed_sections = apply_configuration_updates(processed_payload)
        handle_config_side_effects(changed_sections)

        return jsonify({
            'status': 'success',
            'updated_sections': sorted(changed_sections)
        })
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

        content = file.read().decode('utf-8')

        if file.filename.endswith('.json'):
            config_data = json.loads(content)
        elif file.filename.endswith(('.yaml', '.yml')):
            config_data = yaml.safe_load(content)
        else:
            return jsonify({'error': 'Formato de arquivo não suportado'}), 400

        if not isinstance(config_data, dict):
            return jsonify({'error': 'Formato de configuração inválido'}), 400

        processed_payload, error = prepare_config_payload(config_data)
        if error:
            return jsonify({'error': error}), 400
        if not processed_payload:
            return jsonify({'error': 'Nenhuma configuração válida encontrada no arquivo'}), 400

        changed_sections = apply_configuration_updates(processed_payload)
        handle_config_side_effects(changed_sections)

        return jsonify({
            'status': 'success',
            'updated_sections': sorted(changed_sections)
        })

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
        camera_statuses = camera_manager.get_all_statuses()
        
        # Informações do sistema
        import psutil
        total_motion = sum(status.get('motion_events', 0) for status in camera_statuses.values())
        total_person = sum(status.get('person_events', 0) for status in camera_statuses.values())
        
        system_info = {
            'cameras': list(camera_statuses.values()),
            'detection': {
                'motion_enabled': MOTION_DETECTION['enabled'],
                'yolo_enabled': any(status.get('yolo_active') for status in camera_statuses.values()),
                'confidence': YOLO['confidence']
            },
            'alerts': alert_stats,
            'system': {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_free': psutil.disk_usage('.').free // (1024**3),  # GB
                'uptime': time.time() - start_time if 'start_time' in globals() else 0
            },
            'counts': {
                'motion': total_motion,
                'person': total_person,
                'alerts': alert_stats.get('total_alerts', 0)
            },
            'config': {
                'telegram_enabled': TELEGRAM['enabled'],
                'recording_enabled': RECORDING['enabled'],
                'recording_active': alert_stats.get('is_recording', False)
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
        'camera_defaults': CAMERA_DEFAULTS,
        'cameras': get_camera_entries(),
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
            model = YOLOModel('yolov8n.pt')
            logger.info("Modelo YOLOv8n baixado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao baixar modelo YOLOv8: {e}")
    
    logger.info("Iniciando servidor Flask...")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)




