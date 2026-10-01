# 🌱 GreenPulse Backend

Cloud backend for the **GreenPulse Smart IoT Plant-Care System**, developed for the **IT4030 – Internet of Things** project.

This repository contains the Python backend responsible for receiving IoT sensor data through MQTT, processing contextual information, integrating with the Gemini API, and publishing plant-care recommendations for the Node-RED dashboard.

## ⚙️ Backend Architecture

```text
ESP32
   ↓
HiveMQ Cloud (MQTT/TLS)
   ↓
Python Backend
   ├── Telemetry Validation
   ├── Data Logging / Storage
   ├── Plant Configuration
   ├── Weather Context
   ├── Notification Context
   └── Gemini API
          ↓
   AI Recommendation
          ↓
HiveMQ Cloud
   ↓
Node-RED Dashboard
```

## 🛠️ Tech Stack

- **Python**
- **HiveMQ Cloud**
- **MQTT / TLS**
- **Gemini API**
- **Oracle Cloud Infrastructure**
- **SQLite**
- **JSON**

## 📡 MQTT Topics

```text
greenpulse/device01/telemetry
greenpulse/device01/config
greenpulse/device01/ai
greenpulse/device01/backend/status
```

## 🚀 Local Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd <repository-name>
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create `.env` from `.env.example`:

```env
MQTT_HOST=your-hivemq-host
MQTT_PORT=8883
MQTT_USERNAME=your-username
MQTT_PASSWORD=your-password

GEMINI_API_KEY=your-api-key
GEMINI_MODEL=your-model
```

> ⚠️ Never commit the `.env` file or real API credentials to GitHub.

### 5. Run the backend

```bash
python run.py
```

## 📦 Example Telemetry

```json
{
  "device_id": "device01",
  "temperature": 29.8,
  "humidity": 71,
  "soil_moisture": 43,
  "ph": 6.4,
  "mq135_raw": 1742
}
```

## 🧪 Development

The backend can be tested without the physical ESP32 using the included fake telemetry publisher:

```bash
python tools_publish_test.py
```

Plant configuration can also be simulated using:

```bash
python tools_set_plant.py Tomato
```

## ☁️ Deployment

The final backend is intended to run continuously on an **Oracle Cloud Infrastructure VM**.

Development and testing are performed locally before cloud deployment.

## 🔐 Security

- MQTT communication uses TLS.
- Credentials are stored using environment variables.
- `.env` is excluded from Git.
- External API failures are handled without stopping sensor-data processing.
- Gemini provides plant-care guidance and does not directly control hardware.

## 👨‍💻 Developer

**Buvanaka Eranda**  
IT23366190  
Backend, Cloud & AI Integration

---

**GreenPulse 🌱 | IT4030 – Internet of Things**
