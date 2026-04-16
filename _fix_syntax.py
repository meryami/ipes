path = r'c:\Users\rahma\Desktop\blueprint\backend\bengkel\views.py'
lines = open(path, encoding='utf-8').readlines()

fixed_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Detect the broken pp_list line
    if line.strip() == 'pp_list = "':
        # Next line should be the join continuation
        next_line = lines[i+1] if i+1 < len(lines) else ''
        if '".join(' in next_line or '".join(' in next_line:
            # Merge into one correct line
            indent = len(line) - len(line.lstrip())
            fixed_lines.append(' ' * indent + 'pp_list = chr(10).join(f"{idx2}. {t2}" for idx2, t2 in enumerate(pain_points_raw, 1))\n')
            i += 2  # skip next line
            continue
    fixed_lines.append(line)
    i += 1

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)

# Verify
import subprocess
result = subprocess.run(['python', '-m', 'py_compile', path], capture_output=True, text=True)
print('compile errors:', result.stderr or 'none')
print('done')
