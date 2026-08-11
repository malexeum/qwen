import hashlib

def compute_variation_seed(
    profile_slug: str,
    feature_sha256: str,
    canonical_theta_hash: str
) -> int:
    """
    Детерминированно вычисляет variation seed на основе базовых параметров.
    Единственный источник истины для seed policy (если ранее не был выделен в отдельный метод).
    D1 validator вызывает именно эту функцию для проверки expected_variation_seed.
    """
    # Собираем все компоненты в единый байтовый payload
    # Порядок и разделитель '|' фиксированы контрактом.
    payload = f"{profile_slug}|{feature_sha256}|{canonical_theta_hash}".encode('utf-8')
    
    digest = hashlib.sha256(payload).hexdigest()
    
    # Превращаем первые 16 hex символов в целое число
    # Это дает 64-битный integer, безопасный для numpy/random seed
    return int(digest[:16], 16)
