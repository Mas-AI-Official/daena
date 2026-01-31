import requests
import json
import os

def test_tts():
    url = "http://127.0.0.1:5001/api/tts/speak"
    payload = {
        "text": "Hello, I am testing the voice system.",
        "language": "en",
        "speaker_wav": ""
    }
    
    print(f"Sending TTS request to {url}...")
    try:
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Audio file: {data['audio_file']}")
            
            # Check if file exists
            if os.path.exists(data['audio_file']):
                print(f"✅ Audio file exists on disk: {os.path.abspath(data['audio_file'])}")
            else:
                print(f"❌ Audio file not found on disk: {data['audio_file']}")
        else:
            print(f"❌ Failed! Status code: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_tts()
