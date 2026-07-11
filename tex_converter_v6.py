#!/usr/bin/env python3
"""
tex_converter.py
================
Converter for the .TEX texture format used by "Martian Gothic: Xplosive".

Format (reverse-engineered from mface.tex and RPANIMG.tex):
--------------------------------------------
Header:
    int32   frame_count
    int32   pixel_format   (0 = RGB565, 1 = ARGB4444 -- see below)
    int32[frame_count]   byte offsets into the file, one per frame

Each frame, at its offset:
    uint16  width
    uint16  height
    <width*height> pixels, each a little-endian uint16, encoded according
    to the file's pixel_format:
        0 = RGB565   (5 bits red, 6 bits green, 5 bits blue, no alpha)
        1 = ARGB4444 (4 bits each of alpha, red, green, blue)
    Rows are top-down, no padding.

A .tex file can contain multiple frames (e.g. different damage/blood
stages of a face texture, or animation frames). All frames in one file
share the same pixel_format. This tool extracts every frame to its own
PNG (with transparency preserved for ARGB4444 files), or repacks a
folder of same-format PNGs back into a .tex file. When extracting, a
small "_pixel_format.txt" file is written into the output folder so
that packing back later restores the exact original format.

Usage:
------
Easiest: DRAG AND DROP
    Drag a .tex file onto tex_converter.py -> extracts its frames into
    a folder named after the file, next to it (e.g. mface.tex -> mface/).

    Drag a folder full of frame_00.png, frame_01.png, ... onto
    tex_converter.py -> packs it into a .tex file named after the folder,
    next to it (e.g. mface/ -> mface.tex).

    Drag a folder containing .tex files (including in subfolders, e.g. a
    whole "mesh/undead/" game folder) onto tex_converter.py -> extracts
    every .tex file found, each into its own folder next to it.

    You can drop multiple files/folders at once; each is processed in turn.

Or double-click the script with no arguments for a step-by-step menu.

Or from a command prompt, for scripting / more control:
    Extract all frames from a .tex to PNGs:
        python3 tex_converter.py extract mface.tex -o output_folder/

    Extract just frame 0:
        python3 tex_converter.py extract mface.tex -o output_folder/ --frame 0

    Repack PNGs into a new .tex. The pixel format (RGB565 or ARGB4444) is
    restored automatically from the _pixel_format.txt file that 'extract'
    writes into the folder -- or, if that's missing, inferred from whether
    the PNGs have transparency:
        python3 tex_converter.py pack output_folder/ -o mface_new.tex

Repacking expects files named frame_00.png, frame_01.png, ... (the same
naming used by 'extract'), in the order they should appear in the .tex.
"""

import argparse
import struct
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("This tool requires Pillow. Install it with:\n"
              "    pip install Pillow --break-system-packages")


HEADER_INT_FMT = "<i"      # little-endian int32
FRAME_DIM_FMT = "<HH"      # little-endian uint16, uint16

FORMAT_RGB565 = 0
FORMAT_ARGB4444 = 1
FORMAT_NAMES = {
    FORMAT_RGB565: "RGB565",
    FORMAT_ARGB4444: "ARGB4444",
}
META_FILENAME = "_pixel_format.txt"


def _decode_rgb565(v):
    r5 = (v >> 11) & 0x1F
    g6 = (v >> 5) & 0x3F
    b5 = v & 0x1F
    # Expand 5/6-bit channels to 8-bit via bit replication (the
    # standard, exactly-invertible technique) rather than plain
    # scaling, so a pack->extract->pack round trip is lossless.
    r = (r5 << 3) | (r5 >> 2)
    g = (g6 << 2) | (g6 >> 4)
    b = (b5 << 3) | (b5 >> 2)
    return (r, g, b)


def _encode_rgb565(r, g, b, a):
    r5 = r >> 3
    g6 = g >> 2
    b5 = b >> 3
    return (r5 << 11) | (g6 << 5) | b5


def _decode_argb4444(v):
    a4 = (v >> 12) & 0xF
    r4 = (v >> 8) & 0xF
    g4 = (v >> 4) & 0xF
    b4 = v & 0xF
    a = (a4 << 4) | a4
    r = (r4 << 4) | r4
    g = (g4 << 4) | g4
    b = (b4 << 4) | b4
    return (r, g, b, a)


def _encode_argb4444(r, g, b, a):
    a4 = a >> 4
    r4 = r >> 4
    g4 = g >> 4
    b4 = b >> 4
    return (a4 << 12) | (r4 << 8) | (g4 << 4) | b4


def decode_frame_pixels(pixel_bytes: bytes, width: int, height: int, pixel_format: int) -> "Image.Image":
    """Decode raw pixel bytes into a Pillow image, according to pixel_format."""
    count = width * height
    vals = struct.unpack(f"<{count}H", pixel_bytes)

    if pixel_format == FORMAT_RGB565:
        img = Image.new("RGB", (width, height))
        px = img.load()
        for i, v in enumerate(vals):
            x, y = i % width, i // width
            px[x, y] = _decode_rgb565(v)
        return img

    if pixel_format == FORMAT_ARGB4444:
        img = Image.new("RGBA", (width, height))
        px = img.load()
        for i, v in enumerate(vals):
            x, y = i % width, i // width
            px[x, y] = _decode_argb4444(v)
        return img

    raise ValueError(
        f"unsupported pixel format code {pixel_format} -- only 0 (RGB565) and "
        f"1 (ARGB4444) are currently supported. If TextureFinder shows this "
        f"file with a different format (e.g. 1555, 8888), send it over so "
        f"support can be added."
    )


def encode_frame_pixels(img: "Image.Image", pixel_format: int) -> bytes:
    """Encode a Pillow image into raw pixel bytes, according to pixel_format."""
    img = img.convert("RGBA")
    width, height = img.size
    px = img.load()
    vals = []

    if pixel_format == FORMAT_RGB565:
        for y in range(height):
            for x in range(width):
                r, g, b, a = px[x, y]
                vals.append(_encode_rgb565(r, g, b, a))
    elif pixel_format == FORMAT_ARGB4444:
        for y in range(height):
            for x in range(width):
                r, g, b, a = px[x, y]
                vals.append(_encode_argb4444(r, g, b, a))
    else:
        raise ValueError(f"unsupported pixel format code {pixel_format}")

    return struct.pack(f"<{len(vals)}H", *vals)


def read_tex(path: Path):
    """
    Parse a .tex file. Returns (pixel_format, frames) where frames is a
    list of (width, height, PIL.Image).
    """
    data = path.read_bytes()

    if len(data) < 8:
        raise ValueError(f"file is only {len(data)} bytes -- too small to be a "
                          f"valid .tex (probably empty or a placeholder)")

    frame_count, pixel_format = struct.unpack("<ii", data[0:8])
    offsets = struct.unpack(f"<{frame_count}i", data[8:8 + frame_count * 4])

    frames = []
    for off in offsets:
        width, height = struct.unpack(FRAME_DIM_FMT, data[off:off + 4])
        pixel_bytes = data[off + 4: off + 4 + width * height * 2]
        img = decode_frame_pixels(pixel_bytes, width, height, pixel_format)
        frames.append((width, height, img))
    return pixel_format, frames


def write_tex(path: Path, frames, pixel_format: int):
    """Write a list of PIL.Image frames out as a .tex file with the given pixel_format."""
    frame_count = len(frames)
    header_size = 8 + 4 * frame_count

    frame_blobs = []
    offset = header_size
    offsets = []
    for img in frames:
        width, height = img.size
        pixel_bytes = encode_frame_pixels(img, pixel_format)
        blob = struct.pack(FRAME_DIM_FMT, width, height) + pixel_bytes
        frame_blobs.append(blob)
        offsets.append(offset)
        offset += len(blob)

    with open(path, "wb") as fh:
        fh.write(struct.pack(HEADER_INT_FMT, frame_count))
        fh.write(struct.pack(HEADER_INT_FMT, pixel_format))
        fh.write(struct.pack(f"<{frame_count}i", *offsets))
        for blob in frame_blobs:
            fh.write(blob)


def write_format_meta(out_dir: Path, pixel_format: int):
    """Record the source .tex's pixel format so 'pack' can restore it exactly."""
    name = FORMAT_NAMES.get(pixel_format, f"unknown code {pixel_format}")
    (out_dir / META_FILENAME).write_text(
        f"{pixel_format}\n"
        f"# pixel_format={name} -- used automatically when packing this "
        f"folder back into a .tex. Don't edit or delete this file.\n"
    )


def read_format_meta(in_dir: Path):
    """Return the pixel_format recorded by write_format_meta, or None if absent/unreadable."""
    meta_path = in_dir / META_FILENAME
    if not meta_path.exists():
        return None
    try:
        first_line = meta_path.read_text().splitlines()[0].strip()
        return int(first_line)
    except (ValueError, IndexError, OSError):
        return None


def cmd_extract(args):
    tex_path = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    pixel_format, frames = read_tex(tex_path)
    format_name = FORMAT_NAMES.get(pixel_format, f"unknown code {pixel_format}")
    print(f"{tex_path.name}: {len(frames)} frame(s) found (format: {format_name})")

    targets = range(len(frames)) if args.frame is None else [args.frame]
    for i in targets:
        if i < 0 or i >= len(frames):
            print(f"  frame {i}: out of range, skipping")
            continue
        width, height, img = frames[i]
        out_path = out_dir / f"frame_{i:02d}.png"
        img.save(out_path)
        print(f"  frame {i}: {width}x{height} -> {out_path}")

    write_format_meta(out_dir, pixel_format)


def cmd_pack(args):
    in_dir = Path(args.input)
    out_path = Path(args.output)

    png_files = sorted(in_dir.glob("frame_*.png"))
    if not png_files:
        sys.exit(f"No frame_NN.png files found in {in_dir}")

    frames = [Image.open(p) for p in png_files]

    pixel_format = read_format_meta(in_dir)
    if pixel_format is not None:
        source = f"from {META_FILENAME}"
    else:
        # No metadata (e.g. a hand-made folder, or extracted with an older
        # version of this script) -- infer from whether the PNGs carry an
        # alpha channel, since that's how 'extract' saves each format.
        pixel_format = FORMAT_ARGB4444 if any(img.mode in ("RGBA", "LA") for img in frames) else FORMAT_RGB565
        source = "inferred from image transparency (no _pixel_format.txt found)"

    format_name = FORMAT_NAMES.get(pixel_format, f"unknown code {pixel_format}")
    write_tex(out_path, frames, pixel_format)
    print(f"Packed {len(frames)} frame(s) from {in_dir} -> {out_path}")
    print(f"  pixel format: {format_name} ({source})")
    for p, img in zip(png_files, frames):
        print(f"  {p.name}: {img.size[0]}x{img.size[1]}")


def extract_one_tex(tex_path: Path):
    """Extract a single .tex file into a folder named after it, next to it."""
    out_dir = tex_path.parent / tex_path.stem
    print(f"Extracting: {tex_path.name}  ->  {out_dir}\\")
    args = argparse.Namespace(input=str(tex_path), output=str(out_dir), frame=None)
    cmd_extract(args)


def handle_dropped_path(path: Path):
    """
    Handle a single dropped file or folder (drag & drop onto the script).
    - A .tex file gets its frames extracted into a folder next to it.
    - A folder containing frame_NN.png files gets packed into a .tex
      file next to it.
    - A folder that instead contains .tex files (including in
      subfolders) gets every one of them extracted in place.
    """
    if not path.exists():
        print(f"SKIPPED: path does not exist: {path}")
        return

    if path.is_file() and path.suffix.lower() == ".tex":
        extract_one_tex(path)

    elif path.is_dir():
        png_files = sorted(path.glob("frame_*.png"))
        if png_files:
            out_path = path.parent / (path.name + ".tex")
            print(f"Packing: {path}\\  ->  {out_path.name}")
            args = argparse.Namespace(input=str(path), output=str(out_path))
            cmd_pack(args)
            return

        tex_files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() == ".tex")
        if tex_files:
            print(f"Found {len(tex_files)} .tex file(s) in '{path}' -- extracting each one:")
            print()
            ok_count = 0
            fail_count = 0
            for tex_path in tex_files:
                try:
                    extract_one_tex(tex_path)
                    ok_count += 1
                except Exception as e:
                    fail_count += 1
                    print(f"SKIPPED: '{tex_path.relative_to(path)}' could not be processed ({e})")
                print()
            summary = f"Folder '{path.name}': {ok_count} extracted"
            if fail_count:
                summary += f", {fail_count} skipped due to errors"
            print(summary)
            return

        print(f"SKIPPED: '{path}' has no frame_00.png/frame_01.png/... files to pack, "
              f"and no .tex files to extract")

    else:
        print(f"SKIPPED: don't know what to do with '{path}' "
              f"(expected a .tex file, a folder of frame_NN.png files, or a "
              f"folder containing .tex files)")


def is_drag_and_drop_invocation() -> bool:
    """
    True if the script was launched by dragging one or more files/folders
    onto it in Windows Explorer, rather than run with explicit 'extract'
    or 'pack' command-line arguments.
    """
    if len(sys.argv) < 2:
        return False
    if sys.argv[1] in ("extract", "pack"):
        return False
    # Any dropped item will exist on disk as a real file/folder path.
    return Path(sys.argv[1]).exists()


def run_drag_and_drop(paths):
    print("=" * 60)
    print(" Martian Gothic .TEX <-> PNG converter (drag & drop)")
    print("=" * 60)
    print()
    ok_count = 0
    fail_count = 0
    for raw in paths:
        path = Path(raw)
        try:
            handle_dropped_path(path)
            ok_count += 1
        except Exception as e:
            fail_count += 1
            print(f"SKIPPED: '{path.name}' could not be processed ({e})")
        print()
    summary = f"All done! {ok_count} succeeded"
    if fail_count:
        summary += f", {fail_count} skipped due to errors"
    print(summary)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Convert Martian Gothic .TEX texture files to/from PNG."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Extract frames from a .tex file to PNGs")
    p_extract.add_argument("input", help="Path to the .tex file")
    p_extract.add_argument("-o", "--output", required=True, help="Output folder for PNGs")
    p_extract.add_argument("--frame", type=int, default=None,
                            help="Extract only this frame index (default: all frames)")
    p_extract.set_defaults(func=cmd_extract)

    p_pack = sub.add_parser("pack", help="Pack a folder of frame_NN.png files into a .tex file")
    p_pack.add_argument("input", help="Folder containing frame_00.png, frame_01.png, ...")
    p_pack.add_argument("-o", "--output", required=True, help="Output .tex file path")
    p_pack.set_defaults(func=cmd_pack)

    return parser


def interactive_menu():
    """
    Runs when the script is launched with no arguments at all -- which is
    what happens if you double-click the .py file in Windows Explorer
    instead of running it from a command prompt. Walks the user through
    extract/pack with plain prompts instead of requiring command-line flags.
    """
    print("=" * 60)
    print(" Martian Gothic .TEX <-> PNG converter")
    print("=" * 60)
    print()
    print("No command-line arguments were given, so here's an interactive")
    print("menu instead. (You can also run this from a terminal with")
    print("'extract' or 'pack' arguments -- see the comments at the top")
    print("of this file for exact usage.)")
    print()
    print("What do you want to do?")
    print("  1) Extract frames from a .tex file to PNGs")
    print("  2) Pack a folder of PNGs into a new .tex file")
    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        tex_path = Path(input("Path to the .tex file: ").strip('"').strip())
        if not tex_path.exists():
            print(f"ERROR: file not found: {tex_path}")
            return
        out_dir_input = input(
            "Output folder for PNGs (leave blank to use a folder "
            "next to the .tex file): "
        ).strip('"').strip()
        out_dir = Path(out_dir_input) if out_dir_input else tex_path.with_suffix("")
        args = argparse.Namespace(input=str(tex_path), output=str(out_dir), frame=None)
        cmd_extract(args)
    elif choice == "2":
        in_dir = Path(input("Folder containing frame_00.png, frame_01.png, ...: ").strip('"').strip())
        if not in_dir.exists():
            print(f"ERROR: folder not found: {in_dir}")
            return
        out_path_input = input("Output .tex filename (e.g. mface_new.tex): ").strip('"').strip()
        out_path = Path(out_path_input) if out_path_input else in_dir.with_suffix(".tex")
        args = argparse.Namespace(input=str(in_dir), output=str(out_path))
        cmd_pack(args)
    else:
        print("Not a valid choice (must be 1 or 2).")


def main():
    if is_drag_and_drop_invocation():
        # Launched by dragging file(s)/folder(s) onto the script.
        try:
            run_drag_and_drop(sys.argv[1:])
        except Exception as e:
            print(f"\nERROR: {e}")
        finally:
            _pause()
        return

    if len(sys.argv) == 1:
        # No arguments at all -> almost certainly launched by double-click.
        # Fall back to an interactive menu instead of an argparse error.
        try:
            interactive_menu()
        except Exception as e:
            print(f"\nERROR: {e}")
        finally:
            _pause()
        return

    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print(f"\nERROR: {e}")
    finally:
        # Keep the console window open if this was launched by double-click
        # on Windows (python.exe closes the window instantly otherwise).
        if sys.platform == "win32":
            _pause()


def _pause():
    try:
        input("\nDone. Press Enter to close this window...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
