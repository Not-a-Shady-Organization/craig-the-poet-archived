from bs4 import BeautifulSoup
import requests
from google_tts import synthesize_text
from google.cloud import language
from google.cloud.language import enums
from google.cloud.language import types
from image_downloader import downloadimages
import os
from subprocess import check_output
from shutil import copyfile
from mutagen.mp3 import MP3
import argparse


def change_audio_speed(audio_filepath, multiplier, output_filepath):
    command = f'ffmpeg -i {audio_filepath} -filter:a "atempo={str(multiplier)}" -vn {output_filepath}'
    check_output(command, shell=True)


POSTS_DIRECTORY = './posts'


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

        # Split the entities into sections
        sections = []
        section_period = 3
        for i, entity in enumerate(by_occurance):
            if i % section_period == 0:
                sections.append([])
            sections[i//section_period].append(entity)

        for i, s in enumerate(sections):
            most_salient = sorted(s, key=lambda e: e.salience, reverse=True)[0]
            downloadimages(most_salient.name, f'{post_subdirectory}/images', f'entity-{i+1}')

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
        seconds_per_image = audio.info.length/len(images)

        output_filepath = f'{post_subdirectory}/video/poem.mp4'
        audio_filepath = f'{post_subdirectory}/audio/body.mp3'
        create_video_command = f'ffmpeg -r {1/seconds_per_image} -s 1920x1080 -i {post_subdirectory}/images/frames/%01d.jpg -i {audio_filepath} -c:v libx264 -c:a aac -crf 23 -pix_fmt yuv420p -y {output_filepath}'
        check_output(create_video_command, shell=True)

        # TODO: Add proper start times based on when the word is said


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    args = parser.parse_args()

    if args.url:
        create_poetry(args.url)
    else:
        create_poetry()
