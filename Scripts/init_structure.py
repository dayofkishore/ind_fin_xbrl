from pathlib import Path

# Project root (run from project root)
ROOT = Path(__file__).resolve().parent.parent

STRUCTURE = {
    "config": [],
    "data": [
        "raw",
        "processed",
        "taxonomy",
        "artifacts"
    ],
    "logs": [],
    "src": [
        "ontology",
        "graph",
        "ingestion",
        "normalization",
        "validation",
        "utils"
    ],
    "tests": [],
    "notebooks": [],
    "docs": []
}

def create_structure(base_path: Path, structure: dict):
    for folder, subfolders in structure.items():
        folder_path = base_path / folder
        folder_path.mkdir(exist_ok=True)

        for sub in subfolders:
            (folder_path / sub).mkdir(exist_ok=True)

if __name__ == "__main__":
    create_structure(ROOT, STRUCTURE)
    print("Project structure created successfully.")
