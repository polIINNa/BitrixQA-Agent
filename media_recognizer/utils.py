import base64


def encode_image(img_bytes: bytes) -> str:
    """Кодирует изображение в строку base64."""
    base64_string = base64.b64encode(img_bytes).decode('utf-8')
    return f"data:image/jpeg;base64,{base64_string}"
