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


def add_subtitles_to_video(video_file, subtitle_file, output_file):
    # Формируем команду для FFmpeg
    command = f"ffmpeg -i {video_file} -vf subtitles={subtitle_file} {output_file}"

    # Выполняем команду
    subprocess.call(command, shell=True)


def generate_srt_file(data, output_file, max_words_per_line=4):
    all_data = [{"result": []}]
    for i in range(len(data)):
        all_data[0]["result"].extend(data[i]["result"])
        print(data[i]["result"])
    print(all_data)
    def group_words(data, max_words_per_line):
        groups = []
        current_group = []
        for word_data in data:
            if len(current_group) < max_words_per_line:
                current_group.append(word_data)
            else:
                groups.append(current_group)
                current_group = [word_data]
        if current_group:
            groups.append(current_group)
        return groups

    def format_srt_line(group, count):
        def format_time(time_ms):
            seconds, milliseconds = divmod(time_ms, 1000)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

        start_time = format_time(int(group[0]['start'] * 1000))
        end_time = format_time(int(group[-1]['end'] * 1000))
        text = ' '.join(word['word'] for word in group)
        return f"{count}\n{start_time} --> {end_time}\n{text}\n\n"

    groups = group_words(all_data[0]['result'], max_words_per_line)
    with open(output_file, 'w', encoding='utf-8') as f:
        count = 1
        for group in groups:
            f.write(format_srt_line(group, count))
            count += 1


def convert_mp3_to_wav(input_file, output_file):
    y, sr = librosa.load(input_file)
    sf.write(output_file, y, sr, subtype='pcm_16')


def extract_audio(video_path, output_path):
    video_clip = VideoFileClip(video_path)
    audio_clip = video_clip.audio
    audio_clip.write_audiofile(output_path)
    video_clip.close()
    audio_clip.close()


def get_length(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    return float(result.stdout)


def remove_noise(input_audio_file, output_file):  # Функция для удаления шумов из аудиофайла.
    audio_data, sample_rate = sf.read(input_audio_file)  # Считывание аудиоданных и частоты дискретизации из файла
    if len(audio_data.shape) > 1:  # Проверка на многоканальность: если аудиофайл имеет несколько каналов, усредняем их
        audio_data = np.mean(audio_data, axis=1)
    processed_audio = wiener(audio_data)  # Применение метода Винера для удаления шумов и улучшения качества звука
    sf.write(output_file, processed_audio, sample_rate)  # Сохранение обработанного звука в новый файл


def recognize_audio(input_audio_file,
                    model_path):  # Функция для распознавания речи в аудиофайле с использованием модели.
    model = Model(model_path)  # Инициализация модели для распознавания
    with wave.open(input_audio_file, "rb") as wf:  # Открытие аудиофайла для чтения
        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)
        results = []
        while True:  # Обработка аудиоданных по частям и запись результатов распознавания
            data = wf.readframes(16000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                part_result = json.loads(rec.Result())
                # print(part_result)
                results.append(part_result)
        part_result = json.loads(rec.FinalResult())  # Получение окончательного результата распознавания
        results.append(part_result)
        print(results)
        return results

import conf
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

        if get_length(src) < conf.MAX_VIDEO_DURATION:
            bot.reply_to(message, "Успешно сохранено!")
            proc_numb = 6
            bot.send_message(message.chat.id, f'Начинается этап 1/{proc_numb} \nОтсоедиенение аудио')
            src_audio = f"videos/{message.from_user.id}.mp3"
            extract_audio(src, src_audio)
            passed = 1

            if passed == 1:
                bot.send_message(message.chat.id, f'Начинается этап 2/{proc_numb} \nУдаление шума')

                remove_noise(src_audio, f"videos/{message.from_user.id}_dn.mp3")
                passed = 2
                os.remove(src_audio)

            if passed == 2:
                bot.send_message(message.chat.id, f'Начинается этап 3/{proc_numb} \nКонвертация аудио')
                convert_mp3_to_wav(f"videos/{message.from_user.id}_dn.mp3", f"videos/{message.from_user.id}_dn.wav")
                passed = 3
                os.remove(f"videos/{message.from_user.id}_dn.mp3")

            if passed == 3:
                bot.send_message(message.chat.id,
                                 f'Начинается этап 4/{proc_numb} \nРаспознование речи \nЭто займет до пяти минут\n')
                recogniz = recognize_audio(f"videos/{message.from_user.id}_dn.wav", f"models/vosk-model-ru-0.42")
                os.remove(f"videos/{message.from_user.id}_dn.wav")
                passed = 4

            if passed == 4:
                bot.send_message(message.chat.id, f'Начинается этап 5/{proc_numb} \nГенерация субтитров')
                generate_srt_file(recogniz, f"videos/{message.from_user.id}_subs.srt")
                with open(f"videos/{message.from_user.id}_subs.srt", 'rb') as file:
                    bot.send_document(message.chat.id, file,
                                      caption=os.path.basename(f"videos/{message.from_user.id}_subs.srt"))
                bot.send_message(message.chat.id, f'Генерация субтитров завершена')
                passed = 5

            if passed == 5:
                bot.send_message(message.chat.id, f'Начинается этап 6/{proc_numb} \nВшивание субтитров в видео')
                result_file = f"videos/result_{message.from_user.id}.mp4"
                add_subtitles_to_video(src, f"videos/{message.from_user.id}_subs.srt", result_file)
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
