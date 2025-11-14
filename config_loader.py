import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
CAMERAS_FILE = BASE_DIR / 'cameras.json'
BACKUP_FILE = CAMERAS_FILE.with_suffix('.bak')

DEFAULT_CAMERAS = [
    {
        'id': 'cam1',
        'name': 'Entrada Principal',
        'rtsp': 'rtsp://tiago123.serveftp.com:554/h264',
        'enabled': True
    },
    {
        'id': 'cam2',
        'name': 'Garagem',
        'rtsp': 'rtsp://tiago123.serveftp.com:555/h264',
        'enabled': True
    }
]

_cache: Optional[List[Dict]] = None


def _sanitize_camera(cam: Dict, index: int) -> Dict:
    cam = cam or {}
    cam_id = str(cam.get('id') or f'cam{index}')
    rtsp_url = cam.get('rtsp_url') or cam.get('rtsp') or ''

    return {
        'id': cam_id,
        'name': cam.get('name') or cam_id,
        'rtsp_url': rtsp_url.strip(),
        'enabled': bool(cam.get('enabled', True))
    }


def _ensure_file() -> None:
    if not CAMERAS_FILE.exists():
        CAMERAS_FILE.write_text(
            json.dumps({'cameras': DEFAULT_CAMERAS}, indent=4, ensure_ascii=False),
            encoding='utf-8'
        )


def _write_cameras(cameras: List[Dict]) -> None:
    data = {
        'cameras': [
            {
                'id': cam['id'],
                'name': cam.get('name', cam['id']),
                'rtsp': cam.get('rtsp_url', ''),
                'enabled': bool(cam.get('enabled', True))
            }
            for cam in cameras
        ]
    }
    CAMERAS_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding='utf-8')


def load_cameras() -> List[Dict]:
    global _cache
    _ensure_file()
    try:
        raw = json.loads(CAMERAS_FILE.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        if CAMERAS_FILE.exists():
            CAMERAS_FILE.replace(BACKUP_FILE)
        _write_cameras(DEFAULT_CAMERAS)
        raw = {'cameras': DEFAULT_CAMERAS}

    raw_list = raw.get('cameras')
    if raw_list is None and isinstance(raw, list):
        raw_list = raw

    if not raw_list:
        raw_list = DEFAULT_CAMERAS

    sanitized = [_sanitize_camera(cam, idx) for idx, cam in enumerate(raw_list, start=1)]
    _cache = sanitized
    return deepcopy(_cache)


def get_cameras() -> List[Dict]:
    global _cache
    if _cache is None:
        return load_cameras()
    return deepcopy(_cache)


def save_cameras(cameras: List[Dict]) -> List[Dict]:
    global _cache
    sanitized = [_sanitize_camera(cam, idx) for idx, cam in enumerate(cameras, start=1)]
    _write_cameras(sanitized)
    _cache = sanitized
    return deepcopy(_cache)


def update_camera(camera_id: str, data: Dict) -> Optional[Dict]:
    cameras = get_cameras()
    camera_id = str(camera_id)
    updated = None
    for cam in cameras:
        if cam['id'] == camera_id:
            if 'name' in data:
                cam['name'] = data['name'] or cam['id']
            if 'rtsp' in data:
                cam['rtsp_url'] = data['rtsp'].strip()
            if 'rtsp_url' in data:
                cam['rtsp_url'] = data['rtsp_url'].strip()
            if 'enabled' in data:
                cam['enabled'] = bool(data['enabled'])
            updated = cam
            break
    if not updated:
        return None
    save_cameras(cameras)
    return deepcopy(updated)


def add_camera(camera_data: Dict) -> Dict:
    cameras = get_cameras()
    camera_id = camera_data.get('id') or f'cam{len(cameras) + 1}'
    if any(cam['id'] == camera_id for cam in cameras):
        raise ValueError(f"Camera ID '{camera_id}' ja existe")
    cameras.append(_sanitize_camera(camera_data, len(cameras) + 1))
    save_cameras(cameras)
    return deepcopy(cameras[-1])


def delete_camera(camera_id: str) -> bool:
    camera_id = str(camera_id)
    cameras = get_cameras()
    new_cameras = [cam for cam in cameras if cam['id'] != camera_id]
    if len(new_cameras) == len(cameras):
        return False
    save_cameras(new_cameras)
    return True
