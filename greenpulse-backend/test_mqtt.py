
import paho.mqtt.client as mqtt
import time
from greenpulse.config import Config
Config.validate()
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, 'test_pub')
client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD)
client.tls_set()
client.connect(Config.MQTT_HOST, Config.MQTT_PORT)
client.loop_start()
client.publish('greenpulse/device01/config', '{\"plant_type\":\"Pea\"}', qos=1)
time.sleep(2)
client.disconnect()
print('Published test message')

