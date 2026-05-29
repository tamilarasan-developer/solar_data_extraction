from django.core.management.base import BaseCommand

import requests
from bs4 import BeautifulSoup
import urllib3
import time
from datetime import datetime
from decimal import Decimal
from django.utils.timezone import make_aware

from solar.models import (
    FeederDataRaw,
    MainFeederData
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def round_to_15_minutes(dt):
    return dt.replace(
        minute=(dt.minute // 15) * 15,
        second=0,
        microsecond=0
    )


def safe_decimal(value):
    try:
        return Decimal(str(value).strip())
    except Exception:
        return Decimal("0")


class Command(BaseCommand):
    help = "Capture TNEB Live Dashboard Data"

    def handle(self, *args, **kwargs):

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

        while True:
            self.stdout.write("Starting live data capture cycle...")
            try:
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

                self.stdout.write("Opening Login Page...")

                response = session.get(
                    LOGIN_URL,
                    headers=headers,
                    verify=False
                )

                self.stdout.write(
                    f"Login Page Status: {response.status_code}"
                )

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

                self.stdout.write("Logging in...")

                login_response = session.post(
                    LOGIN_URL,
                    data=payload,
                    headers=headers,
                    verify=False,
                    allow_redirects=True
                )

                self.stdout.write(
                    f"Login Status: {login_response.status_code}"
                )

                # ---------------------------------------------------
                # CHECK LOGIN
                # ---------------------------------------------------

                if "txtpassword" in login_response.text.lower():
                    self.stdout.write(
                        self.style.ERROR("LOGIN FAILED")
                    )
                    raise Exception("Login failed due to incorrect credentials or page state.")

                self.stdout.write(
                    self.style.SUCCESS("LOGIN SUCCESS")
                )

                # ---------------------------------------------------
                # STEP 4 - OPEN DASHBOARD PAGE
                # ---------------------------------------------------

                self.stdout.write("Opening Dashboard Page...")

                dashboard_response = session.get(
                    DASHBOARD_URL,
                    headers={
                        **headers,
                        "Referer": LOGIN_URL
                    },
                    verify=False
                )

                self.stdout.write(
                    f"Dashboard Status: {dashboard_response.status_code}"
                )

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

                payload_string = (
                    f"{{sSubstationId:'{SUBSTATION_ID}'}}"
                )

                self.stdout.write("Calling API...")

                api_response = session.post(
                    API_URL,
                    headers=api_headers,
                    data=payload_string,
                    verify=False
                )

                self.stdout.write(
                    f"API Status: {api_response.status_code}"
                )

                print("\n========== API RESPONSE ==========\n")
                print(api_response.text[:500])

                # ---------------------------------------------------
                # STEP 6 - PARSE JSON
                # ---------------------------------------------------

                json_data = api_response.json()

                if "d" not in json_data:
                    raise Exception("No 'd' key found in API response.")

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
                # SAVE DATA
                # ---------------------------------------------------

                for row in rows:

                    try:
                        rtc_time = row["RTC Time"]

                        if not rtc_time or rtc_time == "---":
                            continue

                        try:
                            rtc_dt = datetime.strptime(
                                rtc_time,
                                "%d/%m/%Y %H:%M:%S"
                            )
                            rtc_dt = make_aware(rtc_dt)
                        except ValueError:
                            continue

                        round_off_time = round_to_15_minutes(
                            rtc_dt
                        )

                        latest = (
                            FeederDataRaw.objects
                            .filter(
                                meter_no=row["Meter No"]
                            )
                            .order_by("-id")
                            .first()
                        )

                        changed = (
                            latest is None
                            or str(latest.mw) != str(row["MW"])
                            or str(latest.mvar) != str(row["MVAr"])
                            or str(latest.export_mw) != str(row["Export MW"])
                            or str(latest.import_mw) != str(row["Import MW"])
                            or str(latest.net_mw) != str(row["Net MW"])
                            or str(latest.rtc_time) != str(row["RTC Time"])
                        )

                        if changed:

                            FeederDataRaw.objects.create(
                                station=row["Station"],
                                round_off_time=round_off_time,
                                ssid=row["SSID"],
                                voltage=row["Voltage"],
                                feeder_name=row["Feeder Name"],
                                meter_no=row["Meter No"],
                                mw=safe_decimal(row["MW"]),
                                mvar=safe_decimal(row["MVAr"]),
                                mw_sign=row["MW Sign"],
                                mvar_sign=row["MVAr Sign"],
                                export_mw=safe_decimal(row["Export MW"]),
                                import_mw=safe_decimal(row["Import MW"]),
                                net_mw=safe_decimal(row["Net MW"]),
                                direction=row["Direction"],
                                communication=row["Communication"],
                                rtc_time=row["RTC Time"]
                            )

                        export_mw = safe_decimal(row["Export MW"])
                        net_mw = safe_decimal(row["Net MW"])

                        obj, created = MainFeederData.objects.get_or_create(
                            station=row["Station"],
                            feeder_name=row["Feeder Name"],
                            round_off_time=round_off_time,
                            defaults={
                                "avg_export_mw": export_mw,
                                "avg_net_mw": net_mw,
                                "sample_count": 1
                            }
                        )

                        if not created:

                            count = obj.sample_count

                            obj.avg_export_mw = (
                                (
                                    obj.avg_export_mw * count
                                )
                                + export_mw
                            ) / (count + 1)

                            obj.avg_net_mw = (
                                (
                                    obj.avg_net_mw * count
                                )
                                + net_mw
                            ) / (count + 1)

                            obj.sample_count += 1

                            obj.save()
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Error processing row for station {row.get('Station')} - feeder {row.get('Feeder Name')}: {e}"
                            )
                        )

                self.stdout.write(
                    self.style.SUCCESS(
                        "Database Save Completed"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"An error occurred during capture cycle: {e}"
                    )
                )

            self.stdout.write("Sleeping for 3 minutes...")
            time.sleep(180)