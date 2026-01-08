"""
WIND PREDICTION LOGIC
Contains the WindPredictor class and data handling utilities for wind forecasting.
NOTE: This is NOT the database models file (which is models.py).
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

class WindPredictor:
    def __init__(self):
        self.horizons = ['30m', '60m', '90m', '120m', '150m', '180m', '210m', '240m']
        # Switch to GradientBoostingRegressor for better performance on structured data
        self.models_u = {h: GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42) for h in self.horizons}
        self.models_v = {h: GradientBoostingRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42) for h in self.horizons}
        self.is_trained = False

    def prepare_features(self, df):
        """Convert raw speed/dir/time into model-optimized features."""
        df = df.copy()
        
        # 1. Cyclical Time Features
        df['hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24)
        
        # 2. Wind Components (U, V)
        rad = np.radians(df['wind_dir'])
        df['u'] = -df['wind_speed'] * np.sin(rad)
        df['v'] = -df['wind_speed'] * np.cos(rad)
        
        # 3. Gust Component (if available)
        if 'wind_gust' in df.columns:
            df['gust_u'] = -df['wind_gust'] * np.sin(rad)
            df['gust_v'] = -df['wind_gust'] * np.cos(rad)
        else:
            df['gust_u'] = df['u']
            df['gust_v'] = df['v']

        # 4. Thermodynamic Features (Temp & Pressure)
        # Using ffill in case some are missing
        if 'temperature' in df.columns:
            df['temperature'] = df['temperature'].ffill()
        if 'altimeter' in df.columns:
            df['altimeter'] = df['altimeter'].ffill()

        # 5. Lags (increased to 6 for better long-term context)
        for lag in [1, 2, 4, 6]:
            df[f'u_lag{lag}'] = df['u'].shift(lag)
            df[f'v_lag{lag}'] = df['v'].shift(lag)
            df[f's_lag{lag}'] = df['wind_speed'].shift(lag)
            if 'temperature' in df.columns:
                df[f't_lag{lag}'] = df['temperature'].shift(lag)
            if 'altimeter' in df.columns:
                df[f'a_lag{lag}'] = df['altimeter'].shift(lag)
            
        return df.dropna()

    def prepare_data(self, df):
        if df.empty:
            return None

        df = df.copy()
        
        # Deduplicate
        if 'original' in df.columns:
            df = df.drop_duplicates(subset=['original', 'timestamp_obj'])

        if 'datetime_obj' not in df.columns:
             if 'timestamp_obj' in df.columns:
                 df['datetime_obj'] = pd.to_datetime(df['timestamp_obj'], format='mixed')
             else:
                 return None
        
        df = df.set_index('datetime_obj').sort_index()
        
        # Resample logic
        res_logic = {'wind_speed': 'mean', 'wind_dir': 'last'}
        if 'wind_gust' in df.columns:
            res_logic['wind_gust'] = 'max'
        if 'temperature' in df.columns:
            res_logic['temperature'] = 'mean'
        if 'altimeter' in df.columns:
            res_logic['altimeter'] = 'mean'
            
        df_resampled = df.resample('30min').agg(res_logic).ffill()
        
        return df_resampled

    def train(self, df):
        # Filter context (already resampled in prepare_data)
        df_resampled = self.prepare_data(df)
        
        # 5. DATA QUALITY SAFEGUARDS
        if df_resampled is None or len(df_resampled) < 20:
            print("Not enough history for ML. Using persistence baseline.")
            self.is_trained = False
            return

        print(f"Training aviation-optimized models on {len(df_resampled)} samples...")
        
        df_feats = self.prepare_features(df_resampled)
        if len(df_feats) < 10:
            return

        # Explicit Circular Handling (U/V components already prepared in prepare_features)
        feature_cols = ['hour_sin', 'hour_cos', 'u', 'v', 'u_lag1', 'v_lag1', 'u_lag2', 'v_lag2', 'u_lag4', 'v_lag4']
        
        if 'station' in df_resampled.columns:
            stations = sorted(df_resampled['station'].unique())
            self.station_map = {s: i for i, s in enumerate(stations)}
            df_feats['station_id'] = df_feats['station'].map(self.station_map)
            feature_cols += ['station_id']
        else:
            self.station_map = {}

        if 'temperature' in df_resampled.columns:
            feature_cols += ['temperature', 't_lag1', 't_lag2']
        if 'altimeter' in df_resampled.columns:
            feature_cols += ['altimeter', 'a_lag1', 'a_lag2']
        
        self.feature_cols = feature_cols
        X_base = df_feats[feature_cols]
        
        shifts = {
            '30m': -1, '60m': -2, '90m': -3, '120m': -4,
            '150m': -5, '180m': -6, '210m': -7, '240m': -8
        }
        
        for horizon, shift_val in shifts.items():
            y_u = df_feats['u'].shift(shift_val)
            y_v = df_feats['v'].shift(shift_val)
            
            valid = ~np.isnan(y_u) & ~np.isnan(y_v)
            if valid.sum() > 5:
                # Use smaller max_depth for stability
                self.models_u[horizon] = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
                self.models_v[horizon] = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
                self.models_u[horizon].fit(X_base[valid], y_u[valid])
                self.models_v[horizon].fit(X_base[valid], y_v[valid])
                
        self.is_trained = True

    def predict(self, current_observation, history_df=None):
        """Aviation-correct wind prediction with persistence, smoothing, and realism."""
        
        s_curr = current_observation.get('wind_speed', 0)
        d_curr = current_observation.get('wind_dir', 0)
        rad_curr = np.radians(d_curr)
        u_pers = -s_curr * np.sin(rad_curr)
        v_pers = -s_curr * np.cos(rad_curr)

        # Baseline: If not trained, return persistence with a SLIGHT diurnal swing to avoid "frozen" values
        if not self.is_trained:
            return self._dynamic_climatology(current_observation)

        # 1. Prepare Prediction Features
        X = None
        if history_df is not None and not history_df.empty:
            # Station-specific filtering
            if 'station' in current_observation and 'station' in history_df.columns:
                 station_history = history_df[history_df['station'] == current_observation['station']]
                 if len(station_history) < 15: 
                      # Try global training if local is thin but global is large
                      if len(history_df) > 100:
                          station_history = history_df
                      else:
                          return self._dynamic_climatology(current_observation)
            else:
                 station_history = history_df

            resampled_hist = self.prepare_data(station_history)
            if resampled_hist is not None and len(resampled_hist) >= 6:
                curr_df = pd.DataFrame([current_observation])
                curr_df['datetime_obj'] = pd.to_datetime(current_observation.get('timestamp_obj', datetime.now()), format='mixed')
                curr_df = curr_df.set_index('datetime_obj')
                
                common_cols = [c for c in resampled_hist.columns if c in curr_df.columns]
                combined = pd.concat([resampled_hist, curr_df[common_cols]])
                combined = combined.resample('30min').last().ffill()
                
                feats = self.prepare_features(combined)
                if not feats.empty:
                    X_input = feats.tail(1).copy()
                    if hasattr(self, 'station_map') and 'station' in X_input.columns:
                        X_input['station_id'] = X_input['station'].map(self.station_map).fillna(-1)
                    X = X_input[[c for c in self.feature_cols if c in X_input.columns]]

        if X is None:
            return self._dynamic_climatology(current_observation)

        # 2. Horizon-weighted Blending (Dynamic alpha)
        # alpha is model weight. alpha starts low (high persistence) and grows.
        weights = {
            '30m': 0.15, '60m': 0.30, '90m': 0.45, '120m': 0.60,
            '150m': 0.70, '180m': 0.80, '210m': 0.90, '240m': 1.0
        }

        results = {}
        last_s, last_d = s_curr, d_curr
        
        for h in self.horizons:
            try:
                pred_u_raw = self.models_u[h].predict(X)[0]
                pred_v_raw = self.models_v[h].predict(X)[0]
                
                alpha = weights.get(h, 0.5)
                # Blend
                pred_u = alpha * pred_u_raw + (1 - alpha) * u_pers
                pred_v = alpha * pred_v_raw + (1 - alpha) * v_pers

                p_speed = np.sqrt(pred_u**2 + pred_v**2)
                p_dir_rad = np.arctan2(-pred_u, -pred_v)
                p_dir = np.degrees(p_dir_rad) % 360
                
                # Continuity Smoothing
                diff_s = p_speed - last_s
                if abs(diff_s) > 3.5: # 7 KT per hour approx
                    p_speed = last_s + np.sign(diff_s) * 3.5
                
                # Aviation Realism
                p_speed = np.clip(p_speed, 0, 45)
                if p_speed < 1.0: p_speed = 0.0
                
                final_speed = float(round(p_speed))
                final_dir = float(round(p_dir / 5) * 5) % 360
                
                results[h] = (final_speed, final_dir)
                last_s, last_d = final_speed, final_dir
            except:
                # Horizon specific fallback
                results[h] = self._dynamic_climatology(current_observation)[h]
        
        return results

    def _dynamic_climatology(self, obs):
        """Returns persistence plus a slight diurnal trend to avoid flat lines."""
        s = obs.get('wind_speed', 0)
        d = obs.get('wind_dir', 0)
        now_hour = datetime.now().hour
        
        results = {}
        for i, h in enumerate(self.horizons):
            # i = 0 (30m), 1 (60m) etc.
            # Add a slight +/- 1.5 KT swing based on time of day
            # (Wind is usually higher in afternoon)
            hour_offset = (i + 1) * 0.5
            target_hour = (now_hour + hour_offset) % 24
            
            # Simple diurnal speed factor (peaks at 15:00 UTC/IST approx)
            diurnal = np.sin(2 * np.pi * (target_hour - 9) / 24) * 1.5
            
            p_s = max(0, float(round(s + diurnal)))
            # Direction stays mostly persistence but with a slight drift
            drift = np.cos(2 * np.pi * (target_hour - 12) / 24) * 5
            p_d = float(round((d + drift) / 5) * 5) % 360
            
            results[h] = (p_s, p_d)
        return results

    def _persistent_fallback(self, current_observation):
        return self._dynamic_climatology(current_observation)

import os
from datetime import datetime

CSV_FILE = "weather_data.csv"

def load_data():
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            if 'original' in df.columns and 'timestamp_obj' in df.columns:
                 df = df.drop_duplicates(subset=['original', 'timestamp_obj'])
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
    
    # Check for duplicate in existing CSV before saving
    if os.path.exists(CSV_FILE):
        try:
            # We don't want to load the WHOLE file every time, but for low-rate updates it's okay.
            # Better: check just the last few lines.
            last_lines = pd.read_csv(CSV_FILE).tail(10)
            if data_dict['original'] in last_lines['original'].values:
                return # Skip duplicate
        except:
            pass

    if 'wind_gust' not in data_dict:
        data_dict['wind_gust'] = data_dict['wind_speed']
    
    cols = ['station', 'original', 'wind_speed', 'wind_gust', 'wind_dir', 'temperature', 'altimeter', 'unit', 'timestamp_str', 'timestamp_obj']
    df = pd.DataFrame([data_dict], columns=cols)
    
    if not os.path.exists(CSV_FILE):
        df.to_csv(CSV_FILE, index=False)
    else:
        try:
            with open(CSV_FILE, 'r') as f:
                header = f.readline().strip().split(',')
            if len(header) != len(cols):
                backup_name = f"weather_data_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
                os.rename(CSV_FILE, backup_name)
                df.to_csv(CSV_FILE, index=False)
            else:
                df.to_csv(CSV_FILE, mode='a', header=False, index=False)
        except:
            df.to_csv(CSV_FILE, mode='a', header=False, index=False)