import asyncio
import logging
from config import get_settings
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, MenuButtonCommands
from bot.handlers.start import router as start_router
from bot.handlers.chat import router as chat_router


logging.basicConfig(level=logging.INFO)

settings = get_settings()

token = Bot(token=settings.bot_token.get_secret_value())
dp=Dispatcher()

dp.include_router(start_router)
dp.include_router(chat_router)


# Запуск бота
async def main():
    await token.set_my_commands([
        BotCommand(
            command="start",
            description="🏠 Главное меню"
        )
    ])
    
    await token.set_chat_menu_button(
        menu_button=MenuButtonCommands()
    )
    
    await dp.start_polling(token)
    
    
if __name__ == "__main__":
    asyncio.run(main())