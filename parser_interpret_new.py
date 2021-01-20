import json
import re
import sys
import string
from wiktionary_languages import * 
from nltk.tokenize import word_tokenize
from parser_core_new import WiktionaryParser
parser = WiktionaryParser()

ancestor = ['from', 'derived', 'through', '<']
cognate = ['cognate', 'cognates', 'compare', 'compares', 'related']
uncertain = ['possible', 'possibly', 'probable', 'probably', 'maybe', 'perhaps']
loan = ['borrowed', '→']
root = ['root', 'stem']
exclusions = ['and', 'the', 'a']

inflections = ['plural', 'genitive', 'diminutive', 'comparative', 'superlative', 'supine', 'preterite']
two_word_inflections = ['present infinitive', 'perfect active', 'past particple', 'present particple',
'feminine singular', 'masculine plural', 'feminine plural']

filename = ''
previous_language_list = []

def start(start_words, debug_mode, passed_filename):

    for s in start_words:
        # set the filename (or use '' for print to screen)
        global filename
        if (passed_filename == ''):
            filename = (s['word'] + '_' + s['language'] + '_' + str(s['variant']) + '.txt').replace(' ', '_')
        else:
            filename = passed_filename

        # create (or re-create) the file if we have a filename, otherwise write to screen
        if (filename != ''):
            open(filename, 'w')

        # meaning defaults to the core word
        if ('meaning' not in s):
            s['meaning'] = s['word']

        # get the basic data from Wiktionary
        word_to_fetch = s['word']
        # reconstructued forms need special handling
        if (word_to_fetch[0] == '*'):
            word_to_fetch = 'Reconstruction:' + s['language'] + '/' + s['word'][1:]
        word_data = parser.fetch(word_to_fetch, s['language'])
        # NB word_data is itself a list, and each item in word_data is a dict

        # if the word is not in Wiktionary, print the error and continue to the next word
        if (len(word_data) == 0):
            print_to_file('\nWORD NOT FOUND: ' + word_to_fetch)
            continue

        if (debug_mode == True):
            print_to_file('\nINITIAL DATA IMPORT')
            input_string = json.dumps(word_data, indent=4, ensure_ascii=False).encode('utf8')
            print_to_file(input_string.decode())


        word = word_data[s['variant'] - 1] # variant is 1-based
        
        # define the new word structure
        new_word = { 
                    'key': (s['word'] + '#' + s['language'] + '#' + str(s['variant'])).replace(' ', '_'),
                    'word': s['word'],
                    'language': s['language'],
                    'variant': s['variant'],
                    'meaning': s['meaning'],
                    'forms': [],
                    'etymology': word['etymology']['text'].replace('{', '').replace('}', ''),
                    'ancestors': [],
                    'descendants': [],
                    'cognate': []
        }

        if (len(word['pronunciations']['text']) > 0):
            new_word['ipa'] = word['pronunciations']['text'][0]

        # add all word forms
        form = 0
        for d in word['definitions']:
            word_def = {
                        'part-of-speech': d['partOfSpeech'],
                        'gender': 'none',
                        'definitions': []
            }
            for t in d['text']:
                word_def['definitions'].append(t)
            new_word['forms'].append(word_def)

            # parse the descendants one by one and interpret
            # for rel in d['relatedWords']:
            #     if (rel['relationshipType'] == 'descendants'):
                    # # handle a glitch in the WiktionaryParser code
                    # # nested descendants result in duplicated text - remove it
                    # for i in range(len(rel['words']) - 1):
                    #     if (rel['words'][i + 1] in rel['words'][i]):
                    #         rel['words'][i] = rel['words'][i].replace(rel['words'][i + 1], '')
                    # for desc in rel['words']:
                    #     parseEtymology(desc, new_word, debug_mode, True)
                        # descendant = extract(desc, debug_mode, True)
                        # interpret(descendant, new_word, True)

            # parse the inflections
            parseInflections(new_word, form)
            form += 1

        # parse the IPA
        if ('ipa' in new_word):
            ipa = new_word['ipa']
            if ('/' in ipa):
                slash1 = ipa.index('/')
                slash2 = ipa.index('/', slash1 + 1)
                new_word['ipa'] = ipa[slash1 : slash2 + 1]

        # parse the etymology and interpret the structure
        parseEtymology(word['etymology']['map'], new_word, debug_mode)

        # print the new word structure
        if (debug_mode == True):
            print_to_file('\nFINAL JSON OUTPUT')
        json_string = json.dumps(new_word, indent=4, ensure_ascii=False).encode('utf8')
        print_to_file(json_string.decode())


def parseInflections(word_structure, form):

    # TODO - the Wiktionary markup specifies many more inflection types, we could capture those directly from the HTML
    # rather than hard coding them in here - see https://en.wiktionary.org/wiki/Category:Form-of_templates

    text = word_tokenize(word_structure['forms'][form]['definitions'][0])

    # concatenate reconstructed word forms
    for i in range(len(text) - 1):
        if (text[i] == '*'):
            text[i] = '*' + text[i + 1]
            # mark the redundant token to be ignored
            text[i + 1] = ''

    # concatenate 2-word inflection types
    for i in range(len(text) - 1):
        check_word = text[i] + ' ' + text[i + 1]
        if (check_word in two_word_inflections):
            text[i] = check_word
            # mark the redundant token to be ignored
            text[i + 1] = ''

    # now remove the redundant tokens
    temp = []
    while text:
        x = text.pop()
        if (x != ''):
            temp.append(x)
    while temp:
        text.append(temp.pop())

    # parse the gender and inflection text
    word_structure['forms'][form]['inflections'] = {}
    # the second element will be gender if it exists
    if (len(text) > 1 and text[1] in ['m', 'f', 'n']):
        word_structure['forms'][form]['gender'] = text[1]

    # check for declensions and conjugations
    if ('declension' in text):
        decl = text[text.index('declension') - 1]
        word_structure['forms'][form]['declension'] = decl
    if ('conjugation' in text):
        conj = text[text.index('conjugation') - 1]
        word_structure['forms'][form]['conjugation'] = conj

    # find any inflections such as plural, genitive
    current_word = ''
    current_inflection = ''
    for i in range(len(text)):
        if (text[i] in inflections or text[i] in two_word_inflections):
            current_inflection = text[i]
            current_word = ''
        else:
            if (current_inflection != ''):
                if (text[i] in [',', ';', ')']):
                    word_structure['forms'][form]['inflections'][current_inflection] = current_word.strip()
                    current_inflection = ''
                    current_word = ''
                else:
                    current_word += text[i] + ' '
    # if there's anything left in current_word, the line must have finished without a breaking symbol
    if (current_word != ''):
        word_structure['forms'][form]['inflections'][current_inflection] = current_word.strip()


# parse the etymology map into words, each with their language and relationship to the core word

def parseEtymology(etymology_map, word_structure, debug_mode):

    mode = 'cognate'  # this is the default mode unless something tells us it's an ancestor word
    uncertain_word = False
    loan_word = False
    root_form = False

    sub_words = []
    debug_string = ''

    # step through each element of the map
    for item in etymology_map:


        # if the item is text only, interpret that
        if ('name' not in item):
            tokens = word_tokenize(item['text'])
            debug_string += 'processing text: ' + item['text'] + ' | '

            for t in tokens:
                if (t.lower() in ancestor):
                    mode = 'ancestor'
                    debug_string += 'setting ancestor mode' + ' | '
                if (t.lower() in cognate):
                    mode = 'cognate'
                    debug_string += 'setting cognate mode' + ' | '
                if (t.lower() in uncertain):
                    uncertain_word = True
                    debug_string += 'marking as uncertain' + ' | '
                if (t.lower() in loan):
                    loan_word = True
                    debug_string += 'marking as loan word' + ' | '
                if (t.lower() in root):
                    root_form = True
                    debug_string += 'marking as root form' + ' | '
            continue

        # if the item is a span block, it's either a Latin form, a gloss, or a language name
        if (item['name'] == 'span'):
            debug_string += 'processing span with text: ' + item['text'] + ' | '

            # if there is a 'mention-tr' tag then this is a Latinised form of the previous word
            # apply it to the last item in the word list
            if ('mention-tr' in item['class'] and len(sub_words) > 0):
                sub_words[-1]['latin-form'] = item['text']
                debug_string += 'setting latin form' + ' | '
                continue

            # if there is a 'mention-gloss' tag then this is a different meaning (a gloss)
            # apply it to the last item in the word list
            if ('mention-gloss' in item['class'] and len(sub_words) > 0):
                sub_words[-1]['meaning'] = item['text']
                debug_string += 'setting meaning' + ' | '
                continue

            # otherwise this is a language name
            # check whether it gives us clues to the upcoming word's relationship
            if ('etyl' in item['class']):
                # do nothing - etyl is deprecated and we must deduce the relationship from the surrounding text
                pass
            if ('cognate' in item['class'] or 'cog' in item['class']):
                mode = 'cognate'
                debug_string += 'setting cognate mode' + ' | '
            if ('derived' in item['class'] or 'der' in item['class']):
                mode = 'ancestor'
                debug_string += 'setting ancestor mode' + ' | '
            if ('borrowed' in item['class'] or 'bor' in item['class']):
                mode = 'ancestor'
                loan_word = True
                debug_string += 'setting ancestor mode & borrowed word' + ' | '
            continue

        # if the item has a 'lang' attribute, it's a related word - process it
        if ('lang' in item):
            debug_string += 'processing language item with text: ' + item['text'] + ' | '

            # otherwise this is a simple word with its associated language - add it to our sub-words list
            sub_word = {
                'word': item['text'],
                'lang-code': item['lang'],
                'meaning': word_structure['meaning'],
                'mode': mode
            }
            if (root_form == True):
                sub_word['root-form'] = True
            if (uncertain_word == True):
                sub_word['uncertain'] = True
            if (loan_word == True):
                sub_word['loan-word'] = True

            if (item['lang'] in language_codes):
                sub_word['language'] = language_codes[item['lang']]

            sub_words.append(sub_word)
            debug_string += 'adding word to list (mode=' + mode + ') | '

            if (debug_mode):
                print_to_file(debug_string)
            debug_string = ''

            # reset everything
            mode = 'cognate'
            uncertain_word = False
            loan_word = False
            root_form = False


    # add the sub-words to the overall word structure
    # only write the parent once
    parent_written = False
    for sub_word in sub_words:
        mode = sub_word['mode']
        del sub_word['mode']
        if (mode == 'ancestor'):
            if (parent_written == False):
                word_structure['parent'] = sub_word
                parent_written = True
            else:
                word_structure['ancestors'].append(sub_word)
        if (mode == 'cognate'):
            word_structure['cognate'].append(sub_word)



def print_to_file(text):
    # print to the named file unless it's '' in which case print to console
    if(filename != ''):
        with open(filename, 'a') as f:
            stdout_temp = sys.stdout
            sys.stdout = f
            print(text)
            sys.stdout = stdout_temp
    else:
        print(text)
            


