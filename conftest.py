# conftest.py — корневой конфиг pytest
# Добавляет корень проекта в sys.path, чтобы пакет lib был виден
# из любой подпапки (tests/, artifacts/, etc.).
import sys
from pathlib import Path

# D:\WORK\AVCoder  (или /path/to/AVCoder на Linux/macOS)
root = Path(__file__).parent.resolve()
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
