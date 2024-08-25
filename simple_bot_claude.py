import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters import Text
from dotenv import load_dotenv
from pydub import AudioSegment
import shutil

# Загрузка переменных окружения
load_dotenv()

# Константы
BOT_TOKEN = os.getenv('BOT_TOKEN')
AUDIO_DIR = 'audio_files'
MAX_DURATION = 60
BUTTON_ADD_FRAGMENT = "Добавить ещё фрагмент"
BUTTON_LISTEN_RESULT = "Прослушать результат"
BUTTON_START_OVER = "Начать сначала"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Вспомогательные функции
def get_user_paths(user_id: int) -> tuple:
    user_dir = os.path.join(AUDIO_DIR, str(user_id))
    user_file = os.path.join(user_dir, 'combined.wav')
    return user_dir, user_file

async def get_audio_duration(file_path: str) -> int:
    audio = AudioSegment.from_file(file_path)
    return round(len(audio) / 1000)

async def combine_audio(existing_file: str, new_file: str) -> AudioSegment:
    existing_audio = AudioSegment.from_file(existing_file)
    new_audio = AudioSegment.from_file(new_file)
    return existing_audio + new_audio

def create_keyboard(*buttons) -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for button in buttons:
        markup.add(types.KeyboardButton(button))
    return markup

# Обработчики команд
@dp.message_handler(commands=['start'])
@dp.message_handler(Text(equals=BUTTON_START_OVER))
async def send_welcome(message: types.Message):
    user_dir, _ = get_user_paths(message.from_user.id)
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
    await message.reply("Запиши голосовое или отправь в чат аудио файл продолжительностью не более 60 секунд.")

@dp.message_handler(content_types=[types.ContentType.AUDIO, types.ContentType.VOICE])
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    user_dir, user_file = get_user_paths(user_id)

    await message.reply("Подождите немного, идёт загрузка файла...")

    os.makedirs(user_dir, exist_ok=True)

    if message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name
    else:
        file_id = message.voice.file_id
        file_name = f"voice_{message.message_id}.ogg"

    file = await bot.get_file(file_id)
    destination = os.path.join(user_dir, file_name)
    await bot.download_file(file.file_path, destination)

    duration = await get_audio_duration(destination)
    remaining_time = MAX_DURATION - (await get_audio_duration(user_file) if os.path.exists(user_file) else 0)

    if duration > remaining_time:
        os.remove(destination)
        await message.reply(f"Допустимая длина аудио в {remaining_time} секунд превышена. Пожалуйста, попробуйте ещё раз.")
        return

    if os.path.exists(user_file):
        combined_audio = await combine_audio(user_file, destination)
    else:
        combined_audio = AudioSegment.from_file(destination)

    combined_audio.export(user_file, format="wav")

    for file in os.listdir(user_dir):
        if file != 'combined.wav':
            os.remove(os.path.join(user_dir, file))

    markup = create_keyboard(BUTTON_ADD_FRAGMENT, BUTTON_LISTEN_RESULT)
    await message.reply(f"Аудио фрагмент длиной {duration} секунд сохранен.", reply_markup=markup)

@dp.message_handler(Text(equals=BUTTON_LISTEN_RESULT))
async def send_combined_audio(message: types.Message):
    _, user_file = get_user_paths(message.from_user.id)

    if os.path.exists(user_file):
        await message.reply("Подождите немного, идёт подготовка файла...")
        markup = create_keyboard(BUTTON_ADD_FRAGMENT, BUTTON_START_OVER)
        
        with open(user_file, 'rb') as audio_file:
            await message.reply_audio(audio_file, reply_markup=markup)
    else:
        await message.reply("Итоговый файл отсутствует. Пожалуйста, добавьте хотя бы один фрагмент.")

@dp.message_handler(Text(equals=BUTTON_ADD_FRAGMENT))
async def prompt_additional_fragment(message: types.Message):
    _, user_file = get_user_paths(message.from_user.id)
    remaining_time = MAX_DURATION - (await get_audio_duration(user_file) if os.path.exists(user_file) else 0)
    await message.reply(f"Запиши голосовое или отправь в чат аудио файл продолжительностью не более {remaining_time} секунд.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)