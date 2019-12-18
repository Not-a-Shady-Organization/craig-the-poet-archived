
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

from subprocess import check_output
import argparse
import os
from shutil import copyfile

from utils import makedir, clean_word, download_image_from_url, LogDecorator
from google_utils import find_entities, synthesize_text, transcribe_audio, interval_of, download_image, list_blobs
from ffmpeg_utils import create_slideshow, add_audio_to_video, change_audio_speed, media_to_mono_flac, resize_image

from Scraper import Scraper
from mutagen.mp3 import MP3


POSTS_DIRECTORY = './posts'

class DomainError(Exception):
    pass

class NoEntitiesInTTS(Exception):
    pass

'''
def next_log_file(directory):
    files = os.listdir(directory)
    if files:
        greatest_num = max([int(filename.replace('log-', '').replace('.txt', '')) for filename in files])
        return f'log-{greatest_num+1}.txt'
    return f'log-{0}.txt'
'''

def next_log_file(log_directory):
    files = os.listdir(log_directory)
    if files:
        greatest_num = max([int(filename.replace('log-', '').replace('.txt', '')) for filename in files])
        return f'log-{greatest_num+1}.txt'
    return 'log-0.txt'


def create_poetry(title, body):
    # Make directories to store files for post
    clean_title = clean_word(title)
    post_subdirectory = f'{POSTS_DIRECTORY}/{clean_title}'
    makedir(post_subdirectory)


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
    body_tts_audio = f'{post_subdirectory}/audio/body.mp3'
    synthesize_text(
        body,
        body_tts_audio,
        name='en-IN-Wavenet-B',
        pitch=-1,
        speaking_rate=0.8,
    )

    # Slow the TTS voice further
    change_audio_speed(f'{post_subdirectory}/audio/body.mp3', .9, f'{post_subdirectory}/audio/body-90-percent.mp3')

    # Find audio length
    audio = MP3(f'{post_subdirectory}/audio/body-90-percent.mp3')
    audio_length = audio.info.length

    # Setup for transcription
    audio_filepath = f'{post_subdirectory}/audio/body-90-percent.mp3'
    flac_audio_filepath = f'{post_subdirectory}/audio/body.flac'

    # Transcribe the audio to learn when words are said
    media_to_mono_flac(audio_filepath, flac_audio_filepath)
    transcription = transcribe_audio(flac_audio_filepath)

    # TODO: Probably don't toss out words we can detect in speech.. Make estimates
    entity_intervals = dict()
    for entity in entities:
        interval = interval_of(entity.name, transcription)
        if interval != None:
            entity_intervals[entity.name] = interval_of(entity.name, transcription)

    entity_information = dict()
    for word, interval in entity_intervals.items():
        image_filepath = download_image(word, f'{post_subdirectory}/images', f'{word}')

        entity_information[word] = {
            'image_filepath': f'{image_filepath}',
            'interval': interval
        }

    # Copy to frames directory to record selections for video
    makedir(f'{post_subdirectory}/images/frames')
    for word, info in entity_information.items():
        resize_image(f'{post_subdirectory}/images/{info["image_filepath"]}', 1920, 1080, f'{post_subdirectory}/images/frames/{word}.jpg')
#        copyfile(f'{post_subdirectory}/images/{info["image_filepath"]}', f'{post_subdirectory}/images/frames/{word}.jpg')

    no_audio_output_filepath = f'{post_subdirectory}/video/no_audio_poem.mp4'
    output_filepath = f'{post_subdirectory}/video/poem.mp4'
    concat_filepath = f'{post_subdirectory}/video/concat.txt'

    # Sort entities by occurance in the source text
    entity_information_list = sorted(list(entity_information.items()), key=lambda x: body.index(' ' + x[0]))

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
            end = audio_length
        image_intervals += [(name, start, end)]


    if image_intervals == []:
        raise NoEntitiesInTTS('No entities were successfully found in the TTS audio.')

    image_information = []
    for (word, start, end) in image_intervals:
        image_information.append((word, start, end, f'../images/frames/{word}.jpg'))

    # Create slideshow
    write_concat_file(concat_filepath, image_information)
    create_slideshow(concat_filepath, no_audio_output_filepath)

    # Add audio to slideshow
    add_audio_to_video(no_audio_output_filepath, audio_filepath, output_filepath)

@LogDecorator()
def write_concat_file(concat_filepath, image_information):
    with open(concat_filepath, 'w') as f:
        f.write('ffconcat version 1.0\n')
        for (word, start, end, filepath) in image_information:
            f.write(f'file {filepath}\n')
            f.write(f'duration {end - start}\n')


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
