import json
from pathlib import Path


def load_jsondata(
    filepath: Path, default: list | dict | None = None
) -> list | dict:
    """
    Загрузка данных из JSON-файла, при его отсутствии - значение по умолчанию
    """
    try:
        with open(filepath, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if default is None else default


def save_jsondata(filepath: Path, data: list | dict) -> None:
    """
    Сохранение данных в JSON-файл
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
