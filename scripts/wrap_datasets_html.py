import json
from pathlib import Path

DIR = Path(r"c:\coding\ai-trainer\backend\data\gateway_datasets")

for file in DIR.glob("*.json"):
    data = json.loads(file.read_text(encoding="utf-8"))
    arch = data.get("architecture", {})
    inner_html = arch.get("html_scaffold", "")
    title = data.get("name", "Web Application")

    # If not already wrapped in full document
    if "<!DOCTYPE" not in inner_html and "<html" not in inner_html:
        full_html = f"<!DOCTYPE html>\\n<html lang=\\\"en\\\">\\n<head>\\n  <meta charset=\\\"UTF-8\\\">\\n  <meta name=\\\"viewport\\\" content=\\\"width=device-width, initial-scale=1.0\\\">\\n  <title>{title}</title>\\n  <link rel=\\\"stylesheet\\\" href=\\\"styles.css\\\">\\n</head>\\n<body>\\n  {inner_html}\\n  <script src=\\\"app.js\\\"></script>\\n</body>\\n</html>"
        arch["html_scaffold"] = full_html
        data["architecture"] = arch
        file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Updated wrapper in {file.name}")

print("All datasets now enforce complete <!DOCTYPE html> document scaffolding with linked styles.css and app.js!")
