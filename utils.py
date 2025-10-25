

def get_article_batches(articles_metadata: dict[str, dict]) -> list[str]:
    """Получить список батчей с данными по статьям"""

    article_batches = []
    batch = []
    for _id in articles_metadata:
        batch.append(f"ID статьи: {_id}\nТема: {articles_metadata[_id]['title']}\nПроблема: {articles_metadata[_id]['problem']}")
        if len(batch) == 10:
            formatted_batch = "\n\n".join(batch)
            article_batches.append(formatted_batch)
            batch = []
    if batch:
        formatted_batch = "\n\n".join(batch)
        article_batches.append(formatted_batch)
    return article_batches


def get_sections_content(article_content: str) -> str:
    """Получить текст из разделов РЕШЕНИЕ, ВАЖНО и ТЕХНИЧЕСКИЕ ДЕТАЛИ"""

    sections = {}
    current_section = None
    lines = article_content.split('\n')

    all_sections = ["РЕШЕНИЕ:", "ВАЖНО:", "ТЕХНИЧЕСКИЕ ДЕТАЛИ:", "СВЯЗАННЫЕ ВОПРОСЫ:",
                    "ПРОБЛЕМА:", "ТЕМА:", "Категория:"]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if any(line.startswith(section) for section in all_sections):
            if line in ["РЕШЕНИЕ:", "ВАЖНО:", "ТЕХНИЧЕСКИЕ ДЕТАЛИ:"]:
                current_section = line.replace(':', '')
                sections[current_section] = []
            else:
                current_section = None
        elif current_section and line:
            sections[current_section].append(line)

    target_sections = ["РЕШЕНИЕ", "ВАЖНО", "ТЕХНИЧЕСКИЕ ДЕТАЛИ"]
    result_parts = []

    for section in target_sections:
        if section in sections and sections[section]:
            result_parts.extend(sections[section])

    return '\n'.join(result_parts)