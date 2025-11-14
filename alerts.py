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
    def __init__(self, config_source=None):
        self.config = config_source or TELEGRAM
        self._warn_if_misconfigured()

    def _warn_if_misconfigured(self):
        if self.enabled and not self.bot_token:
            logger.warning('Telegram enabled but bot_token is missing')

    @property
    def enabled(self):
        return self.config.get('enabled', False)

    @property
    def bot_token(self):
        return self.config.get('bot_token', '')

    @property
    def chat_id(self):
        return self.config.get('chat_id', '')

    @property
    def send_screenshot(self):
        return self.config.get('send_screenshot', True)

    @property
    def message_template(self):
        return self.config.get(
            'message_template',
            'Person detected!\\nLocation: {location}\\nTime: {timestamp}'
        )

    def refresh_from_config(self, config_source=None):
        self.config = config_source or TELEGRAM
        self._warn_if_misconfigured()

    def send_alert(self, image_path=None, location='Camera Principal'):
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False

        try:
            timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            message = self.message_template.format(location=location, timestamp=timestamp)

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, data=data)

            if response.status_code == 200:
                logger.info('Telegram alert sent successfully')

                if self.send_screenshot and image_path and os.path.exists(image_path):
                    self.send_photo(image_path)

                return True

            logger.error(f'Error sending Telegram alert: {response.text}')
            return False

        except Exception as e:
            logger.error(f'Error sending Telegram alert: {e}')
            return False

    def send_photo(self, image_path):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"

            with open(image_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': self.chat_id}
                response = requests.post(url, files=files, data=data)

            if response.status_code == 200:
                logger.info('Telegram photo sent successfully')
            else:
                logger.error(f'Error sending Telegram photo: {response.text}')

        except Exception as e:
            logger.error(f'Error sending Telegram photo: {e}')


class VideoRecorder:
    def __init__(self, config_source=None):
        self.config = config_source or RECORDING
        self.recording = False
        self.video_writer = None
        self.recording_start_time = None
        self.frame_buffer = []
        self.filename = None
        self._ensure_storage_path()

    def _ensure_storage_path(self):
        os.makedirs(self.storage_path, exist_ok=True)

    def refresh_from_config(self, config_source=None):
        self.config = config_source or RECORDING
        self._ensure_storage_path()
        self.frame_buffer = self.frame_buffer[-self.max_buffer_size:]
        if not self.enabled and self.recording:
            self.stop_recording()

    @property
    def enabled(self):
        return self.config.get('enabled', False)

    @property
    def record_on_person(self):
        return self.config.get('record_on_person_detection', True)

    @property
    def duration(self):
        return self.config.get('record_duration', 30)

    @property
    def codec(self):
        return self.config.get('video_codec', 'mp4v')

    @property
    def fps(self):
        return self.config.get('fps', 20)

    @property
    def resolution(self):
        width, height = self.config.get('resolution', (640, 480))
        return int(width), int(height)

    @property
    def storage_path(self):
        return self.config.get('storage_path', 'recordings/')

    @property
    def max_storage_gb(self):
        return self.config.get('max_storage_gb', 10)

    @property
    def max_buffer_size(self):
        return int(self.fps * self.duration)

    def start_recording(self, trigger_reason='Person detection'):
        if not self.enabled or self.recording:
            return False

        try:
            recording_dir = ensure_recording_directory_exists()
            if not recording_dir:
                logger.error('Could not prepare recordings directory')
                return False

            filename = generate_recording_filename()
            full_path = os.path.join(recording_dir, filename)

            fourcc = cv2.VideoWriter_fourcc(*self.codec)
            self.video_writer = cv2.VideoWriter(full_path, fourcc, self.fps, self.resolution)

            if self.video_writer.isOpened():
                self.recording = True
                self.recording_start_time = time.time()
                self.filename = full_path

                for frame in self.frame_buffer:
                    self.video_writer.write(frame)

                logger.info(f'Recording started: {full_path}')
                threading.Timer(self.duration, self.stop_recording).start()
                return True

            logger.error('Could not open VideoWriter')
            return False

        except Exception as e:
            logger.error(f'Error starting recording: {e}')
            return False

    def write_frame(self, frame):
        if not self.enabled:
            return

        if frame.shape[:2][::-1] != self.resolution:
            frame = cv2.resize(frame, self.resolution)

        self.frame_buffer.append(frame)
        if len(self.frame_buffer) > self.max_buffer_size:
            self.frame_buffer.pop(0)

        if self.recording and self.video_writer:
            try:
                self.video_writer.write(frame)
            except Exception as e:
                logger.error(f'Error writing frame: {e}')

    def stop_recording(self):
        if not self.recording or not self.video_writer:
            return

        try:
            self.video_writer.release()
            self.recording = False

            elapsed_time = time.time() - self.recording_start_time
            logger.info(f'Recording finished: {self.filename} ({elapsed_time:.1f}s)')
            self.cleanup_old_recordings()

        except Exception as e:
            logger.error(f'Error stopping recording: {e}')

    def cleanup_old_recordings(self):
        try:
            total_size = 0
            files = []
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
                                except OSError:
                                    continue

            total_size_gb = total_size / (1024 ** 3)

            if total_size_gb > self.max_storage_gb:
                files.sort(key=lambda x: x[1])

                for filepath, _ in files:
                    if total_size_gb <= self.max_storage_gb * 0.8:
                        break

                    try:
                        size = os.path.getsize(filepath)
                        os.remove(filepath)
                        total_size_gb -= size / (1024 ** 3)

                        logger.info(f'Removed old recording: {filepath}')
                        dir_path = os.path.dirname(filepath)
                        try:
                            os.rmdir(dir_path)
                        except OSError:
                            pass

                    except Exception as e:
                        logger.error(f'Error removing file {filepath}: {e}')

        except Exception as e:
            logger.error(f'Error cleaning recordings: {e}')


class AlertManager:
    def __init__(self):
        self.telegram = TelegramNotifier()
        self.recorder = VideoRecorder()
        self.alert_count = 0
        self.last_alert_time = 0
        self.alert_cooldown = 30  # seconds between alerts

    def refresh_from_config(self):
        self.telegram.refresh_from_config()
        self.recorder.refresh_from_config()

    def trigger_alert(self, frame, alert_type='person', location='Camera Principal'):
        current_time = time.time()

        if current_time - self.last_alert_time < self.alert_cooldown:
            return False

        self.alert_count += 1
        self.last_alert_time = current_time

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_path = f'alerts/alerta_{timestamp}.jpg'

        try:
            cv2.imwrite(image_path, frame)
            logger.info(f'Alert image saved: {image_path}')
        except Exception as e:
            logger.error(f'Error saving alert image: {e}')
            image_path = None

        if alert_type == 'person':
            self.telegram.send_alert(image_path, location)

        if alert_type == 'person' and self.recorder.record_on_person:
            self.recorder.start_recording(f'Detection: {alert_type}')

        logger.info(f'Alert #{self.alert_count} triggered: {alert_type} at {location}')
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
