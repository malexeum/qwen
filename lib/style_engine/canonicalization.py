import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, Union, Any

THETA_AXES = [
    "harmony_theta_0",
    "harmony_theta_1",
    "harmony_theta_2",
    "harmony_theta_3",
    "harmony_theta_4",
    "harmony_theta_5",
    "harmony_theta_6",
    "harmony_theta_7",
]

def canonical_json_bytes(data: Union[Dict, list]) -> bytes:
    """
    Сериализует объект в канонический JSON:
    - кодировка UTF-8
    - сортировка ключей
    - компактные разделители (без пробелов)
    """
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':')
    ).encode('utf-8')

def sha256_prefixed(data: bytes) -> str:
    """Возвращает SHA-256 в формате sha256:<hex>."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"

def canonical_file_hash(path: str) -> str:
    """
    Считает хэш файла от его сырых байтов.
    Не применяет LF/CRLF нормализацию — защищает bit-exact идентичность файлов.
    """
    with open(path, 'rb') as f:
        return sha256_prefixed(f.read())

def canonical_feature_hash(obj: Dict[str, Any]) -> str:
    """Считает хэш feature объекта от его канонического JSON-представления."""
    return sha256_prefixed(canonical_json_bytes(obj))

def canonical_float(value: Union[float, str, int]) -> str:
    """
    Форматирует число с плавающей точкой в строку по правилам D1:
    - преобразование через строку (защита от двоичного хвоста float)
    - округление ROUND_HALF_EVEN
    - строго 6 знаков после запятой (fixed-point)
    """
    d = Decimal(str(value))
    quantized = d.quantize(Decimal('1.000000'), rounding=ROUND_HALF_EVEN)
    return f"{quantized:f}"

def canonical_theta_hash(theta: Dict[str, float]) -> str:
    """
    Считает хэш theta-вектора.
    Использует именованные оси строго в порядке THETA_AXES. Сортировка по алфавиту запрещена.
    """
    ordered_pairs = []
    
    for axis in THETA_AXES:
        if axis not in theta:
            raise ValueError(f"Отсутствует обязательная ось: {axis}")
            
        val = theta[axis]
        if not (0.0 <= float(val) <= 1.0):
            raise ValueError(f"Ось {axis} вне диапазона [0, 1]: {val}")
            
        ordered_pairs.append([axis, canonical_float(val)])
        
    payload = canonical_json_bytes(ordered_pairs)
    full_hex = hashlib.sha256(payload).hexdigest()
    
    return f"sha256:{full_hex[:16]}"
