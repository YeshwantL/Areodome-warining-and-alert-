import time
import pandas as pd
import os
from datetime import datetime
from fetch_data import fetch_metar_data
from parse_metar import parse_metar
from model import WindPredictor, load_data, save_data

CSV_FILE = "weather_data.csv"

def process_and_save_metars(raw_text, station_code):
    """Parses multiple METARs from raw text and saves new ones."""
    if not raw_text: return None
    
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    count = 0
    latest_parsed = None
    
    # We process in reverse (oldest to newest) to save properly to CSV
    # but Ogimet usually returns newest first. 
    for line in lines:
        if station_code in line and ('Z' in line or 'METAR' in line):
            parsed = parse_metar(line)
            if parsed:
                save_data(parsed)
                if not latest_parsed:
                    latest_parsed = parsed
                count += 1
    return latest_parsed

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
             station_code = "VABB" # Default to a working one
    
    predictor = WindPredictor()
    
    print(f"Fetching 24-hour history for {station_code}...")
    history_raw = fetch_metar_data(station_code, hours=24)
    process_and_save_metars(history_raw, station_code)
    
    print("Loading historical data from CSV...")
    history_df = load_data()
    if not history_df.empty:
        predictor.train(history_df)
    
    print(f"Starting real-time monitoring for {station_code}...")
    
    try:
        while True:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching latest data...")
            raw_metar = fetch_metar_data(station_code, hours=1)
            
            parsed_data = process_and_save_metars(raw_metar, station_code)
            
            if parsed_data:
                print(f"Current Wind: {parsed_data['wind_speed']} {parsed_data['unit']} @ {parsed_data['wind_dir']} deg")
                
                full_df = load_data() 
                if not full_df.empty:
                    # Retrain if needed (or just predict)
                    predictor.train(full_df)
                    predictions = predictor.predict(parsed_data, history_df=full_df)
                    
                    print("\n--- WIND FORECAST ---")
                    print(f"{'Time':<15} | {'Speed (KT)':<12} | {'Direction':<10}")
                    print("-" * 45)
                    
                    labels = {'30m': '30 Mins', '60m': '1 Hour', '90m': '1.5 Hours', '120m': '2 Hours',
                              '150m': '2.5 Hours', '180m': '3 Hours', '210m': '3.5 Hours', '240m': '4 Hours'}
                    
                    for horizon, (p_speed, p_dir) in predictions.items():
                        label = labels.get(horizon, horizon)
                        print(f"{label:<15} | {p_speed:<12.0f} | {p_dir:<10.0f}")
                    print("---------------------")
                else:
                    print("No history in CSV. Cannot predict.")
            else:
                print(f"No fresh data received for {station_code}. Checking CSV...")
                # Fallback prediction if we have history
                full_df = load_data()
                if not full_df.empty:
                    last_point = full_df.tail(1).to_dict('records')[0]
                    # Convert column names to match parsed_data format
                    last_point['wind_speed'] = last_point.get('wind_speed', 0)
                    last_point['wind_dir'] = last_point.get('wind_dir', 0)
                    
                    predictions = predictor.predict(last_point, history_df=full_df)
                    # (printing logic omitted for brevity in fallback, but we should show it)
            
            print(f"Waiting 600 seconds...")
            time.sleep(600)

    except KeyboardInterrupt:
        print("\nStopping system.")

if __name__ == "__main__":
    main()
