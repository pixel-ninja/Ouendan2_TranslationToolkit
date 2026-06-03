# Ouendan2_TranslationToolkit
A script made to help with the English translation efforts for the NDS game Osu! Tatakae! Ouendan 2.
Not particularly useful without the required project files, but here for posterity/curiosity.

# Requirements
## Python
Requires python 3.10+ with pillow (used to get image widths).
```
pip install pillow
```

## Assets
Relies on the following assets (which I can't host here):
- a rom of the game in .nds format
- data: a folder containing the all of the game's decrypted image files
- images_english: a folder containing the bmp/png images that have been translated
- tools: folder of required exe files that perform the conversions

## Folder Structure
The directory of the project should look like this:
```
📁 .
├── 📄 build.py                                  - Build Script
├── 📄 mapping.py                                - Image to Data mappings
├── 📄 'Osu! Tatakae! Ouendan 2 (Japan).nds'     - Original Rom
├── 📁 data                                      - Game Image Data
├── 📁 images_english                            - Translated Images
└── 📁 tools
    ├── 🛠️ lzss.exe                              - Compress Images
    ├── 🛠️ NitroPacker.exe                       - Unpack/Repack ROM
    ├── 🛠️ yyt2_ncer.exe                         - Convert Image to Palette/Tile/Map
    ├── 🛠️ yyt2_nscr.exe                         - Convert Image to Palette/Tile/Map
    ├── 🛠️ yyt2_ntft.exe                         - Convert Image to Palette/Tile/Map
    ├── 🛠️ xdelta3.exe                           - Generate Patch (optional)
    └── 🛠️ melonDS.exe                           - Launch Translated ROM (optional)
```

# Usage
## Overview
Running `./build.py` will do the following:
- Unpack the original ROM (if not already unpacked)
- Copy, convert and compress translated images into the unpacked ROM
- Repack the ROM (to a new file)
- Generate a patch file
- Launch the game in MelonDS

Run `./build.py -h` to see basic usage instructions.
```
usage: Ouendan2 Rom Builder [-h] [-u] [-c] [-p] [-d] [-l] [-r RECENT] [-f FILTER]

Handles unpacking, converting, compressing, packing and patch generation for the Ouendan 2 translation project.

options:
  -h, --help            show this help message and exit
  -u, --unpack          Force unpack of source rom
  -c, --convert         Convert and compress images
  -p, --pack            Pack output rom
  -d, --delta           Make xdelta patch
  -l, --launch          Launch output rom in MelonDS
  -r RECENT, --recent RECENT
                        Only convert images changed in the last n days
  -f FILTER, --filter FILTER
                        Only convert images with paths containing this filter string

Running without any cpdl flags enables all four.
```

## Examples
Convert files edited in the last 2 days:
```
./build.py -c -r 2
```

Convert files for a specific level:
```
./build.py -c -f "mv/sb03"
```

Convert recent files, repack and launch:
```
./build.py -cpl -r 1
```
