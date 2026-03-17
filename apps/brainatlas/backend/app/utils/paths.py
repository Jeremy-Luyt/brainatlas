from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def data_root() -> Path:
    path = project_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def temp_root() -> Path:
    path = data_root() / "temp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def uploads_root() -> Path:
    path = temp_root() / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_workspace(project_id: str) -> Path:
    path = data_root() / "projects" / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path
