from dataclasses import dataclass

from aivideoalarm.config import Settings
from aivideoalarm.mqtt_client import AlarmMqttClient


@dataclass
class _FakeMsg:
    topic: str
    payload: bytes


def test_configure_door_window_topics_builds_expected_paths():
    client = AlarmMqttClient(Settings())
    client.configure_door_window_topics(
        ["binary_sensor.front_door_contact", "binary_sensor.back_door_contact"],
        base_topic="homeassistant",
    )
    assert client._door_window_topics == {
        "homeassistant/binary_sensor/front_door_contact/state": "binary_sensor.front_door_contact",
        "homeassistant/binary_sensor/back_door_contact/state": "binary_sensor.back_door_contact",
    }


def test_door_window_message_dispatches_to_handler():
    client = AlarmMqttClient(Settings())
    client.configure_door_window_topics(["binary_sensor.front_door_contact"], base_topic="homeassistant")

    received: list[tuple[str, str]] = []
    client.on_door_window_state(lambda entity_id, state: received.append((entity_id, state)))

    msg = _FakeMsg(topic="homeassistant/binary_sensor/front_door_contact/state", payload=b"on")
    client._handle_message(None, None, msg)

    assert received == [("binary_sensor.front_door_contact", "on")]


def test_malformed_entity_id_is_skipped():
    client = AlarmMqttClient(Settings())
    client.configure_door_window_topics(["not_a_valid_entity_id"], base_topic="homeassistant")
    assert client._door_window_topics == {}
