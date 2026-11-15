import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def create_chat(user_id, title):
        conn = await asyncpg.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
        
        try:
            chat_id = await conn.fetchval(
                "INSERT INTO chats (telegram_user_id, title) VALUES ($1, $2) RETURNING id",
                user_id,
                title
            )
            
            return chat_id
        finally:
            await conn.close()
            

async def save_message(chat_id, role, content):
    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    
    try:
        await conn.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES ($1, $2, $3)",
            chat_id,
            role,
            content
        )
    finally:
        await conn.close()

        
async def get_last_chat(user_id):
    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    
    try:
        return await conn.fetchval(
            "SELECT id FROM chats WHERE telegram_user_id = $1 ORDER BY id DESC LIMIT 1",
            user_id
        )
    finally:
        await conn.close()
        
        
async def get_user_chats(user_id):
    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    
    try:
        return await conn.fetch(
            """
            SELECT c.id, c.title
            FROM chats c
            WHERE c.telegram_user_id = $1
            AND EXISTS (
                SELECT 1
                FROM messages m
                WHERE m.chat_id = c.id
            )
            ORDER BY c.id DESC
            """,
            user_id
        )
    finally:
        await conn.close()
        
async def delete_user_history(user_id):
    conn = await asyncpg.connect(
       host=os.getenv("DB_HOST"),
       port=int(os.getenv("DB_PORT")),
       database=os.getenv("DB_NAME"),
       user=os.getenv("DB_USER"),
       password=os.getenv("DB_PASSWORD") 
    )
    
    try:
        async with conn.transaction():
            await conn.execute(
                """
                DELETE FROM messages
                WHERE chat_id IN (
                    SELECT id FROM chats
                    WHERE telegram_user_id = $1
                )
                """,
                user_id 
            )
            
            await conn.execute(
                "DELETE FROM chats WHERE telegram_user_id = $1",
                user_id
            )
    finally:
        await conn.close()
        
async def get_chat_messages(chat_id, user_id):
    conn = await asyncpg.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    
    try:
        return await conn.fetch(
            """
            SELECT m.role, m.content
            FROM messages m
            JOIN chats c ON c.id = m.chat_id
            WHERE c.id = $1 AND c.telegram_user_id = $2
            ORDER BY m.id ASC
            """,
            chat_id,
            user_id
        )
    finally:
        await conn.close()