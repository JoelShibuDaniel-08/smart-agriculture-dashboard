# Smart Agriculture Sensor Dashboard

A full-stack web app that shows live soil moisture, temperature and light
readings from field sensors. ESP32 devices (or the included simulator) send
readings to a REST API, and the dashboard refreshes itself every 5 seconds.

## Hardware / Tech
- ESP32 sensor nodes (soil moisture, temperature and light sensors)
- Python, Flask (backend and REST API)
- SQLite (database)
- HTML, CSS, JavaScript (dashboard)
- Gunicorn and Render (deployment)

## How it works
The ESP32 devices send soil moisture, temperature and light readings over
HTTP to the Flask API, which validates the data and stores it in SQLite.
The dashboard page reads the latest data from the API every 5 seconds and
shows the newest reading for each device along with a recent-readings table.
Users must log in first: the app uses session-based authentication, passwords
are stored as hashes, and every API route requires an active session.

## Setup
1. Install the requirements:
   ```
   pip install -r requirements.txt
   ```
2. Start the app:
   ```
   python app.py
   ```
3. Open http://127.0.0.1:5000, click **Create an account**, then log in.
4. To demo without hardware, run the simulator in a second terminal. It
   streams data from 2 simulated ESP32 devices:
   ```
   python simulator.py --url http://127.0.0.1:5000 --user demo --password demo123 --register
   ```
5. Run the 13 automated tests:
   ```
   python -m unittest -v
   ```

## API
All routes need a logged-in session.

| Method | Route | Description |
|---|---|---|
| POST | `/api/readings` | Add a reading |
| GET | `/api/readings?device_id=&limit=` | List recent readings |
| GET | `/api/latest` | Latest reading for each device |
| GET | `/health` | Health check (no login needed) |

Example body for `POST /api/readings`:
```json
{"device_id": "esp32-field-1", "soil_moisture": 45.5, "temperature": 28.2, "light": 31000}
```

## Deployment
Deploy on Render: push the repo to GitHub, choose **New > Blueprint** in
Render and select the repo. It reads `render.yaml` and starts the app with
`gunicorn app:app`. On the free plan the SQLite data resets when the service
restarts.


## Author
Joel Shibu Daniel
