# 🌱 GreenPulse

**GreenPulse** is a smart IoT plant-care system developed for the **IT4030 – Internet of Things** module.

The project implements the GreenPulse scenario provided as part of the university assignment. An **ESP32-based IoT device** collects plant and environmental measurements and communicates with cloud services through secure MQTT messaging. A cloud-hosted Python backend combines sensor readings with contextual information and uses an LLM to generate plant-care recommendations, which are presented through a Node-RED dashboard.

---

## 🏗️ System Architecture

```text
                    ┌───────────────────────┐
                    │       Sensors         │
                    │ DHT11 | Soil | pH     │
                    │       MQ-135          │
                    └───────────┬───────────┘
                                │
                                ▼
                         ┌─────────────┐
                         │    ESP32    │
                         └──────┬──────┘
                                │
                           MQTT / TLS
                                │
                                ▼
                     ┌───────────────────┐
                     │   HiveMQ Cloud    │
                     │   MQTT Broker     │
                     └─────────┬─────────┘
                               │
                               ▼
                  ┌────────────────────────┐
                  │     Python Backend     │
                  │     Oracle Cloud       │
                  └───────────┬────────────┘
                              │
                 ┌────────────┼─────────────┐
                 │            │             │
                 ▼            ▼             ▼
              Gemini       Weather     Notification/
                API          API           Email
                 │            │             │
                 └────────────┼─────────────┘
                              │
                              ▼
                     Plant-Care Guidance
                              │
                              ▼
                       HiveMQ Cloud
                              │
                              ▼
                    ┌──────────────────┐
                    │     Node-RED     │
                    │    Dashboard     │
                    └──────────────────┘
```

---

## 🔧 Hardware

The GreenPulse prototype uses:

- **ESP32** – main IoT controller
- **DHT11** – temperature and humidity sensing
- **MD0751 Capacitive Soil Moisture Sensor** – soil-moisture monitoring
- **MQ-135** – environmental gas-response monitoring
- **pH Sensor** – pH measurement
- **Local Display** – device-side information display
- **RGB Indicator** – visual status indication

Sensor values requiring calibration are calibrated and validated before being interpreted by the application.

> The MQ-135 is treated as an environmental gas-response / air-quality-response sensor. Raw measurements are not assumed to represent precise AQI or CO₂ concentration without appropriate calibration.

---

## 💻 Technologies

| Component | Technology |
|---|---|
| IoT Controller | ESP32 |
| Device Programming | Arduino / C++ |
| Communication | MQTT |
| Transport Security | TLS |
| MQTT Broker | HiveMQ Cloud |
| Backend | Python |
| Backend Hosting | Oracle Cloud Infrastructure |
| AI / LLM | Gemini API |
| Dashboard | Node-RED |
| Data Format | JSON |
| Local Backend Storage | SQLite |
| Version Control | Git / GitHub |

---

## ✨ Main Features

- Real-time plant and environmental monitoring
- Temperature and humidity monitoring
- Capacitive soil-moisture monitoring
- pH monitoring
- Environmental gas-response monitoring
- Secure MQTT communication using TLS
- Cloud-based MQTT broker
- Python-based backend processing
- Cloud deployment using Oracle Cloud Infrastructure
- AI-generated plant-care recommendations
- Weather context integration
- Relevant email/notification context integration
- Node-RED monitoring dashboard
- User-selectable plant profiles
- Local device display and RGB status indication
- Backend data logging and error handling

---

## 🔄 Data Flow

The basic GreenPulse data flow is:

```text
Sensors
   ↓
ESP32
   ↓
HiveMQ Cloud
   ↓
Python Backend
   ↓
Sensor Data + Plant Profile + Weather + Relevant Notification
   ↓
Gemini API
   ↓
Structured Plant-Care Recommendation
   ↓
HiveMQ Cloud
   ↓
Node-RED Dashboard
```

The ESP32 is responsible for collecting sensor measurements and publishing them through MQTT.

The Python backend receives and validates the telemetry, combines it with contextual information, communicates with the Gemini API, and publishes the generated result back through MQTT.

Node-RED provides the user-facing dashboard for monitoring the system and interacting with supported configuration options.

---

## 📡 MQTT Communication

The current topic structure follows the pattern:

```text
greenpulse/device01/telemetry
greenpulse/device01/config
greenpulse/device01/ai
greenpulse/device01/backend/status
```

### Example Telemetry

```json
{
  "device_id": "device01",
  "temperature": 29.8,
  "humidity": 71.0,
  "soil_moisture": 43.0,
  "ph": 6.4,
  "mq135_raw": 1742
}
```

### Example Plant Configuration

```json
{
  "plant_type": "Tomato"
}
```

The final topic configuration and communication parameters may be adjusted during system integration.

---

## 🌿 Plant Profiles

The dashboard can allow the user to select the plant being monitored.

Example profiles include:

- Tomato
- Chilli
- Basil
- Mint

The selected plant profile is sent through MQTT and used by the backend as additional context when generating plant-care guidance.

---

## 🤖 AI Processing

The Python backend prepares a controlled context using information such as:

```text
Sensor Measurements
        +
Selected Plant
        +
Weather Context
        +
Relevant Plant-Care Notification
        ↓
     Gemini API
        ↓
Plant-Care Recommendation
```

The LLM is used to provide understandable plant-care guidance rather than to replace the underlying sensor measurements.

If the AI service or another external API is temporarily unavailable, the system is designed so that sensor monitoring and MQTT communication can continue independently.

---

## 📊 Node-RED Dashboard

The Node-RED dashboard provides the user interface for GreenPulse.

It is intended to display:

- Current sensor readings
- Device/backend status
- Selected plant profile
- Plant-care recommendations
- Relevant contextual information
- System alerts or status indicators

It also provides user interaction such as selecting the plant profile used by the backend.

---

## ☁️ Cloud Backend

The GreenPulse Python backend is designed to run on an **Oracle Cloud Infrastructure VM**.

Its responsibilities include:

- Connecting securely to HiveMQ Cloud
- Receiving MQTT telemetry
- Validating incoming JSON
- Storing/logging telemetry
- Maintaining plant configuration
- Retrieving external context
- Communicating with the Gemini API
- Handling external service failures
- Publishing structured AI results
- Providing backend status information

Gemini itself is not hosted on Oracle Cloud. The Python application hosted on Oracle Cloud communicates with the Gemini API.

---

## 🔐 Security

The project follows basic IoT and cloud security practices:

- MQTT communication over TLS
- Credentials stored outside source code
- Environment variables for API keys and passwords
- `.env` excluded from Git
- `.env.example` used for configuration templates
- Private keys and credentials excluded from the repository
- Only relevant notification/email information provided to the AI service

**Never commit real credentials, API keys, passwords, or private keys to this repository.**

---

## 📁 Repository Structure

The repository is organized around the main GreenPulse components.

```text
GreenPulse/
│
├── esp32/              # ESP32 firmware and sensor integration
├── backend/            # Python cloud backend
├── node-red/           # Node-RED flows/dashboard
├── docs/               # Project documentation
│
├── .gitignore
├── README.md
└── ...
```

The exact structure may evolve as the project is implemented.

---

## 👥 Team

| Member | Student ID | Main Responsibility |
|---|---|---|
| **Janith Navoda** | IT23355750 | ESP32, Sensors, Calibration & Local Device |
| **Dewruwan Eranga** | IT23365278 | HiveMQ Cloud, MQTT & TLS Communication |
| **Buvanaka Eranda** | IT23366190 | Python Backend, Oracle Cloud & AI Integration |
| **Rahula Srimath** | IT23373648 | Node-RED Dashboard & User Interface |

---

## 🚧 Project Status

GreenPulse is currently under development.

Implementation is being carried out incrementally:

```text
Sensor Integration
       ↓
ESP32 Integration
       ↓
MQTT / HiveMQ
       ↓
Python Backend
       ↓
Node-RED Dashboard
       ↓
External Context
       ↓
Gemini Integration
       ↓
Oracle Cloud Deployment
       ↓
Full System Testing
```

Each component is tested independently before complete end-to-end integration.

---

## 🎓 Academic Project

This repository contains work developed for:

**IT4030 – Internet of Things**

GreenPulse and the ESP32-based project scenario originate from the university assignment requirements. The repository contains our group's implementation of those requirements, including our selected sensors, cloud services, backend implementation, dashboard, integrations, and additional enhancements.

---

## 📌 Disclaimer

GreenPulse is an academic prototype intended for IoT learning and experimentation. Sensor measurements and AI-generated plant-care recommendations should not be treated as laboratory-grade agricultural measurements or professional agricultural advice.
