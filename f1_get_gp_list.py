# f1_get_gp_list.py
import requests
import json
import sys

def get_schedule(year):
    """지정된 연도의 모든 'Race' 세션 정보를 가져옵니다."""
    try:
        url = f"https://api.openf1.org/v1/sessions?year={year}&session_name=Race"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        schedule = []
        for session in data:
            schedule.append({
                "session_key": session.get("session_key"),
                "country_name": session.get("country_name"),
                "meeting_name": session.get("meeting_name"),
                "date_start": session.get("date_start"),
                "circuit_short_name": session.get("circuit_short_name")
            })
        
        schedule.sort(key=lambda x: x['date_start'])
        
        # 결과를 화면에 출력하고 파일로도 저장합니다.
        output_json = json.dumps(schedule, indent=2)
        print(output_json)
        
        # public/data 폴더에 schedule.json 으로 저장
        with open("public/data/schedule.json", "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"\n[성공] public/data/schedule.json 파일에 저장되었습니다.")

    except Exception as e:
        print(json.dumps([{"error": f"API 요청 실패: {e}"}]))

if __name__ == "__main__":
    target_year = 2025
    if len(sys.argv) > 1:
        try:
            target_year = int(sys.argv[1])
        except ValueError:
            print("[오류] 연도를 숫자로 입력해주세요. 예: python f1_get_gp_list.py 2025")
            sys.exit(1)
    
    print(f"{target_year}년 시즌 경기 목록을 가져옵니다...")
    get_schedule(target_year)