#!/usr/bin/env python3

import os
import sys
import shutil
import re
import glob
from collections import defaultdict
import subprocess
from multiprocessing import Pool
import argparse
from datetime import datetime, timedelta

from PIL import Image

import mapping

LANGUAGE = 'english'
PROJECT = 'Osu! Tatakae! Ouendan 2'

TOOLS = './tools'
UNPACKED = './rom_unpacked'
OUTPUT = f'{PROJECT} ({LANGUAGE}).nds'
PATCH = OUTPUT.replace('.nds', f'_{datetime.today().strftime("%y%m%d")}.xdelta')
IMAGES = f'./images_{LANGUAGE}'
DATA_SRC = './data'
DATA_DST = f'{UNPACKED}/data/data'


def find_rom() -> str:
	"""Finds the first nds rom in the running directory
	that doesn't match the output name."""
	files = glob.glob("./*.nds")
	for file in files:
		if os.path.basename(file) != OUTPUT:
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


def is_recent(path: str, days:float=0.0) -> bool:
	modified_timestamp = os.path.getmtime(path)
	modified_date = datetime.fromtimestamp(modified_timestamp)
	current_date = datetime.now()
	return current_date - modified_date < timedelta(days=days)


def convert_images(recent:float=0.0, filter=None) -> None:
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

			image = os.path.join(root, file).replace('\\', '/')
			if recent and not is_recent(image, days=recent):
				continue

			if filter is not None and filter not in image:
				continue

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
			image = os.path.join(root, dir).replace('\\', '/')
			if recent and not is_recent(image, days=recent):
				continue

			if filter is not None and filter not in image:
				continue

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
	parser = argparse.ArgumentParser(
		prog='Ouendan2 Rom Builder',
		description='Handles unpacking, converting, compressing, packing and patch generation for the Ouendan 2 translation project.',
		epilog='Running without any cpdl flags enables all four.')
	parser.add_argument('-u', '--unpack', action='store_true', help="Force unpack of source rom")
	parser.add_argument('-c', '--convert', action='store_true', help="Convert and compress images")
	parser.add_argument('-p', '--pack', action='store_true', help="Pack output rom")
	parser.add_argument('-d', '--delta', action='store_true', help="Make xdelta patch")
	parser.add_argument('-l', '--launch', action='store_true', help="Launch output rom in MelonDS")
	parser.add_argument('-r', '--recent', type=float, default=0.0, help="Only convert images changed in the last n days")
	parser.add_argument('-f', '--filter', help="Only convert images with paths containing this filter string")
	args = parser.parse_args()

	all = args.convert + args.pack + args.delta + args.launch == 0

	print('Finding source nds file')
	rom = find_rom()

	if not os.path.exists(UNPACKED) or args.unpack:
		print(f'Unpacking {os.path.basename(rom)}')
		subprocess.run(f'{TOOLS}/NitroPacker.exe unpack -r "{rom}" -o "{UNPACKED}" -p "{PROJECT}"')
	
	if args.convert or all:
		print('Converting images')
		convert_images(recent=args.recent, filter=args.filter)

	if args.pack or all:
		print(f'Packing Rom: {OUTPUT}')
		subprocess.run(f'{TOOLS}/NitroPacker.exe pack -p "{UNPACKED}/{PROJECT}.json" -r "{OUTPUT}"')

	if args.delta or all:
		print(f'Creating Patch: {PATCH}')
		subprocess.run(f'{TOOLS}/xdelta3.exe -e -f -s "{rom}" "{OUTPUT}" "{PATCH}"')
	
	if args.launch:
		print(f'Launching: {OUTPUT}')
		subprocess.run(f'{TOOLS}/melonDS.exe "{OUTPUT}"')
	
if __name__ == "__main__":
	main()

