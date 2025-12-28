import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Mocking parts or just importing
sys.path.append(os.getcwd())
from model import WindPredictor
from parse_metar import parse_metar

def test_forecast_continuity():
    print("Testing Forecast Continuity and Gust Handling...")
    
    # 1. Test Parsing with Gusts
    metar_with_gust = "VABB 281400Z 28010G20KT 5000 HZ NSC 27/17 Q1013"
    parsed = parse_metar(metar_with_gust)
    print(f"Parsed Gust: {parsed.get('wind_gust')} KT (Expected 20)")
    assert parsed.get('wind_gust') == 20
    
    # 2. Test Prediction with History
    predictor = WindPredictor()
    
    # Create fake history: declining wind
    history = []
    start_time = datetime.now() - timedelta(hours=5)
    for i in range(10):
        t = start_time + timedelta(minutes=30*i)
        history.append({
            "original": f"TEST {t.strftime('%d%H%M')}Z",
            "wind_speed": 15 - i, # Declining speed
            "wind_dir": 270,
            "timestamp_obj": t.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    history_df = pd.DataFrame(history)
    predictor.train(history_df)
    
    current = {
        "wind_speed": 5,
        "wind_dir": 270,
        "timestamp_obj": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "datetime_obj": datetime.now()
    }
    
    print("\nRunning prediction with history context...")
    preds = predictor.predict(current, history_df=history_df)
    
    print(f"Current: 5 KT")
    for horizon, (speed, dir) in preds.items():
        print(f"  {horizon}: {speed:.2f} KT")
        # Since history shows decline, we expect lower or steady low speed, not a jump to 0 or 100
        assert 0 <= speed <= 15

    print("\nVerification Successful: Continuity and Gusts handled.")

if __name__ == "__main__":
    test_forecast_continuity()
