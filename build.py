#!/usr/bin/env python

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

import mapping

# import Levenshtein  # used to approximate unmapped paths

LANGUAGE = 'english'
PROJECT = 'Osu! Tatakae! Ouendan 2'

TOOLS = './tools'
UNPACKED = './rom_unpacked'
OUTPUT = f'{PROJECT} ({LANGUAGE}).nds'
PATCH = OUTPUT.replace('.nds', f'_{datetime.today().strftime("%y%m%d")}.xdelta')
IMAGES_SRC = './images_japanese'
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


# def closest_by_levenshtein(path: str, ext: str, number_to_letter:bool = False) -> str:
# 	name = os.path.basename(os.path.splitext(path)[0])
# 	folder = os.path.dirname(path)
#
# 	if number_to_letter:
# 		letter_number_map = str.maketrans('0123456789', 'abcdefghij')
# 		name = re.sub(r'bg(\d)_(\w)', r'bg_\2\1', name)
# 		name=name.translate(letter_number_map)
#
# 	dist = 1000
# 	result = '__NOT_FOUND__'
# 	for file in os.listdir(folder):
# 		if not file.endswith(ext):
# 			continue
#
# 		nclr_name = os.path.splitext(file)[0]
# 		tmp_dist = Levenshtein.distance(name, nclr_name)
#
# 		# print(name, nclr_name, tmp_dist)
#
# 		if tmp_dist <= dist:
# 			dist = tmp_dist
# 			result = file
#
# 	# print(f'Output:{os.path.basename(os.path.splitext(path)[0])} -> {nclr}, Dist: {dist}')
# 	return f'{folder}/{result}'


def map_paths_2d(path: str) -> tuple[str, str, str]:
	"""Get the matching NCLR and NCGR files for a given NSCR/NCER file.
	This is required as many NSCR/NCER files use NCLER/NCGR files
	with different names/paths."""
	token = '/2d/'
	root, item = path.replace('\\', '/').split(token)
	
	# Check for cached mapping
	if item in mapping.map_2d:
		items = (item, *mapping.map_2d[item])
		return tuple(f'{root}{token}{x}' for x in items)
	
	name, ext = os.path.splitext(path)
	nclr = f'{name}.NCLR_'
	ncgr = f'{name}.NCGR_'

	# Check for simple mapping
	# if not os.path.exists(ncgr):
	# 	print('Finding closest NCGR')
	# 	ncgr = closest_by_levenshtein(path, ext='.NCGR_')
	# 	if not os.path.exists(ncgr):
	# 		return ('', '', '')

	# Check for nearby mapping (e.g. bg0_s -> bg_s, bg1_m -> bg_m)
	if not os.path.exists(nclr):
		nclr = re.sub(r'bg\d\w?_(?:\d(s)|(\w)(?:\w*)?)', r'bg_\1\2', nclr)
		if not os.path.exists(nclr):
			# Get closest palette in folder
			# print('Finding closest NCLR')
			# nclr = closest_by_levenshtein(path, ext='.NCLR_', number_to_letter=True)

			if not os.path.exists(nclr):
				return ('', '', '')

	return (path, ncgr, nclr)
	

def map_paths_3d(path: str) -> tuple[str, str, int]:
	"""Get the tile, palette and tile width power for a given ntft tile filepath.
	This is required as as there is not means to determine width from the ntft file itself.
	Some tiles also use palettes with names not matching their own.
	"""
	token = '/3d/'
	root, item = path.replace('\\', '/').split(token)
	
	if item in mapping.map_3d:
		path = f'{root}{token}{item}'
		palette = f'{root}{token}{mapping.map_3d[item][0]}'
		tile_width_power = mapping.map_3d[item][1]
		items = (item, *mapping.map_3d[item])
		return path, palette, tile_width_power
	else:
		return ('', '', -1)


def image_to_files_and_cmd(path: str, mode: str) -> tuple[tuple[str, ...], str]:
	"""Takes an image and returns the associated files
	and command required to apply it to the unpacked rom."""
	path = path.replace('\\', '/')
	name = os.path.basename(os.path.splitext(path)[0])
	data_root = os.path.dirname(path).replace(IMAGES, DATA_DST)

	if mode == 'ntft':
		# The old way works in one direction only.
		# So since we have a dict of all ntft/ntfp/width
		# combinations for data extraction we may as well use it instead
		# Added benefit is the removal of he dependency on PIL
		# width = Image.open(path).size[0]
		# items = (f'{data_root}/{name}.ntft_',
		# 		f'{data_root}/{name}.ntfp_') 
		# args2 = [path, *items, str(width)]

		tile, palette, tile_width_power = map_paths_3d(f'{data_root}/{name}.ntft_')
		width =  pow(2, tile_width_power) * 8  # Tiles are 8x8 pixels
		args = [path, tile, palette, str(width)]

		print("Orig: ", args2)
		print("New : ", args)
		print(args2 == args)
		print()

	elif mode == 'nscr' or mode == 'ncer':
		items = map_paths_2d(f'{data_root}/{name}.{mode.upper()}_')
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


def extract_data(filter: str|None = None):
	with Pool(os.cpu_count() -1) as p:
		for root, dirs, files in os.walk(DATA_DST):
			src_location = root.replace(DATA_DST, DATA_SRC)
			print(f'Extracting from {root} to {src_location}')

			cmds = []
			for file in files:
				name, ext = os.path.splitext(file)
				filepath = os.path.join(root, file)

				if filter is not None and filter not in filepath:
					continue

				with open(filepath, 'rb') as file_data:
					header = file_data.read(4)
					if header == b'1OZL':
						cmds.append(f'{TOOLS}/quickbms.exe -o {TOOLS}/LZO1.bms "{filepath}" "{src_location}"')
					elif header[0] == 16:  # 0x10
						shutil.copy(filepath, src_location)
						cmds.append(f'{TOOLS}/lzss.exe -d "{os.path.join(src_location, file)}"')

			if cmds:
				os.makedirs(src_location, exist_ok=True)

			p.map(process_cmd, cmds)

	print(f'Extracting Data ... Done!')


def estimate_ntft_width(ntft_path: str) -> int:
	'''
	Determine the width of an uncompressed ntft file by checking the longest
	sequence of non-zero half-bytes and rounding up to the nearest power of 2.
	'''
	count = 0
	max_length = 0
	with open(ntft_path, 'rb') as ntft_file:
		data = ntft_file.read()
		for byte in data:
			for nibble in (byte & 0x0F, byte >> 4):
				if nibble == 0:
					if count > max_length:
						max_length = count
					count = 0
				else:
					count += 1
	
	max_length = (max_length) // 8 * 8
	max_length = 1 << max_length.bit_length()
	return max(max_length, 8)

def extract_images(filter: str|None = None):
	cmds = []
	for root, dirs, files in os.walk(DATA_SRC):
		image_root = root.replace(DATA_SRC, IMAGES_SRC).replace('\\', '/')
		for file in files:
			name, ext = os.path.splitext(file)
			filepath = os.path.join(root, file).replace('\\', '/')

			if filter is not None and filter not in filepath:
				continue

			if not ext in ['.ntft_', '.NSCR_', '.NCER_']:
				continue

			if ext == '.ntft_':
				_, palette, tile_width_power = map_paths_3d(filepath)

				if palette == '':
					print(f'No Mapping: {filepath}')
					continue

				if palette == '?' or not os.path.exists(palette):
					print(f'No Palette: {filepath}')
					continue

				os.makedirs(image_root, exist_ok=True)
				dst_name = f'/{name}.png'

				# Used for debugging tile widths
				# if tile_width_power == -1:
				# 	print('∨∨∨∨∨∨∨ Fix')
				# 	width = estimate_ntft_width(filepath)
				# 	tile_width_power = int(width/8).bit_length() - 1
				# else:
				# 	width =  pow(2, tile_width_power) * 8  # Tiles are 8x8 pixels

				width =  pow(2, tile_width_power) * 8  # Tiles are 8x8 pixels
				print(filepath, width, tile_width_power)

				cmds.append(f'{TOOLS}/yyt2_ntft.exe out "{image_root}{dst_name}" "{filepath}" "{palette}" {width}')

			else:
				mode = 'nscr' if ext == '.NSCR_' else 'ncer'
				_, tile, palette = map_paths_2d(filepath)
				
				if not tile or not palette:
					print(f'No Tile/Palette: {filepath}')
					continue

				print(filepath, tile, palette)

				dst_name = '/' + name

				if mode == 'ncer':
					os.makedirs(image_root + dst_name, exist_ok=True)
				else:
					os.makedirs(image_root, exist_ok=True)
					dst_name += '.bmp'

				cmds.append(f'{TOOLS}/yyt2_{mode}.exe out "{image_root}{dst_name}" "{filepath}" "{tile}" "{palette}"')

	#TODO: Run the batch of commands
	print(f'Extracting Images ...')
	with Pool(os.cpu_count() -1) as p:
		p.map(process_cmd, cmds)
	print(f'Extracting Images ... Done!')


def main():
	parser = argparse.ArgumentParser(
		prog='Ouendan2 Rom Builder',
		description='Handles unpacking, converting, compressing, packing and patch generation for the Ouendan 2 translation project.',
		epilog='Running without any flags is the equvalent of running -cpdl.')
	parser.add_argument('-u', '--unpack', action='store_true', help="Force unpack of source rom")
	parser.add_argument('-e', '--extract', action='store_true', help="Extract and decompress rom data")
	parser.add_argument('-i', '--images', action='store_true', help="Extract images from decompressed rom data")
	parser.add_argument('-c', '--convert', action='store_true', help="Convert and compress custom images")
	parser.add_argument('-p', '--pack', action='store_true', help="Pack output rom")
	parser.add_argument('-d', '--delta', action='store_true', help="Make xdelta patch")
	parser.add_argument('-l', '--launch', action='store_true', help="Launch output rom in MelonDS")
	parser.add_argument('-r', '--recent', type=float, default=0.0, help="Only convert images changed in the last n days")
	parser.add_argument('-f', '--filter', help="Only convert images with paths containing this filter string")
	args = parser.parse_args()

	all = args.unpack + args.extract + args.images + args.convert + args.pack + args.delta + args.launch == 0

	print('Finding source nds file')
	rom = find_rom()

	if not os.path.exists(UNPACKED) or args.unpack:
		print(f'Unpacking {os.path.basename(rom)}')
		subprocess.run(f'{TOOLS}/NitroPacker.exe unpack -r "{rom}" -o "{UNPACKED}" -p "{PROJECT}"')
	
	if not os.path.exists(DATA_SRC) or args.extract:
		print(f'Extracting data')
		extract_data(filter=args.filter)

	if not os.path.exists(IMAGES) or args.images:
		print(f'Extracting images')
		extract_images(filter=args.filter)

	if args.convert or all:
		print('Converting images')
		convert_images(recent=args.recent, filter=args.filter)

	if args.pack or all:
		print(f'Packing Rom: {OUTPUT}')
		subprocess.run(f'{TOOLS}/NitroPacker.exe pack -p "{UNPACKED}/{PROJECT}.json" -r "{OUTPUT}"')

	if args.delta or all:
		print(f'Creating Patch: {PATCH}')
		subprocess.run(f'{TOOLS}/xdelta3.exe -e -f -s "{rom}" "{OUTPUT}" "{PATCH}"')
	
	if args.launch or all:
		print(f'Launching: {OUTPUT}')
		subprocess.run(f'{TOOLS}/melonDS.exe "{OUTPUT}"')
	
if __name__ == "__main__":
	main()

