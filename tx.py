#!/usr/bin/env python3
# Copyright 2026 hobisatelit
# https://github.com/hobisatelit/ssdv2sat
# License: GPL-3.0-or-later
# SSDV doc: https://ukhas.org.uk/doku.php?id=guides:ssdv
VERSION = '0.02'

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

ALPHANUM = string.ascii_uppercase + string.digits

FEND = b'\xC0'
FESC = b'\xDB'
TFEND = b'\xDC'
TFESC = b'\xDD'

def show_progress(i, n, width=30):
    p = int(i) / int(n)
    bar = "█" * int(width * p) + "░" * (width - int(width * p))
    print(f"\r[{bar}] {p:5.1%} - Frame {i:4d}/{n}", end="")

def generate_random_id():
    random_entropy = os.urandom(256)
    byte1, byte2, byte3 = random_entropy[0], random_entropy[1], random_entropy[2]
    return ALPHANUM[byte1 % 36] + ALPHANUM[byte2 % 36] + ALPHANUM[byte3 % 36]

def start_recording(output_filename):
    command = ["sox", "-d", "-r", "44100", "-c", "1", "-t", "wav", "-q", "-V1", output_filename]
    return subprocess.Popen(command)
    
def img2ssdv(packet_length,output_dir,input_filename,callsign,text,quality,max_size,filesuffix):
  try:
    max_w, max_h = max_size
    command = [os.path.join(os.getcwd(),"img2ssdv.py"), "--length", str(packet_length), "--dir", str(output_dir), "--callsign", str(callsign),  input_filename, "--text", str(text), "--quality", str(quality), "--max-size", str(max_w), str(max_h), "--suffix", filesuffix]
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

def main():
    parser = argparse.ArgumentParser(
        description="Convert an image into SSDV, transmit over IL2P using Dire Wolf KISS and record as audio wav",
        epilog="Example: ./tx.py ABCDEF image.jpg"
    )
    parser.add_argument("callsign", help="your actual callsign")
    parser.add_argument("filename", help="input image file (JPG, PNG, etc)")
    parser.add_argument("--host", default="127.0.0.1", help="Dire Wolf host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8001, help="Dire Wolf KISS TCP port (default: 8001)")
    parser.add_argument("--max", type=int, default=DEFAULT_PACKET_LENGTH,
                        help=f"Max data bytes per frame (default: {DEFAULT_PACKET_LENGTH}, min 64, max 256)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"Delay between frames in seconds (default: {DEFAULT_DELAY}, use 0.1-3s for longer satellite pass, and 0 for shortest)")
    parser.add_argument("--quality", type=int, default=20,
                        help="JPEG quality 1–95 (default: 20 – good for SSDV)")  
    parser.add_argument("--text", type=str, default='',
                        help="put small text in the top-left corner of the image") 
    parser.add_argument("--max-size", nargs=2, type=int, metavar=("WIDTH", "HEIGHT"),
                        default=[320, 320],
                        help="Max width and height in pixels (default: 320 320)")
    parser.add_argument("--dir", type=str, default=DEFAULT_AUDIO_DIR,
                        help=f"Directory for save recorded audio wav (default: {DEFAULT_AUDIO_DIR})")
    parser.add_argument("--version", action='version', version=f"ssdv2sat-%(prog)s v{VERSION} by hobisatelit <https://github.com/hobisatelit>", help="Show the version of the application")

    args = parser.parse_args()

    max_w, max_h = args.max_size
    if max_w < 16 or max_h < 16:
        print("Error: max dimensions must be at least 16 pixels", file=sys.stderr)
        sys.exit(1)
                    
    if not (64 <= args.max <= 256):
        print("Error: --max should be between 64 and 256")
        sys.exit(1)
    if not (1 <= args.quality <= 95):
        print("Error: quality must be between 1 and 95", file=sys.stderr)
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

    os.makedirs(AUDIO_DIR, exist_ok=True)

    filename = os.path.abspath(filename)

    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found!")
        sys.exit(1)

    basename = os.path.basename(filename)
    basename_noext = os.path.splitext(basename)[0]
    
    FILE_ID = generate_random_id()
    
    # filename suffix
    FILE_SUFFIX = f"{SRC_CALL}_{FILE_ID}_{PACKET_LENGTH}b_{FRAME_DELAY}s_{args.quality}q"

    # WAV filename includes FILE_ID
    output_wav = f"{basename_noext}_audio_{FILE_SUFFIX}.wav"

    print(f"Image name        : {basename}")
    print(f"FILE_ID           : {FILE_ID}")
    print(f"PACKET_LENGTH     : {PACKET_LENGTH} byte/frame")
    print(f"Frame delay       : {FRAME_DELAY} seconds")
    print(f"Audio output      : {output_wav}")
    print(f"AUDIO DIR         : {os.path.join(os.getcwd(),AUDIO_DIR)}/")
    print(f"KISS target       : {HOST}:{KISS_PORT}\n")

    # === KISS CONNECTION CHECK ===
    print("Checking KISS connection to Dire Wolf...", end=" ")
    sys.stdout.flush()

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((HOST, KISS_PORT))
        print("SUCCESS ✓")
    except socket.timeout:
        print("\nError: Connection timed out.")
        print("   → Is Dire Wolf running with KISSPORT 8001 enabled?")
        sys.exit(1)
    except ConnectionRefusedError:
        print("\nError: Connection refused.")
        print("   → Dire Wolf not listening on port 8001.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: Unexpected connection error: {e}")
        sys.exit(1)

    # === Proceed ===

    ssdv_process = img2ssdv(PACKET_LENGTH,AUDIO_DIR,filename,SRC_CALL,args.text,args.quality,args.max_size,FILE_SUFFIX)

    data = open(os.path.join(AUDIO_DIR, f"{basename_noext}_ssdv_{FILE_SUFFIX}.bin"), 'rb').read()
    frame_num = 0
    offset = 0
    total_bytes = len(data)
    total_frames = (total_bytes + PACKET_LENGTH - 1) // PACKET_LENGTH

    src_addr = ax25_address(SRC_CALL)
    dest_addr = ax25_address(str(FILE_ID) + str(hex(total_frames)[2:]), last=True)

    print("Starting WAV recording...")
    wav_process = start_recording(os.path.join(AUDIO_DIR, output_wav))
    time.sleep(2)

    print(f"Sending {total_bytes} bytes to Dire Wolf in ~{total_frames} frames...\n")

    while offset < total_bytes:
        chunk_size = min(PACKET_LENGTH, total_bytes - offset)
        chunk = data[offset:offset + chunk_size]
        offset += chunk_size
        
        payload = chunk
        frame = dest_addr + src_addr + b'\x03\xf0' + payload
        kiss_frame = FEND + b'\x00' + kiss_escape(frame) + FEND
        
        try:
            sock.sendall(kiss_frame)
            #print(f"Frame {frame_num:4d}/{total_frames-1} → {chunk_size:3d} bytes")
            show_progress(frame_num, total_frames-1)
        except BrokenPipeError:
            print("\nError: Connection lost during transmission.")
            sock.close()
            stop_recording(wav_process)
            sys.exit(1)
            
        frame_num += 1
        
        time.sleep(FRAME_DELAY)
    print()
    sock.close()
    print("\nPress <ENTER> only after the sound ends, or the audio won't save completely")
    input()
    stop_recording(wav_process)

    time.sleep(1)
    if os.path.exists(os.path.join(AUDIO_DIR, output_wav)):
        size_mb = os.path.getsize(os.path.join(AUDIO_DIR, output_wav)) / (1024 * 1024)
        print(f"WAV file saved: {output_wav} ({size_mb:.2f} MB)")
        print(f"Ready for playback over radio. 73!")
    else:
        print("Warning: No WAV file created — check sox/audio setup.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
