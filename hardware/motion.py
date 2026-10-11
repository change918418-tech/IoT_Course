"""移動／播放狀態的 RAM 快取，不操作 GPIO。"""


def new_motion_state():
    return {'sensor_status': 'starting', 'pir_high': False,
            'detected': False, 'last_detected_at': None, 'recent_detections': [],
            'count': 0, 'sensor_error': None, 'music_status': 'starting',
            'music_error': None}
