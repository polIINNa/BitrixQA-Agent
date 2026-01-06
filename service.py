from bitrix_qa_agent.state import InputState
from bitrix_qa_agent.graph import get_simple_graph
from bitrix_qa_agent.context import BitrixQAContext

from media_recognizer.utils import encode_image
from media_recognizer.context import MediaRecognizerContext
from media_recognizer.chains import identify_problem_from_img_chain, image_caption_summarize_chain


async def get_answer(
    chat_history: str | None,
    last_user_message: str,
) -> dict:
    """Получить ответ от QA агента.
    
    Args:
        chat_history: История чата
        last_user_message: Последнее сообщение пользователя
        
    Returns:
        dict с ключами:
            - message_type: тип сообщения (negative, no_need_reply, positive_acknowledgement, 
                           knowledge_required, chat, intent_changed)
            - answer: ответ на вопрос (может быть None)
    """
    context = BitrixQAContext()
    bitrix_qa_graph = get_simple_graph()
    if chat_history is None:
        chat_history = ""
    _input = InputState(
        chat_history=chat_history,
        last_user_message=last_user_message,
    )
    result = await bitrix_qa_graph.ainvoke(
        input=_input,
        context=context
    )
    return {
        "message_type": result["user_message_type"],
        "answer": result["answer"],
    }


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

