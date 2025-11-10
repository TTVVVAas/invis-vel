import requests
import json
import os
from datetime import datetime
import cv2
import threading
import time
import logging
from config import TELEGRAM, RECORDING
from recording_utils import ensure_recording_directory_exists, generate_recording_filename

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.enabled = TELEGRAM.get('enabled', False)
        self.bot_token = TELEGRAM.get('bot_token', '')
        self.chat_id = TELEGRAM.get('chat_id', '')
        self.send_screenshot = TELEGRAM.get('send_screenshot', True)
        self.message_template = TELEGRAM.get('message_template', 
            '🚨 PESSOA DETECTADA!\n📍 Local: {location}\n🕐 Horário: {timestamp}')
        
        if self.enabled and not self.bot_token:
            logger.warning("Telegram ativado mas bot_token não configurado")
    
    def send_alert(self, image_path=None, location="Câmera Principal"):
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        
        try:
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            message = self.message_template.format(
                location=location,
                timestamp=timestamp
            )
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                logger.info(f"Alerta Telegram enviado com sucesso")
                
                # Enviar screenshot se habilitado e disponível
                if self.send_screenshot and image_path and os.path.exists(image_path):
                    self.send_photo(image_path)
                
                return True
            else:
                logger.error(f"Erro ao enviar alerta Telegram: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao enviar alerta Telegram: {e}")
            return False
    
    def send_photo(self, image_path):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
            
            with open(image_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': self.chat_id}
                response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                logger.info("Foto enviada com sucesso via Telegram")
            else:
                logger.error(f"Erro ao enviar foto: {response.text}")
                
        except Exception as e:
            logger.error(f"Erro ao enviar foto Telegram: {e}")

class VideoRecorder:
    def __init__(self):
        self.enabled = RECORDING.get('enabled', False)
        self.record_on_person = RECORDING.get('record_on_person_detection', True)
        self.duration = RECORDING.get('record_duration', 30)
        self.codec = RECORDING.get('video_codec', 'mp4v')
        self.fps = RECORDING.get('fps', 20)
        self.resolution = RECORDING.get('resolution', (640, 480))
        self.storage_path = RECORDING.get('storage_path', 'recordings/')
        self.max_storage_gb = RECORDING.get('max_storage_gb', 10)
        
        self.recording = False
        self.video_writer = None
        self.recording_start_time = None
        self.frame_buffer = []
        self.max_buffer_size = self.fps * self.duration
        
        # Criar diretório de gravações
        os.makedirs(self.storage_path, exist_ok=True)
    
    def start_recording(self, trigger_reason="Detecção de pessoa"):
        if not self.enabled or self.recording:
            return False
        
        try:
            # Criar estrutura de diretórios por data
            recording_dir = ensure_recording_directory_exists()
            if not recording_dir:
                logger.error("Erro ao criar diretório de gravações")
                return False
            
            # Gerar nome de arquivo com timestamp
            filename = generate_recording_filename()
            full_path = os.path.join(recording_dir, filename)
            
            fourcc = cv2.VideoWriter_fourcc(*self.codec)
            self.video_writer = cv2.VideoWriter(full_path, fourcc, self.fps, self.resolution)
            
            if self.video_writer.isOpened():
                self.recording = True
                self.recording_start_time = time.time()
                self.filename = full_path
                
                # Gravar frames do buffer
                for frame in self.frame_buffer:
                    self.video_writer.write(frame)
                
                logger.info(f"Gravação iniciada: {full_path}")
                
                # Agendar parada automática
                threading.Timer(self.duration, self.stop_recording).start()
                
                return True
            else:
                logger.error("Erro ao abrir VideoWriter")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao iniciar gravação: {e}")
            return False
    
    def write_frame(self, frame):
        if not self.enabled:
            return
        
        # Redimensionar frame se necessário
        if frame.shape[:2][::-1] != self.resolution:
            frame = cv2.resize(frame, self.resolution)
        
        # Adicionar ao buffer
        self.frame_buffer.append(frame)
        if len(self.frame_buffer) > self.max_buffer_size:
            self.frame_buffer.pop(0)
        
        # Gravar se estiver gravando
        if self.recording and self.video_writer:
            try:
                self.video_writer.write(frame)
            except Exception as e:
                logger.error(f"Erro ao gravar frame: {e}")
    
    def stop_recording(self):
        if not self.recording or not self.video_writer:
            return
        
        try:
            self.video_writer.release()
            self.recording = False
            
            elapsed_time = time.time() - self.recording_start_time
            logger.info(f"Gravação finalizada: {self.filename} ({elapsed_time:.1f}s)")
            
            # Limpar armazenamento antigo
            self.cleanup_old_recordings()
            
        except Exception as e:
            logger.error(f"Erro ao parar gravação: {e}")
    
    def cleanup_old_recordings(self):
        try:
            # Calcular tamanho total dos arquivos em toda a estrutura de pastas
            total_size = 0
            files = []
            
            # Percorrer toda a estrutura de pastas recordings/ano/mes/dia/
            base_path = get_recordings_base_path()
            if not os.path.exists(base_path):
                return
            
            for year in os.listdir(base_path):
                year_path = os.path.join(base_path, year)
                if not os.path.isdir(year_path):
                    continue
                    
                for month in os.listdir(year_path):
                    month_path = os.path.join(year_path, month)
                    if not os.path.isdir(month_path):
                        continue
                        
                    for day in os.listdir(month_path):
                        day_path = os.path.join(month_path, day)
                        if not os.path.isdir(day_path):
                            continue
                        
                        for filename in os.listdir(day_path):
                            if filename.endswith('.mp4'):
                                filepath = os.path.join(day_path, filename)
                                try:
                                    size = os.path.getsize(filepath)
                                    total_size += size
                                    files.append((filepath, os.path.getmtime(filepath)))
                                except:
                                    continue
            
            # Converter para GB
            total_size_gb = total_size / (1024**3)
            
            if total_size_gb > self.max_storage_gb:
                # Ordenar por data (mais antigos primeiro)
                files.sort(key=lambda x: x[1])
                
                # Remover arquivos antigos até ficar abaixo do limite
                for filepath, _ in files:
                    if total_size_gb <= self.max_storage_gb * 0.8:  # Manter 80% do limite
                        break
                    
                    try:
                        size = os.path.getsize(filepath)
                        os.remove(filepath)
                        total_size_gb -= size / (1024**3)
                        
                        logger.info(f"Arquivo removido para liberar espaço: {filepath}")
                        
                        # Tentar remover pastas vazias
                        dir_path = os.path.dirname(filepath)
                        try:
                            os.rmdir(dir_path)  # Remove se estiver vazio
                        except:
                            pass  # Pasta não vazia, ignora
                            
                    except Exception as e:
                        logger.error(f"Erro ao remover arquivo {filepath}: {e}")
        
        except Exception as e:
            logger.error(f"Erro ao limpar gravações antigas: {e}")

class AlertManager:
    def __init__(self):
        self.telegram = TelegramNotifier()
        self.recorder = VideoRecorder()
        self.alert_count = 0
        self.last_alert_time = 0
        self.alert_cooldown = 30  # segundos entre alertas
    
    def trigger_alert(self, frame, alert_type="person", location="Câmera Principal"):
        current_time = time.time()
        
        # Verificar cooldown
        if current_time - self.last_alert_time < self.alert_cooldown:
            return False
        
        self.alert_count += 1
        self.last_alert_time = current_time
        
        # Salvar imagem de alerta
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = f"alerts/alerta_{timestamp}.jpg"
        
        try:
            cv2.imwrite(image_path, frame)
            logger.info(f"Imagem de alerta salva: {image_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar imagem de alerta: {e}")
            image_path = None
        
        # Enviar notificação Telegram
        if alert_type == "person":
            self.telegram.send_alert(image_path, location)
        
        # Iniciar gravação se configurado
        if alert_type == "person" and self.recorder.record_on_person:
            self.recorder.start_recording(f"Detecção de {alert_type}")
        
        logger.info(f"Alerta #{self.alert_count} disparado: {alert_type} em {location}")
        
        return True
    
    def get_alert_stats(self):
        return {
            'total_alerts': self.alert_count,
            'last_alert_time': self.last_alert_time,
            'telegram_enabled': self.telegram.enabled,
            'recording_enabled': self.recorder.enabled,
            'is_recording': self.recorder.recording
        }

# Instância global do gerenciador de alertas
alert_manager = AlertManager()

def get_alert_manager():
    return alert_manager