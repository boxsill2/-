import fastf1
import json
import sys
import os
from datetime import datetime, timedelta
import pandas as pd

def get_session_with_cache(year, event, session_identifier):
    cache_path = os.path.join(os.path.dirname(__file__), 'cache')
    if not os.path.exists(cache_path):
        os.makedirs(cache_path)
    fastf1.Cache.enable_cache(cache_path)
    
    try:
        # --- 수정된 부분: 새로운 함수 사용 ---
        session = fastf1.get_session(int(year), event, session_identifier)
        session.load(laps=True, telemetry=False, weather=False, messages=True)
        return session
    except Exception as e:
        return {'error': f"FastF1 세션 로드 실패: {e}"}

def get_race_times(year, event, session_identifier):
    session = get_session_with_cache(year, event, session_identifier)
    if isinstance(session, dict) and 'error' in session:
        return session

    all_messages = []
    if session.race_control_messages is not None and not session.race_control_messages.empty:
        messages_df = session.race_control_messages.copy()
        messages_df['Date'] = messages_df['Date'].apply(lambda x: x.isoformat() if pd.notnull(x) else None)
        messages_df.fillna('', inplace=True)
        all_messages = messages_df.to_dict(orient='records')

    race_start_date = None
    race_end_date = None

    if all_messages:
        for msg in all_messages:
            message_text = msg.get('Message', '').lower()
            if 'race start' in message_text or msg.get('Category', '').lower() == 'racestart':
                if msg.get('Date'):
                    race_start_date = datetime.fromisoformat(msg['Date'])
            elif 'chequered flag' in message_text:
                if msg.get('Date'):
                    race_end_date = datetime.fromisoformat(msg['Date'])
        
        if race_start_date and not race_end_date and all_messages:
            last_message_date_str = all_messages[-1].get('Date')
            if last_message_date_str:
                race_end_date = datetime.fromisoformat(last_message_date_str)

    if not race_start_date and session.date:
        race_start_date = session.date.to_pydatetime()

    if not race_end_date and not session.laps.empty:
        last_lap = session.laps.iloc[-1]
        if pd.notnull(last_lap['LapStartDate']) and pd.notnull(last_lap['LapDuration']):
             race_end_date = (last_lap['LapStartDate'] + last_lap['LapDuration']).to_pydatetime()
        elif race_start_date:
            race_end_date = race_start_date + timedelta(hours=2)

    if not race_start_date or not race_end_date:
        if session.session_start_time:
             race_start_date = session.session_start_time.to_pydatetime()
        if session.session_end_time:
             race_end_date = session.session_end_time.to_pydatetime()
        
        if not race_start_date or not race_end_date:
             return {'error': 'Could not determine race start or end time from any available data.'}

    return {
        'race_start_date': race_start_date.isoformat(),
        'race_end_date': race_end_date.isoformat(),
        'all_messages': all_messages
    }

if __name__ == '__main__':
    command = sys.argv[1]
    
    if command == 'race_times':
        # --- 수정된 부분: 인자 파싱 방식 변경 ---
        args = {sys.argv[i].replace('--', ''): sys.argv[i+1] for i in range(2, len(sys.argv), 2)}
        year = args.get('year')
        event = args.get('event')
        session_name = args.get('session')
        
        if year and event and session_name:
            try:
                result = get_race_times(year, event, session_name)
                print(json.dumps(result, indent=4))
            except Exception as e:
                print(json.dumps({'error': str(e)}))
        else:
            print(json.dumps({'error': 'Year, event, and session name arguments are required'}))