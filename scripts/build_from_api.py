# scripts/build_from_api.py
# API(Ergast/JolpI) → public/data/* JSON 생성기
# 사용 예) python scripts/build_from_api.py --year 2025
import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

BASE = "https://api.jolpi.ca/ergast/f1"
TIMEOUT = 25
LARGE_LIMIT = 2000

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DATA_DIR = PUBLIC / "data"
STATS_DIR = DATA_DIR / "stats"
IMAGES_DRIVERS = PUBLIC / "images" / "drivers"

def slugify(text: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", (text or "").lower())).strip("-")

def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return default

def finished_status(status: str) -> bool:
    """
    Ergast의 status가 아래 중 하나면 '완주'로 간주:
    - 'Finished'
    - '+1 Lap' / '+2 Laps' 등
    """
    if not status:
        return False
    if "Finished" in status:
        return True
    if re.fullmatch(r"\+\d+\s+Laps?", status):
        return True
    return False

class Api:
    def __init__(self):
        self.s = requests.Session()

    def get(self, path, **params):
        p = dict(params or {})
        if "limit" not in p:
            p["limit"] = LARGE_LIMIT
        url = f"{BASE}{path}"
        r = self.s.get(url, params=p, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()["MRData"]

    # ===== 데이터 단건 획득 헬퍼 =====
    def driver_standings(self, year: int):
        # 시즌 드라이버 스탠딩(=드라이버 + 소속 팀)을 한 번에 가져오자
        md = self.get(f"/{year}/driverStandings.json")
        lists = md.get("StandingsTable", {}).get("StandingsLists", [])
        return lists[0]["DriverStandings"] if lists else []

    def season_results_for_driver(self, year: int, driver_id: str):
        md = self.get(f"/{year}/drivers/{driver_id}/results.json")
        return md.get("RaceTable", {}).get("Races", [])

    def all_results_for_driver(self, driver_id: str):
        # 커리어 모든 그랑프리 결과 (레이스 단위)
        md = self.get(f"/drivers/{driver_id}/results.json")
        return md.get("RaceTable", {}).get("Races", [])

    def all_driver_standings(self, driver_id: str):
        # 드라이버의 각 시즌 드라이버 순위(챔피언 계산용)
        md = self.get(f"/drivers/{driver_id}/driverStandings.json")
        lists = md.get("StandingsTable", {}).get("StandingsLists", [])
        return lists

def compute_season_stats(api: Api, year: int, driver):
    driver_id = driver["Driver"]["driverId"]
    # standings 포인트/순위는 standings에서 직접 가져오는 것이 정확
    season_position = safe_int(driver.get("position", 0))
    season_points = safe_int(driver.get("points", 0))

    races = api.season_results_for_driver(year, driver_id)

    gp_races = 0
    gp_points_sum = 0
    gp_podiums = 0
    gp_top10s = 0
    wins = 0
    dnfs = 0
    best_grid = None
    poles = 0

    for r in races:
        # Ergast 구조상 이 드라이버의 entry는 길이 1
        res = r.get("Results", [{}])[0]
        pos = safe_int(res.get("position", 0))
        grid = safe_int(res.get("grid", 0))
        pts = safe_int(res.get("points", 0))
        status = res.get("status", "")

        gp_races += 1
        gp_points_sum += pts
        if pos and pos <= 3:
            gp_podiums += 1
        if pos and pos <= 10:
            gp_top10s += 1
        if pos == 1:
            wins += 1
        if not finished_status(status):
            dnfs += 1
        if grid:
            if best_grid is None or grid < best_grid:
                best_grid = grid
        if grid == 1:
            poles += 1

    season = {
        "season_year": year,
        "season_position": season_position if season_position else "-",
        "season_points": season_points if season_points else 0,
        "gp_races": gp_races,
        "gp_points": gp_points_sum,
        "gp_podiums": gp_podiums,
        "gp_top10s": gp_top10s,
        "wins": wins,
        "dnfs": dnfs,
        "best_grid": best_grid if best_grid is not None else "-",
        "poles": poles,
        # Sprint 관련은 Ergast에 제한적이라 기본 0으로 두되, 필요시 확장
        "sprint_races": 0,
        "sprint_points": 0,
        "sprint_podiums": 0,
        "sprint_poles": 0,
        "sprint_top10s": 0,
    }
    return season

def compute_career_stats(api: Api, driver_id: str):
    races = api.all_results_for_driver(driver_id)

    gp_entered = 0
    total_points = 0
    podiums = 0
    best_finish = None
    best_finish_count = 0
    best_grid = None
    poles = 0
    dnfs = 0

    for r in races:
        res = r.get("Results", [{}])[0]
        pos = safe_int(res.get("position", 0))
        grid = safe_int(res.get("grid", 0))
        pts = safe_int(res.get("points", 0))
        status = res.get("status", "")

        gp_entered += 1
        total_points += pts

        if pos and pos <= 3:
            podiums += 1

        # best finish
        if pos:
            if best_finish is None or pos < best_finish:
                best_finish = pos
                best_finish_count = 1
            elif pos == best_finish:
                best_finish_count += 1

        # best grid & poles
        if grid:
            if best_grid is None or grid < best_grid:
                best_grid = grid
            if grid == 1:
                poles += 1

        if not finished_status(status):
            dnfs += 1

    # 챔피언 수 (1회 이상 시즌 포지션 1)
    all_standings = api.all_driver_standings(driver_id)
    world_championships = 0
    for s in all_standings:
        ds = s.get("DriverStandings", [])
        if ds:
            pos = ds[0].get("position")
            if str(pos) == "1":
                world_championships += 1

    career = {
        "gp_entered": gp_entered,
        "points": total_points,
        "best_finish": f"{best_finish} (x{best_finish_count})" if best_finish else "-",
        "podiums": podiums,
        "best_grid": best_grid if best_grid is not None else "-",
        "poles": poles,
        "world_championships": world_championships,
        "dnfs": dnfs,
    }
    return career

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=None, help="가져올 시즌 (예: 2025). 미입력 시 현재 연도.")
    parser.add_argument("--out", default=str(DATA_DIR), help="출력 폴더 (기본: public/data)")
    args = parser.parse_args()

    year = args.year or int(os.getenv("YEAR", "0")) or int(__import__("datetime").date.today().year)
    out = Path(args.out)
    stats_out = Path(out) / "stats"
    out.mkdir(parents=True, exist_ok=True)
    stats_out.mkdir(parents=True, exist_ok=True)

    api = Api()

    # 시즌 standings를 통해 '현재 활동 드라이버 + 팀'을 받는 것이 가장 정확
    standings = api.driver_standings(year)
    if not standings:
        print(f"[warn] {year} 시즌 standings가 비어있습니다. (Ergast/JolpI가 아직 갱신되지 않았을 수 있음)")
        print("      그래도 기존 JSON을 덮어쓰지 않도록 drivers.json은 빈 배열로만 저장합니다.")
        (out / "drivers.json").write_text("[]", encoding="utf-8")
        return

    drivers_out = []

    for row in standings:
        drv = row.get("Driver", {})
        constructors = row.get("Constructors", []) or row.get("Constructor", [])
        team_name = ""
        if isinstance(constructors, list) and constructors:
            team_name = constructors[0].get("name") or ""
        elif isinstance(constructors, dict):
            team_name = constructors.get("name") or ""

        full_name = f"{drv.get('givenName', '').strip()} {drv.get('familyName', '').strip()}".strip()
        slug = slugify(full_name)  # 통일
        code = drv.get("code") or (drv.get("driverId", "")[:3].upper())
        number = drv.get("permanentNumber") or ""  # 문자열로 들어옴
        nationality = drv.get("nationality") or ""

        # drivers.json의 1레코드 구성
        rec = {
            "slug": slug,
            "full_name": full_name,
            "code": code,
            "number": number,
            "team_name": team_name,
            "nationality": nationality,
            # 사진은 프론트/서버에서 slug.png 사용(존재 시). 여기서는 경로만 명시적으로 넣고 싶다면:
            # "photo_src": f"/images/drivers/{slug}.png"
        }
        drivers_out.append(rec)

        # === 상세 통계 생성 ===
        season = compute_season_stats(api, year, row)
        career = compute_career_stats(api, drv["driverId"])
        stats_json = {"season": season, "career": career}

        (stats_out / f"{slug}.json").write_text(
            json.dumps(stats_json, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # drivers.json 저장 (정렬: team_name → full_name)
    drivers_out.sort(key=lambda x: (x.get("team_name", ""), x.get("full_name", "")))
    (Path(out) / "drivers.json").write_text(
        json.dumps(drivers_out, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"[ok] drivers: {len(drivers_out)}, stats dir: {stats_out}")

if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print("[HTTP ERROR]", e, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("[ERROR]", e, file=sys.stderr)
        sys.exit(1)
