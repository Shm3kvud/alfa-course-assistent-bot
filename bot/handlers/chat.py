import asyncio
from aiogram.utils.chat_action import ChatActionSender
from contextlib import suppress
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.history import create_chat, save_message, get_user_chats, delete_user_history, get_chat_messages
from memory.session import clear_history as clear_llm_history, set_history as set_llm_history
from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from bot.keyboards.keyboards import button
from telegramify_markdown import convert, split_entities
from rag.pipeline import answer
import re


router = Router()


class Questions(StatesGroup):
    waiting_question = State()

def resource_buttons(text):
    links = {}

    if "Ссылки на найденные курсы:" in text:
        text, section = text.rsplit("Ссылки на найденные курсы:", 1)

        for title, url in re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", section):
            if url.startswith("https://kurs.alfabank.ru/"):
                links[url] = title

    for title, url in re.findall(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", text):
        if url.startswith("https://kurs.alfabank.ru/"):
            links.setdefault(url, title)

    for url in re.findall(r"https?://[^\s<>()\[\]*]+", text):
        url = url.rstrip(".,;:!?\\")
        if url.startswith("https://kurs.alfabank.ru/"):
            links.setdefault(url, "Материал")

    text = re.sub(r"\[[^\]]+\]\(https?://[^)\s]+\)", "", text)
    text = re.sub(r"https?://[^\s<>()\[\]*]+", "", text)
    text = re.sub(r"(?m)^\s*\*?Ссылка:\*?\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    keyboard = [
        [InlineKeyboardButton(text=f"📚 {title[:55]}", url=url)]
        for url, title in list(links.items())[:3]
    ]

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None

    return text, markup

@router.callback_query(F.data == "ask_question")
async def ask_question(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(Questions.waiting_question)
    await callback.message.answer(
        "Расскажи, с какой задачей в бизнесе нужна помощь."
    )
    
async def animation_dots(status):
    while True:
        for dots in ("", ".", "..", "..."):
            await status.edit_text(f"🔎 Подбираю материалы{dots}")
            await asyncio.sleep(0.5)
            
            
@router.message(Questions.waiting_question, F.text)
async def get_question(message: types.Message, state: FSMContext):
    question = message.text.strip()
    
    if not question:
        await message.answer("Напиши свой вопрос")
        return
    
    data = await state.get_data()
    chat_id = data.get("active_chat_id")
    
    if chat_id is None:
        chat_id = await create_chat(message.from_user.id, question[:60])
        await state.update_data(active_chat_id=chat_id)
        
    await save_message(chat_id, "user", question)
    
    status = await message.answer("🔎 Подбираю материалы...")
    animation = asyncio.create_task(animation_dots(status))
    
    try:
        async with ChatActionSender.typing(
            bot=message.bot,
            chat_id=message.chat.id
        ):
            response = await answer(question, message.from_user.id)
    finally:
        animation.cancel()
        
        with suppress(asyncio.CancelledError):
            await animation
        
        await status.delete()
    
    
    text, keyboard = resource_buttons(response)

    text, entities = convert(text)
    chunks = split_entities(text, entities, max_utf16_len=4000)

    for i, (part, part_entities) in enumerate(chunks):
        await message.answer(
            part,
            entities=[entity.to_dict() for entity in part_entities],
            parse_mode=None,
            reply_markup=keyboard if i == len(chunks) - 1 else None
        )

    await save_message(chat_id, "assistant", response)



    

@router.callback_query(F.data == "new_chat")
async def new_chat(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    clear_llm_history(callback.from_user.id)
    
    await state.clear()
    await state.set_state(Questions.waiting_question)
    
    await callback.message.answer("Новый диалог создан. Напишите свой вопрос")
    
    
@router.callback_query(F.data == "history")
@router.callback_query(F.data.startswith("history_page:"))
async def show_history(callback: types.CallbackQuery):
    await callback.answer()
    
    chats = await get_user_chats(callback.from_user.id)
    
    page = 0
    
    if callback.data.startswith("history_page:"):
        page = int(callback.data.split(":")[1])
        
    total_pages = max(1, (len(chats) + 7) // 8)
    page = max(0, min(page, total_pages - 1))
    
    keyboard = []
    
    for i, chat in enumerate(chats[page * 8:(page + 1) * 8], start=page * 8 + 1):
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"{i}. {chat['title'][:40]}",
                callback_data=f"open_chat:{chat['id']}:{page}"
            )
        ])
    
    if total_pages > 1:
        keyboard.append([
            types.InlineKeyboardButton(
                text = "❮",
                callback_data=f"history_page:{page - 1}" if page > 0 else "history_noop"
            ),
            types.InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="history_noop"
            ),
            types.InlineKeyboardButton(
                text="❯",
                callback_data=f"history_page:{page + 1}" if page < total_pages - 1 else "history_noop"
            )
        ])
        
    keyboard.append([
        types.InlineKeyboardButton(
            text="🗑️ Очистить историю",
            callback_data="clear_history"
        )
    ])
    
    keyboard.append([
        types.InlineKeyboardButton(
            text="← Назад в главное меню",
            callback_data="back_menu"
        )
    ])
    
    text = (
        "История диалогов\nВыберите диалог:"
        if chats else
        "История диалогов\nПока нет сохранённых диалогов."
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    

@router.callback_query(F.data == "history_noop")
async def history_noop(callback: types.CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("open_chat:"))
async def open_chat(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    chat_id = int(callback.data.split(":")[1])
    messages = await get_chat_messages(chat_id, callback.from_user.id)

    if not messages:
        await callback.message.answer("Диалог не найден")
        return

    pairs = []
    user_message = None

    for message in messages:
        if message["role"] == "user":
            user_message = message["content"]
        elif message["role"] == "assistant" and user_message is not None:
            pairs.append({
                "user": user_message,
                "assistant": message["content"],
            })
            user_message = None

    set_llm_history(callback.from_user.id, pairs)

    await state.clear()
    await state.update_data(active_chat_id=chat_id)
    await state.set_state(Questions.waiting_question)

    history_blocks = []

    for message in messages[-3:]:
        if message["role"] == "user":
            history_blocks.append(f"Вы: {message['content']}")
        else:
            answer_text, _ = resource_buttons(message["content"])
            history_blocks.append(f"Бот: {answer_text}")

    text, entities = convert("\n\n".join(history_blocks))
    chunks = split_entities(text, entities, max_utf16_len=4000)

    for part, part_entities in chunks:
        await callback.message.answer(
            part,
            entities=[entity.to_dict() for entity in part_entities],
            parse_mode=None,
        )

    
@router.callback_query(F.data == "back_menu")
async def back_menu(callback: types.CallbackQuery):
    await callback.answer()
    
    name = callback.from_user.first_name
    
    await callback.message.edit_text(
        f"👋 Добро пожаловать в AlfaAI, {name}!",
        reply_markup=button
    )
    
@router.callback_query(F.data == "clear_history")
async def clear_history(callback:types.CallbackQuery):
    await callback.answer()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Да, очистить",
            callback_data="confirm_clear_history"
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="history"
        )]
    ])
    
    await callback.message.edit_text(
        "Вы точно хотите удалить всю историю диалогов?",
        reply_markup=keyboard
    )
    
@router.callback_query(F.data == "confirm_clear_history")
async def confirm_clear_history(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Удаление истории")
    
    try:
        await asyncio.wait_for(
            delete_user_history(callback.from_user.id),
            timeout=10
        )
    except Exception as e:
        print(f"Ошибка удаления истории: {e}", flush=True)
        await callback.message.edit_text(
            "Не удалось очистить историю."
        )
        return 
    
    clear_llm_history(callback.from_user.id)
    await state.clear()
    
    await callback.message.edit_text(
        "✅Успешно! История диалогов очищена.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="← Назад в главное меню",
                callback_data="back_menu"
            )]
        ])
    )

@router.message(~F.text)
async def unsupported_message(message: types.Message):
    await message.answer(
        "Напишите ваш вопрос текстом."
    )