#include <Wire.h>
#include <DHT.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// =====================================================
// GREENPULSE - COMPLETE HARDWARE TEST
//
// Sensors:
// 1. DHT11 Temperature
// 2. DHT11 Humidity
// 3. Soil Moisture
// 4. MQ-135 Air Quality
//
// Interface:
// 5. SSD1306 OLED
// 6. Push Button
// 7. RGB Status LED
//
// OLED Screens:
// 0 = Overall Status
// 1 = Temperature
// 2 = Humidity
// 3 = Soil Moisture
// 4 = Air Quality
//
// RGB:
// GREEN = Normal
// RED   = Attention
// BLUE  = Sensor Error / Startup
// =====================================================


// =====================================================
// PIN DEFINITIONS
// =====================================================

#define MQ135_PIN 3

#define DHT_PIN 4
#define DHT_TYPE DHT11

#define SOIL_PIN 5

#define BUTTON_PIN 7

#define SDA_PIN 8
#define SCL_PIN 9

// Confirmed RGB mapping
#define BLUE_PIN  10
#define GREEN_PIN 11
#define RED_PIN   12


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
// DHT
// =====================================================

DHT dht(DHT_PIN, DHT_TYPE);


// =====================================================
// SENSOR VALUES
// =====================================================

float temperature = 0.0;
float humidity = 0.0;

int soilRaw = 0;
int airRaw = 0;

bool dhtValid = false;


// =====================================================
// TEMPORARY THRESHOLDS
// =====================================================
//
// These are only TEST thresholds.
// We will calibrate them later.
// =====================================================

const float TEMP_LOW = 20.0;
const float TEMP_HIGH = 35.0;

const float HUMIDITY_LOW = 40.0;
const float HUMIDITY_HIGH = 85.0;

// Higher soil reading currently means drier
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
// SENSOR UPDATE TIMER
// =====================================================

unsigned long lastSensorRead = 0;

const unsigned long sensorInterval = 2000;


// =====================================================
// FUNCTION DECLARATIONS
// =====================================================

void readSensors();

void handleButton();

void updateDisplay();

void showStatusScreen();
void showTemperatureScreen();
void showHumidityScreen();
void showSoilScreen();
void showAirQualityScreen();

void updateRGB();

void setRGB(
  bool red,
  bool green,
  bool blue
);


// =====================================================
// SETUP
// =====================================================

void setup() {

  // ---------------------------------------------------
  // IMPORTANT:
  // No Serial Monitor required.
  //
  // This avoids the button issue we previously had.
  // ---------------------------------------------------


  // Button
  pinMode(
    BUTTON_PIN,
    INPUT_PULLUP
  );


  // ADC inputs
  pinMode(
    MQ135_PIN,
    INPUT
  );

  pinMode(
    SOIL_PIN,
    INPUT
  );


  // RGB
  pinMode(
    RED_PIN,
    OUTPUT
  );

  pinMode(
    GREEN_PIN,
    OUTPUT
  );

  pinMode(
    BLUE_PIN,
    OUTPUT
  );


  // LED OFF
  setRGB(
    false,
    false,
    false
  );


  // Start DHT11
  dht.begin();


  // 12-bit ESP32 ADC
  analogReadResolution(12);


  // Start I2C
  Wire.begin(
    SDA_PIN,
    SCL_PIN
  );


  // ===================================================
  // OLED INITIALIZATION
  // ===================================================

  if (!display.begin(
        SSD1306_SWITCHCAPVCC,
        SCREEN_ADDRESS)) {

    // OLED failure
    // Flash BLUE forever

    while (true) {

      setRGB(
        false,
        false,
        true
      );

      delay(300);

      setRGB(
        false,
        false,
        false
      );

      delay(300);
    }
  }


  // ===================================================
  // STARTUP SCREEN
  // ===================================================

  display.clearDisplay();

  display.setTextColor(
    SSD1306_WHITE
  );


  display.setTextSize(2);

  display.setCursor(
    5,
    8
  );

  display.println(
    "GreenPulse"
  );


  display.setTextSize(1);

  display.setCursor(
    20,
    37
  );

  display.println(
    "Sensor System"
  );


  display.setCursor(
    23,
    51
  );

  display.println(
    "Starting..."
  );


  display.display();


  // BLUE during startup
  setRGB(
    false,
    false,
    true
  );


  delay(1500);


  // First sensor reading
  readSensors();

  updateRGB();

  updateDisplay();


  // Start timer from here
  lastSensorRead = millis();
}


// =====================================================
// MAIN LOOP
// =====================================================

void loop() {

  // Check button continuously
  handleButton();


  // Read sensors every 2 seconds
  if (
    millis() - lastSensorRead
    >= sensorInterval
  ) {

    lastSensorRead =
      millis();


    readSensors();


    updateRGB();


    updateDisplay();
  }


  // Very small delay only
  delay(1);
}


// =====================================================
// READ ALL SENSORS
// =====================================================

void readSensors() {

  // ===================================================
  // DHT11
  // ===================================================

  float newHumidity =
    dht.readHumidity();


  float newTemperature =
    dht.readTemperature();


  if (
    !isnan(newTemperature) &&
    !isnan(newHumidity)
  ) {

    temperature =
      newTemperature;

    humidity =
      newHumidity;

    dhtValid =
      true;

  } else {

    dhtValid =
      false;
  }


  // ===================================================
  // SOIL MOISTURE
  // ===================================================

  soilRaw =
    analogRead(SOIL_PIN);


  // ===================================================
  // MQ-135
  // ===================================================

  // Average several readings to make
  // the displayed value less jumpy.

  long mqTotal = 0;

  const int mqSamples = 10;


  for (
    int i = 0;
    i < mqSamples;
    i++
  ) {

    mqTotal +=
      analogRead(MQ135_PIN);

    delay(2);
  }


  airRaw =
    mqTotal / mqSamples;
}


// =====================================================
// BUTTON HANDLER
// =====================================================

void handleButton() {

  bool reading =
    digitalRead(BUTTON_PIN);


  // Button changed
  if (
    reading !=
    lastButtonReading
  ) {

    lastDebounceTime =
      millis();
  }


  // Debounce
  if (
    millis() - lastDebounceTime
    > debounceDelay
  ) {

    if (
      reading !=
      stableButtonState
    ) {

      stableButtonState =
        reading;


      // Button pressed
      if (
        stableButtonState == LOW
      ) {

        currentScreen++;


        // 5 screens
        if (
          currentScreen > 4
        ) {

          currentScreen = 0;
        }


        // Immediately redraw OLED
        updateDisplay();
      }
    }
  }


  lastButtonReading =
    reading;
}


// =====================================================
// RGB STATUS
// =====================================================

void updateRGB() {

  // ===================================================
  // BLUE = DHT SENSOR ERROR
  // ===================================================

  if (!dhtValid) {

    setRGB(
      false,
      false,
      true
    );

    return;
  }


  // ===================================================
  // CHECK CURRENT CONDITIONS
  // ===================================================

  bool tempProblem =

    temperature < TEMP_LOW ||

    temperature > TEMP_HIGH;


  bool humidityProblem =

    humidity < HUMIDITY_LOW ||

    humidity > HUMIDITY_HIGH;


  bool soilProblem =

    soilRaw >
    SOIL_DRY_THRESHOLD;


  // ===================================================
  // IMPORTANT:
  //
  // MQ-135 is NOT used to trigger RED yet.
  //
  // We need to establish its baseline/calibration
  // before deciding what RAW value means bad air.
  // ===================================================


  // RED = Attention required

  if (
    tempProblem ||
    humidityProblem ||
    soilProblem
  ) {

    setRGB(
      true,
      false,
      false
    );

    return;
  }


  // GREEN = current calibrated/test
  // conditions are normal

  setRGB(
    false,
    true,
    false
  );
}


// =====================================================
// RGB OUTPUT
// =====================================================
//
// Your LED is currently wired as common cathode:
//
// HIGH = ON
// LOW  = OFF
//
// Confirmed mapping:
//
// GPIO 12 = RED
// GPIO 11 = GREEN
// GPIO 10 = BLUE
// =====================================================

void setRGB(
  bool red,
  bool green,
  bool blue
) {

  digitalWrite(
    RED_PIN,
    red ? HIGH : LOW
  );


  digitalWrite(
    GREEN_PIN,
    green ? HIGH : LOW
  );


  digitalWrite(
    BLUE_PIN,
    blue ? HIGH : LOW
  );
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


    case 4:

      showAirQualityScreen();

      break;
  }
}


// =====================================================
// SCREEN 0
// OVERALL STATUS
// =====================================================

void showStatusScreen() {

  display.clearDisplay();

  display.setTextColor(
    SSD1306_WHITE
  );


  // Header
  display.setTextSize(1);

  display.setCursor(
    0,
    0
  );

  display.print(
    "GreenPulse"
  );


  display.setCursor(
    92,
    0
  );

  display.print(
    "STATUS"
  );


  display.drawLine(
    0,
    10,
    127,
    10,
    SSD1306_WHITE
  );


  // ===================================================
  // DHT ERROR
  // ===================================================

  if (!dhtValid) {

    display.setTextSize(2);

    display.setCursor(
      30,
      18
    );

    display.println(
      "ERROR"
    );


    display.setTextSize(1);

    display.setCursor(
      24,
      45
    );

    display.println(
      "DHT11 ERROR"
    );


    display.display();

    return;
  }


  // ===================================================
  // CHECK CONDITIONS
  // ===================================================

  bool tempLow =
    temperature < TEMP_LOW;


  bool tempHigh =
    temperature > TEMP_HIGH;


  bool humidityLow =
    humidity < HUMIDITY_LOW;


  bool humidityHigh =
    humidity > HUMIDITY_HIGH;


  bool soilDry =
    soilRaw >
    SOIL_DRY_THRESHOLD;


  bool allGood =

    !tempLow &&

    !tempHigh &&

    !humidityLow &&

    !humidityHigh &&

    !soilDry;


  // ===================================================
  // GOOD
  // ===================================================

  if (allGood) {

    display.setTextSize(2);

    display.setCursor(
      32,
      18
    );

    display.println(
      "GOOD"
    );


    display.setTextSize(1);

    display.setCursor(
      17,
      42
    );

    display.println(
      "All parameters"
    );


    display.setCursor(
      32,
      53
    );

    display.println(
      "normal"
    );
  }


  // ===================================================
  // ATTENTION
  // ===================================================

  else {

    display.setTextSize(2);

    display.setCursor(
      10,
      14
    );

    display.println(
      "ATTENTION"
    );


    display.setTextSize(1);

    int y = 36;


    if (
      tempLow &&
      y <= 56
    ) {

      display.setCursor(
        0,
        y
      );

      display.println(
        "Temperature: LOW"
      );

      y += 10;
    }


    if (
      tempHigh &&
      y <= 56
    ) {

      display.setCursor(
        0,
        y
      );

      display.println(
        "Temperature: HIGH"
      );

      y += 10;
    }


    if (
      humidityLow &&
      y <= 56
    ) {

      display.setCursor(
        0,
        y
      );

      display.println(
        "Humidity: LOW"
      );

      y += 10;
    }


    if (
      humidityHigh &&
      y <= 56
    ) {

      display.setCursor(
        0,
        y
      );

      display.println(
        "Humidity: HIGH"
      );

      y += 10;
    }


    if (
      soilDry &&
      y <= 56
    ) {

      display.setCursor(
        0,
        y
      );

      display.println(
        "Soil: DRY"
      );
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

  display.setTextColor(
    SSD1306_WHITE
  );


  display.setTextSize(1);

  display.setCursor(
    32,
    0
  );

  display.println(
    "GreenPulse"
  );


  display.drawLine(
    0,
    10,
    127,
    10,
    SSD1306_WHITE
  );


  display.setCursor(
    28,
    16
  );

  display.println(
    "TEMPERATURE"
  );


  if (!dhtValid) {

    display.setTextSize(2);

    display.setCursor(
      30,
      32
    );

    display.println(
      "ERROR"
    );

  } else {

    display.setTextSize(2);

    display.setCursor(
      22,
      31
    );


    display.print(
      temperature,
      1
    );

    display.print(
      " C"
    );


    display.setTextSize(1);

    display.setCursor(
      38,
      53
    );


    if (
      temperature < TEMP_LOW
    ) {

      display.print(
        "LOW"
      );

    } else if (
      temperature > TEMP_HIGH
    ) {

      display.print(
        "HIGH"
      );

    } else {

      display.print(
        "NORMAL"
      );
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

  display.setTextColor(
    SSD1306_WHITE
  );


  display.setTextSize(1);

  display.setCursor(
    32,
    0
  );

  display.println(
    "GreenPulse"
  );


  display.drawLine(
    0,
    10,
    127,
    10,
    SSD1306_WHITE
  );


  display.setCursor(
    37,
    16
  );

  display.println(
    "HUMIDITY"
  );


  if (!dhtValid) {

    display.setTextSize(2);

    display.setCursor(
      30,
      32
    );

    display.println(
      "ERROR"
    );

  } else {

    display.setTextSize(2);

    display.setCursor(
      22,
      31
    );


    display.print(
      humidity,
      1
    );

    display.print(
      " %"
    );


    display.setTextSize(1);

    display.setCursor(
      38,
      53
    );


    if (
      humidity < HUMIDITY_LOW
    ) {

      display.print(
        "LOW"
      );

    } else if (
      humidity > HUMIDITY_HIGH
    ) {

      display.print(
        "HIGH"
      );

    } else {

      display.print(
        "NORMAL"
      );
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

  display.setTextColor(
    SSD1306_WHITE
  );


  display.setTextSize(1);

  display.setCursor(
    32,
    0
  );

  display.println(
    "GreenPulse"
  );


  display.drawLine(
    0,
    10,
    127,
    10,
    SSD1306_WHITE
  );


  display.setCursor(
    24,
    16
  );

  display.println(
    "SOIL MOISTURE"
  );


  display.setTextSize(2);

  display.setCursor(
    32,
    31
  );


  display.println(
    soilRaw
  );


  display.setTextSize(1);

  display.setCursor(
    38,
    53
  );


  if (
    soilRaw >
    SOIL_DRY_THRESHOLD
  ) {

    display.print(
      "DRY"
    );

  } else {

    display.print(
      "OK"
    );
  }


  display.display();
}


// =====================================================
// SCREEN 4
// MQ-135 AIR QUALITY
// =====================================================

void showAirQualityScreen() {

  display.clearDisplay();

  display.setTextColor(
    SSD1306_WHITE
  );


  display.setTextSize(1);

  display.setCursor(
    32,
    0
  );

  display.println(
    "GreenPulse"
  );


  display.drawLine(
    0,
    10,
    127,
    10,
    SSD1306_WHITE
  );


  display.setCursor(
    30,
    16
  );

  display.println(
    "AIR QUALITY"
  );


  display.setTextSize(2);

  display.setCursor(
    32,
    30
  );


  display.println(
    airRaw
  );


  display.setTextSize(1);

  display.setCursor(
    22,
    53
  );


  display.print(
    "MQ-135 RAW"
  );


  display.display();
}