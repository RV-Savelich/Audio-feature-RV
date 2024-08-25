import os
from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv
from pydub import AudioSegment

# Загрузка переменных окружения из файла .env
load_dotenv()

# Получение токена бота из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Путь к директории для хранения аудио
AUDIO_DIR = 'audio_files'

# Обработчик команды /start и кнопки "Начать сначала"
@dp.message_handler(commands=['start'])
@dp.message_handler(lambda message: message.text == "Начать сначала")
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    user_dir = os.path.join(AUDIO_DIR, str(user_id))
    user_file = os.path.join(user_dir, 'combined.wav')
    
    # Удаление всех файлов в папке пользователя и самой папки, если она пустая
    if os.path.exists(user_dir):
        for file in os.listdir(user_dir):
            os.remove(os.path.join(user_dir, file))
        
        try:
            os.rmdir(user_dir)  # Удаляет папку только если она пуста
        except OSError:
            pass  # Если папка не пустая, она не будет удалена

    await message.reply("Запиши голосовое или отправь в чат аудио файл продолжительностью не более 60 секунд.")

# Обработчик аудио сообщений
@dp.message_handler(content_types=[types.ContentType.AUDIO, types.ContentType.VOICE])
async def handle_audio(message: types.Message):
    user_id = message.from_user.id
    user_dir = os.path.join(AUDIO_DIR, str(user_id))
    user_file = os.path.join(user_dir, 'combined.wav')

    # Сообщение о начале загрузки
    await message.reply("Подождите немного, идёт загрузка файла...")

    # Создаем директорию для пользователя, если она не существует
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    
    # Получаем информацию о файле
    if message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name
        file_extension = os.path.splitext(file_name)[1] or '.ogg'
    else:  # Voice message
        file_id = message.voice.file_id
        file_name = f"voice_{message.message_id}.ogg"
        file_extension = '.ogg'
    
    # Скачиваем файл
    file = await bot.get_file(file_id)
    file_path = file.file_path
    
    destination = os.path.join(user_dir, file_name)
    await bot.download_file(file_path, destination)
    
    # Проверяем длительность аудио
    audio = AudioSegment.from_file(destination, format=file_extension[1:])
    duration_in_seconds = round(len(audio) / 1000)  # Округление до целого числа секунд
    
    # Оставшееся время
    if os.path.exists(user_file):
        combined_audio = AudioSegment.from_file(user_file)
        remaining_time = 60 - (round(len(combined_audio) / 1000))
    else:
        remaining_time = 60
    
    if duration_in_seconds > remaining_time:
        os.remove(destination)  # Удаляем файл, если он превышает допустимую длину
        await message.reply(f"Допустимая длина аудио в {remaining_time} секунд превышена. Пожалуйста, попробуйте ещё раз.")
    else:
        if os.path.exists(user_file):
            combined_audio = AudioSegment.from_file(user_file)
            combined_audio += audio
        else:
            combined_audio = audio

        combined_audio.export(user_file, format="wav")  # Сохраняем итоговый файл

        # Удаляем все фрагменты, кроме combined.wav
        for file in os.listdir(user_dir):
            if file != 'combined.wav':
                os.remove(os.path.join(user_dir, file))

        # Добавляем кнопки "Добавить фрагмент" и "Прослушать результат"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("Добавить ещё фрагмент"))
        markup.add(types.KeyboardButton("Прослушать результат"))

        remaining_time -= duration_in_seconds
        await message.reply(f"Аудио фрагмент длиной {duration_in_seconds} секунд сохранен.", reply_markup=markup)

# Обработчик кнопки "Прослушать результат"
@dp.message_handler(lambda message: message.text == "Прослушать результат")
async def send_combined_audio(message: types.Message):
    user_id = message.from_user.id
    user_file = os.path.join(AUDIO_DIR, str(user_id), 'combined.wav')

    if os.path.exists(user_file):
        # Сообщение о подготовке результата
        await message.reply("Подождите немного, идёт подготовка файла...")

        # Добавляем кнопки "Начать сначала" и "Добавить ещё фрагмент"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("Добавить ещё фрагмент"))
        markup.add(types.KeyboardButton("Начать сначала"))       

        # Отправляем итоговый аудиофайл пользователю
        with open(user_file, 'rb') as audio_file:
            await message.reply_audio(audio_file, reply_markup=markup)
    else:
        await message.reply("Итоговый файл отсутствует. Пожалуйста, добавьте хотя бы один фрагмент.")

# Обработчик кнопки "Добавить ещё фрагмент"
@dp.message_handler(lambda message: message.text == "Добавить ещё фрагмент")
async def prompt_additional_fragment(message: types.Message):
    user_id = message.from_user.id
    user_dir = os.path.join(AUDIO_DIR, str(user_id))
    user_file = os.path.join(user_dir, 'combined.wav')

    if os.path.exists(user_file):
        combined_audio = AudioSegment.from_file(user_file)
        remaining_time = 60 - (round(len(combined_audio) / 1000))
    else:
        remaining_time = 60

    await message.reply(f"Запиши голосовое или отправь в чат аудио файл продолжительностью не более {remaining_time} секунд.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
