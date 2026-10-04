#include <Wire.h>
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// =====================================================
// GREENPULSE - COMPLETE SENSOR TEST
// =====================================================
//
// DHT11:
//   Air Temperature + Humidity
//
// Soil Moisture:
//   RAW + estimated percentage
//
// LDR:
//   BRIGHT / DARK
//
// DS18B20:
//   Soil / probe temperature
//
// OLED:
//   6 screens
//
// RGB:
//   GREEN = Normal
//   RED   = Attention
//   BLUE  = Sensor error
//
// =====================================================


// =====================================================
// PIN DEFINITIONS
// =====================================================

#define DHT_PIN 4
#define DHT_TYPE DHT11

#define SOIL_PIN 5

#define LDR_PIN 6

#define BUTTON_PIN 7

#define SDA_PIN 8
#define SCL_PIN 9

#define BLUE_PIN  10
#define GREEN_PIN 11
#define RED_PIN   12

#define DS18B20_PIN 13


// =====================================================
// OLED
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
// DHT11
// =====================================================

DHT dht(
  DHT_PIN,
  DHT_TYPE
);


// =====================================================
// DS18B20
// =====================================================

OneWire oneWire(
  DS18B20_PIN
);

DallasTemperature ds18b20(
  &oneWire
);


// =====================================================
// SENSOR VALUES
// =====================================================

float airTemperature = 0.0;
float humidity = 0.0;

float soilTemperature = 0.0;

int soilRaw = 0;
int soilPercent = 0;

int ldrValue = 0;

bool dhtValid = false;
bool ds18b20Valid = false;


// =====================================================
// AIR TEMPERATURE THRESHOLDS
// =====================================================

const float AIR_TEMP_LOW = 20.0;
const float AIR_TEMP_HIGH = 35.0;


// =====================================================
// HUMIDITY THRESHOLDS
// =====================================================

const float HUMIDITY_LOW = 40.0;
const float HUMIDITY_HIGH = 85.0;


// =====================================================
// SOIL TEMPERATURE THRESHOLDS
// =====================================================
//
// Temporary general test values.
// Crop-specific thresholds can be added later.
//

const float SOIL_TEMP_LOW = 15.0;
const float SOIL_TEMP_HIGH = 35.0;


// =====================================================
// SOIL MOISTURE CALIBRATION
// =====================================================
//
// IMPORTANT:
//
// These are temporary values.
//
// Later replace these with YOUR measured:
//
// SOIL_DRY_VALUE
// SOIL_WET_VALUE
//
// =====================================================

const int SOIL_DRY_VALUE = 4095;
const int SOIL_WET_VALUE = 1500;

const int SOIL_DRY_PERCENT = 30;
const int SOIL_WET_PERCENT = 80;


// =====================================================
// OLED SCREEN
// =====================================================
//
// 0 = Overall
// 1 = Air Temperature
// 2 = Humidity
// 3 = Soil Moisture
// 4 = Light
// 5 = Soil Temperature
//
// =====================================================

int currentScreen = 0;


// =====================================================
// BUTTON
// =====================================================

bool lastButtonReading = HIGH;
bool stableButtonState = HIGH;

unsigned long lastDebounceTime = 0;

const unsigned long debounceDelay = 50;


// =====================================================
// SENSOR TIMER
// =====================================================

unsigned long lastSensorRead = 0;

const unsigned long sensorInterval = 2000;


// =====================================================
// FUNCTION DECLARATIONS
// =====================================================

void readSensors();

void handleButton();

void updateDisplay();

void updateRGB();

void setRGB(
  bool red,
  bool green,
  bool blue
);

void showStatusScreen();

void showAirTemperatureScreen();

void showHumidityScreen();

void showSoilMoistureScreen();

void showLightScreen();

void showSoilTemperatureScreen();


// =====================================================
// SETUP
// =====================================================

void setup() {

  // ---------------------------------------------------
  // BUTTON
  // ---------------------------------------------------

  pinMode(
    BUTTON_PIN,
    INPUT_PULLUP
  );


  // ---------------------------------------------------
  // SENSOR INPUTS
  // ---------------------------------------------------

  pinMode(
    SOIL_PIN,
    INPUT
  );

  pinMode(
    LDR_PIN,
    INPUT
  );


  analogReadResolution(12);


  // ---------------------------------------------------
  // RGB
  // ---------------------------------------------------

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


  setRGB(
    false,
    false,
    false
  );


  // ---------------------------------------------------
  // START DHT11
  // ---------------------------------------------------

  dht.begin();


  // ---------------------------------------------------
  // START DS18B20
  // ---------------------------------------------------

  ds18b20.begin();


  // ---------------------------------------------------
  // START OLED
  // ---------------------------------------------------

  Wire.begin(
    SDA_PIN,
    SCL_PIN
  );


  if (!display.begin(
        SSD1306_SWITCHCAPVCC,
        SCREEN_ADDRESS)) {

    // OLED error
    // Flash BLUE LED

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
    36
  );

  display.println(
    "Monitoring System"
  );


  display.setCursor(
    30,
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


  // ===================================================
  // FIRST READING
  // ===================================================

  readSensors();

  updateRGB();

  updateDisplay();


  lastSensorRead =
    millis();
}


// =====================================================
// LOOP
// =====================================================

void loop() {

  // Button remains responsive

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


  delay(1);
}


// =====================================================
// READ ALL SENSORS
// =====================================================

void readSensors() {

  // ===================================================
  // DHT11
  // ===================================================

  float newAirTemperature =
    dht.readTemperature();


  float newHumidity =
    dht.readHumidity();


  if (
    !isnan(newAirTemperature) &&
    !isnan(newHumidity)
  ) {

    airTemperature =
      newAirTemperature;


    humidity =
      newHumidity;


    dhtValid =
      true;

  }

  else {

    dhtValid =
      false;
  }


  // ===================================================
  // SOIL MOISTURE
  // ===================================================

  soilRaw =
    analogRead(SOIL_PIN);


  soilPercent =
    map(
      soilRaw,
      SOIL_DRY_VALUE,
      SOIL_WET_VALUE,
      0,
      100
    );


  soilPercent =
    constrain(
      soilPercent,
      0,
      100
    );


  // ===================================================
  // LDR
  // ===================================================

  ldrValue =
    digitalRead(LDR_PIN);


  // Your module:
  //
  // 0 = BRIGHT
  // 1 = DARK


  // ===================================================
  // DS18B20
  // ===================================================

  ds18b20.requestTemperatures();


  float newSoilTemperature =
    ds18b20.getTempCByIndex(0);


  // -127 C usually means sensor not detected

  if (
    newSoilTemperature != DEVICE_DISCONNECTED_C &&
    newSoilTemperature > -100.0 &&
    newSoilTemperature < 125.0
  ) {

    soilTemperature =
      newSoilTemperature;


    ds18b20Valid =
      true;

  }

  else {

    ds18b20Valid =
      false;
  }
}


// =====================================================
// BUTTON
// =====================================================

void handleButton() {

  bool reading =
    digitalRead(BUTTON_PIN);


  if (
    reading !=
    lastButtonReading
  ) {

    lastDebounceTime =
      millis();
  }


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


      if (
        stableButtonState == LOW
      ) {

        currentScreen++;


        // 6 screens:
        // 0 - 5

        if (
          currentScreen > 5
        ) {

          currentScreen = 0;
        }


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
  // SENSOR ERROR = BLUE
  // ===================================================

  if (
    !dhtValid ||
    !ds18b20Valid
  ) {

    setRGB(
      false,
      false,
      true
    );

    return;
  }


  // ===================================================
  // AIR TEMPERATURE
  // ===================================================

  bool airTempProblem =

    airTemperature < AIR_TEMP_LOW ||

    airTemperature > AIR_TEMP_HIGH;


  // ===================================================
  // HUMIDITY
  // ===================================================

  bool humidityProblem =

    humidity < HUMIDITY_LOW ||

    humidity > HUMIDITY_HIGH;


  // ===================================================
  // SOIL MOISTURE
  // ===================================================

  bool soilMoistureProblem =

    soilPercent <
    SOIL_DRY_PERCENT;


  // ===================================================
  // SOIL TEMPERATURE
  // ===================================================

  bool soilTempProblem =

    soilTemperature < SOIL_TEMP_LOW ||

    soilTemperature > SOIL_TEMP_HIGH;


  // ===================================================
  // ATTENTION = RED
  // ===================================================

  if (
    airTempProblem ||
    humidityProblem ||
    soilMoistureProblem ||
    soilTempProblem
  ) {

    setRGB(
      true,
      false,
      false
    );

    return;
  }


  // ===================================================
  // NORMAL = GREEN
  // ===================================================

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
// Common Cathode RGB:
//
// HIGH = ON
// LOW  = OFF
//
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

      showAirTemperatureScreen();

      break;


    case 2:

      showHumidityScreen();

      break;


    case 3:

      showSoilMoistureScreen();

      break;


    case 4:

      showLightScreen();

      break;


    case 5:

      showSoilTemperatureScreen();

      break;
  }
}


// =====================================================
// SCREEN 1
// OVERALL STATUS
// =====================================================

void showStatusScreen() {

  display.clearDisplay();

  display.setTextColor(
    SSD1306_WHITE
  );


  display.setTextSize(1);


  // Header

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
  // AIR TEMPERATURE
  // ===================================================

  display.setCursor(
    0,
    14
  );

  display.print(
    "Air : "
  );


  if (dhtValid) {

    display.print(
      airTemperature,
      1
    );

    display.print(
      " C"
    );

  }

  else {

    display.print(
      "ERROR"
    );
  }


  // ===================================================
  // HUMIDITY
  // ===================================================

  display.setCursor(
    0,
    24
  );

  display.print(
    "Hum : "
  );


  if (dhtValid) {

    display.print(
      humidity,
      0
    );

    display.print(
      "%"
    );

  }

  else {

    display.print(
      "ERROR"
    );
  }


  // ===================================================
  // SOIL MOISTURE
  // ===================================================

  display.setCursor(
    0,
    34
  );

  display.print(
    "Moist: "
  );


  display.print(
    soilPercent
  );


  display.print(
    "%"
  );


  // ===================================================
  // LIGHT
  // ===================================================

  display.setCursor(
    0,
    44
  );

  display.print(
    "Light: "
  );


  if (
    ldrValue == LOW
  ) {

    display.print(
      "BRIGHT"
    );

  }

  else {

    display.print(
      "DARK"
    );
  }


  // ===================================================
  // SOIL TEMPERATURE
  // ===================================================

  display.setCursor(
    0,
    54
  );

  display.print(
    "SoilT: "
  );


  if (ds18b20Valid) {

    display.print(
      soilTemperature,
      1
    );

    display.print(
      "C"
    );

  }

  else {

    display.print(
      "ERROR"
    );
  }


  display.display();
}


// =====================================================
// SCREEN 2
// AIR TEMPERATURE
// =====================================================

void showAirTemperatureScreen() {

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
    22,
    16
  );

  display.println(
    "AIR TEMPERATURE"
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

  }

  else {

    display.setTextSize(2);

    display.setCursor(
      20,
      30
    );


    display.print(
      airTemperature,
      1
    );


    display.print(
      " C"
    );


    display.setTextSize(1);

    display.setCursor(
      40,
      53
    );


    if (
      airTemperature <
      AIR_TEMP_LOW
    ) {

      display.print(
        "LOW"
      );

    }

    else if (
      airTemperature >
      AIR_TEMP_HIGH
    ) {

      display.print(
        "HIGH"
      );

    }

    else {

      display.print(
        "NORMAL"
      );
    }
  }


  display.display();
}


// =====================================================
// SCREEN 3
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

  }

  else {

    display.setTextSize(2);

    display.setCursor(
      25,
      30
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
      40,
      53
    );


    if (
      humidity <
      HUMIDITY_LOW
    ) {

      display.print(
        "LOW"
      );

    }

    else if (
      humidity >
      HUMIDITY_HIGH
    ) {

      display.print(
        "HIGH"
      );

    }

    else {

      display.print(
        "NORMAL"
      );
    }
  }


  display.display();
}


// =====================================================
// SCREEN 4
// SOIL MOISTURE
// =====================================================

void showSoilMoistureScreen() {

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


  // Percentage

  display.setTextSize(2);

  display.setCursor(
    35,
    28
  );


  display.print(
    soilPercent
  );


  display.print(
    " %"
  );


  // Status

  display.setTextSize(1);

  display.setCursor(
    40,
    47
  );


  if (
    soilPercent <
    SOIL_DRY_PERCENT
  ) {

    display.print(
      "DRY"
    );

  }

  else if (
    soilPercent >
    SOIL_WET_PERCENT
  ) {

    display.print(
      "WET"
    );

  }

  else {

    display.print(
      "NORMAL"
    );
  }


  // RAW reading

  display.setCursor(
    30,
    56
  );


  display.print(
    "RAW: "
  );


  display.print(
    soilRaw
  );


  display.display();
}


// =====================================================
// SCREEN 5
// LIGHT
// =====================================================

void showLightScreen() {

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
    34,
    16
  );

  display.println(
    "LIGHT LEVEL"
  );


  display.setTextSize(2);


  // Confirmed:
  // 0 = BRIGHT
  // 1 = DARK

  if (
    ldrValue == LOW
  ) {

    display.setCursor(
      25,
      30
    );

    display.println(
      "BRIGHT"
    );

  }

  else {

    display.setCursor(
      40,
      30
    );

    display.println(
      "DARK"
    );
  }


  display.setTextSize(1);

  display.setCursor(
    31,
    53
  );


  display.print(
    "Digital: "
  );


  display.print(
    ldrValue
  );


  display.display();
}


// =====================================================
// SCREEN 6
// SOIL TEMPERATURE - DS18B20
// =====================================================

void showSoilTemperatureScreen() {

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
    18,
    16
  );

  display.println(
    "SOIL TEMPERATURE"
  );


  // ===================================================
  // DS18B20 ERROR
  // ===================================================

  if (!ds18b20Valid) {

    display.setTextSize(2);

    display.setCursor(
      30,
      30
    );

    display.println(
      "ERROR"
    );


    display.setTextSize(1);

    display.setCursor(
      10,
      53
    );

    display.println(
      "Check DS18B20"
    );

  }

  else {

    // =================================================
    // TEMPERATURE
    // =================================================

    display.setTextSize(2);

    display.setCursor(
      20,
      30
    );


    display.print(
      soilTemperature,
      1
    );


    display.print(
      " C"
    );


    // =================================================
    // STATUS
    // =================================================

    display.setTextSize(1);

    display.setCursor(
      40,
      53
    );


    if (
      soilTemperature <
      SOIL_TEMP_LOW
    ) {

      display.print(
        "LOW"
      );

    }

    else if (
      soilTemperature >
      SOIL_TEMP_HIGH
    ) {

      display.print(
        "HIGH"
      );

    }

    else {

      display.print(
        "NORMAL"
      );
    }
  }


  display.display();
}