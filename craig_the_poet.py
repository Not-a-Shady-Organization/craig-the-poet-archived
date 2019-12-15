
# Setup for logging
import logging

import argparse
import os
from shutil import copyfile

from utils import makedir, clean_word
from google_utils import find_entities, synthesize_text, transcribe_audio, interval_of, download_image
from ffmpeg_utils import create_slideshow, add_audio_to_video, change_audio_speed, video_to_flac

from Scraper import Scraper
from mutagen.mp3 import MP3


POSTS_DIRECTORY = './posts'

class DomainError(Exception):
    pass

class NoEntitiesInTTS(Exception):
    pass


def next_log_file(directory):
    files = os.listdir(directory)
    if files:
        greatest_num = max([int(filename.replace('log-', '').replace('.txt', '')) for filename in files])
        return f'log-{greatest_num+1}.txt'
    return f'log-{0}.txt'

def create_poetry(title, body):
    # Make directories to store files for post
    clean_title = clean_word(title)
    post_subdirectory = f'{POSTS_DIRECTORY}/{clean_title}'
    makedir(post_subdirectory)

    makedir(f'{post_subdirectory}/logs')
    log_filename = next_log_file(f'{post_subdirectory}/logs')

    # Setup for logging
    LOG_FILEPATH = f'{post_subdirectory}/logs/{log_filename}'
    logging.basicConfig(filename=LOG_FILEPATH, level=logging.DEBUG)
    import LogDecorator

    makedir(f'{post_subdirectory}/audio')
    makedir(f'{post_subdirectory}/images')
    makedir(f'{post_subdirectory}/text')
    makedir(f'{post_subdirectory}/video')

    # Write the post's full text to file
    with open(f'{post_subdirectory}/text/post.txt', 'w') as f:
        f.write(title + '\n')
        f.write(body)

    # Find entities in body and write to file for records
    entities = find_entities(body)
    with open(f'{post_subdirectory}/text/entities.txt', 'w') as f:
        logging.info(f'Entities detected: {[e.name for e in entities]}')
        for entity in entities:
            f.write(str(entity))

    # TTS on both title and body
    title_tts_audio = f'{post_subdirectory}/audio/title.mp3'
    body_tts_audio = f'{post_subdirectory}/audio/body.mp3'
    synthesize_text(title, title_tts_audio)
    synthesize_text(body, body_tts_audio)

    # Slow the TTS voice further
    change_audio_speed(f'{post_subdirectory}/audio/title.mp3', .9, f'{post_subdirectory}/audio/title-90-percent.mp3')
    change_audio_speed(f'{post_subdirectory}/audio/body.mp3', .9, f'{post_subdirectory}/audio/body-90-percent.mp3')

    # Find audio length
    audio = MP3(f'{post_subdirectory}/audio/body-90-percent.mp3')
    audio_length = audio.info.length

    # Setup for transcription
    audio_filepath = f'{post_subdirectory}/audio/body-90-percent.mp3'
    flac_audio_filepath = f'{post_subdirectory}/audio/body.flac'

    # Transcribe the audio to learn when words are said
    video_to_flac(audio_filepath, flac_audio_filepath)
    transcription = transcribe_audio(flac_audio_filepath)


    # TODO: Probably don't toss out words we can detect in speech.. Make estimates
    word_intervals = dict()
    for entity in entities:
        interval = interval_of(entity.name, transcription)
        if interval != None:
            word_intervals[entity.name] = interval_of(entity.name, transcription)

    word_information = dict()
    for word, interval in word_intervals.items():
        image_filepath = download_image(word, f'{post_subdirectory}/images', f'{word}')

        word_information[word] = {
            'image_filepath': f'{image_filepath}',
            'interval': interval
        }

    print(word_information)

    # Copy to frames directory to record selections for video
    makedir(f'{post_subdirectory}/images/frames')
    for word, info in word_information.items():
        copyfile(f'{post_subdirectory}/images/{info["image_filepath"]}', f'{post_subdirectory}/images/frames/{word}.jpg')


    no_audio_output_filepath = f'{post_subdirectory}/video/no_audio_poem.mp4'
    output_filepath = f'{post_subdirectory}/video/poem.mp4'
    concat_filepath = f'{post_subdirectory}/video/concat.txt'

    # Create no audio slideshow
    image_intervals = []
    word_information_list = sorted(list(word_information.items()), key=lambda x: body.index(' ' + x[0]))
    for name, info in word_information_list:
        print(name, body.index(' ' + name))
    print(body)
    print(word_information_list)

    for i, (name, info) in enumerate(word_information_list):
        if i == 0:
            start = 0
        else:
            start = word_information_list[i][1]['interval'][0]

        if i != len(word_information)-1:
            end = word_information_list[i+1][1]['interval'][0]
        else:
            end = audio_length
        image_intervals += [(name, start, end)]

    if image_intervals == []:
        raise NoEntitiesInTTS('No entities were successfully found in the TTS audio.')


    # WRITE CONCAT FILE
    with open(concat_filepath, 'w') as f:
        f.write('ffconcat version 1.0\n')
        for (word, start, end) in image_intervals:
            f.write(f'file ../images/{word_information[word]["image_filepath"]}\n')
            f.write(f'duration {end - start}\n')

    create_slideshow(concat_filepath, no_audio_output_filepath)
    add_audio_to_video(no_audio_output_filepath, audio_filepath, output_filepath)





if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    args = parser.parse_args()

    scraper = Scraper(args.url)
    create_poetry(scraper.title, scraper.body)
