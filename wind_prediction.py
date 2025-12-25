import time
import pandas as pd
import os
from datetime import datetime
from fetch_data import get_latest_metar
from parse_metar import parse_metar
from model import WindPredictor, load_data, save_data

CSV_FILE = "weather_data.csv"


def main():
    print("=== Real-time Wind Prediction System ===")
    
    stations = {
        "1": {"code": "VASD", "name": "SHIRDI AIRPORT"},
        "2": {"code": "VAJJ", "name": "JUHU AIRPORT"},
        "3": {"code": "VAJL", "name": "JALGAON AIRPORT"},
        "4": {"code": "VAAU", "name": "AURANGABAD AIRPORT"},
        "5": {"code": "VOND", "name": "NANDED AIRPORT"},
        "6": {"code": "VAKP", "name": "KOLHAPUR AIRPORT"},
        "7": {"code": "VOSR", "name": "SINDHUDURG AIRPORT"},
        "8": {"code": "VASL", "name": "SOLAPUR AIRPORT"},
        "9": {"code": "VOLT", "name": "LATUR AIRPORT"},
        "10": {"code": "VOGA", "name": "MOPA AIRPORT"},
        "11": {"code": "VANM", "name": "NAVI MUMBAI AIRPORT"},
        "12": {"code": "VABB", "name": "MUMBAI AIRPORT"}
    }

    print("\nSelect a Station:")
    for key, val in stations.items():
        print(f"{key}. {val['code']} - {val['name']}")
    print("Or type a custom station code directly (e.g., VIDP).")

    user_input = input("\nEnter Choice or Code: ").strip()
    
    station_code = ""
    if user_input in stations:
        station_code = stations[user_input]["code"]
        print(f"Selected: {stations[user_input]['name']} ({station_code})")
    else:
        station_code = user_input.upper()
        if len(station_code) < 3:
             print("Invalid code. Using default VIDP.")
             station_code = "VIDP"
    
    if not station_code:
        print("Invalid station code. Exiting.")
        return

    predictor = WindPredictor()
    
    print("Loading historical data...")
    history_df = load_data()
    
    if not history_df.empty:
        history_df['datetime_obj'] = pd.to_datetime(history_df['timestamp_obj'], format='mixed')
        predictor.train(history_df)
    
    print(f"Starting monitoring for {station_code}. Press Ctrl+C to stop.")
    
    print("Checking data availability...")
    initial_check = get_latest_metar(station_code)
    if not initial_check:
        print(f"/!\\ WARNING: No data currently available for {station_code}.")
        print("    This station may not be reporting to the global network (NOAA/Ogimet).")
        print("    You can continue waiting, or Ctrl+C to select a different station.")
        print("    Working stations include: VABB, VASD, VAAU, VAJL, VOND, VOGA.")
    else:
        print("Data source connected successfully.")

    
    try:
        while True:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching data...")
            raw_metar = get_latest_metar(station_code)
            
            if raw_metar:
                lines = [l.strip() for l in raw_metar.strip().split('\n') if l.strip() and "METAR" in l]
                
                if not lines:
                    lines = [l.strip() for l in raw_metar.strip().split('\n') if l.strip() and len(l.strip()) > 20]
                
                if lines:
                    latest_metar = lines[0]
                    print(f"Latest METAR: {latest_metar[:60]}...")
                    
                    parsed_data = parse_metar(latest_metar)
                
                    if parsed_data:
                        print(f"Current Wind: {parsed_data['wind_speed']} {parsed_data['unit']} @ {parsed_data['wind_dir']} deg")
                        
                        save_data(parsed_data)
                        
                        parsed_data['datetime_obj'] = datetime.now() 
                        
                        full_df = load_data() 
                        if not full_df.empty:
                            full_df['datetime_obj'] = pd.to_datetime(full_df['timestamp_obj'], format='mixed')
                            predictor.train(full_df)
                            
                            predictions = predictor.predict(parsed_data)
                            
                            print("\n--- WIND FORECAST ---")
                            print(f"{'Time':<15} | {'Speed (KT)':<12} | {'Direction':<10}")
                            print("-" * 45)
                            
                            labels = {
                                '30m': '30 Mins', 
                                '60m': '1 Hour', 
                                '90m': '1 Hr 30 Min', 
                                '120m': '2 Hours',
                                '150m': '2 Hr 30 Min',
                                '180m': '3 Hours',
                                '210m': '3 Hr 30 Min',
                                '240m': '4 Hours'
                            }
                            
                            for horizon, (p_speed, p_dir) in predictions.items():
                                label = labels.get(horizon, horizon)
                                print(f"{label:<15} | {p_speed:<12.2f} | {p_dir:<10.2f}")
                            print("---------------------")
                        else:
                            print("Not enough history to predict yet.")
                        
                    else:
                        print("Failed to parse METAR (Format unexpected).")
                        print(f"DEBUG: Raw string was: '{latest_metar}'")
                else:
                    print(f"No valid METAR lines found in response.")
            else:
                print(f"No METAR data received for {station_code}. Station might be inactive.")
            
            wait_time = 600
            print(f"Waiting {wait_time} seconds...")
            time.sleep(wait_time)

    except KeyboardInterrupt:
        print("\nStopping system.")

if __name__ == "__main__":
    main()
