import sys
import uvicorn

sys.path.insert(0, r"c:\coding\ai-trainer")

if __name__ == "__main__":
    uvicorn.run("backend.api.main:app", host="127.0.0.1", port=8001, reload=True, reload_dirs=[r"c:\coding\ai-trainer\backend"], log_level="info")
