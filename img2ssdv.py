#!/usr/bin/env python3
# Copyright 2026 hobisatelit
# https://github.com/hobisatelit/ssdv2sat
# License: GPL-3.0-or-later
VERSION = '0.01'

"""
Convert image to SSDV-compatible JPEG.

Features:
- Resize proportionally to fit within max_width × max_height
- Force dimensions to multiple of 16 (SSDV requirement)
- Quality default 20 (user can override)
- 4:2:0 chroma subsampling
- Floating point DCT (Pillow/libjpeg default in most builds)
- No progressive scan
- No EXIF, XMP, IPTC, thumbnails, ICC profile
- Optimize file size (huffman tables)

Usage:
    python ssdv_jpeg.py input.png output.jpg
    python ssdv_jpeg.py photo.jpg ssdv.jpg --max-size 640 480 --quality 35
"""
import os
import argparse
import sys
import subprocess
from PIL import Image

def make_multiple_of_16(n: int) -> int:
    """Round down to nearest multiple of 16 (SSDV needs 16×16 MCU blocks)."""
    return (n // 16) * 16


def resize_to_fit_keep_aspect(
    img: Image.Image,
    max_w: int,
    max_h: int
) -> Image.Image:
    """Resize proportionally so image fits inside max_w × max_h."""
    orig_w, orig_h = img.size
    ratio = min(max_w / orig_w, max_h / orig_h)

    if ratio >= 1.0:
        new_w, new_h = orig_w, orig_h
    else:
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)

    # Force multiples of 16
    new_w = make_multiple_of_16(new_w)
    new_h = make_multiple_of_16(new_h)

    # Minimum 16×16 to avoid invalid SSDV
    new_w = max(new_w, 16)
    new_h = max(new_h, 16)

    return img.resize((new_w, new_h), Image.Resampling.LANCZOS)


def ssdv_encoding(packet_length,input_filename,output_filename,callsign):
  try:
    command = ["ssdv", "-e", "-n", "-q", "1", "-l", str(packet_length), "-c", str(callsign), input_filename, output_filename]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return stderr.decode().strip()
    #return process
  except FileNotFoundError:
    return f"Cannot find SSDV app. {output_filename} not created.."
  except subprocess.CalledProcessError as e:
    print(f"An error occurred while running {app_name}: {e}")
    return None
    

def main():
    parser = argparse.ArgumentParser(description="Convert image to SSDV-compatible JPEG")
    parser.add_argument("input", help="Input image filename (JPG, PNG, etc.)")
    parser.add_argument("--max-size", nargs=2, type=int, metavar=("WIDTH", "HEIGHT"),
                        default=[320, 320],
                        help="Max width and height in pixels (default: 320 320)")
    parser.add_argument("--callsign", type=str, default='ABCDEF',
                        help="your actual callsign (default: ABCDEF)")   
    parser.add_argument("--quality", type=int, default=20,
                        help="JPEG quality 1–95 (default: 20 – good for SSDV)")                  
    parser.add_argument("--length", type=int, default=256,
                        help="SSDV packet length (default: 256) - between 64-256")
    parser.add_argument("--dir", type=str, default=".",
                        help="output directory (default: .)") 
    parser.add_argument("--version", action='version', version=f"ssdv2sat-%(prog)s v{VERSION} by hobisatelit <https://github.com/hobisatelit>", help="Show the version of the application")


    args = parser.parse_args()
    
    basename = os.path.basename(args.input)
    basename_noext = os.path.splitext(args.input)[0]

    small_output_filename = f"{basename_noext}_small.jpg"
    ssdv_output_filename = f"{basename_noext}.bin"

    max_w, max_h = args.max_size
    if max_w < 16 or max_h < 16:
        print("Error: max dimensions must be at least 16 pixels", file=sys.stderr)
        sys.exit(1)

    if not (1 <= args.quality <= 95):
        print("Error: quality must be between 1 and 95", file=sys.stderr)
        sys.exit(1)
        
    if not (64 <= args.length <= 256):
        print("Error: SSDV packet length must be between 64 and 256", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.dir, exist_ok=True)

    try:
        with Image.open(args.input) as im:
            # Convert to RGB if necessary (SSDV expects color JPEG)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            elif im.mode == "L":
                im = im.convert("RGB")  # SSDV usually wants color, even if source is grayscale

            # Resize
            im_resized = resize_to_fit_keep_aspect(im, max_w, max_h)

            # Save with SSDV-friendly settings
            im_resized.save(
                os.path.join(args.dir, small_output_filename),
                format="JPEG",
                quality=args.quality,
                subsampling=0,           # 0 → 4:2:0 chroma subsampling (standard for SSDV)
                optimize=True,           # Optimize Huffman tables
                progressive=False,       # Baseline JPEG only (no progressive)
                exif=b"",                # Strip all EXIF
                icc_profile=None,        # No color profile
                # Pillow does not write XMP/IPTC/thumbnail unless explicitly added
            )
            
                      
            #ssdv auto encode
            ssdv_process = ssdv_encoding(args.length,os.path.join(args.dir, small_output_filename),os.path.join(args.dir, ssdv_output_filename),args.callsign)


            print(f"\nJPEG Optimization → {small_output_filename}")
            print(f"Rezided to   : {im_resized.size[0]}×{im_resized.size[1]} (multiple of 16, aspect preserved)")
            print(f"Quality      : {args.quality}")
            print(f"Subsampling  : 4:2:0")
            print(f"Progressive  : disabled")
            print(f"Metadata     : fully stripped")
            print(f"\nSSDV Encoding → {ssdv_output_filename}")
            print(f"PacketLength : {args.length} bytes")
            print(ssdv_process)

    except FileNotFoundError:
        print(f"Error: Input file not found → {args.input}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
