"""Canonical command boundary shared by buttons, Web, MQTT and sensors."""


class CommandService:
    """Normalize command metadata before handing it to the LED controller."""

    def __init__(self, controller):
        self._controller = controller
        self._next_request_id = 1

    def submit(self, kind, source, value=None):
        request_id = self._next_request_id
        self._next_request_id += 1
        return self._controller.submit_command({
            'request_id': request_id,
            'kind': kind,
            'source': source,
            'value': value,
        })

    def result(self, request_id):
        return self._controller.result(request_id)

    def snapshot(self):
        return self._controller.snapshot()

    def request_stop(self):
        self._controller.request_stop()

    async def wait_stopped(self):
        await self._controller.wait_stopped()
