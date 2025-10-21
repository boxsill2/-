# f1_get_gp_list.py
import requests
import json
import sys
import os

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
                "session_name": session.get("session_name"),
                "session_year": session.get("year"),
                "country_name": session.get("country_name"),
                "meeting_name": session.get("meeting_name"),
                "date_start": session.get("date_start"),
                "circuit_short_name": session.get("circuit_short_name")
            })
        
        schedule.sort(key=lambda x: x['date_start'])
        
        # public/data 폴더 경로 설정
        output_dir = "public/data"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        output_path = os.path.join(output_dir, "schedule.json")
        
        output_json = json.dumps(schedule, indent=2)
        print(output_json)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"\n[성공] {output_path} 파일에 저장되었습니다.")

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