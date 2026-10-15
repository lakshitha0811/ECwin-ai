# EcoTwin AI — Sustainable Energy Monitoring & Optimization

A hackathon prototype combining:
- **IoT**: editable sensor inputs for voltage, current, temperature, occupancy and runtime; ready to be replaced with ESP32/MQTT readings.
- **Computer Vision**: optional pretrained YOLOv8n person/object detection from an uploaded image or video.
- **Digital Twin**: equipment-level energy model and what-if simulation for energy, cost and CO₂ savings.
- **AI training**: Isolation Forest anomaly detector trained on synthetic sensor data by `train_ai.py`.
- **GenAI**: optional Gemini API advisor; if no key is set, a deterministic local advisor still works.

## Run it

1. Install Python 3.10–3.12.
2. Open this folder in VS Code.
3. Create and activate a virtual environment (recommended).
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
5. Train the demo anomaly detector:

   ```bash
   python train_ai.py
   ```
6. Start the platform:

   ```bash
   streamlit run app.py
   ```

The browser opens the dashboard. You can use the dashboard without a Gemini key. Computer vision requires the optional packages and a first-time YOLO weights download.

## Enable GenAI

Set `GEMINI_API_KEY` in your terminal before launching Streamlit.

Windows PowerShell:
```powershell
$env:GEMINI_API_KEY="YOUR_KEY"
streamlit run app.py
```

macOS/Linux:
```bash
export GEMINI_API_KEY="YOUR_KEY"
streamlit run app.py
```

Do not paste API keys into source code or commit them to GitHub.

## IoT connection path

Prototype mode uses manual/simulated sensor inputs. For a real ESP32:
1. Read current/voltage/power using an appropriate isolated energy-meter sensor/module.
2. Publish JSON to an MQTT topic, e.g. `ecotwin/lab/sensors`.
3. Add an MQTT subscriber in a separate module and update the dashboard's sensor state.
4. Calibrate against a certified meter. Never wire mains electricity directly to a microcontroller; use safe, rated modules and qualified supervision.

Example payload:
```json
{
  "device_id": "classroom-01",
  "voltage_v": 230.2,
  "current_a": 4.1,
  "temperature_c": 28.4,
  "occupancy": 0,
  "runtime_hours": 6.5,
  "timestamp": "2026-10-15T10:30:00+05:30"
}
```

## How the model works

- Training features: voltage, current, temperature, occupancy, operating hours.
- `IsolationForest` learns the shape of synthetic “normal” readings and flags unusual combinations.
- It is a demonstration, not a validated fault detector. Train and validate using real facility data for any operational use.
- YOLOv8n is a pretrained general object detector; it is not trained by this project on your room images. Its person count is a rough occupancy signal.

## Energy calculations

- Estimated energy: `kWh = rated_power_W × runtime_hours / 1000`
- Estimated cost: `kWh × tariff`
- Estimated emissions: `kWh × emission_factor`
- Savings are the difference between baseline and the selected simulated scenario.

## Demo flow (3 minutes)

1. Select College classroom and show equipment assumptions.
2. Set occupancy to 0; point out that non-essential equipment can be reviewed.
3. Upload a classroom photo/video and run CV to estimate visible people.
4. Choose “Switch off lights when room is empty” and enable “Assume room is empty”; show the Digital Twin's estimated kWh, cost and CO₂ avoided.
5. Change temperature/current and show anomaly detection.
6. Generate the energy-saving plan; use the Gemini key for live GenAI or demonstrate the local advisor.
7. Download the CSV and JSON snapshot.

## Limitations to state honestly

- Default sensor readings and equipment ratings are simulated/assumed.
- CV does not directly measure energy use; it provides visual context such as occupancy.
- The twin is a simplified estimate and needs calibration with meter data.
- Emission factor and tariff are editable assumptions.
- No physical equipment is controlled by this prototype.
