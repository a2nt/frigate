import os
import cv2
import imutils
import time
import datetime
import ctypes
import logging
import multiprocessing as mp
import queue
import threading
import json
import yaml
from contextlib import closing
import numpy as np
from object_detection.utils import visualization_utils as vis_util
from flask import Flask, Response, make_response, send_file
import paho.mqtt.client as mqtt

from frigate.util import tonumpyarray
from frigate.mqtt import MqttMotionPublisher, MqttObjectPublisher
from frigate.objects import ObjectParser, ObjectCleaner, BestPersonFrame
from frigate.motion import detect_motion
from frigate.video import fetch_frames, FrameTracker, Camera
from frigate.object_detection import FramePrepper, PreppedQueueProcessor

with open('/config/config.yml') as f:
    # use safe_load instead load
    CONFIG = yaml.safe_load(f)

MQTT_HOST = CONFIG['mqtt']['host']
MQTT_PORT = CONFIG.get('mqtt', {}).get('port', 1883)
MQTT_TOPIC_PREFIX = CONFIG.get('mqtt', {}).get('topic_prefix', 'frigate')
MQTT_USER = CONFIG.get('mqtt', {}).get('user')
MQTT_PASS = CONFIG.get('mqtt', {}).get('password')

WEB_PORT = CONFIG.get('web_port', 5000)
DEBUG = (CONFIG.get('debug', '0') == '1')

def main():
    # connect to mqtt and setup last will
    def on_connect(client, userdata, flags, rc):
        print("On connect called")
        # publish a message to signal that the service is running
        client.publish(MQTT_TOPIC_PREFIX+'/available', 'online', retain=True)
    client = mqtt.Client()
    client.on_connect = on_connect
    client.will_set(MQTT_TOPIC_PREFIX+'/available', payload='offline', qos=1, retain=True)
    if not MQTT_USER is None:
        client.username_pw_set(MQTT_USER, password=MQTT_PASS)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    
    # Queue for prepped frames
    # TODO: set length to 1.5x the number of total regions
    prepped_frame_queue = queue.Queue(6)


    camera = Camera('back', CONFIG['cameras']['back'], prepped_frame_queue, client, MQTT_TOPIC_PREFIX)

    cameras = {
        'back': camera
    }

    prepped_queue_processor = PreppedQueueProcessor(
        cameras,
        prepped_frame_queue
    )
    prepped_queue_processor.start()

    camera.start()
    camera.join()

    # create a flask app that encodes frames a mjpeg on demand
    # app = Flask(__name__)

    # @app.route('/best_person.jpg')
    # def best_person():
    #     frame = np.zeros(frame_shape, np.uint8) if camera.get_best_person() is None else camera.get_best_person()
    #     ret, jpg = cv2.imencode('.jpg', frame)
    #     response = make_response(jpg.tobytes())
    #     response.headers['Content-Type'] = 'image/jpg'
    #     return response

    # @app.route('/')
    # def index():
    #     # return a multipart response
    #     return Response(imagestream(),
    #                     mimetype='multipart/x-mixed-replace; boundary=frame')
    # def imagestream():
    #     while True:
    #         # max out at 5 FPS
    #         time.sleep(0.2)
    #         # make a copy of the current detected objects
    #         detected_objects = DETECTED_OBJECTS.copy()
    #         # lock and make a copy of the current frame
    #         with frame_lock:
    #             frame = frame_arr.copy()
    #         # convert to RGB for drawing
    #         frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    #         # draw the bounding boxes on the screen
    #         for obj in detected_objects:
    #             vis_util.draw_bounding_box_on_image_array(frame,
    #                 obj['ymin'],
    #                 obj['xmin'],
    #                 obj['ymax'],
    #                 obj['xmax'],
    #                 color='red',
    #                 thickness=2,
    #                 display_str_list=["{}: {}%".format(obj['name'],int(obj['score']*100))],
    #                 use_normalized_coordinates=False)

    #         for region in regions:
    #             color = (255,255,255)
    #             cv2.rectangle(frame, (region['x_offset'], region['y_offset']), 
    #                 (region['x_offset']+region['size'], region['y_offset']+region['size']), 
    #                 color, 2)

    #         # convert back to BGR
    #         frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    #         # encode the image into a jpg
    #         ret, jpg = cv2.imencode('.jpg', frame)
    #         yield (b'--frame\r\n'
    #             b'Content-Type: image/jpeg\r\n\r\n' + jpg.tobytes() + b'\r\n\r\n')

    # app.run(host='0.0.0.0', port=WEB_PORT, debug=False)

if __name__ == '__main__':
    main()