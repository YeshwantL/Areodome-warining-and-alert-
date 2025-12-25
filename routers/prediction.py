from fastapi import APIRouter, HTTPException, BackgroundTasks
import pandas as pd
from datetime import datetime
from fetch_data import get_latest_metar
from parse_metar import parse_metar
from model import WindPredictor, load_data, save_data

router = APIRouter(
    prefix="/prediction",
    tags=["Prediction"]
)

predictor = WindPredictor()

# Load initial data on import? Or lazy load?
# Let's try to train on startup if possible, or lazy load on first request.
# For simplicity, lazy load inside endpoint or have a global state.

def refresh_model():
    history_df = load_data()
    if not history_df.empty:
        history_df['datetime_obj'] = pd.to_datetime(history_df['timestamp_obj'], format='mixed')
        predictor.train(history_df)

@router.get("/{station_code}")
def get_prediction(station_code: str, background_tasks: BackgroundTasks):
    station_code = station_code.upper()
    
    # 1. Fetch latest data
    raw_metar = get_latest_metar(station_code)
    if not raw_metar:
        raise HTTPException(status_code=404, detail="Could not fetch data for station")
    
    # Extract line
    lines = [l.strip() for l in raw_metar.strip().split('\n') if l.strip() and "METAR" in l]
    if not lines:
        lines = [l.strip() for l in raw_metar.strip().split('\n') if l.strip() and len(l.strip()) > 20]
        
    if not lines:
        raise HTTPException(status_code=404, detail="No valid METAR lines found")
        
    latest_metar = lines[0]
    parsed_data = parse_metar(latest_metar)
    
    if not parsed_data:
        raise HTTPException(status_code=500, detail="Failed to parse METAR")
        
    # 2. Save data
    save_data(parsed_data)
    
    # 3. Predict
    # Train model first (incremental or full retrain)
    # Ideally should be async or background for training speed, but for demo:
    refresh_model()
    
    parsed_data['datetime_obj'] = datetime.now()
    predictions = predictor.predict(parsed_data)
    
    # 4. Format response
    response = {
        "station": station_code,
        "current": parsed_data,
        "forecast": {}
    }
    
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
        response["forecast"][labels.get(horizon, horizon)] = {
            "speed_kt": round(p_speed, 2),
            "direction": round(p_dir, 2)
        }
        
    return response
