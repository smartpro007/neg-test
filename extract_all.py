import os
import json
import requests
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

WVD_FILE = "device.wvd"
# तुमच्या चॅनेलचे आयडी (तुम्ही हवे तेवढे चॅनेल आयडी इथे टाकू शकता)
CHANNEL_IDS = ["157811", "144436"] 

def get_channel_data(channel_id):
    api_url = f"https://iptvmax.site/Premium/Vzy/hmac.php?id={channel_id}"
    try:
        res = requests.get(api_url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                return data.get("channel", {})
    except Exception as e:
        print(f"    [!] API Error for {channel_id}: {e}")
    return None

def extract_all_keys():
    if not os.path.exists(WVD_FILE):
        print("[!] device.wvd not found!")
        return

    device = Device.load(WVD_FILE)
    all_extracted_keys = []

    for ch_id in CHANNEL_IDS:
        print(f"\n----------------------------------------")
        print(f"Processing Channel ID: {ch_id}")
        channel = get_channel_data(ch_id)
        if not channel:
            continue

        name = channel.get('name')
        pssh_b64 = channel.get('pssh')
        widevine_data = channel.get('widevine_data', {})
        auth_token = widevine_data.get('token')
        license_url = widevine_data.get('licenseUrl')

        if not pssh_b64 or not auth_token or not license_url:
            print(f"    [!] Missing required data for {name}")
            continue

        cdm = Cdm.from_device(device)
        session_id = cdm.open()

        try:
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

            response = requests.post(license_url, headers=headers, data=challenge, timeout=15)
            if response.status_code == 200:
                cdm.parse_license(session_id, response.content)
                keys = cdm.get_keys(session_id)
                
                channel_keys = []
                for k in keys:
                    if k.type == "CONTENT":
                        key_hex = k.key.hex() if hasattr(k.key, 'hex') else bytes(k.key).hex()
                        channel_keys.append({
                            "type": str(k.type),
                            "kid": str(k.kid),
                            "key": key_hex
                        })
                
                all_extracted_keys.append({
                    "channelNumber": channel.get('channelNumber'),
                    "name": name,
                    "keys": channel_keys
                })
                print(f"    [+] Successfully extracted keys for {name}")
            else:
                print(f"    [-] License server error: {response.status_code}")

        except Exception as e:
            print(f"    [!] Error: {e}")
        finally:
            cdm.close(session_id)

    # सर्व कीज keys.json फाईलमध्ये सेव्ह करणे
    with open("keys.json", "w", encoding="utf-8") as f:
        json.dump(all_extracted_keys, f, indent=4, ensure_ascii=False)
    print("\n[+] All keys saved successfully to keys.json!")

if __name__ == "__main__":
    extract_all_keys()
    
