import asyncio
import json
import logging
import signal

import paho.mqtt.client as mqtt
from vehicle import Vehicle, vehicle  # Velocitas Vehicle
from velocitas_sdk.vehicle_app import VehicleApp

BROKER_ADDRESS = "127.0.0.1"
PORT = 1883
TOPIC_ALERT = "alert/car"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class CustomVehicleApp(VehicleApp):
    def __init__(self, vehicle_client: Vehicle):
        super().__init__()
        self.Vehicle = vehicle_client

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

    async def on_start(self):
        logger.info("Starting MQTT Client...")
        self.mqtt_client.connect(BROKER_ADDRESS, PORT)
        self.mqtt_client.loop_start()

    async def on_stop(self):
        logger.info("Stopping MQTT Client...")
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()

    def on_connect(self, client, userdata, flags, reason_code):
        if reason_code == 0:
            logger.info("Connected to MQTT Broker successfully.")
            client.subscribe(TOPIC_ALERT)
        else:
            logger.error(f"Failed to connect to MQTT Broker: {reason_code}")

    def on_message(self, client, userdata, message):
        try:
            decoded_message = message.payload.decode("utf-8")
            data = json.loads(decoded_message)
            collision_location = data.get("collision_location")
            logger.info(f"Collision location received: {collision_location}")
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from MQTT message.")


async def main():
    logger.info("Starting CustomVehicleApp...")
    app = CustomVehicleApp(vehicle)
    await app.run()


LOOP = asyncio.get_event_loop()
LOOP.add_signal_handler(signal.SIGTERM, LOOP.stop)
LOOP.run_until_complete(main())
LOOP.close()
