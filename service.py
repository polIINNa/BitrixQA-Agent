#TODO: подумать над тем, нужно ли вообще определять окончание сессии моделью или будет алгоритмом определяться n последних сообщений и тд

from bitrix_qa_agent.state import InputState
from bitrix_qa_agent.graph import get_simple_graph
from bitrix_qa_agent.context import BitrixQAContext

from orchestrator.chains import is_support_session_end_chain

from media_recognizer.utils import encode_image
from media_recognizer.context import MediaRecognizerContext
from media_recognizer.chains import identify_problem_from_img_chain, image_caption_summarize_chain


async def get_answer(chat_history: str | None, last_user_message) -> str:
    """Получить ответ от QA агента"""
    context = BitrixQAContext()
    bitrix_qa_graph = get_simple_graph()
    if chat_history is None:
        chat_history = ""
    _input = InputState(chat_history=chat_history, last_user_message=last_user_message)
    result = await bitrix_qa_graph.ainvoke(
        input=_input,
        context=context
    )
    if result["user_message_type"] == "objection":
        return "need_human"
    else:
        return result["answer"]


async def check_support_session_end(chat: str) -> bool:
    """Определить, завершена сессия поддержки или нет"""
    #TODO: создать контекст отдельный для определени окончания сессии
    context = BitrixQAContext()
    result = await is_support_session_end_chain(model=context.pro_model).ainvoke(
        {
            "chat": chat
        }
    )
    if result == "1":
        return True
    else:
        return False


async def identify_problem_from_img(img_bytes: bytes, caption: str | None = None) -> str:
    """Определить проблему пользователя из изображения"""
    context = MediaRecognizerContext()
    image_url = encode_image(img_bytes)
    problem_from_img = (await identify_problem_from_img_chain(context.image_recognizer_model).ainvoke(
        {"image_url": image_url}
    )).content
    if caption is not None:
        image_caption_summarize = await image_caption_summarize_chain(context.image_caption_summarize_model).ainvoke(
            {
                "image_description": problem_from_img,
                "caption": caption
            }
        )
        return image_caption_summarize
    return problem_from_img


async def get_user_message_from_media(type: str, content: bytes, caption: str | None = None) -> str | None:
    """Получить текстовое сообщение пользователя из медиа-контента"""
    #TODO: добавить другие медиа-типы
    if type == "photo":
        if caption is None:
            return (await identify_problem_from_img(img_bytes=content))
        else:
            return (await identify_problem_from_img(img_bytes=content, caption=caption))
    return None
