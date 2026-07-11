# Martian Gothic: Unification - .TEX Converter

A Python .PY script tool for converting the `.tex` texture files used in *Martian Gothic:
Unification* to and from PNG, so they can be viewed, edited, and repacked.

NOTE: Created with Claude AI, Sonett v5 model, tested by me. 

Feel free to give feedback, suggestions and even fork this further.

---

## Requirements

- **Python 3** (3.8 or newer)
- **Pillow** (the Python imaging library)

Install Pillow from Command Prompt if you don't already have it:

```
pip install Pillow
```

That's the only dependency — everything else the script uses
(`struct`, `argparse`, `pathlib`, etc.) is built into Python.

---

## How to use it

### Option 1 — Drag and drop (easiest)

Drag one or more of the following onto `tex_converter.py`:

| You drop... | What happens |
|---|---|
| a single `.tex` file | extracts its frame(s) into a folder named after it, next to it (e.g. `mface.tex` → `mface\frame_00.png`, ...) |
| a folder of `frame_00.png`, `frame_01.png`, ... | packs them back into a `.tex` file named after the folder, next to it |
| a folder containing `.tex` files (including in subfolders) | recursively finds and extracts every `.tex` file inside, each into its own sibling folder |
| several files/folders at once | processes each one in turn, using the rules above |

The console window stays open with a "press Enter to close" prompt so
you can read the output before it closes.

### Option 2 — Double-click with no arguments

Double-clicking the script directly (without dropping anything onto it)
opens a simple step-by-step menu in the console asking whether you want
to extract or pack, and for the relevant paths.

### Option 3 — Command line (for scripting)

```
# Extract every frame from a .tex file to PNGs
python tex_converter.py extract mface.tex -o output_folder/

# Extract only one frame (e.g. frame 0)
python tex_converter.py extract mface.tex -o output_folder/ --frame 0

# Pack a folder of frame_NN.png files back into a .tex
python tex_converter.py pack output_folder/ -o mface_new.tex
```

---

## Editing textures

1. Extract the `.tex` file (drag & drop is easiest).
2. Edit the `frame_NN.png` files in the resulting folder in any image editor.
   - Keep the same filenames (`frame_00.png`, `frame_01.png`, ...) and the
     same count of frames — the pack step expects exactly that naming.
   - Don't touch `_pixel_format.txt` — it records which of the two pixel
     formats (see below) the original file used, so packing restores it
     automatically without you having to specify it.
3. Drag the edited folder back onto the script (or use `pack` from the
   command line) to produce a new `.tex` file.

**A note on transparency:** if the original texture was RGB565 (opaque,
no alpha channel) and you add transparency to the PNG before repacking,
that transparency will be silently discarded — RGB565 has no alpha bits
to store it in. This is a property of the format itself, not a bug in
the tool.

---

## The .TEX file format

Reverse-engineered from `mface.tex` (RGB565) and `RPANIMG.tex` (ARGB4444).

**Header:**

| Field | Type | Notes |
|---|---|---|
| `frame_count` | int32 | number of frames/sub-images in the file |
| `pixel_format` | int32 | `0` = RGB565, `1` = ARGB4444 |
| `offsets[frame_count]` | int32 each | byte offset of each frame within the file |

**Each frame, at its offset:**

| Field | Type | Notes |
|---|---|---|
| `width` | uint16 | |
| `height` | uint16 | |
| pixel data | `width * height` uint16 values | little-endian, top-down rows, no padding |

**Pixel formats:**

- **`0` — RGB565**: 5 bits red, 6 bits green, 5 bits blue. No alpha
  (always fully opaque).
- **`1` — ARGB4444**: 4 bits each of alpha, red, green, blue.

A single `.tex` file can hold multiple frames — for example, the
different blood/damage stages of a face texture, or animation frames.
All frames within one file share the same `pixel_format`.

This covers every file checked so far in *Martian Gothic: Unification*
(character textures, UI panels, etc.) — the game appears to only use
these two pixel formats. If you ever come across a `.tex` file that
decodes with garbled colors, it likely uses a different `pixel_format`
code than the two handled here; the tool will report the unrecognized
code number rather than silently producing wrong output.

---

## Troubleshooting

- **"unpack requires a buffer of X bytes" / "file is only N bytes"** —
  the `.tex` file is empty, a placeholder, or otherwise not a real
  texture. The tool skips it and continues with the rest of the batch.
- **Double-clicking shows nothing / window flashes and closes** — this
  version pauses before closing so you can read any output; if you're
  still seeing this, make sure you're running the actual updated file.
- **Colors look wrong after extracting** — should no longer happen for
  RGB565/ARGB4444 files.
