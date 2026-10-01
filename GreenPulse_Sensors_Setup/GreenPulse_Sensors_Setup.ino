#include <DHT.h>

// =====================================================
// GreenPulse - ESP32-S3 Sensor Firmware
// Current sensors:
// 1. DHT11 - Temperature & Humidity
// 2. HW-080 + HW-103 - Soil Moisture
// =====================================================


// ---------------- DHT11 Configuration ----------------

#define DHTPIN 4
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);


// ------------- Soil Moisture Configuration -----------

#define SOIL_PIN 5


// =====================================================
// SETUP
// =====================================================

void setup() {

  // Start Serial Monitor
  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("================================");
  Serial.println("     GreenPulse Sensor System");
  Serial.println("================================");

  // Start DHT11
  dht.begin();

  // Configure soil moisture analog input
  pinMode(SOIL_PIN, INPUT);

  Serial.println("Sensors initialized.");
  Serial.println();
}


// =====================================================
// MAIN LOOP
// =====================================================

void loop() {

  // ---------------------------------------------------
  // Read DHT11
  // ---------------------------------------------------

  float humidity = dht.readHumidity();
  float temperature = dht.readTemperature();


  // ---------------------------------------------------
  // Read Soil Moisture Sensor
  // ---------------------------------------------------

  int soilRaw = analogRead(SOIL_PIN);


  // ---------------------------------------------------
  // Print DHT11 Results
  // ---------------------------------------------------

  Serial.println("---------- Sensor Readings ----------");

  if (isnan(humidity) || isnan(temperature)) {

    Serial.println("DHT11: Failed to read sensor!");

  } else {

    Serial.print("Temperature       : ");
    Serial.print(temperature);
    Serial.println(" °C");

    Serial.print("Humidity          : ");
    Serial.print(humidity);
    Serial.println(" %");
  }


  // ---------------------------------------------------
  // Print Soil Moisture Result
  // ---------------------------------------------------

  Serial.print("Soil Moisture RAW : ");
  Serial.println(soilRaw);


  Serial.println("-------------------------------------");
  Serial.println();


  // Wait 2 seconds before next measurement
  delay(2000);
}