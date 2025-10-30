import asyncio

from dotenv import load_dotenv

from router import get_answer

load_dotenv(override=True)


async def bot_handler(message: dict):
    thread_id = f"{message['FROM_USER_ID']}_{message['DIALOG_ID']}"
    query = message["MESSAGE"]
    answer = await get_answer(query=query, thread_id=thread_id)
    return answer

message = {
    "FROM_USER_ID": "1",
    "DIALOG_ID": "1",
    "MESSAGE": "Неет, речь не о вопросах про битрикс. На какие мои вопросы в этом чате вы смогли ответили?"
}
print(asyncio.run(bot_handler(message)))
