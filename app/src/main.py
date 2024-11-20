# Copyright (c) 2024 Contributors to the Eclipse Foundation
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import logging
import signal
import sys
import time
from typing import Optional

import paho.mqtt.client as mqtt
import pygame
from kuksa_client.grpc import VSSClient  # KUKSA Client
from vehicle import Vehicle, vehicle
from velocitas_sdk.vehicle_app import VehicleApp

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

BROKER_ADDRESS = "127.0.0.1"
PORT = 1883
TOPIC_ALERT = "alert/car"
TOPIC_ACCIDENT = "accident"

KUKSA_HOST = "127.0.0.1"
KUKSA_PORT = 55555
VEHICLE_ID = "Vehicle1"

COLLISION_LOCATION = {"latitude": 51, "longitude": 10}

pygame.init()
WIDTH, HEIGHT = 480, 360
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Head-Up Display")
font_large = pygame.font.Font(None, 40)
font_small = pygame.font.Font(None, 20)
clock = pygame.time.Clock()

background_image = pygame.image.load("/workspaces/VehicleHUD/app/src/dashboard.jpg")
background_image = pygame.transform.scale(background_image, (WIDTH, HEIGHT))
warning_icon = pygame.image.load("app/src/alert.png")
warning_icon = pygame.transform.scale(warning_icon, (100, 100))


class CustomVehicleApp(VehicleApp):
    def __init__(self, vehicle_client: Vehicle):
        super().__init__()
        self.Vehicle = vehicle_client

        self.message_to_display: Optional[str] = None
        self.collision_location: Optional[dict] = None
        self.message_display_time: Optional[float] = None

        self.mqtt_client = mqtt.Client()
        logger.info("Starting MQTT Client...")
        self.mqtt_client.connect(BROKER_ADDRESS, PORT)
        self.mqtt_client.loop_start()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

        self.kuksa_client = VSSClient(KUKSA_HOST, KUKSA_PORT)
        self.kuksa_client.connect()

    async def on_stop(self):
        logger.info("Stopping MQTT and KUKSA Clients...")
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.kuksa_client.close()

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
            self.collision_location = data.get("collision_location")
            self.message_to_display = (
                f"Warning: Collision Ahead at {self.collision_location}!"
            )
            self.message_display_time = time.time()
            logger.info(f"Collision location received: {self.collision_location}")
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from MQTT message.")

    def publish_message(self, topic, message):
        result = self.mqtt_client.publish(topic, message)
        status = result[0]
        if status == 0:
            logger.info(f"Message '{message}' sent to topic '{topic}'")
        else:
            logger.error(f"Failed to send message to topic '{topic}'")

    async def monitor_kuksa(self):
        try:
            logger.info("Subscribing to location updates...")
            for update in self.kuksa_client.subscribe_current_values(
                [
                    "Vehicle.CurrentLocation.Latitude",
                    "Vehicle.CurrentLocation.Longitude",
                ]
            ):
                latitude_data = update.get("Vehicle.CurrentLocation.Latitude")
                longitude_data = update.get("Vehicle.CurrentLocation.Longitude")

                if latitude_data is None or longitude_data is None:
                    logger.warning(
                        "Received None for location data. Skipping this update."
                    )
                    continue

                updated_latitude = latitude_data.value
                updated_longitude = longitude_data.value

                if (
                    updated_latitude == COLLISION_LOCATION["latitude"]
                    and updated_longitude == COLLISION_LOCATION["longitude"]
                ):
                    collision_message = {
                        "vehicle_id": VEHICLE_ID,
                        "collision_location": COLLISION_LOCATION,
                        "status": "1",
                    }
                    message = json.dumps(collision_message)
                    self.publish_message(TOPIC_ACCIDENT, message)
                    logger.info(
                        f"{VEHICLE_ID} - Collision detected! Message: {collision_message}"
                    )
                else:
                    logger.debug(
                        f"{VEHICLE_ID} - No collision detected. Current position: Latitude = {updated_latitude}, Longitude = {updated_longitude}"
                    )

                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"KUKSA monitoring failed: {e}")

    async def run(self):
        asyncio.create_task(self.monitor_kuksa())
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            if self.message_to_display:
                self.display_message(self.message_to_display)
                time_difference = (
                    time.time() - self.message_display_time
                    if self.message_display_time is not None
                    else 0.0
                )
                if time_difference > 5:
                    self.message_to_display = None
                    self.collision_location = None
            else:
                screen.blit(background_image, (0, 0))
                pygame.display.flip()

            clock.tick(30)
            await asyncio.sleep(0.03)

    def display_message(self, text):
        screen.blit(background_image, (0, 0))
        screen.blit(warning_icon, (WIDTH // 2 - 50, HEIGHT // 2 - 150))
        message_surface = font_large.render(text, True, (255, 0, 0))
        screen.blit(
            message_surface,
            (WIDTH // 2 - message_surface.get_width() // 2, HEIGHT // 2),
        )
        speed_warning = "Reduce Speed Immediately!"
        speed_surface = font_small.render(speed_warning, True, (255, 255, 0))
        screen.blit(
            speed_surface,
            (WIDTH // 2 - speed_surface.get_width() // 2, HEIGHT // 2 + 100),
        )
        pygame.display.flip()


async def main():
    logger.info("Starting CustomVehicleApp...")
    app = CustomVehicleApp(vehicle)
    await app.run()


if __name__ == "__main__":
    LOOP = asyncio.get_event_loop()
    LOOP.add_signal_handler(signal.SIGTERM, LOOP.stop)
    try:
        LOOP.run_until_complete(main())
    finally:
        LOOP.close()
