import logging
from rag.retriever import aretrieve
from llm.client import generate
from llm.prompts import system_prompt
from memory.session import get_history, add_to_history
from config import get_settings
import re

log = logging.getLogger(__name__)

async def answer(query: str, user_id: int) -> str:
    settings = get_settings()
    k = settings.top_k
    history = get_history(user_id)

    try:
        docs = await aretrieve(query, max(k, 15))
    except Exception:
        log.exception("Ошибка при поиске в БД")
        return "Извините, у меня проблемы с базой знаний. Попробуйте позже."

    types = sorted({str(d.metadata.get("source_type")) for d in docs})
    log.info(
        "retrieval: %r -> %d docs, types=%s",
        query[:80],
        len(docs),
        ",".join(types),
    )

    if not docs:
        log.warning("Контекст не найден")
        return "К сожалению, я не нашёл ответа на этот вопрос. Уточните у оператора."

    context_blocks = []
    for doc in docs:
        block = doc.page_content
        meta = doc.metadata


        facts = []

        if "cost" in meta:
            cost_val = meta["cost"]

            if str(cost_val) == "0" or cost_val == 0:
                facts.append("Стоимость: Бесплатно")
            elif cost_val:
                facts.append(f"Стоимость: {cost_val} руб.")

        if meta.get("duration"):
            facts.append(f"Длительность: {meta['duration']}")

        if str(meta.get("certificate")).lower() == "true":
            facts.append("Выдается сертификат")

        if str(meta.get("trial")).lower() == "true":
            facts.append("Есть пробный период")

        if meta.get("authors"):
            facts.append(f"Авторы: {meta['authors']}")

        if meta.get("url"):
            facts.append(f"Ссылка: {meta['url']}")

        if meta.get("experts"):
            facts.append(f"Эксперты: {meta['experts']}")

        if meta.get("files"):
            facts.append(f"Прикрепленные файлы: {meta['files']}")

        if facts:
            block += "\n[Дополнительные факты]: " + ". ".join(facts) + "."

        context_blocks.append(block)

    context = "\n\n---\n\n".join(context_blocks)

    try:
        answer_text = await generate(
            system_prompt=system_prompt,
            context=context,
            question=query,
            history=history,
        )
        
        add_to_history(user_id, query, answer_text)

        
        links = []
        used_urls = set()

        for doc in docs:
            url = doc.metadata.get("url")

            if (
                not isinstance(url, str)
                or not url.startswith("https://kurs.alfabank.ru/")
                or url in used_urls
            ):
                continue

            match = re.match(r"^[^:]+:\s*'([^']+)'", doc.page_content)
            title = match.group(1) if match else doc.metadata.get("course_title") or "Материал"
            title = re.sub(r"[\[\]\n]", "", title).strip()

            links.append((title, url))
            used_urls.add(url)

            if len(links) == 3:
                break

        if links:
            answer_text += "\n\nСсылки на найденные курсы:\n"
            answer_text += "\n".join(
                f"[{title}]({url})" for title, url in links
            )

        return answer_text



    except Exception:
        log.exception("Ошибка при генерации ответа LLM")
        return "Извините, произошла ошибка. Попробуйте ещё раз."
