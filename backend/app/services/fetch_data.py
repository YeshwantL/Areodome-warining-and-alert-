import requests
import time
from datetime import datetime, timedelta

def fetch_metar_data(station_code, hours=12):
    """
    Fetches METAR data for a given station for the last N hours.
    Tries Ogimet as the primary source for historical/regional data.
    """
    station_code = station_code.upper()
    
    # Ogimet fetch
    end = datetime.utcnow()
    begin = end - timedelta(hours=hours)
    
    ogimet_url = (
        f"https://www.ogimet.com/cgi-bin/getmetar?lang=en&icao={station_code}"
        f"&begin={begin.strftime('%Y%m%d%H%M')}&end={end.strftime('%Y%m%d%H%M')}"
    )
    
    try:
        response = requests.get(ogimet_url, timeout=15)
        if response.status_code == 200:
            return response.text
    except Exception:
        pass

    # Fallback to NOAA for just the latest if Ogimet fails
    if hours <= 1:
        noaa_url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{station_code}.TXT"
        try:
            response = requests.get(noaa_url, timeout=10)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass

    return None
