
'''
-- TODO --
Toss poems which contain few entities
Toss poems which contain long held entities
Try interpolation for None interval entities
Add ability to insert image manually
Add pauses

'''


# Setup for logging
import logging
from contextlib import redirect_stdout

from subprocess import check_output
import io
import argparse
import os
from shutil import copyfile

from utils import makedir, clean_word, download_image_from_url, LogDecorator, text_to_image
from google_utils import find_entities, synthesize_text, transcribe_audio, interval_of, download_image, list_blobs
from ffmpeg_utils import create_slideshow, add_audio_to_video, change_audio_speed, media_to_mono_flac, resize_image, fade_in_fade_out

from Scraper import Scraper
from mutagen.mp3 import MP3


POSTS_DIRECTORY = './posts'

class DomainError(Exception):
    pass

class NoEntitiesInTTS(Exception):
    pass


def next_log_file(log_directory):
    files = os.listdir(log_directory)
    if files:
        greatest_num = max([int(filename.replace('log-', '').replace('.txt', '')) for filename in files])
        return f'log-{greatest_num+1}.txt'
    return 'log-0.txt'


def get_filenames(post_subdirectory):
    return {
        'image_dir': f'{post_subdirectory}/image',
        'frame_dir': f'{post_subdirectory}/image/frame',
        'relative_frame_dir': '../image/frame',

        'post.txt': f'{post_subdirectory}/text/post.txt',
        'entities.txt': f'{post_subdirectory}/text/entities.txt',

        'tts-title.mp3': f'{post_subdirectory}/audio/tts-title.mp3',
        'tts-title-rate-RATE.mp3': f'{post_subdirectory}/audio/tts-title-rate-RATE.mp3',
        'tts-title-rate-RATE.flac': f'{post_subdirectory}/audio/tts-title-rate-RATE.mp3',

        'tts-body.mp3': f'{post_subdirectory}/audio/tts-body.mp3',
        'tts-body-rate-RATE.mp3': f'{post_subdirectory}/audio/tts-body-rate-RATE.mp3',
        'tts-body-rate-RATE.flac': f'{post_subdirectory}/audio/tts-body-rate-RATE.flac',

        'body-slideshow.mp4': f'{post_subdirectory}/video/body-slideshow.mp4',
        'body-slideshow-with-audio.mp4': f'{post_subdirectory}/video/body-slideshow-with-audio.mp4',
        'body-slideshow-with-audio-and-fades.mp4': f'{post_subdirectory}/video/body-slideshow-with-audio-and-fades.mp4',
        'body-concat.txt': f'{post_subdirectory}/video/body-concat.txt',

        'title-frame.jpg': f'{post_subdirectory}/image/frame/title-frame.jpg',
        'title-frame-full.jpg': f'{post_subdirectory}/image/frame/title-frame-full.jpg',
        'relative title-frame-full.jpg': f'../image/frame/title-frame-full.jpg',

        'title-slideshow.mp4': f'{post_subdirectory}/video/title-slideshow.mp4',
        'title-slideshow-with-audio.mp4': f'{post_subdirectory}/video/title-slideshow-with-audio.mp4',
        'title-slideshow-with-audio-and-fades.mp4': f'{post_subdirectory}/video/title-slideshow-with-audio-and-fades.mp4',
        'title-concat.txt': f'{post_subdirectory}/video/title-concat.txt',

        'poem-concat.txt': f'{post_subdirectory}/video/poem-concat.txt',
        'poem.mp4': f'{post_subdirectory}/video/poem.mp4'
    }
    pass



def create_file_structure(post_subdirectory):
    makedir(post_subdirectory)
    makedir(f'{post_subdirectory}/audio')
    makedir(f'{post_subdirectory}/image')
    makedir(f'{post_subdirectory}/text')
    makedir(f'{post_subdirectory}/video')
    makedir(f'{post_subdirectory}/image/frame')




def create_poetry(title, body):
    # Make directories to store files for post
    clean_title = clean_word(title)
    post_subdirectory = f'{POSTS_DIRECTORY}/{clean_title}'

    # Create directories and filenames
    create_file_structure(post_subdirectory)
    file_map = get_filenames(post_subdirectory)

    # Write the post's full text to file
    with open(file_map['post.txt'], 'w') as f:
        f.write(title + '\n')
        f.write(body)

    # Find entities in body and write to file for records
    entities = find_entities(body)
    with open(file_map['entities.txt'], 'w') as f:
        logging.info(f'Entities detected: {[e.name for e in entities]}')
        for entity in entities:
            f.write(str(entity))

    # TTS on both title and body
    synthesize_text(
        title,
        file_map['tts-title.mp3'],
        name='en-IN-Wavenet-B',
        pitch=-1,
        speaking_rate=0.8,
    )

    synthesize_text(
        body,
        file_map['tts-body.mp3'],
        name='en-IN-Wavenet-B',
        pitch=-1,
        speaking_rate=0.8,
    )

    # Slow the TTS voice further
    title_rate = 0.9
    change_audio_speed(
        file_map['tts-title.mp3'],
        title_rate,
        file_map['tts-title-rate-RATE.mp3'].replace('RATE', str(title_rate))
    )

    body_rate = 0.9
    change_audio_speed(
        file_map['tts-body.mp3'],
        body_rate,
        file_map['tts-body-rate-RATE.mp3'].replace('RATE', str(body_rate))
    )

    # Find audio length
    title_audio = MP3(file_map['tts-title-rate-RATE.mp3'].replace('RATE', str(title_rate)))
    title_audio_length = title_audio.info.length
    body_audio = MP3(file_map['tts-body-rate-RATE.mp3'].replace('RATE', str(body_rate)))
    body_audio_length = body_audio.info.length

    # Transcribe the audio to learn when words are said
    media_to_mono_flac(
        file_map['tts-body-rate-RATE.mp3'].replace('RATE', str(body_rate)),
        file_map['tts-body-rate-RATE.flac'].replace('RATE', str(body_rate)),
    )
    transcription = transcribe_audio(file_map['tts-body-rate-RATE.flac'].replace('RATE', str(body_rate)))

    # TODO: Probably don't toss out words we can detect in speech.. Make estimates
    entity_intervals = dict()
    for entity in entities:
        interval = interval_of(entity.name, transcription)
        if interval != None:
            entity_intervals[entity.name] = interval_of(entity.name, transcription)

    entity_information = dict()
    for word, interval in entity_intervals.items():
        image_filepath = download_image(word, file_map['image_dir'], f'{word}')

        entity_information[word] = {
            'image_filepath': f'{image_filepath}',
            'interval': interval
        }

    # Copy to frames directory to record selections for video
    for word, info in entity_information.items():
        resize_image(f'{file_map["image_dir"]}/{info["image_filepath"]}', 1920, 1080, f'{file_map["frame_dir"]}/{word}.jpg')

    # Sort entities by occurance in the source text
    def find_word(word, text):
        try:
            return body.index(' ' + word)
        except ValueError:
            return body.index(word)
    entity_information_list = sorted(list(entity_information.items()), key=lambda x: find_word(x[0], body))

    # Create no audio slideshow
    image_intervals = []
    for i, (name, info) in enumerate(entity_information_list):
        if i == 0:
            start = 0
        else:
            start = entity_information_list[i][1]['interval'][0]

        if i != len(entity_information)-1:
            end = entity_information_list[i+1][1]['interval'][0]
        else:
            end = body_audio_length
        image_intervals += [(name, start, end)]

    if image_intervals == []:
        raise NoEntitiesInTTS('No entities were successfully found in the TTS audio.')

    image_information = []
    for (word, start, end) in image_intervals:
        image_information.append((word, start, end, f"{file_map['relative_frame_dir']}/{word}.jpg"))

    # Create slideshow
    write_concat_file(file_map['body-concat.txt'], image_information)
    create_slideshow(file_map['body-concat.txt'], file_map['body-slideshow.mp4'])

    # Add audio to slideshow
    add_audio_to_video(
        file_map['body-slideshow.mp4'],
        file_map['tts-body-rate-RATE.mp3'].replace('RATE', str(body_rate)),
        file_map['body-slideshow-with-audio.mp4']
    )

    # Text to image the title & resize
    text_to_image(title, file_map['title-frame.jpg'])
    resize_image(file_map['title-frame.jpg'], 1920, 1080, file_map['title-frame-full.jpg'])

    # Create title card slideshow
    title_information = [('title', 0, title_audio_length + 1, file_map['relative title-frame-full.jpg'])]
    write_concat_file(file_map['title-concat.txt'], title_information)
    create_slideshow(file_map['title-concat.txt'], file_map['title-slideshow.mp4'])
    add_audio_to_video(
        file_map['title-slideshow.mp4'],
        file_map['tts-title-rate-RATE.mp3'].replace('RATE', str(title_rate)),
        file_map['title-slideshow-with-audio.mp4']
    )

    fade_length = 0.3
    fade_in_fade_out(file_map['title-slideshow-with-audio.mp4'], fade_length, file_map['title-slideshow-with-audio-and-fades.mp4'])
    fade_in_fade_out(file_map['body-slideshow-with-audio.mp4'], fade_length, file_map['body-slideshow-with-audio-and-fades.mp4'])

    with open(file_map['poem-concat.txt'], 'w') as f:
        f.write(f"file 'title-slideshow-with-audio-and-fades.mp4'\n")
        f.write(f"file 'body-slideshow-with-audio-and-fades.mp4'\n")
    command = f"ffmpeg -y -safe 0 -f concat -i {file_map['poem-concat.txt']} -vcodec copy -acodec copy {file_map['poem.mp4']}"
    check_output(command, shell=True)



@LogDecorator()
def write_concat_file(concat_filepath, image_information):
    with open(concat_filepath, 'w') as f:
        f.write('ffconcat version 1.0\n')
        for (word, start, end, filepath) in image_information:
            f.write(f'file {filepath}\n')
            f.write(f'duration {end - start}\n')

        # BUG: This is the source of some miss timing on images & corruption for YouTube
        # Audio gets misaligned because this file is longer in video than expected
        # Concating seems to advance audio if the track is null Need to set the track to not null
        f.write(f'file {filepath}\n')


@LogDecorator()
def get_craigslist_ad(city, min_word_count=20):
    # Retreive and filter blobs
    blobs = list_blobs('craig-the-poet')
    fresh_city_blobs = [blob for blob in blobs if f'craigslist/{city}' in blob.name and blob.metadata['used'] == 'false']

    for blob in fresh_city_blobs:
        text = blob.download_as_string().decode("utf-8")
        words = text.split()
        if len(words) >= min_word_count:
            splitted = text.split('\n')
            title = splitted[0]
            body = '\n'.join(splitted[1:])
            return {'blob': blob, 'title': title, 'body': body}
    return None



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('city')
    args = parser.parse_args()

    # Setup for logging
    makedir(f'logs')
    log_filename = next_log_file(f'logs')
    LOG_FILEPATH = f'logs/{log_filename}'
    logging.basicConfig(filename=LOG_FILEPATH, level=logging.DEBUG)
    import LogDecorator

    city = args.city
    logging.info(f'Starting program on subject city {city}')
    obj = get_craigslist_ad(city)
    if not obj:
        logging.info(f'No ads left for {city}. Exiting...')
        exit()

    logging.info(f"Ad retreived: \n\tTitle: {obj['title']} \n\tBody: {obj['body']}\n")
    create_poetry(obj['title'], obj['body'])

    logging.info(f"Poem successfully created. Ad blob {obj['blob'].name} marked as used.")

    # TODO: Assume poem was successful and mark ad as used
    blob = obj['blob']
    blob.metadata = {'used': 'true'}
    blob.patch()
