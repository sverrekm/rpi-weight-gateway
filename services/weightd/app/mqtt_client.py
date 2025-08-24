from __future__ import annotations
import json
import threading
import time
from typing import Callable, Optional

import paho.mqtt.client as mqtt


class MQTTClient:
    def __init__(
        self,
        host: Optional[str],
        port: int,
        username: Optional[str],
        password: Optional[str],
        client_id: str = "weightd",
        on_cmd: Optional[Callable[[dict], None]] = None,
        cmd_topic: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self._client = mqtt.Client(client_id=self.client_id, clean_session=True)
        self._client.enable_logger()
        if username and password:
            self._client.username_pw_set(username, password)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._on_cmd = on_cmd
        self._cmd_topic = cmd_topic
        self._connected = False
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def _on_connect(self, client, userdata, flags, rc):  # type: ignore
        self._connected = rc == 0
        if self._connected and self._cmd_topic:
            client.subscribe(self._cmd_topic, qos=1)

    def _on_disconnect(self, client, userdata, rc):  # type: ignore
        self._connected = False

    def _on_message(self, client, userdata, msg):  # type: ignore
        if not self._on_cmd:
            return
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self._on_cmd(payload)
        except Exception:
            pass

    def start(self) -> None:
        if not self.host:
            return
        def loop():
            backoff = 1
            while not self._stop.is_set():
                try:
                    self._client.connect(self.host, self.port, keepalive=30)
                    self._client.loop_forever(retry_first_connection=True)
                except Exception:
                    self._connected = False
                    time.sleep(backoff)
                    backoff = min(30, backoff * 2)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self._client.disconnect()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def publish(self, topic: str, payload: dict, qos: int = 0, retain: bool = False) -> None:
        if not self.host:
            return
        try:
            self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)
        except Exception:
            pass

    @property
    def connected(self) -> bool:
        return self._connected
