/* GreenPulse ESP32 firmware — Arduino-ESP32 3.x, ArduinoJson 7.x
   Libraries: DHT sensor library, Adafruit Unified Sensor, OneWire,
   DallasTemperature, Adafruit GFX, Adafruit SSD1306, PubSubClient, ArduinoJson.
   IMPORTANT: enter your own Wi-Fi and HiveMQ credentials and the CURRENT
   trusted ROOT CA for the HiveMQ endpoint. Never commit secrets to Git.
*/
#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <time.h>
#include <math.h>

// ---- Set these locally. Do not commit real passwords. ----
const char* WIFI_SSID = "SLT-Fiber-2.4G_c6f0";
const char* WIFI_PASSWORD = "join6675";
const char* MQTT_HOST = "greenpulse-e7d7a235.a01.euc1.aws.hivemq.cloud";
const uint16_t MQTT_PORT = 8883;
const char* MQTT_USERNAME = "greenpulse_backend";
const char* MQTT_PASSWORD = "Green12345";

// Paste the trusted PEM ROOT CA that validates the CURRENT HiveMQ endpoint.
// The placeholder intentionally prevents insecure operation.
static const char ROOT_CA[] PROGMEM = R"PEM(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----

)PEM";

const char* DEVICE_ID = "device01";
const char* TOPIC_TELEMETRY = "greenpulse/device01/telemetry";
const char* TOPIC_STATUS = "greenpulse/device01/status";
const char* TOPIC_PROFILE = "greenpulse/device01/profile";
const char* TOPIC_AI = "greenpulse/device01/ai";

constexpr uint8_t PIN_DHT=4, PIN_SOIL=5, PIN_LDR=6, PIN_BUTTON=7;
constexpr uint8_t PIN_SDA=8, PIN_SCL=9, PIN_BLUE=10, PIN_GREEN=11, PIN_RED=12, PIN_DS18B20=13;
constexpr int SOIL_DRY=4095, SOIL_WET=1500;
constexpr uint32_t SENSOR_MS=2000, PUBLISH_MS=5000, WIFI_RETRY_MS=10000, MQTT_RETRY_MS=5000;

DHT dht(PIN_DHT,DHT11);
OneWire oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);
Adafruit_SSD1306 display(128,64,&Wire,-1);
WiFiClientSecure tlsClient;
PubSubClient mqtt(tlsClient);

struct Range { float min,max; };
Range airRange{20,35}, humidityRange{40,85}, soilRange{30,80}, soilTempRange{15,35};
float airTemp=NAN, humidity=NAN, soilTemp=NAN;
int soilRaw=0, soilPercent=0;
String light="UNKNOWN", plant="Not Synced", lightPreference="EITHER", aiTip="", aiPriority="";
bool oledReady=false, profileSynced=false;
uint8_t screenIndex=0;
bool buttonLast=HIGH, buttonStable=HIGH;
uint32_t debounceAt=0, lastSensor=0, lastPublish=0, lastWiFiTry=0, lastMqttTry=0;

void rgb(bool r,bool g,bool b){digitalWrite(PIN_RED,r);digitalWrite(PIN_GREEN,g);digitalWrite(PIN_BLUE,b);}
bool outOfRange(float x,Range r){return isfinite(x)&&(x<r.min||x>r.max);}
void updateLed(){
  if(!isfinite(airTemp)||!isfinite(humidity)||!isfinite(soilTemp)){rgb(false,false,true);return;}
  bool bad=outOfRange(airTemp,airRange)||outOfRange(humidity,humidityRange)||
    outOfRange(soilPercent,soilRange)||outOfRange(soilTemp,soilTempRange)||
    (profileSynced&&lightPreference!="EITHER"&&lightPreference!=light);
  if(bad)rgb(true,false,false);else rgb(false,true,false);
}
void printFloatOrDash(float v,uint8_t digits=1){if(isfinite(v))display.print(v,digits);else display.print("ERR");}
void drawDisplay(){
  if(!oledReady)return;
  display.clearDisplay();display.setTextColor(SSD1306_WHITE);display.setTextSize(1);
  display.setCursor(0,0);display.print("GreenPulse ");display.print(mqtt.connected()?"MQTT":"LOCAL");
  display.drawLine(0,10,127,10,SSD1306_WHITE);
  display.setCursor(0,15);
  switch(screenIndex){
    case 0:
      display.print("Air: ");printFloatOrDash(airTemp);display.println(" C");
      display.print("Hum: ");printFloatOrDash(humidity);display.println(" %");
      display.print("Moist: ");display.print(soilPercent);display.println(" %");
      display.print("Light: ");display.println(light);
      display.print("Soil T: ");printFloatOrDash(soilTemp);display.println(" C");break;
    case 1:display.println("AIR TEMPERATURE");display.setTextSize(2);display.setCursor(0,32);printFloatOrDash(airTemp);display.print(" C");break;
    case 2:display.println("HUMIDITY");display.setTextSize(2);display.setCursor(0,32);printFloatOrDash(humidity);display.print(" %");break;
    case 3:display.println("SOIL MOISTURE");display.setTextSize(2);display.setCursor(0,30);display.print(soilPercent);display.println(" %");display.setTextSize(1);display.print("Raw: ");display.print(soilRaw);break;
    case 4:display.println("LIGHT LEVEL");display.setTextSize(2);display.setCursor(0,30);display.println(light);display.setTextSize(1);display.print("Target: ");display.print(lightPreference);break;
    case 5:display.println("SOIL TEMPERATURE");display.setTextSize(2);display.setCursor(0,32);printFloatOrDash(soilTemp);display.print(" C");break;
    case 6:display.println("ACTIVE PLANT");display.setTextSize(1);display.setCursor(0,30);display.println(plant);display.setCursor(0,52);display.print(profileSynced?"PROFILE SYNCED":"NOT SYNCED");break;
  }
  display.display();
}
void readSensors(){
  float t=dht.readTemperature(),h=dht.readHumidity();
  airTemp=(isfinite(t)?t:NAN);humidity=(isfinite(h)?h:NAN);
  soilRaw=analogRead(PIN_SOIL);
  soilPercent=constrain(map(soilRaw,SOIL_DRY,SOIL_WET,0,100),0,100);
  light=digitalRead(PIN_LDR)==LOW?"BRIGHT":"DARK";
  ds18b20.requestTemperatures();float st=ds18b20.getTempCByIndex(0);
  soilTemp=(st!=DEVICE_DISCONNECTED_C&&st>-100&&st<125)?st:NAN;
  updateLed();drawDisplay();
}
void handleButton(){
  bool v=digitalRead(PIN_BUTTON);
  if(v!=buttonLast)debounceAt=millis();
  if(millis()-debounceAt>50&&v!=buttonStable){buttonStable=v;if(v==LOW){screenIndex=(screenIndex+1)%7;drawDisplay();}}
  buttonLast=v;
}
void setRange(JsonVariantConst v,Range& r){
  if(v.is<JsonObjectConst>()&&!v["min"].isNull()&&!v["max"].isNull()){
    float lo=v["min"].as<float>(),hi=v["max"].as<float>();
    if(isfinite(lo)&&isfinite(hi)&&lo<hi){r.min=lo;r.max=hi;}
  }
}
void onMessage(char* topic,byte* data,unsigned int length){
  JsonDocument doc;
  auto err=deserializeJson(doc,data,length);
  if(err){Serial.printf("MQTT JSON parse failed on %s: %s\n",topic,err.c_str());return;}
  String t(topic);
  if(t==TOPIC_PROFILE){
    if(!doc["plant"].is<const char*>()){Serial.println("Profile missing plant");return;}
    plant=doc["plant"].as<String>();
    setRange(doc["air_temperature"],airRange);setRange(doc["humidity"],humidityRange);
    setRange(doc["soil_moisture"],soilRange);setRange(doc["soil_temperature"],soilTempRange);
    lightPreference=doc["light_preference"].is<const char*>()?doc["light_preference"].as<String>():"EITHER";
    lightPreference.toUpperCase();profileSynced=true;
    Serial.printf("Profile synced: %s\n",plant.c_str());updateLed();drawDisplay();
  }else if(t==TOPIC_AI){
    aiPriority=doc["priority"].is<const char*>()?doc["priority"].as<String>():"";
    aiTip=doc["care_tip"].is<const char*>()?doc["care_tip"].as<String>():"";
    Serial.printf("AI update priority=%s\n",aiPriority.c_str());
  }
}
void publishStatus(const char* state){
  if(!mqtt.connected())return;
  JsonDocument doc;doc["device_id"]=DEVICE_ID;doc["status"]=state;
  char buf[128];size_t n=serializeJson(doc,buf,sizeof(buf));
  bool ok=mqtt.publish(TOPIC_STATUS,(const uint8_t*)buf,n,true);
  Serial.printf("Status publish: %s\n",ok?"OK":"FAILED");
}
void publishTelemetry(){
  if(!mqtt.connected())return;
  JsonDocument doc;doc["device_id"]=DEVICE_ID;
  if(isfinite(airTemp))doc["air_temperature"]=airTemp;else doc["air_temperature"]=nullptr;
  if(isfinite(humidity))doc["humidity"]=humidity;else doc["humidity"]=nullptr;
  doc["soil_moisture"]=soilPercent;doc["soil_moisture_raw"]=soilRaw;
  if(isfinite(soilTemp))doc["soil_temperature"]=soilTemp;else doc["soil_temperature"]=nullptr;
  doc["light"]=light;
  char buf[512];size_t n=serializeJson(doc,buf,sizeof(buf));
  bool ok=mqtt.publish(TOPIC_TELEMETRY,(const uint8_t*)buf,n,false);
  Serial.printf("Telemetry %s: %s\n",ok?"published":"FAILED",buf);
}
void connectWiFi(){
  if(WiFi.status()==WL_CONNECTED)return;
  lastWiFiTry=millis();Serial.println("Connecting to Wi-Fi...");
  WiFi.mode(WIFI_STA);WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
  uint32_t started=millis();
  while(WiFi.status()!=WL_CONNECTED&&millis()-started<10000)delay(200);
  if(WiFi.status()==WL_CONNECTED){Serial.print("Wi-Fi connected, IP: ");Serial.println(WiFi.localIP());}
  else Serial.println("Wi-Fi not connected; retrying later");
}
bool clockReady(){return time(nullptr)>1700000000;}
void connectMQTT(){
  if(WiFi.status()!=WL_CONNECTED||mqtt.connected())return;
  lastMqttTry=millis();
  if(!clockReady()){Serial.println("Waiting for NTP time sync before TLS...");return;}
  String id="greenpulse_esp32_"+String((uint32_t)(ESP.getEfuseMac()>>16),HEX);
  const char* will="{\"device_id\":\"device01\",\"status\":\"OFFLINE\"}";
  Serial.println("Connecting to HiveMQ with verified TLS...");
  bool ok=mqtt.connect(id.c_str(),MQTT_USERNAME,MQTT_PASSWORD,TOPIC_STATUS,1,true,will);
  if(ok){
    Serial.println("HiveMQ connected securely");
    Serial.printf("Profile subscription: %s\n",mqtt.subscribe(TOPIC_PROFILE,1)?"OK":"FAILED");
    Serial.printf("AI subscription: %s\n",mqtt.subscribe(TOPIC_AI,1)?"OK":"FAILED");
    publishStatus("ONLINE");drawDisplay();
  }else Serial.printf("HiveMQ connect failed, MQTT state=%d, TLS lastError=%d\n",mqtt.state(),tlsClient.lastError(nullptr,0));
}
void setup(){
  Serial.begin(115200);delay(500);Serial.println("\nGreenPulse starting...");
  pinMode(PIN_BUTTON,INPUT_PULLUP);pinMode(PIN_SOIL,INPUT);pinMode(PIN_LDR,INPUT);
  pinMode(PIN_RED,OUTPUT);pinMode(PIN_GREEN,OUTPUT);pinMode(PIN_BLUE,OUTPUT);rgb(false,false,true);
  analogReadResolution(12);dht.begin();ds18b20.begin();Wire.begin(PIN_SDA,PIN_SCL);
  oledReady=display.begin(SSD1306_SWITCHCAPVCC,0x3C);
  if(!oledReady)Serial.println("OLED unavailable; MQTT and sensors continue");
  drawDisplay();
  mqtt.setServer(MQTT_HOST,MQTT_PORT);mqtt.setCallback(onMessage);mqtt.setBufferSize(2048);
  if(strstr(ROOT_CA,"REPLACE_WITH_VERIFIED")!=nullptr){
    Serial.println("ERROR: Set ROOT_CA to the trusted CA PEM for your HiveMQ endpoint before MQTT can connect");
  }else tlsClient.setCACert(ROOT_CA);
  connectWiFi();
  if(WiFi.status()==WL_CONNECTED){configTime(0,0,"pool.ntp.org","time.google.com");}
  readSensors();lastSensor=millis();lastPublish=millis();
}
void loop(){
  handleButton();
  if(WiFi.status()!=WL_CONNECTED){
    if(millis()-lastWiFiTry>=WIFI_RETRY_MS){connectWiFi();if(WiFi.status()==WL_CONNECTED)configTime(0,0,"pool.ntp.org","time.google.com");}
  }else{
    if(!mqtt.connected()&&millis()-lastMqttTry>=MQTT_RETRY_MS){
      if(strstr(ROOT_CA,"REPLACE_WITH_VERIFIED")==nullptr)connectMQTT();
    }
    if(mqtt.connected())mqtt.loop();
  }
  if(millis()-lastSensor>=SENSOR_MS){lastSensor=millis();readSensors();}
  if(millis()-lastPublish>=PUBLISH_MS){lastPublish=millis();publishTelemetry();}
  delay(2);
}
