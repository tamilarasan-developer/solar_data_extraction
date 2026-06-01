import os
import django
import requests
from bs4 import BeautifulSoup
import urllib3
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ---------------------------------------------------------
# 1. DJANGO SETUP
# ---------------------------------------------------------
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solar.settings')
django.setup()

from solar.models import FeederDataRaw, MainFeederData
from django.db.models import Avg
from django.utils import timezone
from django.conf import settings

# ---------------------------------------------------------

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOGIN_URL = "https://mail.tneb.in/tneb4g/"
DASHBOARD_URL = "https://mail.tneb.in/tneb4g/SSLiveDashboard.aspx?ssid=2387&ddl=-1&pddl=-1&subddl=-1&sddl=-1"
API_URL = "https://mail.tneb.in/tneb4g/WebService/WS_SSLiveDashboard.asmx/WS_Get_SSLiveInstantDSB"

USERNAME = "ViolaGreen"
PASSWORD = "Viola@123"
SUBSTATION_ID = "2387"

IST_TZ = ZoneInfo('Asia/Kolkata')

def safe_decimal(val):
    try:
        val = val.strip()
        return float(val) if val else 0.0
    except ValueError:
        return 0.0

def round_to_nearest_15_mins(dt_obj):
    minute = dt_obj.minute
    remainder = minute % 15

    if remainder >= 8:
        rounded_minute = minute + (15 - remainder)
    else:
        rounded_minute = minute - remainder

    new_dt = dt_obj.replace(minute=0, second=0, microsecond=0)
    return new_dt + timedelta(minutes=rounded_minute)

def parse_and_round_rtc_time(rtc_str):
    try:
        dt_obj = datetime.strptime(rtc_str.strip(), "%d/%m/%Y %H:%M:%S")
        rounded_dt = round_to_nearest_15_mins(dt_obj)
        if settings.USE_TZ:
            return timezone.make_aware(rounded_dt, timezone=IST_TZ)
        else:
            return rounded_dt
        
    except Exception:
        current_ist_dt = datetime.now(IST_TZ)
        naive_dt = current_ist_dt.replace(tzinfo=None)
        rounded_dt = round_to_nearest_15_mins(naive_dt)
        
        if settings.USE_TZ:
            return timezone.make_aware(rounded_dt, timezone=IST_TZ)
        else:
            return rounded_dt

# ---------------------------------------------------------
# NEW: STANDALONE LOGIN FUNCTION
# ---------------------------------------------------------
def login_to_tneb(session):
    print("   -> [Auth] Performing fresh login to TNEB portal...")
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://mail.tneb.in",
        "Referer": LOGIN_URL
    }
    
    response = session.get(LOGIN_URL, headers=headers, verify=False)
    soup = BeautifulSoup(response.text, "html.parser")
    
    payload = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        if name:
            payload[name] = inp.get("value", "")

    username_field, password_field, button_field = None, None, None

    for key in payload:
        low = key.lower()
        if "user" in low: username_field = key
        elif "pass" in low: password_field = key
        elif "login" in low: button_field = key

    payload[username_field] = USERNAME
    payload[password_field] = PASSWORD

    if button_field:
        payload[button_field] = "Login"

    login_response = session.post(LOGIN_URL, data=payload, headers=headers, verify=False)
    if "txtpassword" in login_response.text.lower():
        print("   -> [Auth Error] Login Failed. Check credentials.")
        return False

    session.get(DASHBOARD_URL, headers=headers, verify=False)
    print("   -> [Auth] Login successful! Session is now active.")
    return True

# ---------------------------------------------------------
# UPDATED: DATA FETCHING (USES EXISTING SESSION)
# ---------------------------------------------------------
def get_dashboard_data(session):
    api_headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://mail.tneb.in",
        "Referer": DASHBOARD_URL,
        "User-Agent": "Mozilla/5.0"
    }

    payload_string = f"{{sSubstationId:'{SUBSTATION_ID}'}}"
    
    print("   -> [Status] Extracting data from dashboard API...")
    response = session.post(API_URL, headers=api_headers, data=payload_string, verify=False)
    
    # If the session expired, TNEB won't return JSON, it will return HTML or a 500 error.
    # This try/except catches a dead session and raises an error so we can log back in.
    try:
        json_data = response.json()
    except Exception:
        raise Exception("Session Invalid")

    raw_data = json_data.get("d", "")
    if not raw_data:
        return []

    records = raw_data.split("|")

    rows = []
    for rec in records:
        rec = rec.strip()
        if not rec: continue
            
        cols = rec.split("~")
        if len(cols) < 35: continue

        feeder_name = cols[4]

        # Storing FULL data. No skips here.
        rows.append({
            "Station": cols[0],
            "SSID": cols[1],
            "Voltage": cols[2],
            "Feeder Name": feeder_name,
            "Meter No": cols[7],
            "MW": cols[20],
            "MVAr": cols[21],
            "MW Sign": cols[22],      
            "MVAr Sign": cols[23],    
            "Export MW": cols[24],
            "Import MW": cols[25],
            "Net MW": cols[26],
            "Direction": cols[27],
            "Communication": cols[17],
            "RTC Time": cols[33]
        })

    return rows

# ---------------------------------------------------------
# BATCH AVERAGING FUNCTION
# ---------------------------------------------------------
def calculate_15min_averages():
    print("\n   -> [Average Process] Ignoring 'CHECK' and 'WIND', averaging ONLY 'SOLAR' datas...")
    
    current_time = datetime.now(IST_TZ)
    naive_current = current_time.replace(tzinfo=None)
    current_round_off = round_to_nearest_15_mins(naive_current)

    if settings.USE_TZ:
        current_round_off = timezone.make_aware(current_round_off, timezone=IST_TZ)
        time_threshold = current_round_off - timedelta(minutes=15)
    else:
        time_threshold = current_round_off - timedelta(minutes=15)

    time_threshold_str = time_threshold.strftime('%Y-%m-%d %I:%M:%S %p')

    # ONLY SOLAR! IGNORE CHECK! IGNORE WIND!
    averages = FeederDataRaw.objects.filter(
        round_off_time=time_threshold_str,
        feeder_name__icontains="SOLAR"  
    ).exclude(
        feeder_name__icontains="CHECK"  
    ).exclude(
        feeder_name__icontains="WIND"   
    ).values(
        'station', 'feeder_name', 'round_off_time'
    ).annotate(
        calculated_export_mw=Avg('export_mw'),
        calculated_net_mw=Avg('net_mw')
    ).order_by()  

    updated_count = 0
    
    if averages:
        print("   -> [Average Output] Extracted and stored:")
        
    for data in averages:
        MainFeederData.objects.update_or_create(
            station=data['station'],
            feeder_name=data['feeder_name'],
            round_off_time=data['round_off_time'],
            defaults={
                'avg_export_mw': data['calculated_export_mw'],
                'avg_net_mw': data['calculated_net_mw']
            }
        )
        updated_count += 1
        round_off_str = data['round_off_time']
        print(f"      * {data['feeder_name']:<40} | Time: {round_off_str} | Export: {data['calculated_export_mw']:.4f} | Net: {data['calculated_net_mw']:.4f}")
        
    if updated_count > 0:
        print(f"   -> [Success] Stored {updated_count} strictly SOLAR records in MainFeederData.")

# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------

# Create ONE persistent session outside the loop!
tneb_session = requests.Session()
is_logged_in = False

while True:
    try:
        current_run_time = datetime.now(IST_TZ)
        if not settings.USE_TZ:
            current_run_time = current_run_time.replace(tzinfo=None)
            print_time_str = current_run_time.strftime('%Y-%m-%d %I:%M:%S %p') + ' IST'
        else:
            print_time_str = current_run_time.strftime('%Y-%m-%d %I:%M:%S %p %Z')
        
        print(f"\n=======================================================")
        print(f"🚀 SCRIPT RUN TRIGGERED AT: {print_time_str}")
        print(f"=======================================================")
        
        # --- NEW: PERSISTENT SESSION LOGIC ---
        if not is_logged_in:
            is_logged_in = login_to_tneb(tneb_session)
            
        rows = []
        if is_logged_in:
            print("   -> [Auth] Using existing active session...")
            try:
                rows = get_dashboard_data(tneb_session)
            except Exception:
                # If fetching fails, the session probably expired. Log in again!
                print("   -> [Warning] Session seems to have expired. Re-authenticating...")
                is_logged_in = login_to_tneb(tneb_session)
                if is_logged_in:
                    rows = get_dashboard_data(tneb_session)
        # -------------------------------------
        
        db_instances = []
        
        if settings.USE_TZ:
            stale_threshold = timezone.now() - timedelta(minutes=45)
        else:
            stale_threshold = datetime.now() - timedelta(minutes=45)

        for row in rows:
            feeder_name = row["Feeder Name"][:255]
            station_val = row["Station"][:255]
            ssid_val = row["SSID"][:50]
            voltage_val = row["Voltage"][:50]
            meter_no_val = row["Meter No"][:50]
            mw_val = safe_decimal(row["MW"])
            mvar_val = safe_decimal(row["MVAr"])
            mw_sign_val = row["MW Sign"][:50]
            mvar_sign_val = row["MVAr Sign"][:50]
            export_mw_val = safe_decimal(row["Export MW"])
            import_mw_val = safe_decimal(row["Import MW"])
            net_mw_val = safe_decimal(row["Net MW"])
            direction_val = row["Direction"][:50]
            comm_val = row["Communication"][:100]
            rtc_val = row["RTC Time"][:100]

            try:
                dt_obj = datetime.strptime(rtc_val.strip(), "%d/%m/%Y %H:%M:%S")
                rtc_time_formatted = dt_obj.strftime("%d/%m/%Y %I:%M:%S %p")
            except Exception:
                rtc_time_formatted = rtc_val

            calculated_round_off = parse_and_round_rtc_time(rtc_val)

            # Warn if stale
            name_up = feeder_name.upper()
            if "SOLAR" in name_up and "CHECK" not in name_up and "WIND" not in name_up:
                if calculated_round_off < stale_threshold:
                    old_date_str = calculated_round_off.strftime("%b %d, %I:%M:%S %p")
                    print(f"   -> [Warning] {feeder_name} is sending old data ({old_date_str}) and was excluded from the average.")

            db_instances.append(
                FeederDataRaw(
                    station=station_val,
                    ssid=ssid_val,
                    voltage=voltage_val,
                    feeder_name=feeder_name,
                    meter_no=meter_no_val,
                    mw=mw_val,
                    mvar=mvar_val,
                    mw_sign=mw_sign_val,       
                    mvar_sign=mvar_sign_val,   
                    export_mw=export_mw_val,
                    import_mw=import_mw_val,
                    net_mw=net_mw_val,
                    direction=direction_val,
                    communication=comm_val,
                    rtc_time=rtc_time_formatted,
                    
                    script_run_time=current_run_time.strftime('%Y-%m-%d %I:%M:%S %p'), 
                    round_off_time=calculated_round_off.strftime('%Y-%m-%d %I:%M:%S %p')
                )
            )

        if db_instances:
            # Step 1: Save EVERYTHING to raw table
            FeederDataRaw.objects.bulk_create(db_instances)
            print(f"   -> [Status] Stored {len(db_instances)} raw rows to the DB (FeederDataRaw).")
            
            # Count the runs to show 1 to 5 progress
            sample_feeder = db_instances[0].feeder_name
            current_target_block = db_instances[0].round_off_time
            
            run_count = FeederDataRaw.objects.filter(
                feeder_name=sample_feeder,
                round_off_time=current_target_block
            ).count()
            
            print(f"   -> [Progress] Count of the times running: Run {run_count} of 5.")
            
            if run_count < 5:
                print("   -> [Status] Waiting to show the average data... (Need 5 total runs).")
            else:
                print("   -> [Status] Totally 5 times run is done! 15 mins slot completed.")
                print("   -> [Status] Preparing to run the next 15 mins slot for the next 5 times...")
                
                # Step 2: Average completed blocks (SOLAR ONLY, NO CHECK, NO WIND)
                calculate_15min_averages()
            
        else:
            print("   -> [Warning] No data extracted in this run. Was the portal completely blank?")

    except Exception as e:
        print("\n❌ ERROR:", e)

    print("\n💤 Sleeping for 180 seconds until next run...")
    time.sleep(180)