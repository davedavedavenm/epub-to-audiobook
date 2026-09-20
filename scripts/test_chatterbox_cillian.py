import time
import requests

url = "http://localhost:8006/v1/audio/speech"
payload = {
    "input": "Though its origins and its government ministers had IRA roots, the independent Ireland over which de Valera presided was deeply at odds with the IRA.",
    "voice": "cillian_irish",
    "response_format": "mp3"
}
print("Requesting from Chatterbox Nano on Zorin...")
t0 = time.time()
r = requests.post(url, json=payload, timeout=120)
elapsed = time.time() - t0
print(f"Done in {elapsed:.2f}s! Status: {r.status_code}, Length: {len(r.content):,} bytes")
with open("/home/dave/cillian_nano_test.mp3", "wb") as f:
    f.write(r.content)
print("Saved /home/dave/cillian_nano_test.mp3 successfully!")
