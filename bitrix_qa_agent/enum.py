import enum


class UserMessageType(enum.Enum):
    """Тип сообщения клиента"""
    NEW_SESSION_REQUIRED = 'new_session_required'
    NEGATIVE = 'negative'
    NO_NEED_REPLY = 'no_need_reply'
    POSITIVE_ACKNOWLEDGEMENT = 'positive_acknowledgement'
    KNOWLEDGE_REQUIRED = 'knowledge_required'
    CHAT = 'chat'


class NodeNames(enum.StrEnum):
    """Названия узлов в графе."""
    check_new_intent = 'Проверка на смену темы диалога'
    admin_node = 'Админ нода, для чата и применения tone of voice'
    check_negative = 'Проверка на негатив от клиента'
    need_reply_check = 'Определение необходимости ответа'
    positive_acknowledgement_check = 'Определение положительного отклика'
    knowledge_required_check = 'Определение необходимости похода в базу знаний'
    identify_search_query = 'Получить запрос для поиска по базе знаний (выделение интента)'
    get_relevant_articles_ids = 'Получить релевантные статьи для формирования ответа'
    form_context = 'Сформировать контекст'
    generate_answer = 'Сгенерировать ответ на вопрос'
