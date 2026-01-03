from pathlib import Path
try:
    content = Path("retry_log.txt").read_text(encoding="utf-16")
    found = False
    patterns = ["QUALITY GATE", "Underproduction", "RAW LLM RESPONSE", "Validation Errors"]
    for line in content.splitlines():
        if any(p in line for p in patterns):
            print(line[:500])
            found = True
    if not found:
        print("No relevant log lines found.")
except Exception as e:
    print(f"Error reading utf-16le: {e}")
    try:
        print(Path("test_output.txt").read_text(encoding="utf-8"))
    except Exception as e2:
        print(f"Error reading utf-8: {e2}")
