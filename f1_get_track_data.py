# f1_get_replay_data.py
import sys
import json
import requests
import pandas as pd
import time

API_BASE = "https://api.openf1.org/v1"

def fetch_api(endpoint, params):
    try:
        url = f"{API_BASE}/{endpoint}"
        response = requests.get(url, params=params, timeout=600)
        response.raise_for_status()
        time.sleep(1)
        return response.json()
    except requests.RequestException as e:
        return {"error": f"API fetching failed for {endpoint}: {str(e)}"}

def process_data(session_key, locations, laps, positions):
    if "error" in locations or "error" in laps or "error" in positions:
        return {"session_key": session_key, "error": "API에서 중요 데이터를 가져오는 데 실패했습니다."}

    df_loc = pd.DataFrame(locations)
    df_laps = pd.DataFrame(laps)
    df_pos = pd.DataFrame(positions)

    for df in [df_loc, df_laps, df_pos]:
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

    frames_map = {}
    for _, row in df_loc.iterrows():
        ts = row['date']
        ts_ms = int(ts.timestamp() * 1000)
        frame = frames_map.setdefault(ts_ms, {"t": ts_ms, "positions": [], "driver_standings": {}})
        frame["positions"].append({
            "driver_number": row['driver_number'],
            "x": row['x'], "y": row['y']
        })

    df_pos_sorted = df_pos.sort_values('date')
    for ts_ms, frame in sorted(frames_map.items()):
        current_time = pd.to_datetime(ts_ms, unit='ms')
        latest_pos = df_pos_sorted[df_pos_sorted['date'] <= current_time]
        if not latest_pos.empty:
            standings = latest_pos.groupby('driver_number')['position'].last().to_dict()
            frame['driver_standings'] = standings

    frames = sorted(frames_map.values(), key=lambda f: f['t'])
    if not frames:
        return {"session_key": session_key, "error": "처리할 유효한 프레임이 없습니다."}

    all_x = [p["x"] for f in frames for p in f["positions"]]
    all_y = [p["y"] for f in frames for p in f["positions"]]
    bbox = {"minX": min(all_x), "maxX": max(all_x), "minY": min(all_y), "maxY": max(all_y)} if all_x else None
    
    duration_ms = frames[-1]['t'] - frames[0]['t']

    return {"session_key": session_key, "duration_ms": duration_ms, "bbox": bbox, "frames": frames}

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "session_key 인자가 필요합니다."}))
        sys.exit(1)
    session_key = sys.argv[1]
    
    params = {"session_key": session_key}
    locations = fetch_api("location", params)
    laps = fetch_api("laps", params)
    positions = fetch_api("position", params)
    
    replay_data = process_data(session_key, locations, laps, positions)
    
    print(json.dumps(replay_data, ensure_ascii=False))

if __name__ == "__main__":
    main()