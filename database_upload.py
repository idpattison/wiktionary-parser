import sys
import json

from google.cloud import firestore
from google.cloud import bigquery

db = firestore.Client()
bq = bigquery.Client()

def main():
    # forms for calling the uploader

    # database_upload.py <filename>
    # --> load the JSON contents of the file, then upload them to the databases

    # we will load the data to 3 separate databases:
    # 1. all fully defined words to a JSON object store (Firestore) - NB Firestore needs to be in native mode
    # 2. all words (fully defined or not) will be stored in SQL (BigQuery) - this will help us to build lists of words to fetch
    # 3. all words will be stored in a graph database (Neo4j) which will enable us to visualise relationships

    # NB BigQuery is a data lake so we will add multiple entries for each word, one for each core word it appears in
    # to see if we need to fetch that word, a QUERY must be run to see if ALL of the entries with a key are partial definitions

    # there should only be 1 argument and it should be the filename
    if (len(sys.argv) == 2):  # NB the program name itself counts as an agrument

        # set up the databases
        bq_dataset_ref = bq.dataset('Words')
        bq_table_ref = bq_dataset_ref.table('all_words')
        bq_table = bq.get_table(bq_table_ref)
        words_to_insert = []
        
        # load the contents of the file
        with open(sys.argv[1]) as json_file:
            words = json.load(json_file) 

        for w in words:

            # add each full word definition to our JSON database
            doc_ref = db.collection('words').document(w['key'])
            doc_ref.set(w)

            # add the short form of each word (core word, ancestors, descendants, cognates) to BigQuery
            core_word = {
                'key': w['key'],
                'word': w['word'],
                'language': w['language'],
                'lang_code': w['lang-code'],
                'variant': w['variant'],
                'meaning': w['meaning'],
                'pronunciation': '',
                'latin_form': '',
                'full_definition': True,
                'parent_key': '',
                'core_word': w['word'],
                'core_word_key': w['key'],
                'relation_to_core_word': 'core',
            }
            # get the first dictionary entry which specifies a phonemic pronunciation - there is usually only one
            ipa_dict = next(iter(w['pronunciation']['phonemic']))
            if (ipa_dict):
                core_word['pronunciation'] = w['pronunciation']['phonemic'][ipa_dict]
            # get the parent word if it exists
            if ('parent' in w):
                p = w['parent']
                core_word['parent_key'] = create_key(p['word'], p['lang-code'], 1)

            words_to_insert.append(core_word)

            # iterate through ancestors adding each word
            for a in w['ancestors']:
                ancestor_word = create_word_to_insert(w, a, 'ancestor')
                words_to_insert.append(ancestor_word)

            # iterate through descendants adding each word
            for d in w['descendants']:
                descendant_word = create_word_to_insert(w, d, 'descendant')
                words_to_insert.append(descendant_word)

            # iterate through cognates adding each word
            for c in w['cognates']:
                cognate_word = create_word_to_insert(w, c, 'cognate')
                words_to_insert.append(cognate_word)

        # write the data
        errors = bq.insert_rows_json(bq_table, words_to_insert)
        if (errors):
            print(errors)


    # no filename specified
    else:
        print('Usage is "database_upload.py <filename>"')



def create_word_to_insert(core_word, related_word, mode):
    return {
        'key': create_key(related_word['word'], related_word['lang-code'], 1),
        'word': related_word['word'],
        'language': related_word['language'],
        'lang_code': related_word['lang-code'],
        'variant': 1,
        'meaning': related_word['meaning'],
        'pronunciation': '',
        'latin_form': '' if 'latin-form' not in related_word else related_word['latin-form'],
        'full_definition': False,
        'parent_key': '',
        'core_word': core_word['word'],
        'core_word_key': core_word['key'],
        'relation_to_core_word': mode,
    }


def create_key(word, lang_code, variant):
    return (word + '#' + lang_code + '#' + str(variant)).replace(' ', '_')


if __name__ == "__main__":
    main()


