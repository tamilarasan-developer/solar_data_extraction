import requests
from bs4 import BeautifulSoup
import pandas as pd
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

LOGIN_URL = "https://mail.tneb.in/tneb4g/"

DASHBOARD_URL = (
    "https://mail.tneb.in/tneb4g/"
    "SSLiveDashboard.aspx?ssid=2387&ddl=-1&pddl=-1&subddl=-1&sddl=-1"
)

API_URL = (
    "https://mail.tneb.in/tneb4g/WebService/"
    "WS_SSLiveDashboard.asmx/WS_Get_SSLiveInstantDSB"
)

USERNAME = "ViolaGreen"
PASSWORD = "Viola@123"

SUBSTATION_ID = "2387"

# ---------------------------------------------------
# SESSION
# ---------------------------------------------------

session = requests.Session()

# ---------------------------------------------------
# HEADERS
# ---------------------------------------------------

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "Origin": "https://mail.tneb.in",
    "Referer": LOGIN_URL
}

# ---------------------------------------------------
# STEP 1 - OPEN LOGIN PAGE
# ---------------------------------------------------

print("Opening Login Page...")

response = session.get(
    LOGIN_URL,
    headers=headers,
    verify=False
)

print("Login Page Status:", response.status_code)

# ---------------------------------------------------
# STEP 2 - PARSE LOGIN PAGE
# ---------------------------------------------------

soup = BeautifulSoup(response.text, "html.parser")

payload = {}

for inp in soup.find_all("input"):

    name = inp.get("name")
    value = inp.get("value", "")

    if name:
        payload[name] = value

# ---------------------------------------------------
# FIND USERNAME/PASSWORD FIELDS
# ---------------------------------------------------

username_field = None
password_field = None
button_field = None

for key in payload.keys():

    low = key.lower()

    if "user" in low:
        username_field = key

    elif "pass" in low:
        password_field = key

    elif "login" in low:
        button_field = key

# ---------------------------------------------------
# SET LOGIN VALUES
# ---------------------------------------------------

payload[username_field] = USERNAME
payload[password_field] = PASSWORD

if button_field:
    payload[button_field] = "Login"

# ---------------------------------------------------
# STEP 3 - LOGIN
# ---------------------------------------------------

print("Logging in...")

login_response = session.post(
    LOGIN_URL,
    data=payload,
    headers=headers,
    verify=False,
    allow_redirects=True
)

print("Login Status:", login_response.status_code)

# ---------------------------------------------------
# CHECK LOGIN
# ---------------------------------------------------

if "txtpassword" in login_response.text.lower():
    print("LOGIN FAILED")
    exit()

print("LOGIN SUCCESS")

# ---------------------------------------------------
# STEP 4 - OPEN DASHBOARD PAGE
# ---------------------------------------------------

print("Opening Dashboard Page...")

dashboard_response = session.get(
    DASHBOARD_URL,
    headers={
        **headers,
        "Referer": LOGIN_URL
    },
    verify=False
)

print("Dashboard Status:", dashboard_response.status_code)

# ---------------------------------------------------
# STEP 5 - API CALL
# ---------------------------------------------------

api_headers = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://mail.tneb.in",
    "Referer": DASHBOARD_URL,
    "User-Agent": headers["User-Agent"]
}

# IMPORTANT
# ASP.NET EXPECTS RAW STRING BODY
payload_string = f"{{sSubstationId:'{SUBSTATION_ID}'}}"

print("Calling API...")

api_response = session.post(
    API_URL,
    headers=api_headers,
    data=payload_string,
    verify=False
)

print("API Status:", api_response.status_code)

print("\n========== API RESPONSE ==========\n")
print(api_response.text[:500])

# ---------------------------------------------------
# STEP 6 - PARSE JSON
# ---------------------------------------------------

json_data = api_response.json()

if "d" not in json_data:
    print("No 'd' key found in response")
    exit()

raw_data = json_data["d"]

# ---------------------------------------------------
# STEP 7 - SPLIT DATA
# ---------------------------------------------------

records = raw_data.split("|")

rows = []

for rec in records:

    rec = rec.strip()

    if not rec:
        continue

    cols = rec.split("~")

    if len(cols) < 35:
        continue

    rows.append({

        "Station": cols[0],
        "SSID": cols[1],
        "Voltage": cols[2],

        "Feeder Name": cols[4],

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

# ---------------------------------------------------
# STEP 8 - DATAFRAME
# ---------------------------------------------------

df = pd.DataFrame(rows)

print("\n================ FEEDER DATA ================\n")

print(df.to_string(index=False))

# ---------------------------------------------------
# SAVE CSV
# ---------------------------------------------------

csv_file = "tneb_feeder_data.csv"

df.to_csv(csv_file, index=False)

print(f"\nCSV Saved Successfully -> {csv_file}")