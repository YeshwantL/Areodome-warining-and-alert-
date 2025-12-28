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

        # 3. Extract Wind (e.g., 28005KT or 28010G20KT)
        # Pattern: (Direction 3 digits or VRB)(Speed 2-3 digits)(Optional G + Guest speed 2-3 digits)(Unit KT/MPS etc)
        # We look for something like 28005KT or 28005G15KT
        wind_match = re.search(r'([0-9]{3}|VRB)([0-9]{2,3})(G[0-9]{2,3})?(KT|MPS|KPH)', metar_str)
        
        if wind_match:
            dir_str, speed_str, gust_str, unit = wind_match.groups()
            
            direction = 0 if dir_str == 'VRB' else int(dir_str)
            speed = int(speed_str)
            gust = int(gust_str[1:]) if gust_str else speed
            
            # Simple unit normalization to KT
            actual_unit = "KT"
            if "MPS" in unit:
                speed = speed * 1.94384
                gust = gust * 1.94384
            elif "KPH" in unit:
                speed = speed * 0.539957
                gust = gust * 0.539957
            
            return {
                "original": metar_str,
                "wind_speed": round(speed, 2),
                "wind_gust": round(gust, 2),
                "wind_dir": direction,
                "unit": actual_unit,
                "timestamp_str": time_match.group(0) if time_match else "",
                "timestamp_obj": timestamp_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        return None
    except Exception as e:
        print(f"Error parsing METAR: {e}")
        return None
