import srt
import telebot
from telebot import types
import os.path
from moviepy.editor import VideoFileClip, CompositeVideoClip
from moviepy.video.tools.subtitles import SubtitlesClip
import subprocess
import numpy as np
import soundfile as sf
import json
import wave
from scipy.signal import wiener
from vosk import Model, KaldiRecognizer
import librosa
import conf
import fuctions


TOKEN = conf.BOT_TOKEN

bot = telebot.TeleBot(TOKEN)
print("Бот был запущен!")

users_in_work = set()


@bot.message_handler(commands=['start'])  # сообщение при старте
def send_welcome(message):
    bot.send_message(message.chat.id, "Старт 0_0")


@bot.message_handler(content_types=['video'])
def send_text(message):
    src = f"videos/{message.from_user.id}.mp4"
    if (((message.video.file_size) / 1024) / 1024) < conf.MAX_FILE_SIZE and os.path.isfile(src) == False:
        bot.send_message(message.chat.id, 'Сохраняется, прошлое видео будет удалено')
        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(src, 'wb') as new_file:
            new_file.write(downloaded_file)

        if fuctions.get_length(src) < conf.MAX_VIDEO_DURATION:
            bot.reply_to(message, "Успешно сохранено!")
            proc_numb = 6
            bot.send_message(message.chat.id, f'Начинается этап 1/{proc_numb} \nОтсоедиенение аудио')
            src_audio = f"videos/{message.from_user.id}.mp3"
            fuctions.extract_audio(src, src_audio)
            passed = 1

            if passed == 1:
                bot.send_message(message.chat.id, f'Начинается этап 2/{proc_numb} \nУдаление шума')

                fuctions.remove_noise(src_audio, f"videos/{message.from_user.id}_dn.mp3")
                passed = 2
                os.remove(src_audio)

            if passed == 2:
                bot.send_message(message.chat.id, f'Начинается этап 3/{proc_numb} \nКонвертация аудио')
                fuctions.convert_mp3_to_wav(f"videos/{message.from_user.id}_dn.mp3", f"videos/{message.from_user.id}_dn.wav")
                passed = 3
                os.remove(f"videos/{message.from_user.id}_dn.mp3")

            if passed == 3:
                bot.send_message(message.chat.id,
                                 f'Начинается этап 4/{proc_numb} \nРаспознование речи \nЭто займет до пяти минут\n')
                recogniz = fuctions.recognize_audio(f"videos/{message.from_user.id}_dn.wav", conf.MODEL_NAME)
                os.remove(f"videos/{message.from_user.id}_dn.wav")
                passed = 4

            if passed == 4:
                bot.send_message(message.chat.id, f'Начинается этап 5/{proc_numb} \nГенерация субтитров')
                fuctions.generate_srt_file(recogniz, f"videos/{message.from_user.id}_subs.srt")
                with open(f"videos/{message.from_user.id}_subs.srt", 'rb') as file:
                    bot.send_document(message.chat.id, file,
                                      caption=os.path.basename(f"videos/{message.from_user.id}_subs.srt"))
                bot.send_message(message.chat.id, f'Генерация субтитров завершена')
                passed = 5

            if passed == 5:
                bot.send_message(message.chat.id, f'Начинается этап 6/{proc_numb} \nВшивание субтитров в видео')
                result_file = f"videos/result_{message.from_user.id}.mp4"
                fuctions.add_subtitles_to_video(src, f"videos/{message.from_user.id}_subs.srt", result_file)
                with open(result_file, 'rb') as video:
                    bot.send_video(message.chat.id, video, caption=os.path.basename(result_file))
                bot.send_message(message.chat.id, f'Завершено! \nДля повторения процесса отправьте новое видео!')
                os.remove(result_file)
                os.remove(f"videos/{message.from_user.id}_subs.srt")

            os.remove(src)
        else:
            bot.reply_to(message, "Слишком длинное видео!")

    else:
        if (os.path.isfile(src)):
            bot.reply_to(message, "Другое видео в обработке!")
        else:
            bot.reply_to(message, "Слишком большое видео!")


bot.polling()
