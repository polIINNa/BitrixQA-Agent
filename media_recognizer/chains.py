from langchain_core.runnables import Runnable
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from media_recognizer.prompts import image_recognizer_prompt_tmpl, image_caption_summarize_prompt_tmpl


def identify_problem_from_img_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для определения проблемы клиента из изображения"""
    return image_recognizer_prompt_tmpl | model


def image_caption_summarize_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для определения проблемы клиента по описанию фото и подписи к фото"""
    return image_caption_summarize_prompt_tmpl | model | StrOutputParser()
