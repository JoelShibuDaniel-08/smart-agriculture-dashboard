# Smart Agriculture Sensor Dashboard

A full-stack web app that shows live soil moisture, temperature and light
readings from field sensors. ESP32 devices (or the included simulator) send
readings to a REST API, and the dashboard refreshes itself every 5 seconds.

## Features
- Flask backend with a REST API on a SQLite database
- Session-based authentication; every API route requires an active login
- Passwords stored as hashes (Werkzeug), never in plain text
- Input validation on all sensor data (types and value ranges)
- Auto-refreshing dashboard (every 5 seconds) with the latest reading per
  device and a recent-readings table
- 13 automated tests (Python `unittest`) run against an isolated test database
- Device simulator: streams data from 2 simulated ESP32 devices, so you can
  demo without hardware
- Ready to deploy on Render using Gunicorn

## Tech stack
Python, Flask, SQLite, HTML/CSS/JavaScript, Gunicorn, Render

## Run locally
```
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000, click **Create an account**, then log in.

## Try it with the simulator
In a second terminal:
```
python simulator.py --url http://127.0.0.1:5000 --user demo --password demo123 --register
```
Two simulated devices (`esp32-field-1`, `esp32-field-2`) start posting
readings and appear on the dashboard.

## Run the tests
```
python -m unittest -v
```

## API
All routes need a logged-in session.

| Method | Route | Description |
|---|---|---|
| POST | `/api/readings` | Add a reading |
| GET | `/api/readings?device_id=&limit=` | List recent readings (newest first) |
| GET | `/api/latest` | Latest reading for each device |
| GET | `/health` | Health check (no login needed) |

Example body for `POST /api/readings`:
```json
{"device_id": "esp32-field-1", "soil_moisture": 45.5, "temperature": 28.2, "light": 31000}
```
Valid ranges: soil moisture 0-100 %, temperature -40 to 85 C, light 0-100000 lux.

## Deploy on Render
1. Push this repo to GitHub.
2. In Render, choose **New > Blueprint** and select the repo. It reads
   `render.yaml`, installs the requirements, and starts `gunicorn app:app`.
3. Render generates a `SECRET_KEY` for you.

Note: on Render's free plan the SQLite file is not permanent and resets when
the service restarts. For permanent data, attach a persistent disk or move
to a hosted database such as PostgreSQL.

## Project structure
```
app.py            Flask app, database, auth, REST API
templates/        Login/register page and dashboard page
static/style.css  Styles
simulator.py      Fake ESP32 devices for demos
test_app.py       13 unit tests
render.yaml       Render deployment config
```

## Author
Joel Shibu Daniel
