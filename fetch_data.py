import requests
import time
from datetime import datetime, timedelta

def get_latest_metar(station_code):
    """
    Tries to fetch the latest METAR for a given station.
    Tries NOAA first, then falls back to Ogimet (which has more international regional stations).
    """
    station_code = station_code.upper()
    
    # 1. Try NOAA (Fast, but usually only major airports)
    noaa_url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{station_code}.TXT"
    try:
        response = requests.get(noaa_url, timeout=10)
        if response.status_code == 200:
            return response.text
    except Exception:
        pass

    # 2. Try Ogimet (Better for regional Indian airports like VASD, VAAU, etc.)
    # Fetching last 12 hours of METARs
    end = datetime.utcnow()
    begin = end - timedelta(hours=12)
    
    ogimet_url = (
        f"https://www.ogimet.com/cgi-bin/getmetar?lang=en&icao={station_code}"
        f"&begin={begin.strftime('%Y%m%d%H%M')}&end={end.strftime('%Y%m%d%H%M')}"
    )
    
    try:
        # User requested to try Ogimet if NOAA fails/empty
        # print(f"NOAA failed/empty for {station_code}. Trying Ogimet...")
        response = requests.get(ogimet_url, timeout=15)
        if response.status_code == 200:
            # Ogimet returns a list of METARs in a specific text format
            return response.text
    except Exception:
        pass

    return None
