#!/usr/bin/env python3
# Copyright 2026 hobisatelit
# https://github.com/hobisatelit/ssdv2sat
# License: GPL-3.0-or-later
# SSDV doc: https://ukhas.org.uk/doku.php?id=guides:ssdv

# This script connects to a Dire Wolf KISS TCP server (port 8001 by default)
# and extracts SSDV packets from IL2P payloads
#
# Payload structure from Dire Wolf KISS:
#   bytes 0–15:   IL2P header (used as image fingerprint / unique id)
#   bytes 16–271: SSDV packet (max: 256 bytes total)
#
# SSDV packet (max: 256 bytes):
#   offset  0: sync        0x55
#   offset  1: sync        0x67
#   offset 2–5: callsign   4 bytes
#   offset  6: image ID    1 byte
#   offset 7–8: packet ID  2 bytes (big-endian)
#   offset 9–255: image data (247 bytes)
VERSION = '0.01'

import socket
import argparse
import sys
import os
import subprocess
from collections import defaultdict

KISS_FEND = b'\xC0'
KISS_DATA_FRAME = 0x00

# 16 byte il2p header + 64 byte minimum ssdv 
MIN_PACKET_LENGTH = 16 + 64

def ssdv_decoding(packet_length,input_filename,output_filename):
  try:
    command = ["ssdv", "-d", "-l", str(packet_length), input_filename, output_filename]
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
  except FileNotFoundError:
    return None
  except subprocess.CalledProcessError as e:
    print(f"An error occurred while running {app_name}: {e}")
    return None

def kiss_unescape(data: bytes) -> bytes:
    """Remove KISS escaping from frame content"""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xDB and i + 1 < len(data):
            if data[i + 1] == 0xDC:
                out.append(0xC0)
            elif data[i + 1] == 0xDD:
                out.append(0xDB)
            else:
                out.append(0xDB)
                out.append(data[i + 1])
            i += 2
        else:
            out.append(data[i])
            i += 1
    return bytes(out)

def bytes_to_hex_preview(b: bytes, max_chars: int = 96) -> str:
    """Convert bytes to space-separated hex string, truncated if long"""
    hex_str = b.hex(' ')
    if len(hex_str) > max_chars:
        return hex_str[:max_chars] + '...'
    return hex_str

def parse_ssdv_packet(ssdv_bytes: bytes, verbose: bool = False) -> dict | None:
    """
    Validate and parse the SSDV packet.
    """
    if ssdv_bytes[0] != 0x55 or ssdv_bytes[1] != 0x67:
        if verbose:
            print(f"  → Invalid sync bytes: {ssdv_bytes[0]:02X} {ssdv_bytes[1]:02X} (expected 55 67)")
        return None
  
    packet_id = (ssdv_bytes[7] << 8) | ssdv_bytes[8]
    image_id  = ssdv_bytes[6]
    return {
        'packet_id': packet_id,
        'image_id': image_id,
        'image_data': ssdv_bytes[0:]  
    }

def main(args):
    print(f"Connecting to Dire Wolf KISS TCP at {args.host}:{args.port} ...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((args.host, args.port))
        print("Connected.")
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)

    # output/ folder next to script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Decode SSDV image fragments to: {output_dir}/")
    print(f"Expecting 16-byte IL2P for ID + min {MIN_PACKET_LENGTH - 16}-byte for SSDV")

    # (callsign, image_id) → {packet_id: image_data (186 bytes)}
    images = defaultdict(dict)
    total_valid = 0

    packet_buf = bytearray()
    in_frame = False

    while True:
        try:
            chunk = sock.recv(1024)
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            break
        except Exception as e:
            print(f"Socket error: {e}", file=sys.stderr)
            break

        if not chunk:
            print("Server closed connection.")
            break

        for byte in chunk:
            if byte == 0xC0:
                if in_frame:
                    # Frame complete
                    if len(packet_buf) >= 1:
                        frame_type = packet_buf[0]
                        payload = kiss_unescape(packet_buf[1:])

                        if frame_type == KISS_DATA_FRAME:
                            if len(payload) >= MIN_PACKET_LENGTH:
                                ssdv_part = payload[16:]
                                ssdv_len = len(ssdv_part)

                                dest_field = payload[0:7]
                                src_field = payload[7:14]
                                
                                file_id = ''.join(chr(c >> 1) for c in dest_field[:6]).strip()
                                src_call = ''.join(chr(c >> 1) for c in src_field[:6]).strip()

                                parsed = parse_ssdv_packet(ssdv_part, verbose=args.verbose)
                                                                
                                if parsed:
                                    parsed['callsign'] = src_call
                                    
                                    if not parsed['image_id']:
                                         parsed['image_id'] = file_id 

                                    key = (parsed['callsign'], parsed['image_id'])
                                    was_new = len(images[key]) == 0

                                    images[key][parsed['packet_id']] = parsed['image_data']

                                    
                                    fname_noext = f"{parsed['callsign']}_{parsed['image_id']}_{ssdv_len}bs"
                                    fname = f"{fname_noext}.bin"
                                    
                                    path = os.path.join(output_dir, fname)

                                    # Write in packet ID order
                                    with open(path, "wb") as f:
                                        for pid in sorted(images[key]):
                                            f.write(images[key][pid])
                                            
                                    if was_new:
                                        print(f"    → New from: {parsed['callsign']}, image: {parsed['image_id']} ({ssdv_len} byte/frags)")
 
                                    if args.verbose:
                                        print(f"\nReceived SSDV candidate ({ssdv_len}) byte:")
                                        print("" + bytes_to_hex_preview(ssdv_part, 1000))

                                    total_valid += 1
                                    print(f"OK  Packet {parsed['packet_id']:5d} | {parsed['callsign']:<8} | "
                                          f"Img {parsed['image_id']} | {len(images[key]):3d} frags | → {fname}")

                                    ssdv_process = ssdv_decoding(ssdv_len,os.path.join(output_dir, fname),os.path.join(output_dir, f"{fname_noext}.jpg"))

                                else:
                                    if args.verbose:
                                        print("  → Rejected (invalid SSDV)")
                            else:
                                if args.verbose:
                                    print(f"  → Wrong payload length: {len(payload)} (expected min {MIN_PACKET_LENGTH})")

                    packet_buf = bytearray()
                    in_frame = False
                else:
                    in_frame = True
                    packet_buf = bytearray()
            elif in_frame:
                packet_buf.append(byte)

    sock.close()
    print(f"\nFinished. Processed {total_valid} valid SSDV packets.")

    if total_valid > 0:
        print("\nFiles created in output/:")
        for (call, img), frags in sorted(images.items()):
            print(f"  {call}_{img}.bin  →  {len(frags)} fragments")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dire Wolf KISS TCP → SSDV → sorted .bin files → JPEG image"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Dire Wolf host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8001, help="Dire Wolf KISS TCP port (default: 8001)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print hex of each received SSDV candidate + parsing details")
    parser.add_argument("--version", action='version', version=f"ssdv2sat-%(prog)s v{VERSION} by hobisatelit <https://github.com/hobisatelit>", help="Show the version of the application")
    args = parser.parse_args()

    try:
        main(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
