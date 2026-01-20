#!/usr/bin/env python3
# Copyright 2026 hobisatelit
# https://github.com/hobisatelit/ssdv2sat
# License: GPL-3.0-or-later
VERSION = '0.01'

import socket
import sys
import time
import subprocess
import os
import hashlib
import string
import argparse

# Default values
DEFAULT_PACKET_LENGTH = 128
DEFAULT_DELAY = 0
DEFAULT_AUDIO_DIR = 'audio'
####################################

parser = argparse.ArgumentParser(
    description="Convert an image into SSDV, transmit over IL2P using Direwolf KISS and record as audio wav",
    epilog="Example: ./tx.py ABCDEF image.jpg"
)
parser.add_argument("callsign", help="your actual callsign")
parser.add_argument("filename", help="input image file (JPG, PNG, etc)")
parser.add_argument("--host", default="127.0.0.1", help="Dire Wolf host (default: 127.0.0.1)")
parser.add_argument("--port", type=int, default=8001, help="Dire Wolf KISS TCP port (default: 8001)")
parser.add_argument("--max", type=int, default=DEFAULT_PACKET_LENGTH,
                    help=f"Max data bytes per frame (default: {DEFAULT_PACKET_LENGTH}, min 64, max 256)")
parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                    help=f"Delay between frames in seconds (default: {DEFAULT_DELAY}, use 1-3s for longer satellite pass, and 0 for shortest)")
parser.add_argument("--dir", type=str, default=DEFAULT_AUDIO_DIR,
                    help=f"Directory for save recorded audio wav (default: {DEFAULT_AUDIO_DIR})")
parser.add_argument("--version", action='version', version=f"ssdv2sat-%(prog)s v{VERSION} by hobisatelit <https://github.com/hobisatelit>", help="Show the version of the application")

args = parser.parse_args()

if not (64 <= args.max <= 256):
    print("Error: --max should be between 64 and 256")
    sys.exit(1)
if args.delay < 0:
    print("Error: --delay cannot be negative")
    sys.exit(1)

HOST = args.host
KISS_PORT = args.port
SRC_CALL = args.callsign
PACKET_LENGTH = args.max
FRAME_DELAY = args.delay
AUDIO_DIR = args.dir
filename = args.filename

ALPHANUM = string.ascii_uppercase + string.digits

def generate_file_id_from_filename(filename):
    hash_obj = hashlib.sha256(filename.encode('utf-8')).digest()
    byte1, byte2, byte3 = hash_obj[0], hash_obj[1], hash_obj[2]
    return ALPHANUM[byte1 % 36] + ALPHANUM[byte2 % 36] + ALPHANUM[byte3 % 36]

def start_recording(output_filename):
    command = ["sox", "-d", "-r", "44100", "-c", "1", "-t", "wav", "-q", "-V1", output_filename]
    return subprocess.Popen(command)
    
def img2ssdv(packet_length,output_dir,input_filename,callsign):
  try:
    command = [os.path.join(os.getcwd(),"img2ssdv.py"), "--length", str(packet_length), "--dir", str(output_dir), "--callsign", str(callsign),  input_filename]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return stderr.decode().strip()
    #return process
  except FileNotFoundError:
    return f"Cannot find img2ssdv.py script. {output_filename} not created.."
  except subprocess.CalledProcessError as e:
    print(f"An error occurred while running {app_name}: {e}")
    return None

def stop_recording(process):
    process.terminate()

FEND = b'\xC0'
FESC = b'\xDB'
TFEND = b'\xDC'
TFESC = b'\xDD'

def kiss_escape(data):
    data = data.replace(FESC, FESC + TFESC)
    data = data.replace(FEND, FESC + TFEND)
    return data

def ax25_address(call, last=False):
    call_padded = call.ljust(6).upper()[:6] + " "
    addr = bytes([ord(c) << 1 for c in call_padded[:6]])
    ssid = (ord(call_padded[6]) << 1) | 0x60
    if last:
        ssid |= 1
    addr += bytes([ssid])
    return addr

# === Main ===
os.makedirs(AUDIO_DIR, exist_ok=True)

filename = os.path.abspath(filename)

if not os.path.exists(filename):
    print(f"Error: File '{filename}' not found!")
    sys.exit(1)

basename = os.path.basename(filename)
basename_noext = os.path.splitext(basename)[0]

FILE_ID = generate_file_id_from_filename(f"{basename}{SRC_CALL}")

# WAV filename includes FILE_ID
output_wav = f"{basename_noext}_audio_{FILE_ID}_{SRC_CALL}_{PACKET_LENGTH}bs_{FRAME_DELAY}s.wav"

print(f"Image name        : {basename}")
print(f"FILE_ID           : {FILE_ID}")
print(f"PACKET_LENGTH     : {PACKET_LENGTH} bytes/frame")
print(f"Frame delay       : {FRAME_DELAY} seconds")
print(f"Audio output      : {output_wav}")
print(f"AUDIO DIR         : {os.path.join(os.getcwd(),AUDIO_DIR)}/")
print(f"KISS target       : {HOST}:{KISS_PORT}\n")

# === KISS CONNECTION CHECK ===
print("Checking KISS connection to Direwolf...", end=" ")
sys.stdout.flush()

sock = None
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((HOST, KISS_PORT))
    print("SUCCESS ✓")
except socket.timeout:
    print("\nError: Connection timed out.")
    print("   → Is Direwolf running with KISSPORT 8001 enabled?")
    sys.exit(1)
except ConnectionRefusedError:
    print("\nError: Connection refused.")
    print("   → Direwolf not listening on port 8001.")
    sys.exit(1)
except Exception as e:
    print(f"\nError: Unexpected connection error: {e}")
    sys.exit(1)

# === Proceed ===

ssdv_process = img2ssdv(PACKET_LENGTH,AUDIO_DIR,filename,SRC_CALL)

print(ssdv_process)

data = open(os.path.join(AUDIO_DIR, f"{basename_noext}.bin"), 'rb').read()
src_addr = ax25_address(SRC_CALL)
dest_addr = ax25_address(FILE_ID, last=True)


print("Starting WAV recording...")
wav_process = start_recording(os.path.join(AUDIO_DIR, output_wav))
time.sleep(2)

frame_num = 0
offset = 0
total_bytes = len(data)
total_frames = (total_bytes + PACKET_LENGTH - 1) // PACKET_LENGTH

print(f"Sending {total_bytes} bytes in ~{total_frames} frames...\n")

while offset < total_bytes:
    chunk_size = min(PACKET_LENGTH, total_bytes - offset)
    chunk = data[offset:offset + chunk_size]
    offset += chunk_size
    
    payload = chunk
    frame = dest_addr + src_addr + b'\x03\xf0' + payload
    kiss_frame = FEND + b'\x00' + kiss_escape(frame) + FEND
    
    try:
        sock.sendall(kiss_frame)
    except BrokenPipeError:
        print("\nError: Connection lost during transmission.")
        sock.close()
        stop_recording(wav_process)
        sys.exit(1)
    
    print(f"Frame {frame_num:4d}/{total_frames-1} → {chunk_size:3d} bytes")
    frame_num += 1
    
    time.sleep(FRAME_DELAY)

sock.close()
print("\nMake sure to only press <ENTER> when the generated sound has ended\nor the audio will not be saved completely.")
input()
stop_recording(wav_process)

time.sleep(1)
if os.path.exists(os.path.join(AUDIO_DIR, output_wav)):
    size_mb = os.path.getsize(os.path.join(AUDIO_DIR, output_wav)) / (1024 * 1024)
    print(f"WAV file saved: {output_wav} ({size_mb:.2f} MB)")
    print(f"Ready for playback over radio")
else:
    print("Warning: No WAV file created — check sox/audio setup.")
