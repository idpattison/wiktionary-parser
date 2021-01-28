import sys
import json
from parser_interpret import start

def main():
    # forms for calling the parser

    # parser
    # --> use the start words defined below

    # parser word
    # --> parse the given word, assume English and 1st variant

    # parser palabra --lang Spanish --variant 2 --meaning word --debug --filename 'myfile.txt'
    # parser --words words.json     (file holds a list of words to parse)
    # --> also use -l -m -v -d -f -w

    # NB variant is now deprecated - we will return all variants of the word in the given language

    start_words = []
    filename = ''
    debug_mode = False

    # if no args are passed then use the start_words array defined here
    # NB the application name is itself the first argument, so there will actually be 1 argument passed
    if (len(sys.argv) == 1):
        start_words = [
            # {'word': 'red', 'language': 'English', 'variant': 1}
            # {'word': 'jardín', 'language': 'Spanish', 'meaning': 'garden', 'variant': 1}
            # {'word': 'Hund', 'language': 'German', 'meaning': 'dog', 'variant': 1}
            {'word': '*raudaz', 'language': 'Proto-Germanic', 'meaning': 'red', 'variant': 1}
            # {'word': 'video', 'language': 'Latin', 'meaning': 'see', 'variant': 1}
        ]

    # if only 1 arg is passed then use that as the word and assume other attributes
    # 'meaning' will default to the word itself if the language is English
    if (len(sys.argv) == 2):
        start_words = [
            {'word': sys.argv[1], 'language': 'English', 'variant': 1}
        ]
    
    # if more than 1 argument, parse the arguments string
    if (len(sys.argv) > 2):
        word = sys.argv[1]
        language = ''
        variant = ''
        meaning = ''

        for x in range(1, len(sys.argv)):
            if (sys.argv[x] in ['--language', '-l']):
                language = sys.argv[x + 1]
            if (sys.argv[x] in ['--variant', '-v']):
                variant = sys.argv[x + 1]
            if (sys.argv[x] in ['--meaning', '-m']):
                meaning = sys.argv[x + 1]
            if (sys.argv[x] in ['--debug', '-d']):
                debug_mode = True
            if (sys.argv[x] in ['--filename', '-f']):
                filename = sys.argv[x + 1]
            if (sys.argv[x] in ['--words', '-w']):
                with open(sys.argv[x + 1]) as json_file:
                    start_words = json.load(json_file) 

        if (language == ''):
            language = 'English'
        if (variant == ''):
            variant = '1'
        if (meaning == ''):
            meaning = word
        
        # if we haven't loaded words from a file
        if (len(start_words) == 0):
            start_words = [
                {'word': word, 'language': language, 'variant': int(variant), 'meaning': meaning}
            ]
    
    # call the parser

    start(start_words, debug_mode, filename)



if __name__ == "__main__":
    main()




