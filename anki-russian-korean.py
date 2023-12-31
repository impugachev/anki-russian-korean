import requests
from os import path
import xml.etree.ElementTree as ET
from icrawler.builtin import GoogleImageCrawler
import genanki
from pathlib import Path
from navertts import NaverTTS
import shutil
import argparse
import logging

CURRENT_DIR = Path(__file__).resolve().parent

MEDIA_DIR = CURRENT_DIR / 'media'
MEDIA_DIR.parent.mkdir(parents=True, exist_ok=True)

ANKI_MODEL = genanki.Model(
    1607392319,
    'Gen model',
    fields=[
        {'name': 'Korean'},
        {'name': 'Russian'},
        {'name': 'Image'},
        {'name': 'Sound'},
    ],
    templates=[
        {
            'name': 'Russian+Korean -> Korean',
            'qfmt': '{{Russian}}<br>{{Image}}{{type:Korean}}',
            'afmt': '{{FrontSide}}<hr id="answer"><br>{{Sound}}',
        },
        {
            'name': 'Korean+Russian -> Russian',
            'qfmt': '{{Korean}}<br>{{Sound}}{{type:Russian}}',
            'afmt': '{{FrontSide}}<hr id="answer">',
        },
    ],
    css="""
        .card {
            font-family: arial;
            font-size: 20px;
            text-align: center;
            color: black;
            background-color: white;
        }
    """
)

def word_dir(word):
    return MEDIA_DIR / word

def make_word_dir(word):
    word_dir(word).mkdir(parents=True, exist_ok=True)

def get_translation(word, api_key):
    res = requests.get('https://krdict.korean.go.kr/api/search', verify=CURRENT_DIR / 'cert.pem', params={
        'key': api_key, 
        'q': word,
        'translated': 'y',
        'trans_lang': '10',
        'lang': 10
    })
    assert res.status_code == 200
    root = ET.fromstring(res.text)
    translations = root.findall("./item/sense/translation/trans_word")
    if translations == []:
        logging.error(f'Не могу найти перевод слова {word}')
        return None
    return translations[0].text

def download_image(word, filename):
    for _ in range(5):
        try:
            crawler = GoogleImageCrawler(storage={'root_dir': MEDIA_DIR}, log_level=logging.ERROR)
            crawler.crawl(keyword=word, max_num=1, overwrite=True)
            break
        except:
            continue
    else:
        logging.error(f'Не могу найти картинку для слова {word}')
        return None
    image_file = next(MEDIA_DIR.glob('000001.*'))
    new_name = word_dir(filename) / f'{filename}{image_file.suffix}'
    image_file.rename(new_name)
    return new_name

def make_sound(word):
    file = word_dir(word) / f'{word}.mp3'
    NaverTTS(word).save(file)
    return file

def make_note(word, api_key):
    make_word_dir(word)
    sound_file = make_sound(word)
    translation = get_translation(word, api_key)
    if translation is None:
        translation = ''
        image_file = download_image(word, word)
    else:
        image_file = download_image(translation.split(';')[0], word)
    if image_file is None:
        image_field = ''
        image_media = []
    else:
        image_field = f'<img src="{image_file.name}">'
        image_media = [image_file]
    note = genanki.Note(model=ANKI_MODEL, fields=[word, translation, image_field, f'[sound:{sound_file.name}]'])
    return (note, [sound_file] + image_media)

def read_words_from_file(file_path):
    with open(args.words_list_file, 'r', encoding='UTF-8') as f:
        words = f.readlines()
    return words

def make_deck(deck_name, api_key, words):
    logger = logging.getLogger('anki-russian-korean')
    logger.setLevel(logging.INFO)

    deck = genanki.Deck(2059400110, deck_name)
    media = []
    for word in words:
        word = word.strip()
        if word == '':
            continue
        logger.info(f'Создаю карточку для слова {word}...')
        try:
            note, media_files = make_note(word, api_key)
            deck.add_note(note)
            media.extend(media_files)
            logger.info(f'Карточка для слова {word} была создана!')
        except Exception as e:
            logger.error(f'Ошибка создания карточки для слова {word}: {e}')

    package = genanki.Package(deck)
    package.media_files = media
    package.write_to_file(CURRENT_DIR / f'{deck_name}.apkg')

parser = argparse.ArgumentParser(
    prog='anki-russian-korean', 
    description='Генерирует колоду для Anki из корейских слов с переводом на русский, картинкой и произношением')
parser.add_argument('deck_name', help='Название колоды')
parser.add_argument('api_key', help='Ключ API krdict')
parser.add_argument('words_list_file', help='Путь к файлу с корейскими словами по одному слову на строке')
parser.add_argument('--no_cleanup', action='store_true', help='Не удалять медиа файлы после работы скрипта')
args = parser.parse_args()

make_deck(args.deck_name, args.api_key, read_words_from_file(args.words_list_file))
if not args.no_cleanup:
    shutil.rmtree(MEDIA_DIR)
