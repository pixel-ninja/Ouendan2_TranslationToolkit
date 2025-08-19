#!/usr/bin/env python3

import os
import sys
import shutil
import re
import glob
from collections import defaultdict
import subprocess
from multiprocessing import Pool

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
		return tuple(f'{root}{token}{x}' for x in items)
	
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
	

def image_to_files_and_cmd(path: str, mode: str) -> tuple[tuple[str, ...], str]:
	"""Takes an image and returns the associated files
	and command required to apply it to the unpacked rom."""
	path = path.replace('\\', '/')
	name = os.path.basename(os.path.splitext(path)[0])
	data_root = os.path.dirname(path).replace(IMAGES, DATA_DST)

	if mode == 'ntft':
		width = Image.open(path).size[0]

		items = (f'{data_root}/{name}.ntft_',
				f'{data_root}/{name}.ntfp_') 

		args = [path, *items, str(width)]

	elif mode == 'nscr' or mode == 'ncer':
		items = map_paths(f'{data_root}/{name}.{mode.upper()}_')
		if '' in items:
			print(f'No Mapping For: {path}')
			return ((), '')

		args = [path, *items]
		if mode == 'ncer':
			ncgr_ref = items[1].replace(DATA_DST, DATA_SRC)
			args.insert(3, ncgr_ref)
	else:
		raise Exception(f'Invalid mode {mode}. Must be ntft, nscr or ncer')

	cmd = f'{TOOLS}/yyt2_{mode}.exe in {" ".join(args)}'
	return items, cmd


def process_cmd(cmd: str) -> None:
	result = subprocess.run(cmd, capture_output=True, text=True)
	print(''.join([s for s in result.stdout.splitlines()]))
	if result.returncode != 0:
		print('Error:', result.stderr)


def process_tasks(tasks: list) -> None:
	for task in tasks:
		items, cmd = task
		for item in items:
			replace_with_decrypted(item)
		process_cmd(cmd)


def convert_images() -> None:
	"""Finds all translated images and passed them to the converter."""
	tasks: dict[str, list] = defaultdict(list)
	files_to_compress: set[str] = set()
	'''tasks is a dict so that commands using the same NCLR file
	are grouped together to avoid race conditions'''

	# Get files and commands
	for root, dirs, files in os.walk(IMAGES):
		data_root = root.replace(IMAGES, DATA_DST)
		for file in files:
			name, ext = os.path.splitext(file)
			if not ext in ['.png', '.bmp']:
				continue

			image = os.path.join(root, file)

			if os.path.exists(f'{data_root}/{name}.ntft_'):
				items, cmd = image_to_files_and_cmd(image, 'ntft')
			elif os.path.exists(f'{data_root}/{name}.NSCR_'):
				items, cmd = image_to_files_and_cmd(image, 'nscr')
			else:
				continue

			tasks[items[-1]].append([items, cmd])
			files_to_compress.update(items)
			print(f'Finding Images: {root}/{name}', end='\r')

		for dir in dirs:
			image = os.path.join(root, dir)
			if os.path.exists(f'{data_root}/{dir}.NCER_'):
				items, cmd = image_to_files_and_cmd(image, 'ncer')
			else:
				continue

			tasks[items[-1]].append([items, cmd])
			files_to_compress.update(items)
			print(f'Finding Images: {root}/{dir}', end='\r')

	print('')
	print('Finding Images: Done!')
	print(f'Processing Images ...')
	with Pool(os.cpu_count() -1) as p:
		p.map(process_tasks, tasks.values())
	print(f'Processing Images ... Done!')
	
	print(f'Compressing Files ...')
	compression_cmds = [f'{TOOLS}/lzss.exe -evn {item}' for item in files_to_compress]
	with Pool(os.cpu_count() -1) as p:
		p.map(process_cmd, compression_cmds)
	print(f'Compressing Files ... Done!')


def main():
	if not os.path.exists(UNPACKED):
		print('Finding nds file')
		rom = find_rom()
		print(f'Unpacking {os.path.basename(rom)}')
		subprocess.run(f'{TOOLS}/NitroPacker.exe unpack -r "{rom}" -o "{UNPACKED}" -p "{PROJECT}"')
	
	print('Converting images')
	convert_images()

	if len(sys.argv) > 1 and sys.argv[1] == 'nopack':
		return

	print(f'Packing Rom: {OUTPUT}')
	subprocess.run(f'{TOOLS}/NitroPacker.exe pack -p "{UNPACKED}/{PROJECT}.json" -r "{OUTPUT}"')

	
if __name__ == "__main__":
	main()

