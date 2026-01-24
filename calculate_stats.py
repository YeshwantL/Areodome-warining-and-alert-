import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from model import WindPredictor, load_data

def calculate_stats():
    print("=== Model Accuracy Calculation ===")
    
    # 1. Load Historical Data
    print("Loading data...")
    df = load_data()
    if df.empty:
        print("Error: No data found in weather_data.csv")
        return

    # Ensure valid datetime
    if 'timestamp_obj' in df.columns:
        df['datetime_obj'] = pd.to_datetime(df['timestamp_obj'], format='mixed')
    
    # 2. Filter for decent amount of history
    # We need enough data to train AND test.
    # Group by station
    stations = df['station'].unique()
    
    overall_stats = {
        'total_predictions': 0,
        'speed_mae': [],
        'dir_mae': [],
        'speed_acc_5kt': 0, # Within 5 KT
        'dir_acc_30deg': 0  # Within 30 Degrees
    }
    
    predictor = WindPredictor()
    
    for station in stations:
        print(f"\nProcessing {station}...")
        station_df = df[df['station'] == station].sort_values('datetime_obj')
        
        if len(station_df) < 50:
            print(f"Skipping {station}: Not enough data ({len(station_df)} rows)")
            continue
            
        # 3. Time Series Cross-Validation (Walk-Forward)
        # We start predicting after first 24 samples (12 hours)
        # And predict for every subsequent point where we have a future verification point.
        
        # Resample to 30min to match model horizons
        # But we verify against ACTUAL observations which might be irregular.
        # So we predict at time T, and assume we had data up to T.
        
        # Optimization: Don't retrain on EVERY step, maybe every 10 steps or train once on past?
        # For true stats, we should ideally retrain update.
        # To be faster, we'll train on first 50%, then predict rest without retraining (static model)
        # OR better: Rolling window.
        
        # Let's do a simple 70/30 split test.
        train_size = int(len(station_df) * 0.7)
        train_df = station_df.iloc[:train_size]
        test_df = station_df.iloc[train_size:]
        
        predictor.train(train_df)
        if not predictor.is_trained:
            print("Model failed to train (insufficient valid targets).")
            continue
            
        print(f"Testing on {len(test_df)} samples...")
        
        for i in range(len(test_df) - 8): # Ensure we have room for 4hr horizon check
            current_obs = test_df.iloc[i].to_dict()
            current_time = current_obs['datetime_obj']
            
            # Predict
            predictions = predictor.predict(current_obs, history_df=train_df) # Pass train_df context
            
            # Verify against future actuals
            for horizon, (pred_spd, pred_dir) in predictions.items():
                minutes = int(horizon[:-1])
                target_time = current_time + timedelta(minutes=minutes)
                
                # Find actual closest to target_time (within 15 mins)
                # Filter strictly from original raw data (station_df) to be accurate
                
                # Check absolute difference
                time_diffs = abs(station_df['datetime_obj'] - target_time)
                closest_idx = time_diffs.idxmin()
                
                if time_diffs[closest_idx].total_seconds() > 1800: # > 30 mins away
                    continue
                    
                actual = station_df.loc[closest_idx]
                act_spd = actual['wind_speed']
                act_dir = actual['wind_dir']
                
                # Metrics
                s_err = abs(pred_spd - act_spd)
                
                # Direction Error (Circular)
                d_err = abs(pred_dir - act_dir)
                d_err = min(d_err, 360 - d_err)
                
                overall_stats['speed_mae'].append(s_err)
                overall_stats['dir_mae'].append(d_err)
                
                if s_err <= 5.0:
                    overall_stats['speed_acc_5kt'] += 1
                if d_err <= 30.0:
                    overall_stats['dir_acc_30deg'] += 1
                    
                overall_stats['total_predictions'] += 1

    # 4. Generate Report
    if overall_stats['total_predictions'] == 0:
        print("\nNo valid predictions could be verified.")
        return

    avg_s_mae = np.mean(overall_stats['speed_mae'])
    avg_d_mae = np.mean(overall_stats['dir_mae'])
    acc_s = (overall_stats['speed_acc_5kt'] / overall_stats['total_predictions']) * 100
    acc_d = (overall_stats['dir_acc_30deg'] / overall_stats['total_predictions']) * 100
    
    report = f"""
============================================
       WIND MODEL ACCURACY REPORT
============================================
Total Predictions Verified: {overall_stats['total_predictions']}

--- Performance Metrics ---
Wind Speed MAE:       {avg_s_mae:.2f} KT
Wind Direction MAE:   {avg_d_mae:.2f} °

--- Accuracy Thresholds ---
Speed Accuracy (within ±5 KT):      {acc_s:.1f}%
Direction Accuracy (within ±30°):   {acc_d:.1f}%
============================================
"""
    print(report)
    
    with open("stats_report.txt", "w") as f:
        f.write(report)
    print("Report saved to stats_report.txt")

if __name__ == "__main__":
    calculate_stats()
