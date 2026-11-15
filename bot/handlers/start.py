from aiogram import Router, types
from aiogram.filters import CommandStart
from bot.keyboards.keyboards import button
from aiogram.types import MenuButtonCommands


router = Router()


# Команда /start
@router.message(CommandStart())
async def start_command(message: types.Message):
    await message.bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonCommands()
    )
    
    name = message.from_user.first_name
    
    await message.answer(
        f"👋 Добро пожаловать в AlfaAI, {name}!",
        reply_markup=button
    )