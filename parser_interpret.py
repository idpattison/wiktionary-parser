import json
import re
import sys
import string
from wiktionary_languages import * 
from nltk.tokenize import word_tokenize
from parser_core import WiktionaryParser
parser = WiktionaryParser()

ancestor = ['from', 'derived', 'through', '<']
cognate = ['cognate', 'cognates', 'compare', 'compares', 'related', 'cf', 'cf.']
uncertain = ['possible', 'possibly', 'probable', 'probably', 'maybe', 'perhaps']
loan = ['borrowed', '→']
root = ['root', 'stem']
exclusions = ['and', 'the', 'a', 'or']

filename = ''

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
                    'ipa': { 'phonemic': {}, 'phonetic': {} },
                    'forms': [],
                    'etymology': word['etymology']['text'].replace('{', '').replace('}', ''),
                    'ancestors': [],
                    'descendants': [],
                    'cognates': []
        }

        # add all word forms
        form = 0
        for d in word['definitions']:
            word_def = {
                        'part-of-speech': d['partOfSpeech'],
                        'gender': 'none',
                        'definitions': [],
                        'inflections': {}
            }
            for t in d['text']['text']:
                word_def['definitions'].append(t)
            new_word['forms'].append(word_def)

            # parse the descendants
            for rel in d['relatedWords']:
                if (rel['relationshipType'] == 'descendants'):
                    parseDescendants(rel['words']['map'], new_word, debug_mode)

            # parse the inflections
            parseInflections(d['text']['map'], new_word, form, debug_mode)
            form += 1

        # parse the IPA
        for ipa_form in word['pronunciations']['text']:
            ipa_type = ipa_form.split(':')[0]
            if (ipa_type not in ['Homophone', 'Homophones', 'Rhyme', 'Rhymes']):
                if ('/' in ipa_form):
                    slash1 = ipa_form.index('/')
                    slash2 = ipa_form.index('/', slash1 + 1)
                    new_word['ipa']['phonemic'][ipa_type] = ipa_form[slash1 : slash2 + 1]
                if ('[' in ipa_form):
                    bracket1 = ipa_form.index('[')
                    bracket2 = ipa_form.index(']', bracket1 + 1)
                    new_word['ipa']['phonetic'][ipa_type] = ipa_form[bracket1 : bracket2 + 1]

        # parse the etymology and interpret the structure
        parseEtymology(word['etymology']['map'], new_word, debug_mode)

        # print the new word structure
        if (debug_mode == True):
            print_to_file('\nFINAL JSON OUTPUT')
        json_string = json.dumps(new_word, indent=4, ensure_ascii=False).encode('utf8')
        print_to_file(json_string.decode())


def parseInflections(inflections_map, word_structure, form, debug_mode):

    # TODO - the Wiktionary markup specifies many more inflection types, we could capture those directly from the HTML
    # rather than hard coding them in here - see https://en.wiktionary.org/wiki/Category:Form-of_templates


    infl_type = ''
    debug_string = ''

    # step through each element of the map
    for item in inflections_map:

        # if the item is text only, interpret that
        if ('name' not in item and 'text' in item):
            debug_string += 'found text: ' + item['text'] + ' | '

        else:
            # if the item is an italic block, it's probably an inflection type
            if (item['name'] == 'i'):
                # check for declensions and conjugations
                if ('conjugation' in item['text']):
                    word_structure['forms'][form]['inflections']['conjugation'] = item['text']
                    debug_string += 'found conjugation: ' + item['text'] + ' | '
                elif ('declension' in item['text']):
                    word_structure['forms'][form]['inflections']['declension'] = item['text']
                    debug_string += 'found declension: ' + item['text'] + ' | '
                else:
                    # filter out unimportant words
                    if (item['text'] not in exclusions and '(' not in item['text']):
                        infl_type = item['text']
                        debug_string += 'found inflection type: ' + item['text'] + ' | '

            # if the item is a bold block, it's probably an inflection word
            if (item['name'] == 'b'):
                if (infl_type not in word_structure['forms'][form]['inflections']):
                    word_structure['forms'][form]['inflections'][infl_type] = item['text']
                    debug_string += 'found inflection word: ' + item['text'] + ' | '

            # if the item is a span block, it may be a gender
            if (item['name'] == 'span' and 'gender' in item['class']):
                if (word_structure['forms'][form]['gender'] == 'none'):
                    word_structure['forms'][form]['gender'] = item['text']
                    debug_string += 'found gender: ' + item['text'] + ' | '


        if (debug_mode):
            print_to_file(debug_string)
        debug_string = ''



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
                sub_word['borrowed'] = True

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

        if (debug_mode):
            print_to_file(debug_string)
        debug_string = ''


    # add the sub-words to the overall word structure
    # write the parent separately as well
    parent_written = False
    for sub_word in sub_words:
        mode = sub_word['mode']
        del sub_word['mode']
        if (mode == 'ancestor'):
            if (parent_written == False):
                word_structure['parent'] = sub_word
                parent_written = True
            word_structure['ancestors'].append(sub_word)
        if (mode == 'cognate'):
            word_structure['cognates'].append(sub_word)


# parse the descendant words, each with their language and any modifiers (latin forms, loan words, etc)

def parseDescendants(descendant_map, word_structure, debug_mode):

    uncertain_word = False
    loan_word = False

    sub_words = []
    debug_string = ''

    # step through each element of the map - NB this is a 2-dimensional list by language
    for language in descendant_map:
        for item in language:

            # if the item is text only, interpret that
            # NB for now we should not see these - maybe later as we find more complex text forms
            if ('name' not in item):
                debug_string += 'Found text: ' + item['text'] + ' | '
                continue

            # if the item is a span block, it's either a descendant word, a Latin form, a gloss, or a qualifier
            if (item['name'] == 'span'):
                debug_string += 'processing span with text: ' + item['text'] + ' | '

                # if there is a 'title' tag then this is a qualifier of the upcoming word
                if ('title' in item):
                    if (item['title'] == 'borrowed'):
                        loan_word = True
                        debug_string += 'marking as loan word | '
                    if (item['title'] == 'uncertain'):
                        uncertain_word = True
                        debug_string += 'marking as uncertain | '
                    continue

                # if there is a 'tr' tag then this is a Latinised form
                # apply it to the last item in the word list
                if ('tr' in item['class'] and len(sub_words) > 0):
                    sub_words[-1]['latin-form'] = item['text']
                    debug_string += 'setting Latin form' + ' | '
                    continue

                # otherwise this is a descendant word with its language - add it to our sub-words list
                sub_word = {
                    'word': item['text'],
                    'lang-code': item['lang'],
                    'meaning': word_structure['meaning']
                }
                if (uncertain_word == True):
                    sub_word['uncertain'] = True
                if (loan_word == True):
                    sub_word['loan-word'] = True

                if (item['lang'] in language_codes):
                    sub_word['language'] = language_codes[item['lang']]

                sub_words.append(sub_word)
                debug_string += 'adding word to list | '

                if (debug_mode):
                    print_to_file(debug_string)
                debug_string = ''

                # reset everything
                uncertain_word = False
                loan_word = False

            if (debug_mode):
                print_to_file(debug_string)
            debug_string = ''


    # add the sub-words to the overall word structure
    for sub_word in sub_words:
        word_structure['descendants'].append(sub_word)



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
            


