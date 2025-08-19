#!/usr/bin/env python3

from ntpath import splitext
import os
import sys
import shutil
import re
import glob
import subprocess

from PIL import Image

import mapping

LANGUAGE = 'english'
PROJECT = 'Osu! Tatakae! Ouendan 2'

TOOLS = './tools'
UNPACKED = './rom_unpacked'
OUTPUT = f'{PROJECT} ({LANGUAGE}).nds'
IMAGES = f'./images_{LANGUAGE}'
DATA_SRC = './data'
DATA_DST = f'{UNPACKED}/data/data'


def find_rom() -> str:
	"""Finds the first nds rom in the running directory
	that doesn't match the output name."""
	files = glob.glob("./*.nds")
	for file in files:
		if file != OUTPUT:
			return file
	raise Exception(f'No nds file found. Ensure you have the {PROJECT} rom in the same directory as this script.')


def replace_with_decrypted(path: str) -> str:
	"""Replace encrypted rom image file with predecrypted version."""
	if not os.path.exists(path):
		print(f'Does not exist: {path}')
	decrypted = path.replace(DATA_DST, DATA_SRC)
	shutil.copyfile(decrypted, path)
	return path


def map_paths(path: str) -> tuple[str, str, str]:
	"""Get the matching NCLR and NCGR files for a given NSCR/NCER file.
	This is required as many NSCR/NCER files use NCLER/NCGR files
	with different names/paths."""
	token = '/2d/'
	root, item = path.replace('\\', '/').split('/2d/')
	
	# Check for nonstandard mapping
	if item in mapping.map_2d:
		items = (item, *mapping.map_2d[item])
		return tuple(f'{root}{token}{x}' for x in items)  # type: ignore
	
	name, ext = os.path.splitext(path)
	nclr = f'{name}.NCLR_'
	ncgr = f'{name}.NCGR_'

	# Check for simple mapping
	if not os.path.exists(ncgr):
		return ('', '', '')

	# Check for nearby mapping (e.g. bg0_s -> bg_s, bg1_m -> bg_m)
	if not os.path.exists(nclr):
		nclr = re.sub(r'bg\d\w?_(?:\d(s)|(\w)(?:\w*)?)', r'bg_\1\2', nclr)
		if not os.path.exists(nclr):
			return ('', '', '')

	return (path, ncgr, nclr)
	

def convert_image(path: str, mode: str) -> None:
	"""Takes an image and applies it to the unpacked rom files."""
	path = path.replace('\\', '/')
	name = os.path.basename(splitext(path)[0])
	data_root = os.path.dirname(path).replace(IMAGES, DATA_DST)

	if mode not in ['ntft', 'nscr', 'ncer']:
		raise Exception(f'Invalid mode {mode}. Must be ntft, nscr or ncer')

	items = []
	args = []
	if mode == 'ntft':
		width = Image.open(path).size[0]

		items = [f'{data_root}/{name}.ntft_',
				f'{data_root}/{name}.ntfp_'] 

		args = [path, *items, str(width)]
		# ntft = replace_with_decrypted(f'{data_root}/{name}.ntft_')
		# ntfp = replace_with_decrypted(f'{data_root}/{name}.ntfp_')
		# subprocess.run(f'{TOOLS}/yyt2_{mode}.exe in {" ".join(args)}')
		# subprocess.run(f'{TOOLS}/lzss.exe -evn {" ".join(items)}')
	elif mode in ['nscr', 'ncer']:
		items = map_paths(f'{data_root}/{name}.{mode.upper()}_')
		if '' in items:
			print(f'No Mapping For: {path}')
			return
		
		# for item in items:
		# 	replace_with_decrypted(item)

		args = [path, *items]
		if mode == 'ncer':
			ncgr_ref = items[1].replace(DATA_DST, DATA_SRC)
			args.insert(3, ncgr_ref)

	for item in items:
		replace_with_decrypted(item)

	subprocess.run(f'{TOOLS}/yyt2_{mode}.exe in {" ".join(args)}')
	subprocess.run(f'{TOOLS}/lzss.exe -evn {" ".join(items)}')


def convert_images() -> None:
	"""Finds all translated images and passed them to the converter."""
	for root, dirs, files in os.walk(IMAGES):
		data_root = root.replace(IMAGES, DATA_DST)
		for file in files:
			name, ext = os.path.splitext(file)
			if not ext in ['.png', '.bmp']:
				continue

			image = os.path.join(root, file)

			if os.path.exists(f'{data_root}/{name}.ntft_'):
				result = convert_image(image, 'ntft')
			elif os.path.exists(f'{data_root}/{name}.NSCR_'):
				result = convert_image(image, 'nscr')

		for dir in dirs:
			image = os.path.join(root, dir)
			if os.path.exists(f'{data_root}/{dir}.NCER_'):
				result = convert_image(image, 'ncer')


def main():
	if not os.path.exists(UNPACKED):
		print('Finding nds file')
		rom = find_rom()
		print(f'Unpacking {os.path.basename(rom)}')
		subprocess.run(f'{TOOLS}/NitroPacker.exe unpack -r "{rom}" -o "{UNPACKED}" -p "{PROJECT}"')
	
	print('Converting images')
	convert_images()

	print(f'Packing Rom: {OUTPUT}')
	subprocess.run(f'{TOOLS}/NitroPacker.exe pack -p "{UNPACKED}/{PROJECT}.json" -r "{OUTPUT}"')

	
if __name__ == "__main__":
	main()

