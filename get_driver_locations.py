# get_driver_locations.py
import sys
import requests
import json

def get_data_in_range(session_key, start_time_str, end_time_str):
    """
    위치, 순위, 차량 데이터, 레이스 컨트롤 메시지를 각각 독립적으로 가져옵니다.
    """
    locations = []
    positions = []
    car_data = []
    race_control = []
    error_message = None

    try:
        # 각 API 엔드포인트에 데이터 요청
        url_loc = f"https://api.openf1.org/v1/location?session_key={session_key}&date>={start_time_str}&date<{end_time_str}"
        response_loc = requests.get(url_loc, timeout=30)
        response_loc.raise_for_status()
        locations = response_loc.json()

        url_pos = f"https://api.openf1.org/v1/position?session_key={session_key}&date>={start_time_str}&date<{end_time_str}"
        response_pos = requests.get(url_pos, timeout=30)
        response_pos.raise_for_status()
        positions = response_pos.json()

        url_car = f"https://api.openf1.org/v1/car_data?session_key={session_key}&date>={start_time_str}&date<{end_time_str}"
        response_car = requests.get(url_car, timeout=30)
        response_car.raise_for_status()
        car_data = response_car.json()

        url_rc = f"https://api.openf1.org/v1/race_control?session_key={session_key}&date>={start_time_str}&date<{end_time_str}"
        response_rc = requests.get(url_rc, timeout=30)
        response_rc.raise_for_status()
        race_control = response_rc.json()

    except requests.exceptions.RequestException as e:
        error_message = f"API 서버 접속에 실패했습니다. PC의 네트워크 연결 또는 방화벽 설정을 확인해주세요. (원본 에러: {e})"
    
    except Exception as e:
        error_message = f"데이터 처리 중 알 수 없는 오류가 발생했습니다: {e}"

    if error_message:
        print(json.dumps({"error": error_message, "locations": [], "positions": [], "car_data": [], "race_control": []}))
    else:
        print(json.dumps({
            "locations": locations,
            "positions": positions,
            "car_data": car_data,
            "race_control": race_control
        }))

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(json.dumps({"error": "세션 키, 시작 시간, 종료 시간을 인자로 전달해야 합니다."}))
        sys.exit(1)
    
    get_data_in_range(sys.argv[1], sys.argv[2], sys.argv[3])