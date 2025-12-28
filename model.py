"""
WIND PREDICTION LOGIC
Contains the WindPredictor class and data handling utilities for wind forecasting.
NOTE: This is NOT the database models file (which is models.py).
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

class WindPredictor:
    def __init__(self):
        self.horizons = ['30m', '60m', '90m', '120m', '150m', '180m', '210m', '240m']
        # We now predict U and V components separately for better directional accuracy
        self.models_u = {h: RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42) for h in self.horizons}
        self.models_v = {h: RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42) for h in self.horizons}
        self.is_trained = False

    def prepare_features(self, df):
        """Convert raw speed/dir/time into model-optimized features."""
        df = df.copy()
        
        # 1. Cyclical Time Features
        df['hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24)
        
        # 2. Wind Components (U, V)
        # Using standard meteorology formula (wind FROM direction)
        rad = np.radians(df['wind_dir'])
        df['u'] = -df['wind_speed'] * np.sin(rad)
        df['v'] = -df['wind_speed'] * np.cos(rad)
        
        # 3. Gust Component (if available)
        # Often gustiness is a good indicator of turbulence/change
        if 'wind_gust' in df.columns:
            df['gust_u'] = -df['wind_gust'] * np.sin(rad)
            df['gust_v'] = -df['wind_gust'] * np.cos(rad)
        else:
            df['gust_u'] = df['u']
            df['gust_v'] = df['v']

        # 4. Lags (Capturing momentum)
        for lag in [1, 2, 4]: # 30m, 60m, 120m ago
            df[f'u_lag{lag}'] = df['u'].shift(lag)
            df[f'v_lag{lag}'] = df['v'].shift(lag)
            df[f's_lag{lag}'] = df['wind_speed'].shift(lag)
            if 'wind_gust' in df.columns:
                df[f'g_lag{lag}'] = df['wind_gust'].shift(lag)
            
        return df.dropna()

    def prepare_data(self, df):
        if df.empty:
            return None

        df = df.copy()
        
        # Deduplicate: Drop exact same METAR for same station at same time
        if 'original' in df.columns:
            df = df.drop_duplicates(subset=['original', 'timestamp_obj'])

        if 'datetime_obj' not in df.columns:
             if 'timestamp_obj' in df.columns:
                 df['datetime_obj'] = pd.to_datetime(df['timestamp_obj'], format='mixed')
             else:
                 return None
        
        df = df.set_index('datetime_obj').sort_index()
        
        # Resample to 30min and handle missing values
        # We use mean for speed to smooth out jitter, and last for direction
        res_logic = {'wind_speed': 'mean', 'wind_dir': 'last'}
        if 'wind_gust' in df.columns:
            res_logic['wind_gust'] = 'max'
            
        df_resampled = df.resample('30min').agg(res_logic).ffill()
        
        return df_resampled

    def train(self, df):
        df_resampled = self.prepare_data(df)
        if df_resampled is None or len(df_resampled) < 15:
            print("Not enough data to train (need at least ~8 hours history).")
            return

        print(f"Training advanced models on {len(df_resampled)} samples...")
        
        df_feats = self.prepare_features(df_resampled)
        if len(df_feats) < 10:
            return

        feature_cols = ['hour_sin', 'hour_cos', 'u', 'v', 'u_lag1', 'v_lag1', 'u_lag2', 'v_lag2']
        if 'wind_gust' in df_resampled.columns:
             feature_cols += ['gust_u', 'gust_v']
        
        X_base = df_feats[feature_cols]
        
        shifts = {
            '30m': -1, '60m': -2, '90m': -3, '120m': -4,
            '150m': -5, '180m': -6, '210m': -7, '240m': -8
        }
        
        for horizon, shift_val in shifts.items():
            # We must shift the resampled df before feature engineering or align them
            # Easiest: shift the target columns in the already featured df
            y_u = df_feats['u'].shift(shift_val)
            y_v = df_feats['v'].shift(shift_val)
            
            valid = ~np.isnan(y_u) & ~np.isnan(y_v)
            if valid.sum() > 5:
                self.models_u[horizon].fit(X_base[valid], y_u[valid])
                self.models_v[horizon].fit(X_base[valid], y_v[valid])
                
        self.is_trained = True

    def predict(self, current_observation, history_df=None):
        """Predict wind with historical context if available."""
        if not self.is_trained:
            s = current_observation['wind_speed']
            d = current_observation['wind_dir']
            return {h: (s, d) for h in self.horizons}

        # 1. Prepare Features for the LAST point
        # We need the last few points for lags.
        if history_df is not None and not history_df.empty:
            resampled_hist = self.prepare_data(history_df)
            if resampled_hist is not None and len(resampled_hist) >= 4:
                # Add current observation to history for feature calculation
                curr_df = pd.DataFrame([current_observation])
                if 'timestamp_obj' in curr_df.columns:
                    curr_df['datetime_obj'] = pd.to_datetime(curr_df['timestamp_obj'], format='mixed')
                else:
                    curr_df['datetime_obj'] = datetime.now()
                curr_df = curr_df.set_index('datetime_obj')
                
                # Combine
                # Extract common columns to avoid concat errors
                common_cols = [c for c in resampled_hist.columns if c in curr_df.columns]
                combined = pd.concat([resampled_hist, curr_df[common_cols]])
                combined = combined.resample('30min').last().ffill()
                
                feats = self.prepare_features(combined)
                if not feats.empty:
                    X_input = feats.tail(1)
                    feature_cols = ['hour_sin', 'hour_cos', 'u', 'v', 'u_lag1', 'v_lag1', 'u_lag2', 'v_lag2']
                    if 'gust_u' in feats.columns:
                        feature_cols += ['gust_u', 'gust_v']
                    
                    X = X_input[feature_cols]
                else:
                    return self._persistent_fallback(current_observation)
            else:
                return self._persistent_fallback(current_observation)
        else:
            return self._persistent_fallback(current_observation)

        results = {}
        for h in self.horizons:
            try:
                pred_u = self.models_u[h].predict(X)[0]
                pred_v = self.models_v[h].predict(X)[0]
                
                # Convert back to speed/dir
                p_speed = np.sqrt(pred_u**2 + pred_v**2)
                p_dir_rad = np.arctan2(-pred_u, -pred_v)
                p_dir = np.degrees(p_dir_rad) % 360
                
                results[h] = (p_speed, p_dir)
            except:
                results[h] = (current_observation['wind_speed'], current_observation['wind_dir'])
        
        return results

    def _persistent_fallback(self, current_observation):
        s = current_observation['wind_speed']
        d = current_observation['wind_dir']
        return {h: (s, d) for h in self.horizons}

import os
from datetime import datetime

CSV_FILE = "weather_data.csv"

def load_data():
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            if 'timestamp_obj' in df.columns:
                 df['datetime_obj'] = pd.to_datetime(df['timestamp_obj'], format='mixed')
            return df
        except Exception as e:
            print(f"Error loading CSV: {e}")
            return pd.DataFrame()
            
    return pd.DataFrame()

def save_data(data_dict):
    if 'timestamp_obj' not in data_dict or not data_dict['timestamp_obj']:
         data_dict['timestamp_obj'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if 'wind_gust' not in data_dict:
        data_dict['wind_gust'] = data_dict['wind_speed']
    
    cols = ['original', 'wind_speed', 'wind_gust', 'wind_dir', 'unit', 'timestamp_str', 'timestamp_obj']
    df = pd.DataFrame([data_dict], columns=cols)
    
    if not os.path.exists(CSV_FILE):
        df.to_csv(CSV_FILE, index=False)
    else:
        df.to_csv(CSV_FILE, mode='a', header=False, index=False)