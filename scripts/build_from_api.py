import requests
import json
from datetime import datetime
import os
import re
import time

# --- CONFIG ---
CURRENT_SEASON = datetime.now().year
BASE_URL = "https://api.jolpi.ca/ergast/f1"
OUTPUT_DIR_STATS = "public/data/stats"
OUTPUT_DIR_DRIVERS = "public/data"
TEAM_COLORS_FILE = "f1_team.json" 

# Slug (URL) 수동 수정
SLUG_FIXES = {
    "de_vries": "nyck-de-vries",
    "hulkenberg": "nico-hulkenberg",
    "kevin_magnussen": "kevin-magnussen"
}

# 이름 수동 수정
NAME_FIXES = {
    "Nyck de Vries": "Nyck De Vries",
    "Nico Hülkenberg": "Nico Hulkenberg"
}

def safe_get_request(url, retries=3, delay=5):
    """
    HTTP GET 요청을 보내고, 429 오류 시 재시도하는 함수
    """
    for i in range(retries):
        try:
            response = requests.get(url)
            if response.status_code == 429:
                print(f"  -> Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"[HTTP ERROR] {e}")
            if i < retries - 1:
                print(f"  -> Retrying... ({i+1}/{retries})")
                time.sleep(delay)
            else:
                return None
    return None


def slugify(name):
    name = name.lower()
    name = re.sub(r'[^a-z0-9]+', '-', name)
    return name.strip('-')

def get_current_drivers():
    url = f"{BASE_URL}/{CURRENT_SEASON}/drivers.json"
    response = safe_get_request(url)
    if not response or response.status_code != 200:
        print(f"[HTTP ERROR] Failed to fetch current drivers from url: {url}")
        return []
    data = response.json()
    drivers = data['MRData']['DriverTable']['Drivers']
    
    driver_list = []
    for d in drivers:
        full_name = f"{d['givenName']} {d['familyName']}"
        if full_name in NAME_FIXES:
            full_name = NAME_FIXES[full_name]

        slug = slugify(full_name)
        if d['driverId'] in SLUG_FIXES:
            slug = SLUG_FIXES[d['driverId']]
        
        driver_number = d.get('permanentNumber', '')
        
        driver_info = {
            "driverId": d['driverId'],
            "slug": slug,
            "full_name": full_name,
            "number": driver_number,
            "code": d.get('code', ''),
            "nationality": d['nationality'],
            "photo_src": f"/images/drivers/{driver_number}.png" if driver_number else ""
        }
        driver_list.append(driver_info)
    return driver_list

def get_driver_season_stats(driver_id, season):
    season_stats = {}
    url_results = f"{BASE_URL}/{season}/drivers/{driver_id}/results.json"
    res_results = safe_get_request(url_results)
    if not res_results or res_results.status_code != 200:
        return None, None
    races = res_results.json()['MRData']['RaceTable']['Races']

    if not races:
        return {}, None

    season_stats['gp_races'] = len(races)
    season_stats['gp_points'] = sum(float(r['Results'][0]['points']) for r in races)
    season_stats['gp_podiums'] = sum(1 for r in races if r['Results'][0].get('position') and r['Results'][0]['position'].isdigit() and int(r['Results'][0]['position']) <= 3)
    season_stats['gp_top10'] = sum(1 for r in races if r['Results'][0].get('position') and r['Results'][0]['position'].isdigit() and int(r['Results'][0]['position']) <= 10)
    
    dnfs = 0
    for r in races:
        status = r['Results'][0]['status']
        if 'Finished' not in status and '+' not in status:
            dnfs += 1
    season_stats['dnfs'] = dnfs

    url_standings = f"{BASE_URL}/{season}/drivers/{driver_id}/driverStandings.json"
    res_standings = safe_get_request(url_standings)
    if res_standings and res_standings.status_code == 200:
        standings = res_standings.json()['MRData']['StandingsTable']['StandingsLists']
        if standings and standings[0].get('DriverStandings'):
            driver_standing = standings[0]['DriverStandings'][0]
            season_stats['season_position'] = driver_standing.get('position')
            season_stats['season_points'] = driver_standing.get('points')

    team_name = races[-1]['Results'][0]['Constructor']['name'] if races else None
    return season_stats, team_name


def get_driver_career_stats(driver_id):
    career_stats = {}
    
    url = f"{BASE_URL}/drivers/{driver_id}/results.json?limit=1000"
    res = safe_get_request(url)
    if not res or res.status_code != 200:
        return None
    races = res.json()['MRData']['RaceTable']['Races']
    
    career_stats['gp_entered'] = len(races)
    career_stats['career_points'] = sum(float(r['Results'][0]['points']) for r in races)
    career_stats['podiums'] = sum(1 for r in races if r['Results'][0].get('position') and r['Results'][0]['position'].isdigit() and int(r['Results'][0]['position']) <= 3)
    
    dnfs = 0
    for r in races:
        status = r['Results'][0]['status']
        if 'Finished' not in status and '+' not in status:
            dnfs += 1
    career_stats['dnfs'] = dnfs

    poles_res = safe_get_request(f"{BASE_URL}/drivers/{driver_id}/results/1.json")
    if poles_res and poles_res.status_code == 200:
        career_stats['poles'] = int(poles_res.json()['MRData']['total'])
    else:
        career_stats['poles'] = 0

    best_finish_pos = float('inf')
    for r in races:
        pos_str = r['Results'][0].get('position')
        if pos_str and pos_str.isdigit():
            pos = int(pos_str)
            if pos < best_finish_pos:
                best_finish_pos = pos
    career_stats['best_finish'] = best_finish_pos if best_finish_pos != float('inf') else '-'

    best_grid_res = safe_get_request(f"{BASE_URL}/drivers/{driver_id}/qualifying.json?limit=1000")
    if best_grid_res and best_grid_res.status_code == 200:
        qualifying_results = best_grid_res.json()['MRData']['RaceTable']['Races']
        if qualifying_results:
            best_grid_positions = [int(q['QualifyingResults'][0]['position']) for q in qualifying_results if q.get('QualifyingResults') and q['QualifyingResults'][0].get('position')]
            if best_grid_positions:
                career_stats['best_grid'] = min(best_grid_positions)
            else:
                career_stats['best_grid'] = '-'
        else:
            career_stats['best_grid'] = '-'
    else:
        career_stats['best_grid'] = '-'

    seasons_res = safe_get_request(f"{BASE_URL}/drivers/{driver_id}/seasons.json?limit=100")
    if not seasons_res or seasons_res.status_code != 200:
        return None
    
    seasons = [s['season'] for s in seasons_res.json()['MRData']['SeasonTable']['Seasons']]
    
    standings_data = []
    for season in seasons:
        standing_res = safe_get_request(f"{BASE_URL}/{season}/drivers/{driver_id}/driverStandings.json")
        if standing_res and standing_res.status_code == 200:
            season_standings = standing_res.json()['MRData']['StandingsTable']['StandingsLists']
            if season_standings:
                standings_data.extend(season_standings)

    if standings_data:
        valid_standings = [
            s['DriverStandings'][0] for s in standings_data
            if s.get('DriverStandings') and s['DriverStandings'][0].get('position')
        ]

        if valid_standings:
            career_stats['titles'] = sum(1 for st in valid_standings if st['position'] == '1')
        else:
            career_stats['titles'] = 0
    else:
        career_stats['titles'] = 0

    return career_stats

def main():
    if not os.path.exists(OUTPUT_DIR_STATS):
        os.makedirs(OUTPUT_DIR_STATS)

    try:
        with open(TEAM_COLORS_FILE, 'r', encoding='utf-8') as f:
            team_colors_data = json.load(f)
        # --- 수정된 부분 ---
        team_color_map = {team['name']: team['teamColor'] for team in team_colors_data}
    except FileNotFoundError:
        print(f"Error: '{TEAM_COLORS_FILE}' not found. Team colors will not be added.")
        team_color_map = {}

    all_drivers_data = get_current_drivers()

    for driver in all_drivers_data:
        print(f"Processing {driver['full_name']}...")
        
        season_stats, team_name = get_driver_season_stats(driver['driverId'], CURRENT_SEASON)
        career_stats = get_driver_career_stats(driver['driverId'])
        
        if team_name:
            driver['team_name'] = team_name
            driver['team_colour'] = team_color_map.get(team_name, '#FFFFFF')

        driver_stats = {
            "info": driver,
            "season": season_stats,
            "career": career_stats
        }

        output_path = os.path.join(OUTPUT_DIR_STATS, f"{driver['slug']}.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(driver_stats, f, ensure_ascii=False, indent=2)
        
        print(f"  -> Saved stats to {output_path}")
        time.sleep(1.1)

    drivers_output_path = os.path.join(OUTPUT_DIR_DRIVERS, "drivers.json")
    with open(drivers_output_path, 'w', encoding='utf-8') as f:
        json.dump(all_drivers_data, f, ensure_ascii=False, indent=2)
    print(f"\nSaved all drivers list to {drivers_output_path}")


if __name__ == "__main__":
    main()