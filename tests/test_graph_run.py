import asyncio

from dotenv import load_dotenv

from router import get_answer

load_dotenv(override=True)


async def bot_handler(message: dict):
    thread_id = f"{message['FROM_USER_ID']}_{message['DIALOG_ID']}"
    query = message["MESSAGE"]
    answer = await get_answer(query=query, thread_id=thread_id)
    return answer

queries = [
    "Как перенести данные из Экселя в Битрикс?",
    "Как распечатать страницу из Битрикса?",
    "А распечатать страницу оттуда?",
    "Какой есть функционал в профиле сотрудника?"
]
message = {
    "FROM_USER_ID": "5",
    "DIALOG_ID": "3",
    "MESSAGE": "Как перенести данные из Экселя в Битрикс?"
}
print(asyncio.run(bot_handler(message)))
