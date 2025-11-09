import asyncio

from dotenv import load_dotenv

from service import get_answer

load_dotenv(override=True)


async def bot_handler(message: dict):
    thread_id = f"{message['FROM_USER_ID']}_{message['DIALOG_ID']}"
    query = message["MESSAGE"]
    answer = await get_answer(query=query, thread_id=thread_id)
    return answer

queries = [
    "Добрый день!",
    "Как перенести данные из Экселя в Битрикс?",
    "Возникла проблема: как перенести данные из Экселя в Битрикс?"
    "Не могу понять, как перенести данные из экселя в Битрикс"
    "Как распечатать страницу из Битрикса?",
    "А распечатать страницу оттуда?",
    "Какой есть функционал в профиле сотрудника?"
]
message = {
    "FROM_USER_ID": "8",
    "DIALOG_ID": "35",
    "MESSAGE": "Хорошо, спасибо"
}
print(asyncio.run(bot_handler(message)))
