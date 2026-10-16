import sys
import os
import requests
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

WVD_FILE = "device.wvd"
CHANNEL_ID = sys.argv[1] if len(sys.argv) > 1 else "157811"

def fetch_channel_data():
    api_url = f"https://iptvmax.site/Premium/Vzy/hmac.php?id={CHANNEL_ID}"
    print(f"[1] Fetching data from API for ID: {CHANNEL_ID}...")
    try:
        res = requests.get(api_url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                return data.get("channel", {})
    except Exception as e:
        print(f"    [!] API Error: {e}")
    return None

def test_keys():
    channel = fetch_channel_data()
    if not channel:
        print("    [!] Failed to get channel data from API.")
        return

    print(f"\n[+] Channel Name : {channel.get('name')}")
    print(f"    PSSH         : {channel.get('pssh')}")
    
    pssh_b64 = channel.get("pssh")
    if not pssh_b64:
        print("    [!] PSSH is null for this channel!")
        return

    widevine_data = channel.get("widevine_data", {})
    auth_token = widevine_data.get("token")
    license_url = widevine_data.get("licenseUrl")

    if not auth_token or not license_url:
        print("    [!] Token or License URL missing!")
        return

    print("[2] Loading x86 TV CDM device...")
    if not os.path.exists(WVD_FILE):
        print("    [!] device.wvd not found!")
        return

    device = Device.load(WVD_FILE)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()

    try:
        print("[3] Generating Widevine Challenge...")
        pssh = PSSH(pssh_b64)
        challenge = cdm.get_license_challenge(session_id, pssh)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; AOSP TV on x86) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "Content-Type": "application/octet-stream",
            "Origin": "https://www.vzy.one",
            "Referer": "https://www.vzy.one/",
            "nv-tenant-id": "DSHP4R35",
            "nv-authorizations": auth_token,
            "Accept": "*/*"
        }

        print("[4] Sending Challenge to Nagra License Server...")
        response = requests.post(license_url, headers=headers, data=challenge, timeout=15)
        
        print(f"    Response Status: {response.status_code}")

        if response.status_code == 200:
            print("\n[+] SUCCESS! Parsing license...")
            cdm.parse_license(session_id, response.content)
            
            keys = cdm.get_keys(session_id)
            print(f"\n==================== FOUND {len(keys)} KEYS ====================")
            for i, k in enumerate(keys):
                print(f"--- Key #{i+1} ---")
                try:
                    print(f"Type : {k.type}")
                except:
                    pass
                try:
                    print(f"KID  : {k.kid}")
                except:
                    pass
                try:
                    key_hex = k.key.hex() if hasattr(k.key, 'hex') else bytes(k.key).hex()
                    print(f"KEY  : {key_hex}")
                except:
                    pass
                print("-" * 50)
        else:
            print(f"\n[-] Failed to fetch keys. Response: {response.text}")

    except Exception as exc:
        print(f"\n[!] Error: {exc}")
    finally:
        cdm.close(session_id)
        print("Session closed.")

if __name__ == "__main__":
    test_keys()
    
