# Configurações do Sistema de Vigilância IA RTSP
# Este arquivo contém todas as configurações do sistema

import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Obter chave secreta do ambiente ou usar padrão
SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'sua_chave_secreta_muito_segura_aqui')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Configurações da Câmera RTSP
CAMERA = {
    'rtsp_url': 'rtsp://usuario:senha@ip_da_camera:554/stream',
    'reconnect_attempts': 5,
    'reconnect_delay': 2,  # segundos
    'frame_rate': 30,
    'buffer_size': 4096
}

# Configurações de Detecção de Movimento
MOTION_DETECTION = {
    'enabled': True,
    'min_area': 500,  # área mínima em pixels para considerar movimento
    'history': 500,   # histórico do MOG2
    'var_threshold': 16,  # limiar de variação
    'detect_shadows': True
}

# Configurações do YOLOv8
YOLO = {
    'model': 'yolov8n.pt',  # modelo leve para CPU
    'confidence': 0.5,      # limiar de confiança
    'classes': [0],         # classe 0 = pessoa
    'detection_cooldown': 2  # segundos entre detecções
}

# Configurações do Sistema
SYSTEM = {
    'host': '0.0.0.0',
    'port': 5000,
    'debug': False,
    'secret_key': 'sua_chave_secreta_muito_segura_aqui',
    'max_alerts': 100,  # número máximo de alertas para manter
    'alert_retention_days': 7
}

# Configurações de Segurança
SECURITY = {
    'username': 'admin',
    'password_hash': None,  # será gerado automaticamente
    'session_timeout': 3600,  # segundos (1 hora)
    'max_login_attempts': 5,
    'lockout_duration': 300,  # segundos (5 minutos)
    'secret_key': SECRET_KEY  # usar do ambiente
}

# Configurações de Alertas (Telegram - Opcional)
TELEGRAM = {
    'enabled': False,
    'bot_token': TELEGRAM_BOT_TOKEN,  # do ambiente
    'chat_id': TELEGRAM_CHAT_ID,      # do ambiente
    'send_screenshot': True,
    'message_template': '🚨 PESSOA DETECTADA!\n📍 Local: {location}\n🕐 Horário: {timestamp}\n📷 Screenshot anexada'
}

# Configurações de Gravação
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

# Configurações de IP (Whitelist - Opcional)
IP_WHITELIST = {
    'enabled': False,
    'allowed_ips': [
        '192.168.1.0/24',  # rede local
        '127.0.0.1',       # localhost
        # Adicione mais IPs conforme necessário
    ]
}

# Configurações de Horário (Opcional)
SCHEDULE = {
    'enabled': False,
    'active_hours': {
        'start': '22:00',  # horário de início
        'end': '06:00'     # horário de término
    },
    'days_of_week': [0, 1, 2, 3, 4, 5, 6],  # 0=domingo, 6=sábado
}

# Configurações de Logging
LOGGING = {
    'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    'file': 'system.log',
    'max_size_mb': 100,
    'backup_count': 5
}

# Configurações de Performance
PERFORMANCE = {
    'thread_pool_size': 4,
    'max_frame_queue': 10,
    'enable_gpu': False,  # True se tiver CUDA instalado
    'cpu_limit': 80,      # limite de uso de CPU em %
    'memory_limit': 2048  # limite de memória em MB
}