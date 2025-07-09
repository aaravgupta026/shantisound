import pyaudio
import numpy as np
import os
import time
import pandas as pd

# --- Audio Config ---
CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
SLEEP_TIME = 1.0  # seconds between checks

# --- Sound Thresholds ---
LOUD_THRESHOLD = 3500
QUIET_THRESHOLD = 1000

# --- Volume Settings ---
VOLUME_STEP = 5
MIN_VOL = 15
MAX_VOL = 80

# --- Load volume preferences from CSV ---
csv_path = "volume_data.csv"
if os.path.exists(csv_path):
    volume_data = pd.read_csv(csv_path)
    volume_data['label'] = volume_data['label'].str.lower()
else:
    volume_data = None
    print("⚠️ volume_data.csv not found. Will use peak detection only.")

# --- Volume Commands ---
def get_volume():
    vol = os.popen("amixer get Master | grep -oP '\\[\\d+%' | grep -oP '\\d+'").readline()
    return int(vol.strip()) if vol else 70

def set_volume(vol):
    vol = max(MIN_VOL, min(MAX_VOL, vol))
    os.system(f"amixer -D pulse sset Master {vol}% > /dev/null")
    return vol

# --- Setup PyAudio ---
p = pyaudio.PyAudio()

# --- Detect system output (PulseAudio Monitor) ---
output_device_index = None
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    if "pulse" in info["name"].lower():
        output_device_index = i
        break

if output_device_index is None:
    raise RuntimeError("❌ Could not find PulseAudio output device. Make sure PulseAudio is running.")

# --- Open stream ---
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=output_device_index,
                frames_per_buffer=CHUNK)

print("🎧 Smart Volume Controller is live. Ctrl+C to stop.")
current_volume = get_volume()

try:
    while True:
        data = np.frombuffer(stream.read(CHUNK), dtype=np.int16)
        peak = np.abs(data).max()
        print(f"🎚️ Peak: {peak}, Volume: {current_volume}%")

        # OPTIONAL: Replace this with real-time sound classification
        # For now, classify based on peak value only
        if volume_data is not None:
            # Simulated classification by peak
            if peak > 400:
                label = "siren"
            elif 100< peak <250:
                label = "speech"
            elif peak < 100:
                label = "quiet"
            else:
                label = "normal"

            print(f"🧠 Label: {label}")
            match = volume_data[volume_data['label'].str.strip().str.lower() == label.lower()]

            if not match.empty:
                target_volume = int(match['target_volume'].values[0])
                tolerance = int(match['tolerance'].values[0])
                lower_limit = target_volume - tolerance
                upper_limit = target_volume + tolerance

                if current_volume < lower_limit:
                    current_volume = set_volume(target_volume)
                    print(f"🔊 Too quiet → raising volume to {target_volume}% for {label}")
                elif current_volume > upper_limit:
                    current_volume = set_volume(target_volume)
                    print(f"🔉 Too loud → lowering volume to {target_volume}% for {label}")
                else:
                    print("🎵 Volume already in comfortable range")
        else:
            if peak > LOUD_THRESHOLD and current_volume > MIN_VOL:
                current_volume -= VOLUME_STEP
                current_volume = set_volume(current_volume)
                print("🔉 Loud scene → lowering volume")
            elif peak < QUIET_THRESHOLD and current_volume < MAX_VOL:
                current_volume += VOLUME_STEP
                current_volume = set_volume(current_volume)
                print("🔊 Quiet scene → increasing volume")
            else:
                print("🎵 Normal scene → volume steady")

        time.sleep(SLEEP_TIME)

except KeyboardInterrupt:
    print("\n🛑 Exiting. Restoring to 70% volume.")
    set_volume(70)
    stream.stop_stream()
    stream.close()
    p.terminate()

