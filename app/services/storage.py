from pathlib import Path
from werkzeug.datastructures import FileStorage


class StorageService:
    def save_upload(self, upload: FileStorage, relative_path: str) -> Path:
        raise NotImplementedError

    def write_text(self, relative_path: str, text: str) -> Path:
        raise NotImplementedError


class LocalStorage(StorageService):
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError("Storage path escapes storage root")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def save_upload(self, upload: FileStorage, relative_path: str) -> Path:
        path = self._resolve(relative_path)
        upload.save(path)
        return path

    def write_text(self, relative_path: str, text: str) -> Path:
        path = self._resolve(relative_path)
        path.write_text(text, encoding="utf-8")
        return path


def get_storage(app):
    backend = app.config.get("STORAGE_BACKEND", "local")
    if backend != "local":
        raise NotImplementedError(f"Storage backend {backend} is not implemented yet")
    return LocalStorage(Path(app.config["STORAGE_ROOT"]))
