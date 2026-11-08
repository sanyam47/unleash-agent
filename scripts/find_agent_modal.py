with open(r"c:\coding\ai-trainer\frontend\index.html", "r", encoding="utf-8") as f:
    text = f.read()

import re
m = re.search(r'id=["\']agentProjectModal["\']', text)
if m:
    start = max(0, m.start() - 50)
    end = min(len(text), m.end() + 1500)
    print(text[start:end])
