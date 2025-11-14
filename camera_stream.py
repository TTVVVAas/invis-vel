import logging
import threading
import time
from datetime import datetime

import cv2
import numpy as np

from alerts import get_alert_manager
from config import CAMERA_DEFAULTS, MOTION_DETECTION, YOLO, PERFORMANCE

logger = logging.getLogger(__name__)


class CameraStream:
    def __init__(self, camera_info, camera_settings=None):
        self.info = camera_info
        self.settings = camera_settings or CAMERA_DEFAULTS

        self.camera_id = self.info.get('id', 'camera')
        self.camera_name = self.info.get('name', self.camera_id)
        self.default_rtsp = self.info.get('rtsp_url') or 'rtsp://usuario:senha@ip_da_camera:554/stream'

        self.rtsp_url = None
        self.cap = None
        self.running = False
        self.lock = threading.Lock()
        self.background_subtractor = None
        self.connected = False

        self.stream_frame = None
        self.last_frame_shape = (480, 640, 3)
        self.last_frame_success = time.time()

        self.motion_detected = False
        self.person_detected = False
        self.motion_events = 0
        self.person_events = 0

        self.last_detection_time = 0
        self.last_inference_time = 0
        self.latest_detections = []
        self.latest_detections_ts = 0
        self.detections_total = 0

        self.capture_thread = None
        self.detection_thread = None
        self.capture_frame_count = 0
        self.capture_last_fps_check = time.time()
        self.capture_fps = 0.0

        # Config defaults
        self.performance_settings = PERFORMANCE
        self.detection_interval = 0.5
        self.detect_on_motion_only = True
        self.detection_resize = None
        self.use_gpu = False
        self.cache_last_frame = True

        self.reconnect_attempts = 5
        self.reconnect_delay = 2
        self.frame_rate = 30
        self.frame_failure_timeout = self.settings.get('frame_failure_timeout', 5)

        self.apply_config(initial=True)
        self.start_stream()

    def _create_capture(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        buffer_size = self.settings.get('buffer_size')
        if cap is not None and buffer_size is not None:
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
            except Exception as exc:  # pragma: no cover - best effort
                logger.debug('Nao foi possivel ajustar buffer da camera %s: %s', self.camera_id, exc)
        return cap

    def apply_config(self, initial=False):
        restart_stream = False

        new_rtsp = self.info.get('rtsp_url') or self.default_rtsp
        if self.rtsp_url is None:
            self.rtsp_url = new_rtsp
        elif new_rtsp != self.rtsp_url:
            restart_stream = True
            self.rtsp_url = new_rtsp

        self.reconnect_attempts = self.settings.get('reconnect_attempts', 5)
        self.reconnect_delay = self.settings.get('reconnect_delay', 2)
        self.frame_rate = self.settings.get('frame_rate', 30)
        self.frame_failure_timeout = self.settings.get('frame_failure_timeout', self.frame_failure_timeout)

        self.performance_settings = PERFORMANCE
        self.detection_interval = max(
            0.2,
            float(self.performance_settings.get('process_interval', 0.5))
        )
        self.detect_on_motion_only = self.performance_settings.get('detect_on_motion_only', True)
        self.detection_resize = self._resolve_detection_resize(self.performance_settings.get('detection_resize'))
        self.use_gpu = self.performance_settings.get('use_gpu', False)

        new_history = MOTION_DETECTION.get('history', 500)
        new_threshold = MOTION_DETECTION.get('var_threshold', 16)
        new_detect_shadows = MOTION_DETECTION.get('detect_shadows', True)

        needs_new_bg = (
            initial
            or self.background_subtractor is None
            or new_history != getattr(self, 'motion_history', None)
            or new_threshold != getattr(self, 'motion_var_threshold', None)
            or new_detect_shadows != getattr(self, 'motion_detect_shadows', None)
        )

        if needs_new_bg:
            self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=new_history,
                varThreshold=new_threshold,
                detectShadows=new_detect_shadows
            )
            self.motion_history = new_history
            self.motion_var_threshold = new_threshold
            self.motion_detect_shadows = new_detect_shadows

        self.motion_min_area = MOTION_DETECTION.get('min_area', 500)
        self.motion_enabled = MOTION_DETECTION.get('enabled', True)

        new_model_path = YOLO.get('model', 'yolov8n.pt')
        if initial or new_model_path != getattr(self, 'yolo_model_path', None):
            try:
                from ultralytics import YOLO as YOLOModel

                self.yolo_model = YOLOModel(new_model_path)
                if self.use_gpu:
                    try:
                        self.yolo_model.to('cuda')
                        logger.info('YOLO movido para GPU (%s)', self.camera_id)
                    except Exception as gpu_err:
                        logger.warning('Falha ao usar GPU na camera %s: %s', self.camera_id, gpu_err)
                self.yolo_model_path = new_model_path
            except Exception as exc:
                logger.error('Erro ao carregar modelo YOLO para %s: %s', self.camera_id, exc)
                self.yolo_model = None

        self.detection_cooldown = YOLO.get('detection_cooldown', 2)
        self.yolo_confidence = YOLO.get('confidence', 0.5)
        self.yolo_classes = YOLO.get('classes', [0])

        if restart_stream:
            self.restart_stream()

    def start_stream(self):
        if self.running:
            return

        self.running = True
        if self.cap is None:
            try:
                self.cap = self._create_capture()
                if self.cap.isOpened():
                    logger.info('Conexao RTSP %s estabelecida', self.camera_id)
                    self.last_frame_success = time.time()
                else:
                    logger.error('Falha ao conectar camera %s', self.camera_id)
                    self.cap.release()
                    self.cap = None
            except Exception as exc:
                logger.error('Erro ao iniciar stream %s: %s', self.camera_id, exc)
                self.cap = None

        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

        if self.detection_thread is None or not self.detection_thread.is_alive():
            self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.detection_thread.start()

    def restart_stream(self):
        self.stop()
        self.start_stream()

    def _capture_loop(self):
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                self.connected = False
                self._publish_placeholder()
                self._attempt_reconnect()
                time.sleep(self.reconnect_delay)
                continue

            ret, frame = self.cap.read()
            if ret and frame is not None:
                self.connected = True
                self.last_frame_success = time.time()
                self.last_frame_shape = frame.shape
                self.capture_frame_count += 1
                now = time.time()
                elapsed = now - self.capture_last_fps_check
                if elapsed >= 1:
                    self.capture_fps = self.capture_frame_count / elapsed
                    self.capture_frame_count = 0
                    self.capture_last_fps_check = now
                with self.lock:
                    self.stream_frame = frame.copy()
            else:
                self.connected = False
                self._publish_placeholder()
                if time.time() - self.last_frame_success > self.frame_failure_timeout:
                    logger.warning('[RECONNECT] Tentando reconectar camera %s', self.camera_id)
                    self._attempt_reconnect()

            time.sleep(1 / max(self.frame_rate, 1))

    def _detection_loop(self):
        next_run = time.time()
        while self.running:
            now = time.time()
            if now < next_run:
                time.sleep(0.05)
                continue

            frame = self._snapshot_stream_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            try:
                self._process_detection_frame(frame)
            except Exception as exc:
                logger.error('Erro no processamento da camera %s: %s', self.camera_id, exc)

            next_run = time.time() + self.detection_interval

    def _should_run_yolo(self, motion_detected_now):
        if self.yolo_model is None:
            return False
        if self.detect_on_motion_only and self.motion_enabled and not motion_detected_now:
            return False
        if self.last_inference_time and (time.time() - self.last_inference_time) < self.detection_interval:
            return False
        if self.last_detection_time and (time.time() - self.last_detection_time) <= self.detection_cooldown:
            return False
        return True

    def _process_detection_frame(self, frame):
        motion_detected_now = False
        person_detected_now = False
        detections_data = []
        current_time = time.time()

        if self.motion_enabled and self.background_subtractor is not None:
            fg_mask = self.background_subtractor.apply(frame)
            contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                if cv2.contourArea(contour) < self.motion_min_area:
                    continue
                motion_detected_now = True
                break

        run_yolo = self._should_run_yolo(motion_detected_now)

        if run_yolo:
            detection_frame = frame
            scale_x = 1.0
            scale_y = 1.0
            target_size = self.detection_resize
            width = height = None
            if isinstance(target_size, tuple):
                width, height = target_size
            elif isinstance(target_size, int) and target_size > 0:
                width = target_size
                height = max(1, int(frame.shape[0] * (width / frame.shape[1])))
            if width and height:
                detection_frame = cv2.resize(frame, (width, height))
                scale_x = frame.shape[1] / float(width)
                scale_y = frame.shape[0] / float(height)

            yolo_results = self.yolo_model(
                detection_frame,
                conf=self.yolo_confidence,
                classes=self.yolo_classes,
                verbose=False
            )

            boxes = getattr(yolo_results[0], 'boxes', None)
            if boxes is not None and len(boxes) > 0:
                person_detected_now = True
                self.person_events += 1
                for box in boxes:
                    coords = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    x1 = int(coords[0] * scale_x)
                    y1 = int(coords[1] * scale_y)
                    x2 = int(coords[2] * scale_x)
                    y2 = int(coords[3] * scale_y)
                    detections_data.append({
                        'bbox': (x1, y1, x2, y2),
                        'confidence': conf
                    })

                annotated = frame.copy()
                for det in detections_data:
                    (x1, y1, x2, y2) = det['bbox']
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(
                        annotated,
                        f'{det["confidence"]:.2f}',
                        (x1, max(20, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2
                    )

                self.save_alert_image(annotated)

                try:
                    alert_manager = get_alert_manager()
                    alert_manager.recorder.write_frame(annotated)
                except Exception as exc:
                    logger.debug('Recorder indisponivel para %s: %s', self.camera_id, exc)

                self.last_detection_time = current_time
                self.detections_total += len(detections_data)

            self.last_inference_time = current_time

        with self.lock:
            self.motion_detected = motion_detected_now
            self.person_detected = person_detected_now
            if motion_detected_now:
                self.motion_events += 1
            if detections_data:
                self.latest_detections = detections_data
                self.latest_detections_ts = current_time
            elif (current_time - self.latest_detections_ts) > max(self.detection_interval * 2, 1.0):
                self.latest_detections = []

    def _snapshot_stream_frame(self):
        with self.lock:
            if self.stream_frame is None:
                return None
            return self.stream_frame.copy()

    def get_frame(self):
        with self.lock:
            frame = self.stream_frame.copy() if self.stream_frame is not None else None
            motion = self.motion_detected
            person = self.person_detected
            detections = list(self.latest_detections)
            detections_ts = self.latest_detections_ts

        if frame is None:
            frame = self._gray_frame()

        if detections and (time.time() - detections_ts) <= max(self.detection_interval * 2, 1.5):
            for det in detections:
                (x1, y1, x2, y2) = det['bbox']
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

        status_text = 'STATUS: '
        color = (0, 255, 0)
        if person:
            status_text += 'PESSOA DETECTADA'
            color = (0, 0, 255)
        elif motion:
            status_text += 'MOVIMENTO DETECTADO'
            color = (0, 255, 255)
        else:
            status_text += 'MONITORANDO'

        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.putText(
            frame,
            datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        _, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()

    def generate_frames(self):
        while True:
            frame = self.get_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                time.sleep(0.1)

    def get_status(self):
        return {
            'id': self.camera_id,
            'name': self.camera_name,
            'connected': self.connected,
            'state': 'online' if self.connected else 'offline',
            'rtsp_url': self.rtsp_url,
            'motion_detected': self.motion_detected,
            'person_detected': self.person_detected,
            'motion_events': self.motion_events,
            'person_events': self.person_events,
            'detection_count': self.detections_total,
            'last_frame': self.last_frame_success,
            'last_detection_ts': self.last_detection_time,
            'last_detection': self._format_timestamp(self.last_detection_time),
            'last_inference_ts': self.last_inference_time,
            'last_inference': self._format_timestamp(self.last_inference_time),
            'yolo_active': self.yolo_model is not None,
            'ai_active': self.yolo_model is not None,
            'frame_rate': round(self.capture_fps, 2),
            'process_interval': self.detection_interval
        }

    def update_rtsp_url(self, new_url):
        if not new_url or new_url == self.rtsp_url:
            return False

        self.info['rtsp_url'] = new_url
        self.apply_config()
        return True

    def stop(self):
        self.running = False

        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2)
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2)

        self.capture_thread = None
        self.detection_thread = None

        if self.cap:
            self.cap.release()
            self.cap = None

    def _attempt_reconnect(self):
        if self.cap:
            self.cap.release()
            self.cap = None

        for attempt in range(self.reconnect_attempts):
            try:
                self.cap = self._create_capture()
                if self.cap.isOpened():
                    logger.info('Reconexao bem-sucedida para %s', self.camera_id)
                    self.last_frame_success = time.time()
                    self.connected = True
                    return
            except Exception as exc:
                logger.error('Erro ao reconectar camera %s: %s', self.camera_id, exc)

            time.sleep(self.reconnect_delay)

        self.connected = False
        logger.error('Falha ao reconectar camera %s apos %s tentativas', self.camera_id, self.reconnect_attempts)

    def _publish_placeholder(self):
        with self.lock:
            self.connected = False
            if self.cache_last_frame and self.stream_frame is not None:
                frame = self.stream_frame.copy()
                cv2.putText(
                    frame,
                    'Reconectando camera...',
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 0),
                    2
                )
                self.stream_frame = frame
            else:
                self.stream_frame = self._gray_frame()

    def _gray_frame(self):
        height, width = self.last_frame_shape[:2]
        placeholder = np.full((height, width, 3), 30, dtype=np.uint8)
        cv2.putText(
            placeholder,
            'Aguardando sinal...',
            (10, max(30, int(height * 0.15))),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )
        return placeholder

    def save_alert_image(self, frame):
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'alerts/alerta_{timestamp}_{self.camera_id}.jpg'
            cv2.imwrite(filename, frame)

            alert_manager = get_alert_manager()
            alert_manager.trigger_alert(frame, 'person', self.camera_name)
        except Exception as exc:
            logger.error('Erro ao salvar alerta da camera %s: %s', self.camera_id, exc)

    @staticmethod
    def _resolve_detection_resize(value):
        if isinstance(value, (list, tuple)) and len(value) == 2:
            try:
                width = int(value[0])
                height = int(value[1])
                if width > 0 and height > 0:
                    return (width, height)
            except (TypeError, ValueError):
                return None
        try:
            if isinstance(value, (int, float)):
                width = int(value)
                if width > 0:
                    return width
        except (TypeError, ValueError):
            return None
        return None

    @staticmethod
    def _format_timestamp(ts):
        if not ts:
            return None
        try:
            return datetime.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M:%S')
        except Exception:
            return None

