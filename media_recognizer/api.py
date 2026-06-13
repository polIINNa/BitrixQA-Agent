"""Публичный API для распознавания медиа-контента."""
from media_recognizer.utils import encode_image
from media_recognizer.context import get_media_recognizer_context
from media_recognizer.chains import identify_problem_from_img_chain, image_caption_summarize_chain


async def identify_problem_from_image(
    img_bytes: bytes,
    caption: str | None = None,
) -> str:
    """
    Определить проблему пользователя из изображения.
    
    Args:
        img_bytes: байты изображения
        caption: подпись к изображению (опционально)
        
    Returns:
        Описание проблемы пользователя
    """
    context = get_media_recognizer_context()
    image_url = encode_image(img_bytes)
    
    problem_from_img = (
        await identify_problem_from_img_chain(context.image_recognizer_model)
        .ainvoke({"image_url": image_url})
    ).content
    
    if caption is not None:
        return await image_caption_summarize_chain(
            context.image_caption_summarize_model
        ).ainvoke({
            "image_description": problem_from_img,
            "caption": caption,
        })
    
    return problem_from_img


async def extract_text_from_media(
    media_type: str,
    content: bytes | None,
    caption: str | None = None,
) -> str | None:
    """
    Извлечь текстовое описание из медиа-контента.
    
    Args:
        media_type: тип медиа (photo, video, audio и т.д.)
        content: байты медиа-контента
        caption: подпись к медиа (опционально)
        
    Returns:
        Текстовое описание или None если тип не поддерживается
    """
    if content is None:
        return None

    # TODO: добавить поддержку других медиа-типов
    if media_type == "photo":
        return await identify_problem_from_image(img_bytes=content, caption=caption)
    
    return None

