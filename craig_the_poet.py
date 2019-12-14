from bs4 import BeautifulSoup
from google.cloud import speech_v1p1beta1
import requests
from google_tts import synthesize_text
from google.cloud import language
from google.cloud.language import enums
from google.cloud.language import types
from image_downloader import downloadimages
import io
import os
from subprocess import check_output
from shutil import copyfile
from mutagen.mp3 import MP3
import argparse
from youtube_utils import video_to_flac


def interval_of(word, transcription):
    transcibed_words = [w for w in transcription.words]
    if word.lower() not in [w.word.lower() for w in transcibed_words]:
        return None

    for w in transcibed_words:
        if w.word.lower() == word.lower():
            start_time = float(str(w.start_time.seconds) + '.' + str(w.start_time.nanos))
            end_time = float(str(w.end_time.seconds) + '.' + str(w.end_time.nanos))
            return (start_time, end_time)


def change_audio_speed(audio_filepath, multiplier, output_filepath):
    command = f'ffmpeg -i {audio_filepath} -filter:a "atempo={str(multiplier)}" -vn {output_filepath}'
    check_output(command, shell=True)


POSTS_DIRECTORY = './posts'


def transcribe(audio_filepath):
    client = speech_v1p1beta1.SpeechClient()
    enable_word_time_offsets = True
    enable_word_confidence = True
    language_code = "en-US"
    config = {
        "enable_word_confidence": enable_word_confidence,
        "enable_word_time_offsets": enable_word_time_offsets,
        "language_code": language_code,
    }
    with io.open(audio_filepath, "rb") as f:
        content = f.read()
    audio = {"content": content}

    response = client.recognize(config, audio)

    # TODO: We throw out alternatives and only use the first one.. they may be helpful
    # The first result includes start and end time word offsets
    try:
        result = response.results[0]
    except:
        return None

    # First alternative is the most probable result
    alternative = result.alternatives[0]
    return alternative



def create_poetry(url=''):
    desired_count = 2
    clean_word = lambda x: ''.join([c for c in x.lower().replace(' ', '-') if c.isalpha() or c.isdigit() or c == '-']).rstrip()

    # Instantiates a client
    client = language.LanguageServiceClient()

    craigslist_subdomain_url = 'https://portland.craigslist.org/d/missed-connections/search/mis'

    if url == '':
        page = requests.get(craigslist_subdomain_url)
        soup = BeautifulSoup(page.text, 'html.parser')
        elements = soup.find_all(class_='result-title')

        # Grab CL posts
        postings = []
        for element in elements[30:40]:
            try:
                result_url = element['href']
                result_page = requests.get(result_url)
                result_soup = BeautifulSoup(result_page.text, 'html.parser')

                result_title = result_soup.find(id='titletextonly')
                result_title_blob = result_title.text

                result_body = result_soup.find(id='postingbody')
                if len(result_body.text) < 200:
                    continue

                bad_text = 'QR Code Link to This Post'
                result_text = [x for x in result_body.text.split('\n') if x != bad_text and x != '']
                result_blob = '\n'.join(result_text)

                postings += [
                    {
                        'title': result_title_blob,
                        'body': result_blob
                    }
                ]

                if len(postings) == desired_count:
                    break
            except:
                print('Posting had no body, or we were rejected')

    else:
        postings = []

        result_page = requests.get(url)
        result_soup = BeautifulSoup(result_page.text, 'html.parser')

        result_title = result_soup.find(id='titletextonly')
        result_title_blob = result_title.text

        result_body = result_soup.find(id='postingbody')

        bad_text = 'QR Code Link to This Post'
        result_text = [x for x in result_body.text.split('\n') if x != bad_text and x != '']
        result_blob = '\n'.join(result_text)

        postings += [
            {
                'title': result_title_blob,
                'body': result_blob
            }
        ]



#    postings = [{
#        'title': 'Meet you last night at a bar.',
#        'body': '''Hi, This is a long shot, but you said you loved reddit. You are from Jersey. I was sitting on the bench that stretches the entirety of the bar on the right side completely engrossed in browsing Reddit. I was there to be a wingman for my roommate, and you walked up and sit right next to me and asked me what I was doing, I said I was browsing Reddit, initially uninterested. You told me you just watched your friends fight, You then stated you loved Reddit and we talked about you majoring in Analytics and coding in SAS and Python, so I proceeded to show you my desktop that I built cause I thought it was cool that you were into coding too! (I'm Mostly into Visual Studio) then my roommate walked up and you seemed to get a little uncomfortable and you guys talked about football teams til my other roommate walked up and you quickly called out to a friend and disappeared (I don't blame you tbh), I just wanted to see if we could chat. I hope you see this.
#        '''
#    }]


    # Do TTS for each post & download images for each post
    for post in postings:
        print(post['title'])
        print(post['body'])

        clean_title = clean_word(post["title"])

        post_subdirectory = f'{POSTS_DIRECTORY}/{clean_title}'
        if not os.path.exists(post_subdirectory):
            os.makedirs(post_subdirectory)
            os.makedirs(f'{post_subdirectory}/audio')
            os.makedirs(f'{post_subdirectory}/images')
            os.makedirs(f'{post_subdirectory}/text')

        with open(f'{post_subdirectory}/text/post.txt', 'w') as f:
            f.write(post['title'] + '\n')
            f.write(post['body'])

        # TTS on both title and body
        synthesize_text(post['title'], f'{post_subdirectory}/audio/title.mp3')
        synthesize_text(post['body'], f'{post_subdirectory}/audio/body.mp3')

        # Find entities in the source text
        document = types.Document(
            content=post['body'],
            type=enums.Document.Type.PLAIN_TEXT
        )
        response = client.analyze_entities(document=document)
        entities = response.entities

        # Sort the entities by occurance in the source text
        by_occurance = sorted(entities, key=lambda e: post['body'].index(e.mentions[0].text.content))

        word_to_image_filepath = dict()
        for i, entity in enumerate(by_occurance):
            downloadimages(entity.name, f'{post_subdirectory}/images', f'entity-{i+1}')
            files = os.listdir(f'{post_subdirectory}/images/entity-{i+1}')
            if files != []:
                word_to_image_filepath[entity.name] = f'entity-{i+1}/{files[0]}'


        # Choose images
        images = []
        if not os.path.exists(f'{post_subdirectory}/images/frames'):
            os.makedirs(f'{post_subdirectory}/images/frames')

        for i in range(len(by_occurance)):
            dir_name = f'{post_subdirectory}/images/entity-{i+1}'
            if os.path.exists(dir_name) and len(os.listdir(dir_name)) > 0:
                images.append(dir_name + '/' + os.listdir(dir_name)[0])

        for i, image in enumerate(images):
            copyfile(image, f'{post_subdirectory}/images/frames/{i}.jpg')

        change_audio_speed(f'{post_subdirectory}/audio/title.mp3', 0.85, f'{post_subdirectory}/audio/title-85-percent.mp3')
        change_audio_speed(f'{post_subdirectory}/audio/body.mp3', 0.85, f'{post_subdirectory}/audio/body-85-percent.mp3')

        if not os.path.exists(f'{post_subdirectory}/video'):
            os.makedirs(f'{post_subdirectory}/video')


        audio = MP3(f'{post_subdirectory}/audio/body-85-percent.mp3')
        audio_length = audio.info.length

        no_audio_output_filepath = f'{post_subdirectory}/video/no_audio_poem.mp4'
        output_filepath = f'{post_subdirectory}/video/poem.mp4'
        audio_filepath = f'{post_subdirectory}/audio/body.mp3'
        flac_audio_filepath = f'{post_subdirectory}/audio/body.flac'
        concat_filepath = f'{post_subdirectory}/video/concat.txt'

        video_to_flac(audio_filepath, flac_audio_filepath, 'a.txt')
        transcription = transcribe(flac_audio_filepath)


        word_start_times = [(entity.name, interval_of(entity.name, transcription)) for entity in by_occurance]
        word_start_times = [(word, wst) for (word, wst) in word_start_times if (wst != None)]

        image_intervals = []
        for i, (name, wst) in enumerate(word_start_times):
            if i == len(word_start_times)-1:
                start = word_start_times[i][1][0]
                end = audio_length
                image_intervals += [(name, start, end)]
                continue

            if i == 0:
                start = 0
                end = word_start_times[i+1][1][0]
                image_intervals += [(name, start, end)]
            else:
                start = word_start_times[i][1][0]
                end = word_start_times[i+1][1][0]
                image_intervals += [(name, start, end)]


        # WRITE CONCAT FILE
        with open(concat_filepath, 'w') as f:
            f.write('ffconcat version 1.0\n')
            for (word, start, end) in image_intervals:
                f.write(f'file ../images/{word_to_image_filepath[word]}\n')
                f.write(f'duration {end - start}\n')

        no_audio_poem_command = f"ffmpeg -safe 0 -i {concat_filepath} -c:v libx264 -crf 23 -pix_fmt yuv420p {no_audio_output_filepath}"
        check_output(no_audio_poem_command, shell=True)

        # This command generates a video ffmpeg -i concat.txt -c:v libx264 -crf 23 -pix_fmt yuv420p out.mp4
        # This command attaches audio to that video....
        add_audio_command = f'ffmpeg -i {no_audio_output_filepath} -i {audio_filepath} -c:v libx264 -c:a aac -y  {output_filepath}'
#        create_video_command = f'ffmpeg -r {} -s 1920x1080 -i {post_subdirectory}/images/frames/%01d.jpg -i {audio_filepath} -c:v libx264 -c:a aac -crf 23 -pix_fmt yuv420p -y {output_filepath}'
        check_output(add_audio_command, shell=True)

        # TODO: Add proper start times based on when the word is said


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    args = parser.parse_args()

    if args.url:
        create_poetry(args.url)
    else:
        create_poetry()
