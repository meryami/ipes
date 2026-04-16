path = r'c:\Users\rahma\Desktop\blueprint\backend\bengkel\views.py'
with open(path, encoding='utf-8') as f:
    text = f.read()

# Fix 1: save_ps — add session.pop + redirect to ?tab=ps
old1 = '            messages.success(request, "Problem Statement berjaya disimpan.")\n            return redirect(blueprint_url + "?tab=spaf")'
new1 = '            messages.success(request, "Problem Statement berjaya disimpan.")\n            request.session.pop("spaf_generated_ps", None)\n            request.session.modified = True\n            return redirect(blueprint_url + "?tab=ps")'
assert old1 in text, "fix1 not found"
text = text.replace(old1, new1, 1)

# Fix 2: del_ps — redirect to ?tab=ps
old2 = '            SpafProblemStatement.objects.filter(pk=pid, user=request.user).delete()\n            return redirect(blueprint_url + "?tab=spaf")'
new2 = '            SpafProblemStatement.objects.filter(pk=pid, user=request.user).delete()\n            return redirect(blueprint_url + "?tab=ps")'
assert old2 in text, "fix2 not found"
text = text.replace(old2, new2, 1)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("done — ?tab=ps count:", text.count("?tab=ps"))
