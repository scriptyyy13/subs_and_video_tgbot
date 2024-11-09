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