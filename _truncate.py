path = r'c:\Users\rahma\Desktop\blueprint\backend\bengkel\views.py'
lines = open(path, encoding='utf-8').readlines()

# Find the line where our appended function starts
for i, l in enumerate(lines):
    if '@login_required' in l and i > 1800:
        cutoff = i
        break
else:
    cutoff = 1806

print(f"Cutting at line {cutoff+1}: {repr(lines[cutoff])}")
lines = lines[:cutoff]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("truncated to", len(lines), "lines")
