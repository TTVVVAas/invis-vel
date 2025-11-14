# ConfiguraÃ§Ãµes do Sistema de VigilÃ¢ncia IA RTSP
# Este arquivo contÃ©m todas as configuraÃ§Ãµes do sistema

import os
from dotenv import load_dotenv

# Carregar variÃ¡veis de ambiente do arquivo .env
load_dotenv()

# Obter chave secreta do ambiente ou usar padrÃ£o
SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'sua_chave_secreta_muito_segura_aqui')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# ConfiguraÃ§Ãµes da CÃ¢mera RTSP (defaults globais)
CAMERA_DEFAULTS = {
    'reconnect_attempts': 5,
    'reconnect_delay': 2,
    'frame_rate': 30,
    'buffer_size': 4096,
    'frame_failure_timeout': 5
}

# ConfiguraÃ§Ãµes de DetecÃ§Ã£o de Movimento
MOTION_DETECTION = {
    'enabled': True,
    'min_area': 500,  # Ã¡rea mÃ­nima em pixels para considerar movimento
    'history': 500,   # histÃ³rico do MOG2
    'var_threshold': 16,  # limiar de variaÃ§Ã£o
    'detect_shadows': True
}

# ConfiguraÃ§Ãµes do YOLOv8
YOLO = {
    'model': 'yolov8n.pt',  # modelo leve para CPU
    'confidence': 0.5,      # limiar de confianÃ§a
    'classes': [0],         # classe 0 = pessoa
    'detection_cooldown': 2  # segundos entre detecÃ§Ãµes
}

# ConfiguraÃ§Ãµes do Sistema
SYSTEM = {
    'host': '0.0.0.0',
    'port': 5000,
    'debug': False,
    'secret_key': 'sua_chave_secreta_muito_segura_aqui',
    'max_alerts': 100,  # nÃºmero mÃ¡ximo de alertas para manter
    'alert_retention_days': 7
}

# ConfiguraÃ§Ãµes de SeguranÃ§a
SECURITY = {
    'username': 'admin',
    'password_hash': None,  # serÃ¡ gerado automaticamente
    'session_timeout': 3600,  # segundos (1 hora)
    'max_login_attempts': 5,
    'lockout_duration': 300,  # segundos (5 minutos)
    'secret_key': SECRET_KEY  # usar do ambiente
}

# ConfiguraÃ§Ãµes de Alertas (Telegram - Opcional)
TELEGRAM = {
    'enabled': False,
    'bot_token': TELEGRAM_BOT_TOKEN,  # do ambiente
    'chat_id': TELEGRAM_CHAT_ID,      # do ambiente
    'send_screenshot': True,
    'message_template': 'ðŸš¨ PESSOA DETECTADA!\nðŸ“ Local: {location}\nðŸ• HorÃ¡rio: {timestamp}\nðŸ“· Screenshot anexada'
}

# ConfiguraÃ§Ãµes de GravaÃ§Ã£o
RECORDING = {
    'enabled': False,
    'record_on_person_detection': True,
    'record_duration': 30,  # segundos
    'video_codec': 'mp4v',
    'fps': 20,
    'resolution': (640, 480),
    'storage_path': 'recordings/',
    'max_storage_gb': 10
}

# ConfiguraÃ§Ãµes de IP (Whitelist - Opcional)
IP_WHITELIST = {
    'enabled': False,
    'allowed_ips': [
        '192.168.1.0/24',  # rede local
        '127.0.0.1',       # localhost
        # Adicione mais IPs conforme necessÃ¡rio
    ]
}

# ConfiguraÃ§Ãµes de HorÃ¡rio (Opcional)
SCHEDULE = {
    'enabled': False,
    'active_hours': {
        'start': '22:00',  # horÃ¡rio de inÃ­cio
        'end': '06:00'     # horÃ¡rio de tÃ©rmino
    },
    'days_of_week': [0, 1, 2, 3, 4, 5, 6],  # 0=domingo, 6=sÃ¡bado
}

# ConfiguraÃ§Ãµes de Logging
LOGGING = {
    'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    'file': 'system.log',
    'max_size_mb': 100,
    'backup_count': 5
}

# ConfiguraÃ§Ãµes de Performance
def _get_float_env(var_name, default):
    value = os.getenv(var_name)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


PERFORMANCE = {
    'process_interval': _get_float_env('PROCESS_INTERVAL', 0.5),
    'detection_resize': int(os.getenv('DETECTION_RESIZE', 640)),
    'detect_on_motion_only': True,
    'use_gpu': os.getenv('YOLO_USE_GPU', 'false').lower() in {'1', 'true', 'yes'}
}

