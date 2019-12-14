import os
import io

from google.cloud import language, speech_v1p1beta1
from google.cloud.language import enums, types
from google_tts import synthesize_text



class MissingAPIKeyError(Exception):
    pass

# Check if API key file is loaded
api_key_filepath = os.environ['GOOGLE_APPLICATION_CREDENTIALS']
if not os.path.exists(api_key_filepath):
    raise MissingAPIKeyError()




# Find entities in text and return in order of occurance
def find_entities(text):
    # Instantiates a client
    client = language.LanguageServiceClient()

    document = types.Document(
        content=text,
        type=enums.Document.Type.PLAIN_TEXT
    )
    response = client.analyze_entities(document=document)
    entities = response.entities

    # Sort the entities by occurance in the source text
    by_occurance = sorted(entities, key=lambda e: text.index(e.mentions[0].text.content))
    return by_occurance



def transcribe_audio(audio_filepath):
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


def interval_of(word, transcription):
    transcibed_words = [w for w in transcription.words]
    if word.lower() not in [w.word.lower() for w in transcibed_words]:
        return None

    for w in transcibed_words:
        if w.word.lower() == word.lower():
            start_time = float(str(w.start_time.seconds) + '.' + str(w.start_time.nanos))
            end_time = float(str(w.end_time.seconds) + '.' + str(w.end_time.nanos))
            return (start_time, end_time)
