
'''
-- TODO --
Toss poems which contain few entities
Toss poems which contain long held entities
Try interpolation for None interval entities
Add ability to insert image manually
Add pauses


Make videos of title and poem
Attach audio at proper spot

'''


# Setup for logging
import logging

from subprocess import check_output
import argparse
import os
from shutil import copyfile

from utils import makedir, clean_word, download_image_from_url, text_to_image
from google_utils import find_entities, synthesize_text, transcribe_audio, interval_of, download_image
from ffmpeg_utils import create_slideshow, add_audio_to_video, change_audio_speed, media_to_mono_flac, resize_image, fade_in_fade_out

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

    # Setup for logging
    makedir(f'{post_subdirectory}/logs')
    log_filename = next_log_file(f'{post_subdirectory}/logs')
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

    text_to_image(title, f'{post_subdirectory}/images/title.jpg')
    resize_image(f'{post_subdirectory}/images/title.jpg', 1920, 1080, f'{post_subdirectory}/images/title-full-size.jpg')

    # TTS on both title and body
    title_tts_audio = f'{post_subdirectory}/audio/title.mp3'
    synthesize_text(
        title,
        title_tts_audio,
        name='en-IN-Wavenet-B',
        pitch=-1,
        speaking_rate=0.7,
    )

    body_tts_audio = f'{post_subdirectory}/audio/body.mp3'
    synthesize_text(
        body,
        body_tts_audio,
        name='en-IN-Wavenet-B',
        pitch=-1,
        speaking_rate=0.8,
    )

    # Slow the TTS voice further
    change_audio_speed(f'{post_subdirectory}/audio/title.mp3', .9, f'{post_subdirectory}/audio/title-90-percent.mp3')
    change_audio_speed(f'{post_subdirectory}/audio/body.mp3', .9, f'{post_subdirectory}/audio/body-90-percent.mp3')

    # Find audio length
    audio = MP3(f'{post_subdirectory}/audio/title-90-percent.mp3')
    title_audio_length = audio.info.length

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

    # Resize and copy to frames directory to record selections for video
    makedir(f'{post_subdirectory}/images/frames')
    for word, info in entity_information.items():
        resize_image(f'{post_subdirectory}/images/{info["image_filepath"]}', 1920, 1080, f'{post_subdirectory}/images/frames/{word}.jpg')

    no_audio_output_filepath = f'{post_subdirectory}/video/no_audio_poem.mp4'
    output_filepath = f'{post_subdirectory}/video/poem_with_audio.mp4'
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

    video_approved = False
    while not video_approved:
        # Create slideshow
        write_concat_file(concat_filepath, image_information)
        create_slideshow(concat_filepath, no_audio_output_filepath)

        # Add audio to slideshow
        add_audio_to_video(no_audio_output_filepath, audio_filepath, output_filepath)

        # Watch video
        check_output(f'open {output_filepath}'.split())

        answer = input('Do you like the current slides? ').lower()
        if answer == 'y':
            video_approved = True
            continue

        entity_to_replace = ''
        while entity_to_replace not in [x[0] for x in image_intervals]:
            print(f'In order, entities were... {[x[0] for x in image_intervals]}')
            entity_to_replace = input('Which entity\'s image should be replaced? ')

        url = input('URL of replacing image: ')
        download_image_from_url(url, f'{post_subdirectory}/images/{entity_to_replace}/manually-added.jpg')
        resize_image( f'{post_subdirectory}/images/{entity_to_replace}/manually-added.jpg', 1920, 1080,  f'{post_subdirectory}/images/frames/{entity_to_replace}.jpg')


    answer = input('Do you want to add a slide? ').lower()[0]
    video_approved = answer != 'y'
    while not video_approved:
        url = input('URL of replacing image: ')
        makedir(f'{post_subdirectory}/images/manually-added')
        download_image_from_url(url, f'{post_subdirectory}/images/manually-added/manually-added.jpg')
        resize_image( f'{post_subdirectory}/images/manually-added/manually-added.jpg', 1920, 1080,  f'{post_subdirectory}/images/frames/manually-added.jpg')

        insert_start = float(input('Start time for new image: '))
        insert_end = float(input('End time for new image: '))

        new_image_information = []
        for word, start, end, filepath in image_information:
            # If inserted image begins within this image's time
            if insert_start > start and insert_start < end:
                new_image_information.append((word, start, insert_start, filepath))
                new_image_information.append(('manually-added', insert_start, insert_end, f'../images/frames/manually-added.jpg'))
            # If inserted image ends within this image's time
            elif insert_end > start and insert_end < end:
                new_image_information.append((word, insert_end, end, filepath))
            else:
                new_image_information.append((word, start, end, filepath))
        image_information = new_image_information

        # Create slideshow
        write_concat_file(concat_filepath, image_information)
        create_slideshow(concat_filepath, no_audio_output_filepath)

        # Add audio to slideshow
        add_audio_to_video(no_audio_output_filepath, audio_filepath, output_filepath)

        # Watch video
        check_output(f'open {output_filepath}'.split())

        answer = input('Do you want to add a slide? ').lower()[0]
        video_approved = answer != 'y'

    fade_in_fade_out(output_filepath, .4, f'{post_subdirectory}/video/poem-body-fades.mp4')

    # Create title slideshow
    title_concat_filepath = f'{post_subdirectory}/video/concat_title.txt'
    no_audio_output_title_filepath = f'{post_subdirectory}/video/no_audio_title.mp4'
    title_with_audio_filepath = f'{post_subdirectory}/video/title_with_audio.mp4'
    title_output_filepath = f'{post_subdirectory}/video/title.mp4'
    title_image_information = [('title', 0, title_audio_length + 1.5, f'../images/title-full-size.jpg')]
    write_concat_file(title_concat_filepath, title_image_information)
    create_slideshow(title_concat_filepath, no_audio_output_title_filepath)
    add_audio_to_video(no_audio_output_title_filepath, f'{post_subdirectory}/audio/title-90-percent.mp3', title_with_audio_filepath)
    fade_in_fade_out(title_with_audio_filepath, 0.4, title_output_filepath)




def write_concat_file(concat_filepath, image_information):
    with open(concat_filepath, 'w') as f:
        f.write('ffconcat version 1.0\n')


        for (word, start, end, filepath) in image_information:
            f.write(f'file {filepath}\n')
            f.write(f'duration {end - start}\n')

        # Concat files are a little broken in FFMPEG ... https://stackoverflow.com/questions/46952350/ffmpeg-concat-demuxer-with-duration-filter-issue
        f.write(f'file {filepath}\n')





if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    args = parser.parse_args()

    scraper = Scraper(args.url)
    create_poetry(scraper.title, scraper.body)
