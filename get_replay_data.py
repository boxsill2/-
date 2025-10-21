# get_replay_data.py
import requests
import json
import argparse
from datetime import datetime


def _parse_iso(date_str):
    """Return timezone-aware datetime from API ISO strings."""
    if not date_str:
        return None
    try:
        # OpenF1는 UTC(+00:00) 오프셋이 있는 ISO 포맷을 사용합니다.
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None

API_BASE = 'https://api.openf1.org/v1'

def fetch_data(endpoint, params):
    """OpenF1 API로부터 데이터를 가져오는 공통 함수"""
    try:
        response = requests.get(f"{API_BASE}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        # 오류 발생 시, Node.js가 처리할 수 있도록 JSON 형태로 오류 메시지 출력
        print(json.dumps({"error": str(e)}))
        exit(1)

def get_race_times(session_key):
    """'Race Control' 메시지를 분석하여 실제 경주 시작 및 종료 시간을 찾습니다."""
    messages = fetch_data('race_control', {'session_key': session_key})

    if isinstance(messages, dict) and messages.get('error'):
        return messages

    # 날짜 순으로 정렬해 분석 정확도를 높입니다.
    sorted_messages = sorted(
        [msg for msg in messages if msg.get('date')],
        key=lambda msg: msg['date']
    )

    def find_first(predicate):
        return next((msg for msg in sorted_messages if predicate(msg)), None)

    def find_last(predicate):
        for msg in reversed(sorted_messages):
            if predicate(msg):
                return msg
        return None

    # 1) 'Race start' 메시지 우선, 2) 'Green flag', 3) 레이스 범주 첫 메시지 순으로 탐색합니다.
    race_start_msg = (
        find_first(lambda m: m.get('message', '').lower().startswith('race start'))
        or find_first(lambda m: 'green flag' in m.get('message', '').lower())
        or find_first(lambda m: m.get('category') == 'Race')
    )

    # 1) 체커드 플래그, 2) 레이스 범주 마지막 메시지를 종료 시각으로 사용합니다.
    chequered_flag_msg = (
        find_last(lambda m: 'chequered flag' in m.get('message', '').lower())
        or find_last(lambda m: m.get('category') == 'Race')
    )

    if not race_start_msg or not chequered_flag_msg:
        return {"error": "Could not determine race start or end time from race control messages."}

    race_start_date = _parse_iso(race_start_msg.get('date'))
    race_end_date = _parse_iso(chequered_flag_msg.get('date'))

    if not race_start_date or not race_end_date:
        return {"error": "Invalid race control timestamps returned by OpenF1."}

    if race_end_date <= race_start_date:
        return {"error": "Race control end time is not after start time."}

    return {
        "race_start_date": race_start_msg['date'],
        "race_end_date": chequered_flag_msg['date'],
        "all_messages": sorted_messages  # DNF 등 다른 정보 처리를 위해 전체 메시지 포함
    }

def get_data_chunk(session_key, start_iso, end_iso):
    """지정된 시간 범위의 위치, 순위 데이터를 가져옵니다."""
    params = {'session_key': session_key, 'date>': start_iso, 'date<': end_iso}
    
    # 여러 데이터를 동시에 가져오기 (실제로는 비동기 처리가 더 효율적이지만, 단순화를 위해 순차 처리)
    locations = fetch_data('location', params)
    positions = fetch_data('position', params)
    
    return {
        "locations": locations,
        "positions": positions
    }

def main():
    """명령줄 인자를 받아 요청을 처리하고 결과를 JSON으로 출력합니다."""
    parser = argparse.ArgumentParser(description="Fetch F1 replay data from OpenF1 API.")
    # 어떤 종류의 데이터를 가져올지 선택하는 인자 추가
    parser.add_argument('task', choices=['race_times', 'chunk'], help="Task to perform: 'race_times' or 'chunk'.")
    parser.add_argument('--session_key', required=True, help="The session key for the race.")
    parser.add_argument('--start_time', help="Start time in ISO format (for 'chunk' task).")
    parser.add_argument('--end_time', help="End time in ISO format (for 'chunk' task).")

    args = parser.parse_args()
    
    result = {}
    if args.task == 'race_times':
        result = get_race_times(args.session_key)
    elif args.task == 'chunk':
        if not args.start_time or not args.end_time:
            result = {"error": "--start_time and --end_time are required for 'chunk' task."}
        else:
            result = get_data_chunk(args.session_key, args.start_time, args.end_time)

    # 결과를 JSON 형태로 표준 출력(print)하여 Node.js 서버에 전달
    print(json.dumps(result))

if __name__ == '__main__':
    main()