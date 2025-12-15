```powershell
$$$$$$$$\ $$\      $$\ $$$$$$$$\ $$\   $$\  $$$$$$\  
$$  _____|$$$\    $$$ |$$  _____|$$ |  $$ |$$  __$$\ 
$$ |      $$$$\  $$$$ |$$ |      $$ |  $$ |$$ /  \__|
$$$$$\    $$\$$\$$ $$ |$$$$$\    $$ |  $$ |$$ |$$$$\ 
$$  __|   $$ \$$$  $$ |$$  __|   $$ |  $$ |$$ |\_$$ |
$$ |      $$ |\$  /$$ |$$ |      $$ |  $$ |$$ |  $$ |
$$ |      $$ | \_/ $$ |$$ |      \$$$$$$  |\$$$$$$  |
\__|      \__|     \__|\__|       \______/  \______/ 
```

# 🦂 FMFUG — Fast Memory Friendly Username Generator

**FMFUG** is a high-performance, multithreaded username generator written in Python. It is designed to handle millions of name combinations without consuming excessive RAM, making it ideal for generating large wordlists for pentesting, security assessments, or system administration.

---

## 🚀 Features

- **Memory Friendly**: Uses lazy evaluation and streaming. Can process millions of names with minimal RAM usage.
- **Fast I/O**: Implements output buffering to minimize disk write operations.
- **Multithreaded**: processes names in parallel for maximum speed.
- **Customizable**: Supports custom format patterns (e.g., `first.last`, `first[1]last`).
- **Combinatorial Mode**: Can generate combinations from separate first and last name files (Cartesian product) without loading everything into memory.

---

## ❓ Why ❓

- **username-anarchy** made my pc burn down to ashes

---

## 📦 Installation

### 1. Install from pypi

**Using pipx**
```bash
pipx install fmfug
```

### 2. Install from source
1. Clone the repository:
    ```bash
    git clone https://github.com/0xudodelige/fmfug.git
    cd fmfug
    ```
2. Install:
    **Using pipx**
    ```bash
    pipx install .
    ```
    *(Note: The script works without tqdm, but installing it provides a progress bar).*

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
| `-i`, `--input INPUT` | Input file with full names (default: users.txt, use - for stdin) |
| `-fn`, `--first-names FIRST_NAMES` | File containing first names (one per line) |
| `-ln`, `--last-names LAST_NAMES` | File containing last names (one per line) |
| `-o`, `--output OUTPUT` | Output file (default: stdout) |
| `-f`, `--format FORMAT_LIST` | Add custom format pattern (repeatable) |
| `--formats FORMATS` | File containing format patterns |
| `-t`, `--threads THREADS` | Number of threads (default: 4) |
| `--case-sensitive` | Preserve original case |
| `-q`, `--quiet` | Quiet mode (for redirection or pipe) |
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

![FMFUG Example GIF](https://github.com/0xudodelige/fmfug/blob/main/fmfug.gif?raw=true)

### 1. Basic usage
```bash
fmfug
```

### 2. Output to file
```bash
fmfug -o usernames.txt
```

### 3. Use 8 threads
```bash
fmfug -t 8
```

### 4. Inline custom formats
```bash
fmfug -f "first.last" -f "first[1].last" -o out.txt
```

### 5. Load custom formats from file
```bash
fmfug --formats patterns.txt
```

### 6. Case-sensitive output
```bash
fmfug --case-sensitive
```

### 7. First/Last name combination mode
```bash
fmfug --first-names fn.txt --last-names ln.txt
```

---

## 📜 License
MIT License. See LICENSE file for details.
