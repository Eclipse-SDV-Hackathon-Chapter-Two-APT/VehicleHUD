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
import random
import signal
import sys
import time
from typing import Optional

import geopy.distance
import paho.mqtt.client as mqtt
import pygame
from kuksa_client.grpc import VSSClient  # KUKSA Client
from vehicle import Vehicle, vehicle
from velocitas_sdk.vehicle_app import VehicleApp

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# MQTT Configuration
BROKER_ADDRESS = "127.0.0.1"
PORT = 1883
TOPIC_ALERT = "alert/car"
TOPIC_WEATHER = "alert/weather"
TOPIC_ACCIDENT = "accident"


# KUKSA Configuration
KUKSA_HOST = "127.0.0.1"
KUKSA_PORT = 55555
VEHICLE_ID = "Vehicle1"


# Pygame Configuration
pygame.init()
WIDTH, HEIGHT = 1024, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Head-Up Display")
font_large = pygame.font.Font(None, 40)
font_small = pygame.font.Font(None, 20)
clock = pygame.time.Clock()

background_image = pygame.image.load("/workspaces/VehicleHUD/app/src/Hit&Run Case.png")
background_image = pygame.transform.scale(background_image, (WIDTH, HEIGHT))

weather_background_image = pygame.image.load(
    "/workspaces/VehicleHUD/app/src/Weather Alert Case.png"
)
weather_background_image = pygame.transform.scale(
    weather_background_image, (WIDTH, HEIGHT)
)

warning_icon = pygame.image.load("/workspaces/VehicleHUD/app/src/alert_msg.png")
warning_icon = pygame.transform.scale(warning_icon, (240, 175))

warning_speed_icon = pygame.image.load("app/src/alert_speed.png")
warning_speed_icon = pygame.transform.scale(warning_speed_icon, (280, 270))

warning_road_icon = pygame.image.load("/workspaces/VehicleHUD/app/src/alert_road.png")
warning_road_icon = pygame.transform.scale(warning_road_icon, (328, 99))

two_car_icon = pygame.image.load("/workspaces/VehicleHUD/app/src/signal.png")
two_car_icon = pygame.transform.scale(two_car_icon, (64, 64))

weather_speed_icon = pygame.image.load(
    "/workspaces/VehicleHUD/app/src/weather_speed.png"
)
weather_speed_icon = pygame.transform.scale(weather_speed_icon, (278 * 0.8, 269 * 0.8))

alert_weather_icon = pygame.image.load(
    "/workspaces/VehicleHUD/app/src/alert_weather.png"
)
alert_weather_icon = pygame.transform.scale(alert_weather_icon, (325, 279))


class CustomVehicleApp(VehicleApp):
    def __init__(self, vehicle_client: Vehicle):
        super().__init__()
        self.Vehicle = vehicle_client

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(BROKER_ADDRESS, PORT)
        self.mqtt_client.loop_start()

        self.kuksa_client = VSSClient(KUKSA_HOST, KUKSA_PORT)
        self.kuksa_client.connect()

        # Variables
        self.message_to_display: Optional[str] = None
        self.slide_value = 0
        self.humidity = 0
        self.slide_cnt = 0
        self.time_cnt = 0
        self.message_display_time: Optional[float] = None
        self.current_speed = random.randrange(66, 75)
        self.this_location = {"latitude": 50, "longitude": 9}
        self.collision_location = {"latitude": 100, "longitude": 9}

    async def on_stop(self):
        logger.info("Stopping MQTT and KUKSA Clients...")
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.kuksa_client.close()

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            logger.info("Connected to MQTT Broker successfully.")
            client.subscribe([(TOPIC_ALERT, 0), (TOPIC_WEATHER, 0)])
        else:
            logger.error(f"Failed to connect to MQTT Broker: {reason_code}")

    def on_message(self, client, userdata, message):
        try:
            decoded_message = message.payload.decode("utf-8")
            data = json.loads(decoded_message)

            if message.topic == TOPIC_WEATHER:
                self.slide_value = data.get("slide_value", 0)
                self.humidity = data.get("humidity", 0)
                if self.slide_value >= 500:
                    self.slide_cnt += 1
                self.message_to_display = f"Slide Count: {self.slide_cnt}"
                logger.info(f"Weather Data Received: {data}")
            elif message.topic == TOPIC_ALERT:
                self.collision_location = data.get("collision_location")
                logger.info(self.collision_location)
                accident_distance = geopy.distance.distance(
                    (
                        self.collision_location["latitude"],
                        self.collision_location["longitude"],
                    ),
                    (self.this_location["latitude"], self.this_location["longitude"]),
                ).km
                self.message_to_display = (
                    f"Collision Distance: {round(accident_distance, 1)} KM"
                    # f"Collision Distance: {0} KM"
                )

                logger.info(f"Collision Data Received: {data}")
                logger.info(f"{self.message_to_display}")

            self.message_display_time = time.time()
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def monitor_kuksa(self):
        try:
            logger.info("Subscribing to KUKSA data...")
            for update in self.kuksa_client.subscribe_current_values(
                [
                    "Vehicle.CurrentLocation.Latitude",
                    "Vehicle.CurrentLocation.Longitude",
                ]
            ):
                latitude = update.get("Vehicle.CurrentLocation.Latitude").value
                longitude = update.get("Vehicle.CurrentLocation.Longitude").value

                if latitude and longitude:
                    self.this_location["latitude"] = latitude
                    self.this_location["longitude"] = longitude
                    logger.info(self.this_location["latitude"])
        except Exception as e:
            logger.error(f"KUKSA monitoring failed: {e}")

    async def run(self):
        asyncio.create_task(self.monitor_kuksa())
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            # self.this_location["latitude"] -= 0.05
            # self.this_location["longitude"] -= 0.03
            # # logger.info(f"{pro}")
            if self.message_to_display:
                # logger.info(f"{self.message_to_display}")
                self.display_message(self.message_to_display)
                if time.time() - self.message_display_time > 5:
                    self.message_to_display = None
            else:
                screen.blit(background_image, (0, 0))
                pygame.display.flip()
            # logger.info("dsddas")

            clock.tick(30)
            await asyncio.sleep(0.03)

    def display_message(self, text):
        if "Slide Count" in text:
            logger.info("Displaying weather-related warning...")
            screen.blit(weather_background_image, (0, 0))
            screen.blit(weather_speed_icon, (WIDTH // 2 - 330, HEIGHT // 2 - 90))
            screen.blit(alert_weather_icon, (WIDTH // 2 - 125, HEIGHT // 2 - 120))
            screen.blit(two_car_icon, (WIDTH // 2 - 350, HEIGHT // 2 - 80))
            # message_surface = font_large.render(text, True, (0, 255, 0))
            # screen.blit(message_surface, (WIDTH // 2 + 120, HEIGHT // 2 - 50))
        else:
            logger.info("Displaying collision-related warning...")
            screen.blit(background_image, (0, 0))
            if self.collision_location["latitude"] < 52:
                screen.blit(warning_speed_icon, (WIDTH // 2 - 330, HEIGHT // 2 - 90))
            screen.blit(warning_icon, (WIDTH // 2, HEIGHT // 2 - 120))
            screen.blit(warning_road_icon, (WIDTH // 2 + 10, HEIGHT // 2 + 40))
            message_surface = font_large.render(text, True, (255, 0, 0))
            screen.blit(message_surface, (WIDTH // 2 + 120, HEIGHT // 2 - 50))
        pygame.display.flip()

    # pygame.display.flip()  # 화면 업데이트
    # def display_message(self, text):
    #     # logger.info(ds)
    #     #  normal
    #     screen.blit(background_image, (0, 0))
    #     logger.info(self.collision_location["latitude"])
    #     if self.collision_location["latitude"] < 52:
    #         screen.blit(warning_speed_icon, (WIDTH // 2 - 330, HEIGHT // 2 - 90))
    #     screen.blit(warning_icon, (WIDTH // 2, HEIGHT // 2 - 120))
    #     screen.blit(warning_road_icon, (WIDTH // 2 + 10, HEIGHT // 2 + 40))
    #     message_surface = font_large.render(text, True, (255, 255, 255))
    #     screen.blit(message_surface, (WIDTH // 2 + 120, HEIGHT // 2 - 50))

    #     # weather implement

    #     if self.collision_location["latitude"] < 52:
    #         screen.blit(weather_speed_icon, (WIDTH // 2 - 330, HEIGHT // 2 - 90))
    #     screen.blit(alert_weather_icon, (WIDTH // 2, HEIGHT // 2 - 120))
    #     message_surface = font_large.render(text, True, (255, 255, 255))
    #     screen.blit(two_car_icon, (WIDTH // 2 + 10, HEIGHT // 2 + 40))
    #     screen.blit(message_surface, (WIDTH // 2 + 120, HEIGHT // 2 - 50))
    #     pygame.display.flip()


# weather_speed_icon,  alert_weather_icon,  two_car_icon


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
