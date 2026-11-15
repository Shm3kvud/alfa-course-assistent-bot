import logging

log = logging.getLogger(__name__)

_history_storage: dict[int, list[dict]] = {}

def get_history(user_id: int) -> list[dict]:
    return _history_storage.get(user_id, [])

def set_history(user_id: int, history: list[dict]) -> None:
    if history:
        _history_storage[user_id] = history[-5:]
    else:
        _history_storage.pop(user_id, None)

def clear_history(user_id: int) -> None:
    _history_storage.pop(user_id, None)

def add_to_history(user_id: int, user_message: str, bot_message: str):
    if user_id not in _history_storage:
        _history_storage[user_id] = []
    
    _history_storage[user_id].append({
        "user": user_message,
        "assistant": bot_message
    })
    
    _history_storage[user_id] = _history_storage[user_id][-5:]
    log.info("История для %s обновлена. Всего сообщений: %d", user_id, len(_history_storage[user_id]))