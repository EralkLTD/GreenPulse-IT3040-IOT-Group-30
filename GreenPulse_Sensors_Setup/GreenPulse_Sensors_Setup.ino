#include <Wire.h>
#include <DHT.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// =====================================================
// GreenPulse - Sensor + OLED + LED Integration Test
//
// Components:
// 1. DHT11 - Temperature & Humidity
// 2. Soil Moisture Sensor - Analog
// 3. SSD1306 OLED Display
// 4. RGB LED - single-channel test
// =====================================================


// ---------------- DHT11 ----------------

#define DHTPIN 4
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);


// ---------------- Soil Moisture ----------------

#define SOIL_PIN 5


// ---------------- RGB LED ----------------

// One RGB channel only for now.
// GPIO 6 -> 270 ohm resistor -> RGB LED color leg

#define LED_PIN 6


// ---------------- OLED ----------------

#define SDA_PIN 8
#define SCL_PIN 9

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

Adafruit_SSD1306 display(
  SCREEN_WIDTH,
  SCREEN_HEIGHT,
  &Wire,
  OLED_RESET
);


// =====================================================
// SETUP
// =====================================================

void setup() {

  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("GreenPulse Sensor + LED Test");
  Serial.println("----------------------------");

  // Start DHT11
  dht.begin();

  // Configure soil sensor ADC
  analogReadResolution(12);

  // Configure LED
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Start I2C
  Wire.begin(SDA_PIN, SCL_PIN);

  // Start OLED
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {

    Serial.println("ERROR: OLED initialization failed!");

    while (true) {
      delay(1000);
    }
  }

  Serial.println("OLED initialized successfully.");

  // ---------------- Startup Screen ----------------

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(2);
  display.setCursor(5, 10);
  display.println("GreenPulse");

  display.setTextSize(1);
  display.setCursor(22, 40);
  display.println("Sensor System");

  display.setCursor(27, 52);
  display.println("Starting...");

  display.display();

  // LED startup test
  digitalWrite(LED_PIN, HIGH);
  delay(1000);

  digitalWrite(LED_PIN, LOW);
  delay(1000);
}


// =====================================================
// LOOP
// =====================================================

void loop() {

  // ---------------- Read DHT11 ----------------

  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();


  // ---------------- Read Soil Sensor ----------------

  int soilRaw = analogRead(SOIL_PIN);


  // ---------------- Determine Sensor Status ----------------

  bool dhtOK =
    !isnan(temperature) &&
    !isnan(humidity);


  // ---------------- LED ----------------
  //
  // Temporary logic:
  //
  // LED ON  = sensors are being read successfully
  // LED OFF = DHT11 read failure
  //
  // Later we will replace this with proper
  // GreenPulse threshold logic.

  if (dhtOK) {

    digitalWrite(LED_PIN, HIGH);

  } else {

    digitalWrite(LED_PIN, LOW);
  }


  // ---------------- Serial Monitor ----------------

  Serial.println();
  Serial.println("------ GreenPulse Readings ------");

  if (!dhtOK) {

    Serial.println("DHT11: Read failed!");

  } else {

    Serial.print("Temperature : ");
    Serial.print(temperature, 1);
    Serial.println(" C");

    Serial.print("Humidity    : ");
    Serial.print(humidity, 1);
    Serial.println(" %");
  }

  Serial.print("Soil RAW    : ");
  Serial.println(soilRaw);

  Serial.print("LED Status  : ");

  if (dhtOK) {
    Serial.println("ON");
  } else {
    Serial.println("OFF");
  }

  Serial.println("---------------------------------");


  // ---------------- OLED ----------------

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);


  // Header

  display.setTextSize(1);
  display.setCursor(34, 0);
  display.println("GreenPulse");

  display.drawLine(0, 10, 127, 10, SSD1306_WHITE);


  // Temperature

  display.setCursor(0, 17);
  display.print("Temp : ");

  if (isnan(temperature)) {

    display.println("ERROR");

  } else {

    display.print(temperature, 1);
    display.println(" C");
  }


  // Humidity

  display.setCursor(0, 30);
  display.print("Hum  : ");

  if (isnan(humidity)) {

    display.println("ERROR");

  } else {

    display.print(humidity, 1);
    display.println(" %");
  }


  // Soil moisture

  display.setCursor(0, 43);
  display.print("Soil : ");
  display.println(soilRaw);


  // Status

  display.drawLine(0, 54, 127, 54, SSD1306_WHITE);

  display.setCursor(0, 56);
  display.print("Status: ");

  if (dhtOK) {

    display.print("OK");

  } else {

    display.print("CHECK");
  }


  // Update OLED

  display.display();


  // DHT11 should not be sampled too quickly

  delay(2000);
}