#include <Wire.h>
#include <DHT.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// =====================================================
// GreenPulse - Integrated Sensor Monitoring Firmware
//
// Hardware:
// 1. DHT11 Temperature & Humidity Sensor
// 2. Soil Moisture Sensor
// 3. SSD1306 128x64 OLED
// 4. RGB LED
// 5. Push Button
//
// OLED pages:
// 0 - Overall Status
// 1 - Temperature
// 2 - Humidity
// 3 - Soil Moisture
// =====================================================


// =====================================================
// PIN CONFIGURATION
// =====================================================

// DHT11
#define DHTPIN 4
#define DHTTYPE DHT11

// Soil moisture
#define SOIL_PIN 5

// Push button
#define BUTTON_PIN 7

// OLED I2C
#define SDA_PIN 8
#define SCL_PIN 9

// RGB LED
// IMPORTANT:
// Keep this GPIO set to the pin you already used successfully
// for your LED test.
#define LED_PIN 6


// =====================================================
// OLED CONFIGURATION
// =====================================================

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
// DHT OBJECT
// =====================================================

DHT dht(DHTPIN, DHTTYPE);


// =====================================================
// SENSOR VALUES
// =====================================================

float temperature = 0.0;
float humidity = 0.0;
int soilRaw = 0;

bool dhtValid = false;


// =====================================================
// TEMPORARY THRESHOLDS
// =====================================================
//
// These are TEST thresholds.
// Soil threshold MUST be calibrated later.
//
// Change these after collecting real sensor data.
// =====================================================

const float TEMP_LOW = 20.0;
const float TEMP_HIGH = 35.0;

const float HUMIDITY_LOW = 40.0;
const float HUMIDITY_HIGH = 85.0;

// TEMPORARY soil threshold.
//
// Your sensor previously showed high RAW values when dry.
// Therefore:
//
// Higher RAW = drier
//
// This value is NOT final.
//
const int SOIL_DRY_THRESHOLD = 3000;


// =====================================================
// BUTTON VARIABLES
// =====================================================

int currentScreen = 0;

bool lastButtonReading = HIGH;
bool stableButtonState = HIGH;

unsigned long lastDebounceTime = 0;

const unsigned long debounceDelay = 50;


// =====================================================
// SENSOR TIMING
// =====================================================
//
// DHT11 should not be read continuously.
// Read sensors every 2 seconds.
// =====================================================

unsigned long lastSensorRead = 0;

const unsigned long sensorInterval = 2000;


// =====================================================
// FUNCTION DECLARATIONS
// =====================================================

void readSensors();
void handleButton();
void updateDisplay();
void updateLED();

void showStatusScreen();
void showTemperatureScreen();
void showHumidityScreen();
void showSoilScreen();


// =====================================================
// SETUP
// =====================================================

void setup() {

  // ---------------------------------------------------
  // IMPORTANT:
  // No Serial.begin() here.
  //
  // The device operates completely independently
  // from Arduino Serial Monitor.
  // ---------------------------------------------------


  // Push button
  pinMode(BUTTON_PIN, INPUT_PULLUP);


  // LED
  pinMode(LED_PIN, OUTPUT);

  digitalWrite(LED_PIN, LOW);


  // Start DHT11
  dht.begin();


  // ESP32 ADC
  analogReadResolution(12);


  // Start I2C
  Wire.begin(SDA_PIN, SCL_PIN);


  // Start OLED
  if (!display.begin(
        SSD1306_SWITCHCAPVCC,
        SCREEN_ADDRESS)) {

    // OLED initialization failed
    while (true) {

      // Flash LED to indicate hardware error
      digitalWrite(LED_PIN, HIGH);
      delay(200);

      digitalWrite(LED_PIN, LOW);
      delay(200);
    }
  }


  // ---------------------------------------------------
  // Startup screen
  // ---------------------------------------------------

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(2);
  display.setCursor(5, 10);
  display.println("GreenPulse");

  display.setTextSize(1);

  display.setCursor(20, 40);
  display.println("Sensor System");

  display.setCursor(30, 52);
  display.println("Starting...");

  display.display();


  delay(1500);


  // First sensor reading
  readSensors();

  updateLED();

  updateDisplay();
}


// =====================================================
// MAIN LOOP
// =====================================================

void loop() {

  // Handle button continuously
  handleButton();


  // ---------------------------------------------------
  // Read sensors every 2 seconds
  // ---------------------------------------------------

  if (millis() - lastSensorRead >= sensorInterval) {

    lastSensorRead = millis();

    readSensors();

    updateLED();

    updateDisplay();
  }


  // Prevent unnecessary CPU spinning
  delay(1);
}


// =====================================================
// READ SENSORS
// =====================================================

void readSensors() {

  // DHT11
  float newHumidity = dht.readHumidity();
  float newTemperature = dht.readTemperature();


  // Check DHT reading
  if (!isnan(newTemperature) &&
      !isnan(newHumidity)) {

    temperature = newTemperature;
    humidity = newHumidity;

    dhtValid = true;

  } else {

    dhtValid = false;
  }


  // Soil moisture
  soilRaw = analogRead(SOIL_PIN);
}


// =====================================================
// BUTTON HANDLING
// =====================================================

void handleButton() {

  bool reading = digitalRead(BUTTON_PIN);


  // Detect electrical state change
  if (reading != lastButtonReading) {

    lastDebounceTime = millis();
  }


  // Wait until button becomes stable
  if ((millis() - lastDebounceTime) >
      debounceDelay) {

    if (reading != stableButtonState) {

      stableButtonState = reading;


      // INPUT_PULLUP means:
      //
      // HIGH = released
      // LOW  = pressed

      if (stableButtonState == LOW) {

        currentScreen++;


        // Four screens:
        // 0, 1, 2, 3

        if (currentScreen > 3) {

          currentScreen = 0;
        }


        // Immediately update OLED
        updateDisplay();
      }
    }
  }


  lastButtonReading = reading;
}


// =====================================================
// DISPLAY CONTROLLER
// =====================================================

void updateDisplay() {

  switch (currentScreen) {

    case 0:

      showStatusScreen();

      break;


    case 1:

      showTemperatureScreen();

      break;


    case 2:

      showHumidityScreen();

      break;


    case 3:

      showSoilScreen();

      break;
  }
}


// =====================================================
// SCREEN 0
// OVERALL STATUS
// =====================================================

void showStatusScreen() {

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);


  // Header
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.print("GreenPulse");

  display.setCursor(92, 0);
  display.print("STATUS");


  display.drawLine(
    0,
    10,
    127,
    10,
    SSD1306_WHITE
  );


  // ---------------------------------------------------
  // Sensor error
  // ---------------------------------------------------

  if (!dhtValid) {

    display.setTextSize(2);

    display.setCursor(15, 18);
    display.println("ERROR");


    display.setTextSize(1);

    display.setCursor(10, 45);
    display.println("Check DHT11");


    display.display();

    return;
  }


  // ---------------------------------------------------
  // Determine problems
  // ---------------------------------------------------

  bool tempLow =
    temperature < TEMP_LOW;

  bool tempHigh =
    temperature > TEMP_HIGH;


  bool humidityLow =
    humidity < HUMIDITY_LOW;

  bool humidityHigh =
    humidity > HUMIDITY_HIGH;


  bool soilDry =
    soilRaw > SOIL_DRY_THRESHOLD;


  bool allGood =
    !tempLow &&
    !tempHigh &&
    !humidityLow &&
    !humidityHigh &&
    !soilDry;


  // ---------------------------------------------------
  // GOOD STATUS
  // ---------------------------------------------------

  if (allGood) {

    display.setTextSize(2);

    display.setCursor(32, 18);
    display.println("GOOD");


    display.setTextSize(1);

    display.setCursor(17, 43);
    display.println("All parameters");

    display.setCursor(32, 53);
    display.println("normal");
  }


  // ---------------------------------------------------
  // ATTENTION STATUS
  // ---------------------------------------------------

  else {

    display.setTextSize(2);

    display.setCursor(10, 14);
    display.println("ATTENTION");


    display.setTextSize(1);


    int y = 36;


    if (tempLow) {

      display.setCursor(0, y);
      display.println("Temperature: LOW");

      y += 10;
    }


    if (tempHigh) {

      display.setCursor(0, y);
      display.println("Temperature: HIGH");

      y += 10;
    }


    if (humidityLow) {

      display.setCursor(0, y);
      display.println("Humidity: LOW");

      y += 10;
    }


    if (humidityHigh) {

      display.setCursor(0, y);
      display.println("Humidity: HIGH");

      y += 10;
    }


    if (soilDry && y <= 56) {

      display.setCursor(0, y);
      display.println("Soil: DRY");
    }
  }


  display.display();
}


// =====================================================
// SCREEN 1
// TEMPERATURE
// =====================================================

void showTemperatureScreen() {

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);


  display.setTextSize(1);

  display.setCursor(32, 0);
  display.println("GreenPulse");


  display.drawLine(
    0,
    10,
    127,
    10,
    SSD1306_WHITE
  );


  display.setCursor(28, 16);
  display.println("TEMPERATURE");


  if (!dhtValid) {

    display.setTextSize(2);

    display.setCursor(30, 32);
    display.println("ERROR");

  } else {

    display.setTextSize(2);

    display.setCursor(22, 31);

    display.print(temperature, 1);

    display.print(" C");


    display.setTextSize(1);

    display.setCursor(38, 53);


    if (temperature < TEMP_LOW) {

      display.print("LOW");

    } else if (temperature > TEMP_HIGH) {

      display.print("HIGH");

    } else {

      display.print("NORMAL");
    }
  }


  display.display();
}


// =====================================================
// SCREEN 2
// HUMIDITY
// =====================================================

void showHumidityScreen() {

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);


  display.setTextSize(1);

  display.setCursor(32, 0);
  display.println("GreenPulse");


  display.drawLine(
    0,
    10,
    127,
    10,
    SSD1306_WHITE
  );


  display.setCursor(37, 16);
  display.println("HUMIDITY");


  if (!dhtValid) {

    display.setTextSize(2);

    display.setCursor(30, 32);
    display.println("ERROR");

  } else {

    display.setTextSize(2);

    display.setCursor(22, 31);

    display.print(humidity, 1);

    display.print(" %");


    display.setTextSize(1);

    display.setCursor(38, 53);


    if (humidity < HUMIDITY_LOW) {

      display.print("LOW");

    } else if (humidity > HUMIDITY_HIGH) {

      display.print("HIGH");

    } else {

      display.print("NORMAL");
    }
  }


  display.display();
}


// =====================================================
// SCREEN 3
// SOIL MOISTURE
// =====================================================

void showSoilScreen() {

  display.clearDisplay();

  display.setTextColor(SSD1306_WHITE);


  display.setTextSize(1);

  display.setCursor(32, 0);
  display.println("GreenPulse");


  display.drawLine(
    0,
    10,
    127,
    10,
    SSD1306_WHITE
  );


  display.setCursor(24, 16);
  display.println("SOIL MOISTURE");


  display.setTextSize(2);

  display.setCursor(32, 31);

  display.println(soilRaw);


  display.setTextSize(1);

  display.setCursor(38, 53);


  if (soilRaw > SOIL_DRY_THRESHOLD) {

    display.print("DRY");

  } else {

    display.print("OK");
  }


  display.display();
}


// =====================================================
// LED STATUS
// =====================================================

void updateLED() {

  // For now we use the connected LED channel
  // as an attention indicator.

  bool problem = false;


  if (!dhtValid) {

    problem = true;

  } else {

    if (temperature < TEMP_LOW ||
        temperature > TEMP_HIGH) {

      problem = true;
    }


    if (humidity < HUMIDITY_LOW ||
        humidity > HUMIDITY_HIGH) {

      problem = true;
    }


    if (soilRaw > SOIL_DRY_THRESHOLD) {

      problem = true;
    }
  }


  // LED ON = attention required
  // LED OFF = normal

  if (problem) {

    digitalWrite(LED_PIN, HIGH);

  } else {

    digitalWrite(LED_PIN, LOW);
  }
}