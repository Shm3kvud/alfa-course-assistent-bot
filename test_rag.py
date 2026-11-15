import asyncio
import logging
import os

# модель уже в кэше скачана, не качаем с хф, иначе 5 минут ретраев (хз почему)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from rag.ingest import ingest
from rag.pipeline import answer
from rag.retriever import aretrieve

log = logging.getLogger("demo_rag")

QUERIES = [
    "хочу открыть табачный магазин, с чего начать",
    "как выбрать налогообложение для ИП",
    "как продвигать магазин и привлекать покупателей",
    "как приготовить борщ",  # off-topic
]


async def main():
    for q in QUERIES:
        docs = await aretrieve(q, 3)
        print(f"\n----- {q}\n    Найдено: {len(docs)}")
        for d in docs:
            text = d.page_content[:80].replace("\n", " ") + "..."
            print(
                f" - {d.metadata.get('id')}\n   {text}\n"
            )

    print("\n----- Полный RAG-ответ -----")
    print(await answer("Как выбрать налогообложение для ИП?", 1))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

    # ingest()
    asyncio.run(main())
