#!/usr/bin/env python3
"""
Fast Memory Friendly Username Generator (Optimized)
- Multiprocessing (Bypasses GIL for 100% CPU usage)
- No-Regex Template Engine (Fast String Concatenation)
- Streaming input (Low RAM)
- Buffered Output (Fast Disk I/O)
"""

version = "1.2.1"

import argparse
import sys
import re
import itertools
import os
from pathlib import Path
from typing import Iterator, List, TextIO, Optional, Tuple, Any
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

# Try to import tqdm for progress bar, else fallback to dummy
try:
    from tqdm import tqdm
except ImportError:
    print("[!] tqdm not installed, no progress bar :(")
    class tqdm:
        def __init__(self, iterable=None, total=None, unit='it', disable=False):
            self.iterable = iterable
        def __iter__(self): return iter(self.iterable)
        def update(self, n=1): pass
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_value, traceback): pass

# --- TEMPLATE ENGINE (Optimization Core) ---

class TemplateInstruction:
    """Stores a single instruction for building a username part."""
    __slots__ = ('type', 'value', 'length', 'casing') # Optimization for memory
    def __init__(self, type_: str, value: str, length: Optional[int] = None, casing: str = 'none'):
        self.type = type_   # 'const' (static text) or 'var' (first/last/middle)
        self.value = value  # The text or the key name
        self.length = length # Truncation length (if any)
        self.casing = casing # Case handling fo this instruction

class CompiledFormat:
    """Holds the instructions for a specific format string."""
    def __init__(self, instructions: List[TemplateInstruction], 
                 is_numeric: bool, max_num: int, 
                 casing: str, original_fmt: str):
        self.instructions = instructions
        self.is_numeric = is_numeric # True if format ends with iterator (e.g. first5)
        self.max_num = max_num       # The max number for iterator
        self.original_fmt = original_fmt

    @classmethod
    def compile_format(CompiledFormat, format_str: str):
        """
        Parses a format string ONCE into a list of optimized instructions.
        Replaces runtime Regex with static list iteration.
        """
        
        # 1. Detect Numeric Suffix (e.g., "first.last5")
        # Logic: Ends with digits, but those digits are NOT part of a bracket like [1]
        is_numeric = False
        max_num = 0
        clean_fmt = format_str

        # Regex to find ending digits that are NOT a bracket index
        # We look for digits at the end ($) preceded by something that isn't a closing bracket
        re_numeric_suffix = re.compile(r'^(.*?)(\d+)$')
        
        # Check if it looks like a numeric suffix format
        if not format_str.endswith(']'):
            match = re_numeric_suffix.match(format_str)
            if match:
                clean_fmt = match.group(1)
                max_num = int(match.group(2))
                is_numeric = True

        # 2. Parse Tokens (first, middle, last, [n])
        # This regex identifies keywords and optional length constraints
        token_pattern = re.compile(r'(first|middle|last)(?:\[(\d+)\])?', re.IGNORECASE)
        
        instructions = []
        last_pos = 0
        
        for match in token_pattern.finditer(clean_fmt):
            # Text preceding the token (separators like ., -, _)
            if match.start() > last_pos:
                static_text = clean_fmt[last_pos:match.start()]
                instructions.append(TemplateInstruction('const', static_text))
            
            # The Variable (first/middle/last)
            key = match.group(1)
            length = int(match.group(2)) if match.group(2) else None

            # Detect Casing Strategy based on the token string
            casing = 'none'
            if key.isupper():
                casing = 'upper'
            elif key and key[0].isupper():
                casing = 'capitalize'
            instructions.append(TemplateInstruction('var', key.lower(), length, casing))
            
            last_pos = match.end()
        
        # Remaining text after the last token
        if last_pos < len(clean_fmt):
            instructions.append(TemplateInstruction('const', clean_fmt[last_pos:]))

        return CompiledFormat(instructions, is_numeric, max_num, casing, format_str)

class Utils:
    # --- UTILS ---
    @staticmethod
    def batch_write(file_handle: TextIO, buffer: List[str]):
        """Writes the buffer to disk in one go."""
        if not buffer or not file_handle:
            return
        file_handle.write('\n'.join(buffer) + '\n')

    @staticmethod
    def chunked_iterable(iterable, size):
        """Helper to slice an iterator into chunks."""
        it = iter(iterable)
        while True:
            chunk = tuple(itertools.islice(it, size))
            if not chunk:
                break
            yield chunk

    @staticmethod
    def load_names(filepath: Path) -> List[str]:
        """Loads names into memory (List) to allow easy slicing."""
        if filepath.as_posix() == "-":
            return [line.strip() for line in sys.stdin if line.strip()]
        if not filepath.exists():
            raise FileNotFoundError(f"{filepath} not found.")
        with filepath.open('r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]

    @staticmethod
    def load_formats(filepath: Path) -> List[str]:
        if not filepath.exists():
            raise FileNotFoundError(f"{filepath} not found.")
        with filepath.open('r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]



class UsernameGenerator:
    # Default Formats
    DEFAULT_FORMATS = [
        'first', 'last', 'firstlast', 'lastfirst',
        'first.last', 'last.first', 'first-last', 'last-first',
        'first_last', 'last_first', 'first[1].last', 'last[1].first',
        'firstlast[1]', 'first[1]last', 'last[1]first', 'lastfirst[1]', 
        'first[1]last[1]', 'last[1]first[1]',
    ]

    def __init__(self, name_source, total_items, raw_formats, threads, case_sensitive, logger):
        self.name_source = name_source
        self.total_items = total_items
        # self.out_handle = out_handle
        self.threads = threads
        self.case_sensitive = case_sensitive
        self.logger = logger
        self.total_generated = 0
        self.bar_format = '[{elapsed} -> {remaining}] {n_fmt}/{total_fmt} | {desc}: {percentage:3.0f}% | {bar} {rate_fmt}{postfix}'

        # Compile Formats
        self.logger.log("[*] Compiling formats...")
        self.compiled_formats = [CompiledFormat.compile_format(fmt) for fmt in (raw_formats if raw_formats else self.DEFAULT_FORMATS)]
        self.logger.log(f"[*] Using {len(self.compiled_formats)} formats")

        # Numeric suffix formats will ouput more than 1 username per format
        total_formats = sum([cf.max_num + 1 for cf in self.compiled_formats])
        # Calculate expected total for progress bar
        self.expected_total = self.total_items * total_formats
        self.logger.log(f"[*] Expecting an output of {self.total_items * total_formats} usernames")

        # Execution Config
        # We need bigger chunks for multiprocessing to offset the pickling cost
        # If we have 1M names and 4 cores -> 250k names per core theoretically
        # But we stream chunks. 5000 is a good balance for memory vs speed.
        self.BATCH_SIZE = 4000
        self.WRITE_BUFFER_SIZE = 20000

        # We define a maximum number on pending workers (ex: 2x number of threads)
        # Prevents loading the whole file in memory using the lazy iterator
        self.MAX_PENDING_FUTURES = self.threads * 2

    def generate(self, out_handle: TextIO):

        # Note: Numeric suffixes might increase this, but it's an estimate.

        self.logger.log(f"[*] Processes: {self.threads}")
        self.logger.log("[*] Generating...")

        total_generated = 0
        output_buffer = []

        # 2. Parallel Execution (WITH BACKPRESSURE)
        with ProcessPoolExecutor(max_workers=self.threads) as executor:
            
            show_bar = (out_handle is not sys.stdout)
            
            pending_futures = set()
            
            # Fonction helper pour traiter les résultats (évite la duplication de code)
            def process_done_futures(done_set):
                for future in done_set:
                    try:
                        batch_results = future.result()
                        count = len(batch_results)
                        self.total_generated += count
                        pbar.update(count)
                        
                        if out_handle:
                            output_buffer.extend(batch_results)
                            if len(output_buffer) >= self.WRITE_BUFFER_SIZE:
                                Utils.batch_write(out_handle, output_buffer)
                                output_buffer.clear() # Important: clear in place
                        else:
                            for res in batch_results:
                                print(res)
                    except Exception as e:
                        sys.stderr.write(f"[!] Worker Error: {e}\n")

            with tqdm(total=self.expected_total, unit=" username", disable=not show_bar, bar_format=self.bar_format, unit_scale=True) as pbar:
                
                # Futures submit loop
                for chunk in Utils.chunked_iterable(self.name_source, self.BATCH_SIZE):
                    
                    # 1. If we have too much futures ongoing, wait for one to finish
                    if len(pending_futures) >= self.MAX_PENDING_FUTURES:
                        # wait() blocks until at least ONE future completes
                        done, pending_futures = wait(pending_futures, return_when=FIRST_COMPLETED)
                        process_done_futures(done)
                    
                    # 2. Submit a new futute
                    fut = executor.submit(self.worker_process_batch, chunk, self.compiled_formats, self.case_sensitive)
                    pending_futures.add(fut)

                # 3. Wait for all pending futures at the end
                while pending_futures:
                    done, pending_futures = wait(pending_futures, return_when=FIRST_COMPLETED)
                    process_done_futures(done)
            
            # Flush final buffer
            if out_handle and output_buffer:
                Utils.batch_write(out_handle, output_buffer)


    # --- Worker Function (Executed by a Thread) ---

    def worker_process_batch(self, names_batch: List[Any], 
                             compiled_formats: List[CompiledFormat], 
                             global_case_sensitive: bool) -> List[str]:
        """
        Executed by independent processes.
        Receives a batch of raw name data and generates usernames based on compiled formats.
        """
        results = []
        
        # Pre-allocate reuseable dictionary to avoid creation overhead
        parts = {'first': '', 'middle': '', 'last': ''}
        
        for item in names_batch:
            # 1. Parse Name
            if isinstance(item, tuple): # Combination mode (fn, ln)
                fn, ln = item
                parts['first'] = fn
                parts['middle'] = ''
                parts['last'] = ln
            else: # String mode "John Doe"
                raw_parts = item.strip().split()
                if not raw_parts: continue
                parts['first'] = raw_parts[0]
                parts['middle'] = raw_parts[1] if len(raw_parts) > 2 else ''
                parts['last'] = raw_parts[-1] if len(raw_parts) > 1 else ''

            if not parts['first']: continue

            # 2. Apply Formats
            for fmt in compiled_formats:
                
                # Build the string (Fast Loop)
                # Using a list comprehension or loop with join is faster than +=
                segments = []
                valid_gen = True
                
                for instr in fmt.instructions:
                    if instr.type == 'const':
                        segments.append(instr.value)
                    else:
                        # It's a variable (first/last)
                        val = parts[instr.value]
                        if val:
                            if global_case_sensitive:
                                if instr.casing == 'upper':
                                    val = val.upper()
                                elif instr.casing == 'capitalize':
                                    val = val.capitalize()
                            if instr.length:
                                segments.append(val[:instr.length])
                            else:
                                segments.append(val)
                        else:
                            # If a required part is missing (e.g. middle name), we might skip
                            # But standard behavior is often just empty string. 
                            # We append empty string.
                            segments.append('')

                base_result = "".join(segments)
                
                # If result is empty or just whitespace, skip
                if not base_result or not base_result.strip():
                    continue

                # 4. Handle Numeric Suffixes
                if fmt.is_numeric:
                    for i in range(fmt.max_num + 1):
                        results.append(f"{base_result}{i}")
                else:
                    results.append(base_result)
                    
        return results

class Logger:
    def __init__(self, output, quiet):
        self.output = output
        self.quiet = quiet

    # Logging helper
    def log(self, msg):
        if not self.quiet and (self.output or sys.stderr.isatty()):
            sys.stderr.write(msg + "\n")

# --- MAIN CONTROLLER ---

def main():
    parser = argparse.ArgumentParser(
        description="Fast Memory Friendly Username Generator v" + version,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Reusing exact same arguments as original script
    parser.add_argument('-i', '--input', type=Path, default=Path('users.txt'), help='Input file with names (use - for stdin)')
    parser.add_argument('-o', '--output', type=Path, help='Output file (Default: stdout)')
    parser.add_argument('-f', '--format', action='append', dest='format_list', help='Add format pattern')
    parser.add_argument('--formats', type=Path, help='File with format patterns')
    parser.add_argument('-t', '--threads', type=int, default=os.cpu_count(), help='Number of processes (Default: CPU count)')
    parser.add_argument('-fn', '--first-names', type=Path, help='First names file')
    parser.add_argument('-ln', '--last-names', type=Path, help='Last names file')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode (for redirection or pipe)')
    parser.add_argument('-cs', '--case-sensitive', action='store_true', help='Preserve case based on format')
    parser.add_argument('-lf', '--list-formats', action='store_true', help='Show default formats')

    args = parser.parse_args()

    if args.list_formats:
        print("\n".join(UsernameGenerator.DEFAULT_FORMATS))
        return 0
    
    logger = Logger(args.output, args.quiet)

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
    logger.log(ascii_logo)

    try:
        out_handle = None
        # 1. Prepare Data Source
        name_source = []
        total_items = 0
        
        # Combination Mode (Cartesian Product)
        if args.first_names and args.last_names:
            logger.log(f"[*] Loading lists...")
            fns = Utils.load_names(args.first_names)
            lns = Utils.load_names(args.last_names)
            # We don't materialize the full list to save RAM, we iterate
            name_source = itertools.product(fns, lns)
            total_items = len(fns) * len(lns)
            logger.log(f"[*] Mode: Combination ({len(fns)} fnames x {len(lns)} lnames = {total_items} base names)")
        
        # Single List Mode
        else:
            if args.input.as_posix() == "-" or args.input.exists():
                logger.log(f"[*] Loading input: {args.input}")
                name_source = Utils.load_names(args.input)
                total_items = len(name_source)
                logger.log(f"[*] Mode: Single List ({total_items} items)")
            else:
                logger.log(f"[!] Input file {args.input} not found.")
                sys.exit(1)

        # 2. Prepare Formats
        raw_formats = None
        if args.formats:
            raw_formats = Utils.load_formats(args.formats)
        elif args.format_list:
            raw_formats = args.format_list

        # 3. Setup Output
        out_handle = sys.stdout
        if args.output:
            out_handle = args.output.open('w', encoding='utf-8')
            logger.log(f"[*] Output: {args.output}")
        else:
            logger.log("[*] Output: stdout")

        generator = UsernameGenerator(
                                name_source,
                                total_items,
                                raw_formats,  
                                args.threads, 
                                args.case_sensitive,
                                logger
                                )

        generator.generate(out_handle)
        
        logger.log(f"\n[✓] Done! Generated {generator.total_generated} usernames.")

    except KeyboardInterrupt:
        logger.log("\n[!] Interrupted by user.")
        # Executor will clean up automatically on exit
    except Exception as e:
        logger.log(f"\n[!] Critical Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if out_handle:
            out_handle.close()

if __name__ == "__main__":
    main()
