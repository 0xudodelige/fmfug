$$$$$$$$\ $$\      $$\ $$$$$$$$\ $$\   $$\  $$$$$$\  
$$  _____|$$$\    $$$ |$$  _____|$$ |  $$ |$$  __$$\ 
$$ |      $$$$\  $$$$ |$$ |      $$ |  $$ |$$ /  \__|
$$$$$\    $$\$$\$$ $$ |$$$$$\    $$ |  $$ |$$ |$$$$\ 
$$  __|   $$ \$$$  $$ |$$  __|   $$ |  $$ |$$ |\_$$ |
$$ |      $$ |\$  /$$ |$$ |      $$ |  $$ |$$ |  $$ |
$$ |      $$ | \_/ $$ |$$ |      \$$$$$$  |\$$$$$$  |
\__|      \__|     \__|\__|       \______/  \______/ 


# 🦂 FMFUG — Fast Memory Friendly Username Generator

**FMFUG** is a high-performance, multithreaded username generator written in Python. It is designed to handle millions of name combinations without consuming excessive RAM, making it ideal for generating large wordlists for pentesting, security assessments, or system administration.

---

## 🚀 Features

- **Memory Friendly**: Uses lazy evaluation and streaming. Can process millions of names with minimal RAM usage.
- **Fast I/O**: Implements output buffering to minimize disk write operations.
- **Multithreaded**: processes names in parallel for maximum speed.
- **Customizable**: Supports custom format patterns (e.g., `first.last`, `f-last`, `first[3]last`).
- **Combinatorial Mode**: Can generate combinations from separate first and last name files (Cartesian product) without loading everything into memory.

---

## 📦 Installation

1. Clone the repository:
    ```bash
    git clone [https://github.com/0xudodelige/fmfug.git](https://github.com/0xudodelige/fmfug.git)
    cd fmfug
    ```
2. Install:
    **Using pip**
    ```bash
    pip install .
    ```
    *(Note: The script works without tqdm, but installing it provides a progress bar).*
    
    **Using pipx**
    ```
    pipx install .
    ```

---

## 🧑💻 Usage

```
usage: fmfug [-h] [-i INPUT] [-o OUTPUT] [-f FORMAT_LIST]
                [--formats FORMATS] [-t THREADS] [--no-parallel]
                [--case-sensitive] [-q] [--list-formats]
                [--first-names FIRST_NAMES] [--last-names LAST_NAMES]

Generate username variations (streaming + multithreading)
```

---

## 🛠 Command-Line Options

| Option | Description |
|-------|-------------|
| `-i`, `--input INPUT` | Input file with full names (default: users.txt) |
| `--first-names FIRST_NAMES` | File containing first names (one per line) |
| `--last-names LAST_NAMES` | File containing last names (one per line) |
| `-o`, `--output OUTPUT` | Output file (default: stdout) |
| `-f`, `--format FORMAT_LIST` | Add custom format pattern (repeatable) |
| `--formats FORMATS` | File containing format patterns |
| `-t`, `--threads THREADS` | Number of threads (default: 4) |
| `--case-sensitive` | Preserve original case |
| `-q`, `--quiet` | Quiet mode |
| `--list-formats` | Show default format patterns |
| `-h`, `--help` | Show help message |

---

## 🧩 Supported Format Patterns

### **Name Components**
```
first     → full first name
last      → full last name
middle    → middle name (if present)
```

### **Combinations**
```
firstlast
first.last
first_last
first-last
13__37@firstFOOlastBAR (Why not)
```

### **Truncation**
```
first[1] → first character of first name (Initial)
last[4]  → first 4 characters of last name
```

### **Capitalization**
```
First       → Capitalized
Last        → Capitalized
FirstLast   → PascalCase
```

### **Numeric Suffixes**
```
first5  → appends 0..5
last12   → appends 0..12
```

---

## 📘 Examples

### 1. Basic usage
```bash
fmfug.py
```

### 2. Output to file
```bash
fmfug.py -o usernames.txt
```

### 3. Use 8 threads
```bash
fmfug.py -t 8
```

### 4. Inline custom formats
```bash
fmfug.py -f "first.last" -f "f.last" -o out.txt
```

### 5. Load custom formats from file
```bash
fmfug.py --formats patterns.txt
```

### 6. Case-sensitive output
```bash
fmfug.py --case-sensitive
```

### 7. First/Last name combination mode
```bash
fmfug.py --first-names fn.txt --last-names ln.txt
```

---

## 📜 License
MIT License. See LICENSE file for details.
