from pathlib import Path


artifact = Path("dist/demo.txt")
artifact.parent.mkdir(exist_ok=True)
artifact.write_text("completion verified\n", encoding="utf-8")
