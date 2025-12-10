#!/usr/bin/env python3
"""
Fast Memory Friendly Username Generator v1.0
- Streaming input (Low RAM)
- Threaded Generation
- Buffered Output (Fast Disk I/O)
- Progress Bar
"""

version = "1.0"

import argparse
import sys
import re
import itertools
from pathlib import Path
from typing import Iterator, List, TextIO, Optional, Union, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from tqdm import tqdm
except ImportError:
    print("[!] tqdm not installed, no progress bar :(")
    class tqdm:
        def __init__(self, iterable=None, total=None, unit='it', disable=False):
            self.iterable = iterable
            self.total = total
            self.n = 0
        def __iter__(self): return iter(self.iterable)
        def update(self, n=1): self.n += n
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_value, traceback): pass

class UsernameGenerator:
    """Generates username variations with custom format support."""
    
    DEFAULT_FORMATS = [
        'first', 'last', 'firstlast', 'lastfirst',
        'first.last', 'last.first', 'first-last', 'last-first',
        'first_last', 'last_first', 'first[1].last', 'last[1].first',
        'firstlast[1]', 'first[1]last', 'last[1]first', 'lastfirst[1]', 'first[1]last[1]', 'last[1]first[1]',
    ]
    
    def __init__(self, case_sensitive: bool = True, formats: Optional[List[str]] = None):
        self.case_sensitive = case_sensitive
        self.formats = formats or self.DEFAULT_FORMATS
        
        # --- Pre-compiled Regex ---
        self.re_numeric = re.compile(r'(first|middle|last)(\[(\d+)\])?(\d+)$')
        self.re_bracket = re.compile(r'(first|middle|last)\[(\d+)\]')
        self.re_keywords = re.compile(r'(first|middle|last)')
        self.re_separators = re.compile(r'([._-])')

    def parse_name(self, name: str) -> dict:
        parts = name.strip().split()
        return {
            'first': parts[0] if len(parts) > 0 else '',
            'middle': parts[1] if len(parts) > 2 else '',
            'last': parts[-1] if len(parts) > 1 else '',
        }
    
    def _process_format(self, format_str: str, name_parts: dict) -> Optional[str]:
        result = format_str
        
        # Handling lengths [n]
        def replace_with_length(match):
            (part, length) = match.group(1, 2)
            value = name_parts.get(part, '')
            return value[:int(length)] if value else ''
        
        result = self.re_bracket.sub(replace_with_length, result)
        
        # Keywords substitutions
        replacements = {
            'first': name_parts.get('first', ''),
            'middle': name_parts.get('middle', ''),
            'last': name_parts.get('last', ''),
        }

        # We treat each keyword part of the format indepently 
        parts_arr = self.re_keywords.split(result)
        final_parts = []
        for part in parts_arr:
            if part in replacements:
                final_parts.append(replacements[part])
            else:
                final_parts.append(part)
        result = "".join(final_parts)

        # Case handling
        if result and not self.case_sensitive:
            result = result.lower()
        elif result:
            if format_str and format_str[0].isupper() and len(format_str) > 1:
                if format_str.isupper():
                    result = result.upper()
                else:
                    split_parts = self.re_separators.split(result)
                    result = ''.join(p.capitalize() if p and p[0].isalpha() else p for p in split_parts)
        
        return result if result and not result.isspace() else None
    
    def apply_format(self, format_str: str, name_parts: dict) -> Iterator[str]:
        # Handling numerical suffixes (first5 -> anna0...anna5)
        match = self.re_numeric.match(format_str)
        if match:
            (base_format, num) = match.group(1, 4) # (\d+)
            base_username = self._process_format(base_format, name_parts)
            if base_username:
                for i in range(int(num) + 1):
                    yield f"{base_username}{i}"
            return
        
        username = self._process_format(format_str, name_parts)
        if username:
            yield username
    
    def generate_from_name(self, name: str) -> List[str]:
        """Retourne une LISTE de résultats au lieu de yield, pour le buffering."""
        results = []
        name = name.strip()
        if not name:
            return results
        
        name_parts = self.parse_name(name)
        if not name_parts['first']:
            return results
        
        for format_pattern in self.formats:
            for res in self.apply_format(format_pattern, name_parts):
                results.append(res)
        return results

    def process_single_task(self, args) -> List[str]:
        """Wrapper pour l'executor."""
        name, fn, ln = args
        full_name = f"{fn} {ln}" if fn and ln else name
        return self.generate_from_name(full_name)


# --- FONCTIONS UTILITAIRES ---

def batch_write(file_handle: TextIO, buffer: List[str]):
    """Écrit le buffer d'un coup sur le disque."""
    if not buffer or not file_handle:
        return
    # join is faster than successive write syscalls
    file_handle.write('\n'.join(buffer) + '\n')

def run_processing(generator: UsernameGenerator, 
                  name_iterator: Iterator, 
                  total_count: int, 
                  output_file: Optional[TextIO], 
                  workers: int = 4):
    """
    Gestionnaire principal : Parallélisme + Buffer + Backpressure
    """
    
    # Configuration
    WRITE_BUFFER_SIZE = 1000  # Number of lines before writing to IO
    CHUNK_SIZE = workers * 200 # Number of names loaded in RAM concurrently
    
    output_buffer = []
    total_generated = 0
    
    # Wrapper pour gérer les tuples (fn, ln) ou str (name)
    def prepare_args(item):
        if isinstance(item, tuple):
            return (None, item[0], item[1]) # (None, fn, ln)
        return (item, None, None)           # (name, None, None)

    # L'Executor
    with ThreadPoolExecutor(max_workers=workers) as executor:
        
        # Barre de progression
        # On désactive la barre si on écrit sur stdout pour ne pas polluer la sortie
        show_bar = output_file is not None and output_file != sys.stdout
        
        with tqdm(total=total_count, unit=" name", disable=not show_bar) as pbar:
            
            iterator = iter(name_iterator)
            
            while True:
                # 1. Load a small slice
                chunk = list(itertools.islice(iterator, CHUNK_SIZE))
                if not chunk:
                    break
                
                # 2. Submit slice
                futures = {
                    executor.submit(generator.process_single_task, prepare_args(item)): item 
                    for item in chunk
                }
                
                # 3. Aggregate resulting usernames
                for future in as_completed(futures):
                    try:
                        usernames = future.result()
                        total_generated += len(usernames)
                        
                        # --- Buffered disk writing ---
                        if output_file:
                            output_buffer.extend(usernames)
                            if len(output_buffer) >= WRITE_BUFFER_SIZE:
                                batch_write(output_file, output_buffer)
                                output_buffer = [] # Reset buffer
                        else:
                            # Print directly to stdout
                            for u in usernames:
                                print(u)
                                
                    except Exception as e:
                        original_item = futures[future]
                        sys.stderr.write(f"[!] Error processing {original_item}: {e}\n")
                    
                    finally:
                        pbar.update(1)
            
            # 4. Write rest of the buffer
            if output_file and output_buffer:
                batch_write(output_file, output_buffer)

    return total_generated

def load_names(filepath: Path) -> List[str]:
    if not filepath.exists():
        raise FileNotFoundError(f"{filepath} not found.")
    with filepath.open('r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def load_formats(filepath: Path) -> List[str]:
    if not filepath.exists():
        raise FileNotFoundError(f"{filepath} not found.")
    with filepath.open('r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# --- MAIN ---

def main():
    parser = argparse.ArgumentParser(
        description="Fast Memory Friendly Username Generator v" + version,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('-i', '--input', type=Path, default=Path('users.txt'), help='Input file with names')
    parser.add_argument('-o', '--output', type=Path, help='Output file (Default: stdout)')
    parser.add_argument('-f', '--format', action='append', dest='format_list', help='Add format pattern')
    parser.add_argument('--formats', type=Path, help='File with format patterns')
    parser.add_argument('-t', '--threads', type=int, default=4, help='Number of threads')
    parser.add_argument('-fn', '--first-names', type=Path, help='First names file')
    parser.add_argument('-ln', '--last-names', type=Path, help='Last names file')
    parser.add_argument('-cs', '--case-sensitive', action='store_true', help='Preserve case')
    parser.add_argument('-lf', '--list-formats', action='store_true', help='Show default formats')

    args = parser.parse_args()

    if args.list_formats:
        print("\n".join(UsernameGenerator.DEFAULT_FORMATS))
        return 0

    def log(msg):
        if args.output or sys.stderr.isatty():
            sys.stderr.write(msg + "\n")
    ascii_logo = f"""
$$$$$$$$\\ $$\\      $$\\ $$$$$$$$\\ $$\\   $$\\  $$$$$$\\  
$$  _____|$$$\\    $$$ |$$  _____|$$ |  $$ |$$  __$$\\ 
$$ |      $$$$\\  $$$$ |$$ |      $$ |  $$ |$$ /  \\__|
$$$$$\\    $$\\$$\\$$ $$ |$$$$$\\    $$ |  $$ |$$ |$$$$\\ 
$$  __|   $$ \\$$$  $$ |$$  __|   $$ |  $$ |$$ |\\_$$ |
$$ |      $$ |\\$  /$$ |$$ |      $$ |  $$ |$$ |  $$ |
$$ |      $$ | \\_/ $$ |$$ |      \\$$$$$$  |\\$$$$$$  |
\\__|      \\__|     \\__|\\__|       \\______/  \\______/

    v{version}
    Made in France ♥               by Udodelige
    """
    log(ascii_logo)

    try:
        # Preparing data (Lazy iterator)
        name_iterator = []
        total_items = 0
        
        # Combination mode (First x Last)
        if args.first_names and args.last_names:
            log(f"[*] Loading lists...")
            fns = load_names(args.first_names)
            lns = load_names(args.last_names)
            # itertools.product does not load everything in RAM
            name_iterator = itertools.product(fns, lns)
            total_items = len(fns) * len(lns)
            log(f"[*] Mode: Combination ({len(fns)} fnames x {len(lns)} lnames = {total_items} names)")
        
        # Simple mode ("john doe" format)
        else:
            log(f"[*] Loading input: {args.input}")
            names = load_names(args.input)
            name_iterator = names
            total_items = len(names)
            log(f"[*] Mode: Single List ({total_items} items)")

        # Formats
        formats = None
        if args.formats:
            formats = load_formats(args.formats)
        elif args.format_list:
            formats = args.format_list
        
        # Output
        out_handle = None
        if args.output:
            out_handle = args.output.open('w', encoding='utf-8')
            log(f"[*] Output: {args.output}")
        else:
            log("[*] Output: stdout")

        # Initialisation
        generator = UsernameGenerator(
            case_sensitive=args.case_sensitive,
            formats=formats
        )

        log(f"[*] Using {len(generator.formats)} formats")
        
        log(f"[*] Expecting {total_items * len(generator.formats)} total output usernames")
        
        log(f"[*] Threads: {args.threads}")
        log("[*] Generating...")

        # Execution
        total = run_processing(generator, name_iterator, total_items, out_handle, args.threads)
        
        log(f"\n[✓] Done! Generated {total} usernames.")

    except KeyboardInterrupt:
        log("\n[!] Interrupted.")
    except Exception as e:
        log(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if out_handle:
            out_handle.close()

if __name__ == "__main__":
    main()
