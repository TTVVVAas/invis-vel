import logging

from camera_stream import CameraStream
from config import CAMERA_DEFAULTS
from config_loader import (
    get_cameras as load_cameras_from_store,
    update_camera as persist_camera_update,
    add_camera as persist_add_camera,
    delete_camera as persist_delete_camera
)

logger = logging.getLogger(__name__)


class CameraManager:
    def __init__(self, cameras=None, base_settings=None):
        self.cameras_config = self._normalize_cameras(cameras or load_cameras_from_store())
        self.settings = base_settings or CAMERA_DEFAULTS
        self.streams = {}
        self._init_streams()

    def _normalize_cameras(self, cameras):
        normalized = {}
        if isinstance(cameras, dict):
            iterable = cameras.items()
        else:
            iterable = []
            for cam in cameras or []:
                if isinstance(cam, dict):
                    iterable.append((cam.get('id'), cam))

        for cam_id, cam in iterable:
            if not isinstance(cam, dict):
                continue
            resolved_id = cam_id or cam.get('id')
            if not resolved_id:
                logger.warning('Camera sem ID ignorada: %s', cam)
                continue
            resolved_id = str(resolved_id)
            cam.setdefault('id', resolved_id)
            cam.setdefault('name', resolved_id)
            cam.setdefault('rtsp_url', cam.get('rtsp') or '')
            cam.setdefault('enabled', True)
            normalized[resolved_id] = cam
        return normalized

    def _init_streams(self):
        for cam_id, cam in self.cameras_config.items():
            if not cam.get('enabled', True):
                continue
            if cam_id in self.streams:
                continue
            self.streams[cam_id] = CameraStream(cam, self.settings)

    def get_stream(self, camera_id):
        if camera_id is None:
            return None
        return self.streams.get(str(camera_id))

    def get_default_stream(self):
        return next(iter(self.streams.values()), None)

    def get_all_statuses(self):
        statuses = {}
        for cam_id, cam in self.cameras_config.items():
            stream = self.streams.get(cam_id)
            if stream:
                status = stream.get_status()
                status['enabled'] = cam.get('enabled', True)
                statuses[cam_id] = status
            else:
                statuses[cam_id] = {
                    'id': cam_id,
                    'name': cam.get('name', cam_id),
                    'connected': False,
                    'state': 'disabled' if not cam.get('enabled', True) else 'offline',
                    'rtsp_url': cam.get('rtsp_url', ''),
                    'enabled': cam.get('enabled', True),
                    'motion_detected': False,
                    'person_detected': False,
                    'motion_events': cam.get('motion_events', 0),
                    'person_events': cam.get('person_events', 0),
                    'detection_count': 0,
                    'frame_rate': 0.0,
                    'process_interval': None,
                    'last_detection_ts': None,
                    'last_inference_ts': None
                }
        return statuses

    def apply_config(self):
        for stream in self.streams.values():
            stream.apply_config()

    def update_camera(self, camera_id, data):
        updated = persist_camera_update(camera_id, data)
        if not updated:
            return None

        camera_id = str(updated['id'])
        self.cameras_config[camera_id] = updated
        enabled = updated.get('enabled', True)
        stream = self.streams.get(camera_id)

        if not enabled:
            if stream:
                stream.stop()
                del self.streams[camera_id]
            logger.info('Camera %s desativada', camera_id)
            return updated

        if stream:
            stream.info.update(updated)
            stream.apply_config()
            logger.info('Camera %s atualizada', camera_id)
        else:
            self.streams[camera_id] = CameraStream(updated, self.settings)
            logger.info('Camera %s inicializada', camera_id)

        return updated

    def update_camera_rtsp(self, camera_id, new_url):
        return bool(self.update_camera(camera_id, {'rtsp_url': new_url}))

    def add_camera(self, camera_data):
        try:
            new_cam = persist_add_camera(camera_data)
        except ValueError as exc:
            logger.error('Nao foi possivel adicionar camera: %s', exc)
            raise

        cam_id = str(new_cam['id'])
        self.cameras_config[cam_id] = new_cam
        if new_cam.get('enabled', True):
            self.streams[cam_id] = CameraStream(new_cam, self.settings)
        return new_cam

    def delete_camera(self, camera_id):
        camera_id = str(camera_id)
        removed = persist_delete_camera(camera_id)
        if not removed:
            return False
        stream = self.streams.pop(camera_id, None)
        if stream:
            stream.stop()
        self.cameras_config.pop(camera_id, None)
        logger.info('Camera %s removida', camera_id)
        return True

    def stop_all(self):
        for stream in self.streams.values():
            stream.stop()

