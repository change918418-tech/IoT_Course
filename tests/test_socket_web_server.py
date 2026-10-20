"""
test_socket_web_server.py - 測試基於原生 Socket / uasyncio 的輕量 Web 伺服器
驗證 Microdot 移除後，所有 Web 端點與原生 TCP Socket 網路通訊完全維持既有契約。
"""

import unittest
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class SocketWebServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import web_server
        self.web = web_server
        self.web.load_html()

        class MockCommandService:
            def submit(self, kind, source, value=None):
                return {'status': 'accepted', 'request_id': 101, 'kind': kind, 'source': source, 'value': value}
            def snapshot(self):
                return {'available': True, 'mode': 'AUTO', 'desired_color': 7, 'alert_active': False}
            def result(self, request_id):
                if request_id == 101:
                    return {'status': 'completed', 'request_id': 101, 'source': 'web'}
                return None

        class MockMqttManager:
            def request_publish(self, event):
                event.set()
                return {'status': 'accepted', 'request_id': 202, 'error': None}
            def publish_status(self):
                return {'status': 'published', 'request_id': 202, 'error': None}

        class MockSensorSnapshot:
            def snapshot(self):
                return {
                    'temperature': {'value': 26.5, 'valid': True, 'quality': 'good', 'age_ms': 50},
                    'humidity': {'value': 55.0, 'valid': True, 'quality': 'good', 'age_ms': 50},
                    'light': {'value': 1200, 'valid': True, 'quality': 'good', 'age_ms': 50},
                    'sample_seq': 12,
                    'status': 'ready',
                }

        self.web.command_service = MockCommandService()
        self.web.mqtt_manager = MockMqttManager()
        self.web.publish_event = asyncio.Event()
        self.web.sensor_snapshot = MockSensorSnapshot()

    async def test_get_index_html(self):
        req = self.web.Request(method='GET', path='/')
        res = await self.web.app.dispatch_request(req)
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/html', res.headers.get('Content-Type', ''))
        self.assertIn('<!DOCTYPE html>', res.body)

    async def test_get_test_page(self):
        req = self.web.Request(method='GET', path='/test')
        res = await self.web.app.dispatch_request(req)
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/html', res.headers.get('Content-Type', ''))
        self.assertIn('ESP32 Socket Web Server 運行正常', res.body)

    async def test_get_static_assets(self):
        req_js = self.web.Request(method='GET', path='/assets/uplot/1.6.32/uPlot.iife.min.js')
        res_js = await self.web.app.dispatch_request(req_js)
        self.assertEqual(res_js.status_code, 200)
        self.assertIn('application/javascript', res_js.headers.get('Content-Type', ''))
        self.assertIn('max-age=31536000', res_js.headers.get('Cache-Control', ''))
        if hasattr(res_js.body, 'close'):
            res_js.body.close()

        req_css = self.web.Request(method='GET', path='/assets/uplot/1.6.32/uPlot.min.css')
        res_css = await self.web.app.dispatch_request(req_css)
        self.assertEqual(res_css.status_code, 200)
        self.assertIn('text/css', res_css.headers.get('Content-Type', ''))
        if hasattr(res_css.body, 'close'):
            res_css.body.close()

    async def test_api_data_contract(self):
        req = self.web.Request(method='GET', path='/api/data')
        res = await self.web.app.dispatch_request(req)
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.body)
        self.assertEqual(data['temp'], 26.5)
        self.assertEqual(data['humidity'], 55.0)
        self.assertEqual(data['light'], 1200)
        self.assertEqual(data['status'], 'ready')
        self.assertIn('light_thresholds', data)
        self.assertIn('led', data)
        self.assertIn('rfid', data)
        self.assertIn('motion', data)

    async def test_api_data_uses_threshold_defaults_for_legacy_config(self):
        config = self.web.config
        missing = object()
        original_trigger = getattr(config, 'LIGHT_ALERT_TRIGGER_ADC', missing)
        original_reset = getattr(config, 'LIGHT_ALERT_RESET_ADC', missing)
        try:
            if original_trigger is not missing:
                delattr(config, 'LIGHT_ALERT_TRIGGER_ADC')
            if original_reset is not missing:
                delattr(config, 'LIGHT_ALERT_RESET_ADC')
            res = await self.web.app.dispatch_request(
                self.web.Request(method='GET', path='/api/data'))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(json.loads(res.body)['light_thresholds'], {
                'trigger': 1000,
                'reset': 1100,
                'dark_when_high': False,
            })
        finally:
            if original_trigger is not missing:
                config.LIGHT_ALERT_TRIGGER_ADC = original_trigger
            if original_reset is not missing:
                config.LIGHT_ALERT_RESET_ADC = original_reset

    async def test_api_led_endpoints(self):
        # Toggle
        res_toggle = await self.web.app.dispatch_request(
            self.web.Request(method='POST', path='/api/led/toggle'))
        self.assertEqual(res_toggle.status_code, 202)
        self.assertEqual(json.loads(res_toggle.body)['status'], 'accepted')

        # Commands
        body_cmd = json.dumps({'kind': 'set_color', 'value': 4}).encode('utf-8')
        res_cmd = await self.web.app.dispatch_request(
            self.web.Request(method='POST', path='/api/led/commands', body=body_cmd))
        self.assertEqual(res_cmd.status_code, 202)
        cmd_id = json.loads(res_cmd.body)['request_id']

        # Command result
        res_res = await self.web.app.dispatch_request(
            self.web.Request(method='GET', path=f'/api/led/commands/{cmd_id}'))
        self.assertEqual(res_res.status_code, 200)
        self.assertEqual(json.loads(res_res.body)['status'], 'completed')

        # Mode
        body_mode = json.dumps({'mode': 'MANUAL'}).encode('utf-8')
        res_mode = await self.web.app.dispatch_request(
            self.web.Request(method='POST', path='/api/led/mode', body=body_mode))
        self.assertEqual(res_mode.status_code, 202)

    async def test_tcp_socket_communication(self):
        """啟動真實本機 TCP Socket 伺服器，模擬瀏覽器連線並發送真實 HTTP 請求。"""
        server = await asyncio.start_server(self.web.app._handle_client, '127.0.0.1', 0)
        port = server.sockets[0].getsockname()[1]

        try:
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            http_req = (
                b"POST /api/led/toggle HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Length: 0\r\n"
                b"Connection: close\r\n\r\n"
            )
            writer.write(http_req)
            await writer.drain()

            raw_response = await reader.read()
            writer.close()
            await writer.wait_closed()

            self.assertTrue(raw_response.startswith(b"HTTP/1.1 202 Accepted\r\n"))
            self.assertIn(b"Content-Type: application/json; charset=utf-8", raw_response)
            header_end = raw_response.find(b"\r\n\r\n")
            body_json = json.loads(raw_response[header_end + 4:].decode('utf-8'))
            self.assertEqual(body_json['status'], 'accepted')
            self.assertEqual(body_json['kind'], 'cycle')
        finally:
            server.close()
            await server.wait_closed()


if __name__ == '__main__':
    unittest.main()
