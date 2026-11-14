import asyncio
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.history import create_chat, get_last_chat, save_message, get_user_chats, delete_user_history
from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from bot.keyboards.keyboards import button
from rag.pipeline import answer
import re
import html


router = Router()


class Questions(StatesGroup):
    waiting_question = State()


@router.callback_query(F.data == "ask_question")
async def ask_question(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(Questions.waiting_question)
    
    await callback.message.answer(
        "Расскажи, с какой задачей в бизнесе нужна помощь."
    )
    
    
@router.message(Questions.waiting_question, F.text)
async def get_question(message: types.Message):
    question = message.text.strip()
    
    if not question:
        await message.answer("Напиши свой вопрос")
        return
    
    
    chat_id = await get_last_chat(message.from_user.id)
    
    if chat_id is None:
        chat_id = await create_chat(message.from_user.id, question[:60])
        
    await save_message(chat_id, "user", question)
    
    response = await answer(question, message.from_user.id)
    
    
    response = response.replace("**", "")

    formatted = []
    items = []

    for line in response.splitlines():
        if re.match(r"^\s*\d+[.)]\s*", line):
            items.append(html.escape(line))
        else:
            if items:
                formatted.append(
                    "<blockquote>" + "\n".join(items) + "</blockquote>"
                )
                items = []

            formatted.append(html.escape(line))

    if items:
        formatted.append(
            "<blockquote>" + "\n".join(items) + "</blockquote>"
        )

    await message.answer("\n".join(formatted), parse_mode="HTML")

    await save_message(chat_id, "assistant", response)

    

@router.callback_query(F.data == "new_chat")
async def new_chat(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    await create_chat(callback.from_user.id, "Новый диалог")
    
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
                callback_data=f"open_chat:{chat['id']}:[{page}]"
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
