# GreenPulse — Manual End-to-End Testing Checklist

This checklist guides manual verification on real hardware (ESP32), HiveMQ Cloud, Node-RED Dashboard 2.0, and Gmail SMTP.

---

## 1. Prerequisites & Environment Check

- [ ] **`.env` Configuration**:
  - `MQTT_HOST`, `MQTT_PORT` (8883), `MQTT_USERNAME`, `MQTT_PASSWORD` are populated.
  - `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` (16-character Google App Password) are configured.
  - `GEMINI_API_KEY` is set.
- [ ] **SQLite Database**:
  - Run migration test: `.venv\Scripts\python tests\test_phase1_migration.py`
  - Ensure all 8 tables are present and WAL mode is active.
- [ ] **Backend Process**:
  - Run `.venv\Scripts\python run.py`
  - Verify terminal output shows:
    - `Connected to HiveMQ Cloud broker.`
    - `Subscription request sent for: telemetry, config, location, notification/settings.`
    - `Restoring stored plant profile and location on connect.`
    - `Daily summary scheduler started.`

---

## 2. Upgrade A: Worldwide Location Autocomplete Verification

- [ ] **Node-RED Import**:
  - Open Node-RED editor (e.g., `http://localhost:1880`).
  - Import `nodered/greenpulse_dashboard_flow.json` (or paste `nodered/location_autocomplete_template.html` into a `ui-template` node).
  - Configure HiveMQ Cloud credentials in the `mqtt-broker` configuration node.
  - Deploy the flow.
- [ ] **Dashboard Loading**:
  - Navigate to `/dashboard/greenhouse`.
  - Verify the **Greenhouse Location** card appears with dark-mode styling and a "Ready" badge.
- [ ] **Search & Debounce**:
  - Type `Colo` in the search box.
  - Verify loading spinner appears after ~400ms and suggestions drop down including:
    `Colombo, Western Province, Sri Lanka (LK)`.
- [ ] **Duplicate Place Names Test**:
  - Search `London`.
  - Verify suggestions display both `London, England, United Kingdom` and `London, Ontario, Canada`.
- [ ] **Selection & Publication**:
  - Select `Colombo, Western Province, Sri Lanka`.
  - Verify the card switches to the confirmed state showing:
    - 📍 `Colombo, Western Province, Sri Lanka`
    - `Lat: 6.9271°, Lon: 79.8612°`
    - Green "Confirmed" badge.
  - In backend logs, verify:
    - `Location validation passed. Device=device01 Latitude=6.9271 Longitude=79.8612`
    - `Published resolved location: Colombo, Western Province, Sri Lanka`
- [ ] **Persistence Across Refresh**:
  - Refresh the Node-RED dashboard browser page (`F5`).
  - Verify the confirmed location (`Colombo, Western Province, Sri Lanka`) restores immediately from the retained MQTT message.
- [ ] **Backend Restart**:
  - Stop the backend (`Ctrl+C`) and restart `.venv\Scripts\python run.py`.
  - Verify the backend reads the stored location from SQLite and immediately republishes it to `greenpulse/device01/location/resolved`.

---

## 3. Upgrade B: Smart Notifications & Recipient Management

- [ ] **Notification Center Panel**:
  - In the dashboard, locate the **Notification Center & Alerts** card.
  - Verify the two tabs: **Recipients** and **Recent Alerts**.
- [ ] **Add Email Recipient**:
  - Enter your valid email address (e.g., your personal Gmail).
  - Select alert categories: `💧 Watering`, `🌡️ Temp`, `💨 Humidity`, `⛈️ Weather`, `🚨 Critical`, `📋 Daily`.
  - Click **+ Add Recipient**.
  - Verify backend logs: `Recipient added: your.email@example.com`.
  - Verify the recipient appears in the "Configured Email Recipients" list with all active category tags.
- [ ] **Send Test Email Verification**:
  - Click **✉️ Send Test** next to your email address.
  - Check your inbox within 10–30 seconds.
  - Verify receipt of email:
    - Subject: `[GreenPulse] Test Notification - Email Delivery Verified`
    - Sender: `GreenPulse Greenhouse <your-configured-gmail>`
    - HTML styling: Dark glassmorphic card with green header and "Connected" status badge.
- [ ] **Rate Limiting Check**:
  - Immediately click **✉️ Send Test** again on the same recipient.
  - Verify feedback shows rate limit active (5-minute cooldown notice).
- [ ] **Live Telemetry & Watering Alert Trigger**:
  - Power on the ESP32 (or simulate dry soil using `tools_publish_test.py`).
  - When soil moisture is below the crop threshold (e.g. <60% for Tomato) for 2 consecutive cycles:
    - Backend generates `WATERING` notification ID.
    - Gemini produces a contextual summary and rain-aware care recommendation.
    - Email is delivered asynchronously to subscribed recipients.
    - Node-RED Notification Center displays the alert under **Recent Alerts** with a `MEDIUM` or `CRITICAL` pill.
- [ ] **Cooldown Verification**:
  - Allow ESP32 to continue publishing low soil moisture for the next 10 minutes.
  - Verify NO duplicate emails are sent (120-minute cooldown active).
- [ ] **Recovery Notification**:
  - Water the soil sensor or simulate soil moisture > 65%.
  - After 2 consecutive normal readings:
    - Backend detects condition normalized.
    - Publishes `RECOVERY_WATERING` event.
    - Sends green Recovery notice to recipients subscribed to recovery/critical updates.
- [ ] **Daily Summary Trigger**:
  - In Python, run:
    ```bash
    .venv\Scripts\python -c "from greenpulse.daily_summary_service import DailySummaryService; DailySummaryService().send_daily_summary_now()"
    ```
  - Check inbox for: `[GreenPulse Daily Summary] Tomato Status - YYYY-MM-DD`.
  - Verify sensor metrics grid and AI care insights are present.

---

## 4. ESP32 Hardware Non-Regression

- [ ] **OLED SSD1306 Display**:
  - Verify current temperature, humidity, and plant name cycle cleanly.
- [ ] **RGB Status LED**:
  - Displays green when in safe threshold, blue during MQTT network operations, yellow/red when in alert.
- [ ] **Plant Profile Synchronization**:
  - Change selected crop in Node-RED from Tomato to Basil.
  - Verify ESP32 OLED updates the active crop name and thresholds without needing firmware re-flashing.
