import json
import re
import sys
import string
from wiktionary_languages import * 
from nltk.tokenize import word_tokenize
from parser_core import WiktionaryParser
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
parent_written = False
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
                    'etymology': word['etymology'].replace('{', '').replace('}', ''),
                    'ancestors': [],
                    'descendants': [],
                    'related': []
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
            for rel in d['relatedWords']:
                if (rel['relationshipType'] == 'descendants'):
                    # # handle a glitch in the WiktionaryParser code
                    # # nested descendants result in duplicated text - remove it
                    # for i in range(len(rel['words']) - 1):
                    #     if (rel['words'][i + 1] in rel['words'][i]):
                    #         rel['words'][i] = rel['words'][i].replace(rel['words'][i + 1], '')
                    for desc in rel['words']:
                        parseEtymology(desc, new_word, debug_mode, True)
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
        parseEtymology(word['etymology'], new_word, debug_mode)
        # structure = extract(word['etymology'], debug_mode)
        # interpret(structure, new_word)

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


# parse the etymology text into words, each with their language and relationship to the core word
# NB this coule be the main etymology text, or individual descendant strings

def parseEtymology(text, word_structure, debug_mode, descendant=False):

    #  INITIAL SETUP

    # use NLTK to tokenize the text
    tokens = word_tokenize(text)
    global parent_written
    parent_written = False

    # build a basic token definition consisting of a dict item for each token
    td = []
    for t in tokens:
        td.append({'token': t})


    # LANGUAGE NAMES

    # parse across word triples and mark any 3-word languages
    for i in range(len(td) - 2):
        checkWord = td[i]['token'] + ' ' + td[i + 1]['token'] + ' ' + td[i + 2]['token']
        if (checkWord in threeWordLanguages):
            td[i]['token'] = checkWord
            td[i]['language'] = True
            # mark the redundant tokens to be ignored
            td[i + 1]['ignoreFlag'] = True
            td[i + 2]['ignoreFlag'] = True

    # parse across word tuples and mark any 2-word languages
    for i in range(len(td) - 1):
        if ('ignoreFlag' in td[i]):
            pass
        else:
            checkWord = td[i]['token'] + ' ' + td[i + 1]['token']
            if (checkWord in twoWordLanguages):
                td[i]['token'] = checkWord
                td[i]['language'] = True
                # mark the redundant token to be ignored
                td[i + 1]['ignoreFlag'] = True

    # parse across tokens and mark any 1-word languages
    for i in range(len(td)):
        if ('ignoreFlag' in td[i]):
            pass
        else:
            checkWord = td[i]['token']
            if (checkWord in singleWordLanguages):
                td[i]['token'] = checkWord
                td[i]['language'] = True


    # ETYMOLOGICAL WORDS

    # the data from Wiktionary will return our etymoloical words wrapped in brackets { }
    # as the tokenizer will separate these, we need to restore them
    # NB as a side effect, this will also restore reconstructed word form such as *h₁rowdʰós which the
    # tokenizer will split into * and h₁rowdʰós
    for i in range(len(td) - 2):
        if ('ignoreFlag' in td[i]):
            pass
        else:
            if (td[i]['token'] == '{'):
                # find the matching end quote token
                quote2 = i + 1
                while (quote2 < len(td) and td[quote2]['token'] != '}'):
                    quote2 += 1
                if (quote2 < len(td)):
                    for x in range(i, quote2):
                        if (x != i and td[x + 1]['token'] != '}' and td[x]['token'] not in ['*', '(', ')'] and td[x + 1]['token'] not in ['(', ')'] ):
                            td[i]['token'] += ' '
                        td[i]['token'] += td[x + 1]['token']
                        # mark the redundant tokens to be ignored
                        td[x + 1]['ignoreFlag'] = True


    # DIFFERENT MEANINGS

    # look for forms like “redhead” in quotes showing a similar but different meaning
    for i in range(len(td) - 2):
        if ('ignoreFlag' in td[i]):
            pass
        else:
            if (td[i]['token'] == '“'):
                # find the matching end quote token
                quote2 = i + 1
                while (quote2 < len(td) and td[quote2]['token'] != '”'):
                    quote2 += 1
                if (quote2 < len(td)):
                    for x in range(i, quote2):
                        if (x != i and td[x + 1]['token'] not in ['”', ',', ';']):
                            td[i]['token'] += ' '
                        td[i]['token'] += td[x + 1]['token']
                        # mark the redundant tokens to be ignored
                        td[x + 1]['ignoreFlag'] = True


    # now remove the redundant tokens
    temp = []
    while td:
        x = td.pop()
        if not 'ignoreFlag' in x:
            temp.append(x)
    while temp:
        td.append(temp.pop())

    
    # INTERPRET THE STRUCTURE

    # parse over the token definitions and build a structured etymology
    language_list = []
    word_list = []
    mode = 'descendant' if (descendant == True) else 'cognate'
    attrs = {
        'different-meaning': '',
        'uncertain': False,
        'loan-word': False,
        'latin-form': '',
        'root-form': False
    }

    global previous_language_list
    previous_language_list.clear()
    debug_string = ''

    for d in td:

        token = d['token']
        debug_string = 'Token: ' + token + ' | '

        # if this is an ancestor or cognate word, flush any current language / word data, the set the mode
        if ((token.lower() in ancestor or token.lower() in cognate) and descendant == False):
            if (len(word_list) > 0 and len(language_list) > 0):
                debug_string += 'flushing words [' + ' '.join(language_list) + ' ' + ' '.join(word_list) + '] | ' 
                flushWords(word_list, language_list, mode, attrs, word_structure)
            mode = 'ancestor' if (token.lower() in ancestor) else 'cognate'
            debug_string += 'setting mode to ' + mode + ' | '

        # if this is a language, add it to the language list
        # if there are already words in the word list, then this must be a new language - so flush previous
        if ('language' in d):
            if (len(word_list) > 0):
                debug_string += 'flushing words [' + ' '.join(language_list) + ' ' + ' '.join(word_list) + '] | ' 
                flushWords(word_list, language_list, mode, attrs, word_structure)
            language_list.append(token)
            debug_string += 'adding language ' + token + ' | '

        # if this is an etymological word, remove the brackets and add it to the word list
        if (len(token) > 0 and token[0] == '{' and token[-1] == '}'):
            # however if it is a Latin form and there is an existing word in non-Latin form, add it as a Latin form instead
            if (len(word_list) > 0 and isNonLatin(word_list[0]) and isLatin(token)):
                attrs['latin-form'] = token.strip('{}')
                debug_string += 'adding Latin form ' + token.strip('{}') + ' | '
            else:
                word_list.append(token.strip('{}'))
                debug_string += 'adding word ' + token.strip('{}') + ' | '

        # if this is a word (or words) wrapped in quotes, remove them and add it as a different meaning
        if (len(token) > 2 and token[0] == '“' and token[-1] == '”'):
            attrs['different-meaning'] = token[1:-1]
            debug_string += 'adding different meaning ' + token + ' | '

        # if this is a word denoting uncertainty, flag it
        if (token.lower() in uncertain):
            attrs['uncertain'] = True
            debug_string += 'flagging as uncertain | '

        # if this is a word denoting a loan word, flag it
        if (token.lower() in loan):
            attrs['loan-word'] = True
            debug_string += 'flagging as loan word | '

        # if this is a word denoting a root form, copy the previous language across to this
        # if there are any words in the list, flush them
        if (token.lower() in root and descendant == False):
            if (len(word_list) > 0):
                debug_string += 'flushing words [' + ' '.join(language_list) + ' ' + ' '.join(word_list) + '] | ' 
                flushWords(word_list, language_list, mode, attrs, word_structure)
            attrs['root-form'] = True
            debug_string += 'adding language(s) ' + ' '.join(previous_language_list) + ' | '
            language_list += previous_language_list
            debug_string += 'flagging as root form | '

        # if this is a full stop, treat it as an explicit stop and flush any words
        if (token == '.'):
            if (len(word_list) > 0):
                debug_string += 'full stop | flushing words [' + ' '.join(language_list) + ' ' + ' '.join(word_list) + '] | ' 
                flushWords(word_list, language_list, mode, attrs, word_structure)

        if (debug_mode):
            print_to_file(debug_string)

    # if there are still items in the word and language lists, flush them
    if (len(word_list) > 0):
        debug_string += 'end of tokens | flushing words [' + ' '.join(language_list) + ' ' + ' '.join(word_list) + '] | ' 
        flushWords(word_list, language_list, mode, attrs, word_structure)
        if (debug_mode):
            print_to_file(debug_string)

        

# write the language list and word list items to the word structure

def flushWords(word_list, language_list, mode, attrs, word_structure):

    # handle forms such as "Language word1, derived from word2"
    global previous_language_list
    if (mode == 'ancestor' and len(word_list) > 0 and len(language_list) == 0):
        language_list += previous_language_list

    # iterate through the lists and write each word
    for language in language_list:
        for word in word_list:
            sub_word = {
                'word': word,
                'language': language,
                'meaning': word_structure['meaning']
            }
            if (attrs['different-meaning'] != ''):
                sub_word['meaning'] = attrs['different-meaning']
            if (attrs['latin-form'] != ''):
                sub_word['latin-form'] = attrs['latin-form']
            if (attrs['root-form']):
                sub_word['root-form'] = True
            if (attrs['uncertain']):
                sub_word['uncertain'] = True
            if (attrs['loan-word']):
                sub_word['loan-word'] = True

            # add the sub-words to the overall word structure
            # only write the parent once
            global parent_written
            if (mode == 'ancestor'):
                if (parent_written == False):
                    word_structure['parent'] = sub_word
                    parent_written = True
                else:
                    word_structure['ancestors'].append(sub_word)
            if (mode == 'cognate'):
                word_structure['related'].append(sub_word)
            if (mode == 'descendant'):
                word_structure['descendants'].append(sub_word)

    # reset everything
    previous_language_list.clear()
    previous_language_list += language_list
    language_list.clear()
    word_list.clear()
    mode = 'cognate'   # this is the default unless a word in the etymology modifies it
    attrs['different-meaning'] = ''
    attrs['uncertain'] = False
    attrs['loan-word'] = False
    attrs['latin-form'] = ''
    attrs['root-form'] = False


def isLatin(text):
    # is there at least one Latin alphabet character in the string?
    return re.search('[a-zA-Z]', text)

def isNonLatin(text):
    # are there zero Latin alphabet characters in the string?
    return not re.search('[a-zA-Z]', text)


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
            


