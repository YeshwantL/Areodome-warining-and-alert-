import sys
import os
from fastapi import APIRouter, HTTPException, BackgroundTasks
import pandas as pd
from datetime import datetime

# Allow standalone execution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    refresh_model()
    
    history_df = load_data()
    # Filter history for this station to provide context
    station_history = history_df[history_df['original'].str.contains(station_code, na=False)] if not history_df.empty else pd.DataFrame()
    
    parsed_data['datetime_obj'] = datetime.now()
    predictions = predictor.predict(parsed_data, history_df=station_history)
    
    # --- Persistence Correction ---
    # We want the "+0m" (current) to match perfectly, and smooth out the transition.
    current_speed = parsed_data['wind_speed']
    current_dir = parsed_data['wind_dir']
    
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
    
    # Implementation of Persistence Correction (Decaying Bias)
    # If model says 10kts but METAR is 15kts, we add +5kts to 30m, +3.75 to 60m...
    # For now, let's just ensure continuity by blending or just reporting direct model output 
    # if it's already reasonably close.
    
    for i, (horizon, (p_speed, p_dir)) in enumerate(predictions.items()):
        # Decaying persistence correction formula:
        # horizon_index starts at 1 (30m)
        decay = 1.0 / (i + 1) 
        # Corrected speed = Predicted + (Actual - Predicted_now) * decay
        # But we don't have "Predicted_now" easily without a separate 0m prediction.
        # Simple approach: Bias the first few points towards 'current'
        
        corrected_speed = p_speed
        # If it's the very next point (+30m), give it 50% weight from current
        if i == 0:
            corrected_speed = (current_speed * 0.5) + (p_speed * 0.5)
        elif i == 1:
            corrected_speed = (current_speed * 0.25) + (p_speed * 0.75)
            
        response["forecast"][labels.get(horizon, horizon)] = {
            "speed_kt": round(corrected_speed, 2),
            "direction": round(p_dir, 2)
        }
        
    return response
