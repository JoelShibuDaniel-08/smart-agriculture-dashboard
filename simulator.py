"""
Device simulator: pretends to be ESP32 sensor nodes so you can demo the
dashboard without any hardware.

It logs in with a dashboard account, then posts readings for 2 simulated
devices (esp32-field-1 and esp32-field-2) over HTTP, running concurrently.

Usage:
    python simulator.py --url http://127.0.0.1:5000 --user demo --password demo123
    python simulator.py --url https://your-app.onrender.com --user demo --password demo123

Create the account first on the /register page (or use --register).
Requires:  pip install requests
"""

import argparse
import random
import threading
import time

import requests

DEVICES = ["esp32-field-1", "esp32-field-2"]


def make_reading(device_id, state):
    """Random-walk values so the dashboard shows believable changes."""
    state["soil_moisture"] = min(100, max(0, state["soil_moisture"] + random.uniform(-2, 2)))
    state["temperature"] = min(60, max(-10, state["temperature"] + random.uniform(-0.5, 0.5)))
    state["light"] = min(100000, max(0, state["light"] + random.uniform(-3000, 3000)))
    return {
        "device_id": device_id,
        "soil_moisture": round(state["soil_moisture"], 1),
        "temperature": round(state["temperature"], 1),
        "light": round(state["light"]),
    }


def run_device(base_url, session, device_id, interval, stop_event):
    state = {
        "soil_moisture": random.uniform(30, 70),
        "temperature": random.uniform(22, 32),
        "light": random.uniform(20000, 60000),
    }
    while not stop_event.is_set():
        reading = make_reading(device_id, state)
        try:
            resp = session.post(f"{base_url}/api/readings", json=reading, timeout=10)
            print(f"[{device_id}] {resp.status_code} {reading}")
        except requests.RequestException as exc:
            print(f"[{device_id}] request failed: {exc}")
        stop_event.wait(interval)


def main():
    parser = argparse.ArgumentParser(description="Smart Agriculture device simulator")
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between readings")
    parser.add_argument("--register", action="store_true", help="create the account first")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    session = requests.Session()

    if args.register:
        session.post(f"{base_url}/register",
                     data={"username": args.user, "password": args.password})

    resp = session.post(f"{base_url}/login",
                        data={"username": args.user, "password": args.password},
                        allow_redirects=False)
    check = session.get(f"{base_url}/api/latest")
    if check.status_code != 200:
        print("Login failed. Check the username and password.")
        return

    print(f"Logged in. Simulating {len(DEVICES)} devices. Press Ctrl+C to stop.")
    stop_event = threading.Event()
    threads = [
        threading.Thread(target=run_device,
                         args=(base_url, session, d, args.interval, stop_event),
                         daemon=True)
        for d in DEVICES
    ]
    for t in threads:
        t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        print("\nStopped.")


if __name__ == "__main__":
    main()
