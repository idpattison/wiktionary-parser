import json
import re
import sys
import string
from wiktionary_languages import * 
from nltk.tokenize import word_tokenize
from parser_core import WiktionaryParser
# from wiktionaryparser import WiktionaryParser
parser = WiktionaryParser()

ancestor = ['from', 'derived', 'through', '<']
cognate = ['cognate', 'compare']
uncertain = ['possible', 'possibly', 'probable', 'probably', 'maybe', 'perhaps']
loan = ['borrowed', '→']
root = ['root', 'stem']
exclusions = ['and', 'the', 'a']
inflections = ['plural', 'genitive', 'diminutive', 'comparative', 'superlative', 'supine']
two_word_inflections = ['present infinitive', 'perfect active',
'feminine singular', 'masculine plural', 'feminine plural']
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
            print_to_file(filename, '\nWORD NOT FOUND: ' + word_to_fetch)
            continue

        if (debug_mode == True):
            print_to_file(filename, '\nINITIAL DATA IMPORT')
            input_string = json.dumps(word_data, indent=4, ensure_ascii=False).encode('utf8')
            print_to_file(filename, input_string.decode())


        word = word_data[s['variant'] - 1] # variant is 1-based
        
        # define the new word structure
        new_word = { 
                    'word': s['word'],
                    'language': s['language'],
                    'variant': s['variant'],
                    'meaning': s['meaning'],
                    'forms': [],
                    'etymology': word['etymology'],
                    'ancestors': [],
                    'descendants': [],
                    'related': []
        }

        if (len(word['pronunciations']['text']) > 0):
            new_word['ipa'] = word['pronunciations']['text'][0]

        # add all word forms
        new_word['hash'] = hash(new_word['word'] + new_word['language'] + str(new_word['variant']))
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
                    # handle a glitch in the WiktionaryParser code
                    # nested descendants result in duplicated text - remove it
                    for i in range(len(rel['words']) - 1):
                        if (rel['words'][i + 1] in rel['words'][i]):
                            rel['words'][i] = rel['words'][i].replace(rel['words'][i + 1], '')
                    for desc in rel['words']:
                        descendant = extract(desc, debug_mode, True)
                        interpret(descendant, new_word, True)

            # parse the inflections
            processInflections(new_word, form)
            form += 1

        # parse the IPA
        if ('ipa' in new_word):
            ipa = new_word['ipa']
            if ('/' in ipa):
                slash1 = ipa.index('/')
                slash2 = ipa.index('/', slash1 + 1)
                new_word['ipa'] = ipa[slash1 : slash2 + 1]

        # parse the etymology and interpret the structure
        structure = extract(word['etymology'], debug_mode)
        interpret(structure, new_word)

        # print the new word structure
        if (debug_mode == True):
            print_to_file(filename, '\nFINAL JSON OUTPUT')
        json_string = json.dumps(new_word, indent=4, ensure_ascii=False).encode('utf8')
        print_to_file(filename, json_string.decode())


def processInflections(word_structure, form):
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


def extract(text, debug_mode, descendant=False):
    
    # INITIAL SETUP
    
    # use NLTK to tokenise the text
    tokens = word_tokenize(text)

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


    # RECONSTRUCTED WORD FORMS

    # in lingusitics, reconstructed words are shown like this: *h₁rowdʰós - but will be 2 separate tokens
    # parse across word tuples and mark any reconstructed words
    for i in range(len(td) - 1):
        if ('ignoreFlag' in td[i]):
            pass
        else:
            if (td[i]['token'] == '*'):
                td[i]['token'] = '*' + td[i + 1]['token']
                td[i]['reconstructed'] = True
                # mark the redundant token to be ignored
                td[i + 1]['ignoreFlag'] = True


    # SIMILAR MEANINGS

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
                        if (x != i and td[x + 1]['token'] != ',' and td[x + 1]['token'] != '”'):
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



    # PARSING THE STRUCTURE

    # parse over the token definitions and build a structured etymology
    structure = []
    phrase = []

    for d in td:
        # NB if we're dealing with a descendant string, don't break
        # build up a phrase until we hit a breaking token
        # if this token is an open-brace, start a new phrase
        if (d['token'] == '(' and descendant == False):
            structure.append(phrase)
            phrase = []
    
        phrase.append(d)
        # if this token is a comma, end-brace, or other breaking punctuation, end the phrase here
        if (d['token'] in [',', ')', '.', ';', '\n'] and descendant == False):
            structure.append(phrase)
            phrase = []
            continue

        # if this is an ancestor word and we already have a language in the phrase, start a new phrase
        if (d['token'] in ancestor):
            language_present = False
            for tk in phrase:
                if ('language' in tk):
                    language_present = True
            if (language_present == True):
                # we've already added this token to the current phrase so remove it
                phrase.pop()
                structure.append(phrase)
                phrase = []
                phrase.append(tk)


    # if there is anything left in phrase[] then we have reached the end of the structure without 
    # breaking - append this to end of the previous phrase
    if (len(phrase) > 0):
        if (len(structure) == 0):
            structure.append(phrase)
        else:
            for tk in phrase:
                structure[-1].append(tk)


    # append any tokens in braces to the end of the language-word pair
    # this should result in the form "Ancient Greek ἐρυθρός ( eruthrós )"
    # but filter out those brackets with e.g. "( compare ..."
    # NB cannot append the first line to a previous one so start at the second line
    for s in range(2, len(structure)):    
        if (len(structure[s]) > 0 and structure[s][0]['token'] == '('):
            if (structure[s][1]['token'].lower() not in cognate and
                structure[s][1]['token'].lower() not in ancestor):
                line = s
                while True:
                    for phrase in structure[line]:
                        structure[s - 1].append(phrase)
                    structure[line] = []
                    line += 1
                    if (structure[s - 1][-1]['token'] == ')' or line == len(structure)):
                        break


    # CONCATENATE RELATED PHRASES

    # first remove all singleton commas as they get in the way
    for s in range(len(structure)):
        if (len(structure[s]) == 1 and structure[s][0]['token'] == ','):
            structure[s].clear()
    
    # NB do this backwards in case we need to join multiple lines
    for s in range(len(structure) - 2, 0, -1):
        # if the phrase has a single language, ends in a comma, and the next phrase starts with a language
        # this will happen if there are multiple languages associated with one word
        if (len(structure[s]) == 2 and 'language' in structure[s][0] and
            structure[s][1]['token'] == ',' and 'language' in structure[s + 1][0]):
            for t in structure[s + 1]:
                structure[s].append(t)
            structure[s + 1] = []
            continue

        # if the phrase ends in a comma, and the next phrase starts with a word which is
        # not a 'keyword' or a language (this should have been detected above)
        # this will happen if there are multiple words associated with one language
        if (len(structure[s]) > 0 and structure[s][-1]['token'] == ',' and 
            'language' not in structure[s + 1][0] and
            structure[s + 1][0]['token'].lower() not in ancestor and
            structure[s + 1][0]['token'].lower() not in cognate and
            structure[s + 1][0]['token'].lower() not in uncertain and
            structure[s + 1][0]['token'].lower() not in root and
            structure[s + 1][0]['token'].lower() not in loan and
            structure[s + 1][0]['token'].lower() not in exclusions):
            for t in structure[s + 1]:
                structure[s].append(t)
            structure[s + 1] = []
            continue


    # STRIP OUT BLANK PHRASES

    temp = []
    while structure:
        x = structure.pop()
        if len(x) > 0:
            temp.append(x)
    while temp:
        structure.append(temp.pop())


    # print the structure
    if (debug_mode == True):
        print_to_file(filename, '\nINTERIM STRUCTURE')
        for st in structure:
            text = ''
            for tk in st:
                text += ' ' + tk['token']
            print_to_file(filename, text)

    return structure

def interpret(structure, word_structure, descendant=False):

    # INTERPRET THE STRUCTURAL COMPONENTS

    parent_found = False
    language_list = []
    meaning = word_structure['meaning']

    for si in structure:

        previous_language = language_list
        language_list = []
        word_list = []
        word_relation_type = 'descendant' if descendant == True else 'related'
        uncertain_word = False
        loan_word = False
        root_word = False
        brace_mode = False
        brace_at_start = True if (si[0]['token'] == '(') else False
        different_meaning = ''
        latin_form = ''

        # examine each token and interpret its impact on the phrase
        for t in si:
            token = t['token']

            # first check we're not in 'brace mode' - that's handled separately
            if (not brace_mode):
                # is it denoting an ancestor word? (typically 'from')
                # NB the first ancestor will be the direct parent
                if (token.lower() in ancestor):
                    if (parent_found):
                        word_relation_type = 'ancestor'
                    else:
                        word_relation_type = 'parent'
                        parent_found = True
                    continue

                # is it denoting a related word? (this is the default)
                if (token.lower() in cognate):
                    word_relation_type = 'related'
                    continue

                # is it denoting uncertainty?
                if (token.lower() in uncertain):
                    uncertain_word = True
                    continue

                # is it denoting a loan word?
                # NB for forms like "borrowed from" this should detect an ancestor which is also a loan word
                if (token.lower() in loan):
                    loan_word = True
                    continue

                # is it a language? add it to the list
                # also discard any words gathered prior to this, as they will be superfluous
                if ('language' in t):
                    language_list.append(token)
                    word_list.clear() 
                    continue

                # is it denoting a root or stem form?
                # NB a problem here is this - compare "from the root *h₁rewdʰ-" with 'Low Germn root, rod"
                # assume that if there is already a language in play, this is an actual word
                # otherwise copy the previous language(s)
                if (token.lower() in root):
                    if (len(language_list) == 0):
                        root_word = True
                        language_list = previous_language
                        continue
                    else:
                        pass  # carry on to the next if statement

                # is it any other word (i.e. not punctuation)? add it to the list
                # check against a set of predefined exclusions
                if (token != '' and token not in string.punctuation and 
                    token.lower() not in exclusions):
                    word_list.append(token)
                    continue

                # is it an open brace? if so go to brace mode unless it's the first token
                if (token == '('):
                    if (brace_at_start == True):
                        brace_at_start = False
                    else:
                        brace_mode = True
                    continue

            else: # brace mode

                # if it's any kind of punctuation then ignore
                if (token in string.punctuation):
                    continue

                # is it enclosed in quotes? if so record a different meaning
                if (len(token) > 2 and token[0] == '“' and token[-1] == '”'):
                    different_meaning = token[1:-1]
                    continue

                # if not, then if the core word is non-Latin, record a Latinised form
                if (len(word_list) > 0 and not re.search('[a-zA-Z]', word_list[0])):
                    latin_form = token

        # if we found no words or languages in this phrase, ignore it
        if (len(word_list) == 0 or len(language_list) == 0):
            continue
 
        # build up the sub-word structure, one for each language and word
        parent_written = False
        for language in language_list:
            for word in word_list:
                sub_word = {
                    'word': word,
                    'language': language,
                    'meaning': meaning
                }
                if (different_meaning != ''):
                    sub_word['meaning'] = different_meaning
                if (latin_form != ''):
                    sub_word['latin-form'] = latin_form
                if (root_word):
                    sub_word['root-form'] = True
                if (uncertain_word):
                    sub_word['uncertain'] = True
                if (loan_word):
                    sub_word['loan_word'] = True

                # add the sub-words to the overall word structure
                # only write the parent once
                if (word_relation_type == 'parent'):
                    if (parent_written == False):
                        word_structure['parent'] = sub_word
                        parent_written = True
                if (word_relation_type == 'ancestor'):
                    word_structure['ancestors'].append(sub_word)
                if (word_relation_type == 'related'):
                    word_structure['related'].append(sub_word)
                if (word_relation_type == 'descendant'):
                    word_structure['descendants'].append(sub_word)

def print_to_file(filename, text):
    # print to the named file unless it's '' in which case print to console
    if(filename != ''):
        with open(filename, 'a') as f:
            stdout_temp = sys.stdout
            sys.stdout = f
            print(text)
            sys.stdout = stdout_temp
    else:
        print(text)
            


