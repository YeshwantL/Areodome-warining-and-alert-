import re
from datetime import datetime

def parse_metar(metar_str):
    """
    Simpler METAR parser to extract wind speed, direction, and timestamp.
    Example: VABB 201030Z 28005KT 5000 HZ FEW025 32/24 Q1012 NOSIG
    """
    try:
        # 1. Extract station (e.g., VABB)
        station_match = re.search(r'^([A-Z]{4})', metar_str)
        station = station_match.group(1) if station_match else "Unknown"

        # 2. Extract Timestamp (e.g., 201030Z -> Day 20, 10:30 UTC)
        time_match = re.search(r'(\d{2})(\d{2})(\d{2})Z', metar_str)
        timestamp_str = ""
        if time_match:
            day, hour, minute = time_match.groups()
            now = datetime.now()
            # Note: This is an approximation of the actual date
            timestamp_str = f"{now.year}-{now.month:02d}-{day} {hour}:{minute}:00"

        # 3. Extract Wind (e.g., 28005KT or VRB02KT)
        # Pattern: (Direction 3 digits or VRB)(Speed 2-3 digits)(Unit KT/MPS)
        wind_match = re.search(r'([0-9]{3}|VRB)([0-9]{2,3})(KT|MPS|G[0-9]{2,3})', metar_str)
        
        if wind_match:
            dir_str, speed_str, unit = wind_match.groups()
            
            # Convert VRB to a default or keep as 0? 
            # For simplistic prediction, let's treat VRB as -1 or 0, 
            # but ideally we handle it. Here we use 0.
            direction = 0 if dir_str == 'VRB' else int(dir_str)
            
            # Handle gusts (e.g. 10G20KT)
            if 'G' in unit:
                # Just take the base speed for now, or handle specifically
                speed = int(speed_str)
            else:
                speed = int(speed_str)
            
            # Simple unit normalization KT
            actual_unit = "KT"
            if "MPS" in unit:
                speed = speed * 1.94384 # m/s to knots
            
            return {
                "original": metar_str,
                "wind_speed": speed,
                "wind_dir": direction,
                "unit": actual_unit,
                "timestamp_str": time_match.group(0) if time_match else "",
                "timestamp_obj": timestamp_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        return None
    except Exception as e:
        print(f"Error parsing METAR: {e}")
        return None
