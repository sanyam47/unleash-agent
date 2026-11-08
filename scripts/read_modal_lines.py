with open(r"c:\coding\ai-trainer\frontend\index.html", "r", encoding="utf-8") as f:
    text = f.read()

import re
m = re.search(r'id=["\']agentProjectModal["\']', text)
if m:
    lines = text[m.start():m.start() + 1500].splitlines()
    for i, l in enumerate(lines[:35]):
        print(f"{i}: {l}")
