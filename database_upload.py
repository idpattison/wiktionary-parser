import sys
import json

from google.cloud import firestore
from google.cloud import bigquery
from neo4j import GraphDatabase

db = firestore.Client()
bq = bigquery.Client()

with open('secrets.json') as secrets_file:
    secrets = json.load(secrets_file)

graph = GraphDatabase.driver(secrets['url'], auth=(secrets['user'], secrets['pw']))

def main():
    # forms for calling the uploader

    # database_upload.py <filename> --no-graph OR --graph-only (alias -n / -g)
    # --> load the JSON contents of the file, then upload them to the databases

    # we will load the data to 3 separate databases:
    # 1. all fully defined words to a JSON object store (Firestore) - NB Firestore needs to be in native mode
    # 2. all words (fully defined or not) will be stored in SQL (BigQuery) - this will help us to build lists of words to fetch
    # 3. all words will be stored in a graph database (Neo4j) which will enable us to visualise relationships

    # NB BigQuery is a data lake so we will add multiple entries for each word, one for each core word it appears in
    # to see if we need to fetch that word, a QUERY must be run to see if ALL of the entries with a key are partial definitions

    # there should only be at least 1 argument and that should be the filename
    if (len(sys.argv) >= 2):  # NB the program name itself counts as an argument

        # check the mode
        mode = 'normal'
        if (len(sys.argv) == 3 and sys.argv[2] in ['--graph-only', '-g']):
            mode = 'graph-only'
        if (len(sys.argv) == 3 and sys.argv[2] in ['--no-graph', '-n']):
            mode = 'no-graph'

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
            if (mode != 'graph-only'):
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
                'definition': w['definition'],
                'pronunciation': '',
                'latin_form': '' if 'latin-form' not in w else w['latin-form'],
                'full_definition': True,
                'parent_key': '',
                'core_word': w['word'],
                'core_word_key': w['key'],
                'relation_to_core_word': 'core',
                'uncertain': False,
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

            # add the word to the graph if it doesn't already exist
            # record the word, language, key, meaning
            if (mode != 'no-graph'):
                create_graph_node(w['word'], w['language'], w['meaning'], w['key'])

            # iterate through ancestors adding each word
            for a in w['ancestors']:
                # update BigQuery
                ancestor_word = create_word_to_insert(w, a, 'borrowed ancestor') if ('loan-word' in a) else create_word_to_insert(w, a,'ancestor')
                words_to_insert.append(ancestor_word)
                # update the graph
                if (mode != 'no-graph'):
                    key = create_key(a['word'], a['lang-code'], 1)
                    create_graph_node(a['word'], a['language'], a['meaning'], key)
                    create_derived_relationship(w['key'], w['language'], key, a['language'], ('loan-word' in a), ('uncertain' in a))

            # iterate through descendants adding each word
            for d in w['descendants']:
                descendant_word = create_word_to_insert(w, d, 'loaned descendant') if ('loan-word' in d) else create_word_to_insert(w, d, 'descendant')
                words_to_insert.append(descendant_word)
                # update the graph
                if (mode != 'no-graph'):
                    key = create_key(d['word'], d['lang-code'], 1)
                    create_graph_node(d['word'], d['language'], d['meaning'], key)
                    create_derived_relationship(key, d['language'], w['key'], w['language'], ('loan-word' in d), ('uncertain' in a))

            # iterate through cognates adding each word
            for c in w['cognates']:
                cognate_word = create_word_to_insert(w, c, 'cognate')
                words_to_insert.append(cognate_word)
                # update the graph
                if (mode != 'no-graph'):
                    key = create_key(c['word'], c['lang-code'], 1)
                    create_graph_node(c['word'], c['language'], c['meaning'], key)
                    create_cognate_relationship(w['key'], w['language'], key, c['language'])

        # write the data
        if (mode != 'graph-only'):
            errors = bq.insert_rows_json(bq_table, words_to_insert)
            if (errors):
                print(errors)


    # no filename specified
    else:
        print('Usage is "database_upload.py <filename>"')


# BigQuery functions

def create_word_to_insert(core_word, related_word, mode):
    return {
        'key': create_key(related_word['word'], related_word['lang-code'], 1),
        'word': related_word['word'],
        'language': related_word['language'],
        'lang_code': related_word['lang-code'],
        'variant': 1,
        'meaning': related_word['meaning'],
        'definition': '',
        'pronunciation': '',
        'latin_form': '' if 'latin-form' not in related_word else related_word['latin-form'],
        'full_definition': False,
        'parent_key': '',
        'core_word': core_word['word'],
        'core_word_key': core_word['key'],
        'relation_to_core_word': mode,
        'uncertain': True if ('uncertain' in related_word) else False,
    }

def create_key(word, lang_code, variant):
    return (word + '#' + lang_code + '#' + str(variant)).replace(' ', '_')


# Graph database functions

def create_graph_node(word, language, meaning, key):
    with graph.session() as session:
        if not (session.read_transaction(graph_node_exists, language, key)):
            session.write_transaction(create_graph_node_tx, word, language, meaning, key)

def create_graph_node_tx(tx, word, language, meaning, key):
    query = (
        "CREATE (w:" + safe_language(language) + " { word: $word, meaning: $meaning, key: $key }) "
        "RETURN w"
    )
    return tx.run(query, word=word, meaning=meaning, key=key)

def graph_node_exists(tx, language, key):
    query = (
        "MATCH (w:" + safe_language(language) + ") "
        "WHERE w.key = $key "
        "RETURN w"
    )
    result = tx.run(query, key=key)
    return result.single() != None

def create_derived_relationship(key_from, lang_from, key_to, lang_to, loan, uncertain):
    rel_type = 'IS_DERIVED_FROM' if (loan == False) else 'IS_BORROWED_FROM'
    if (uncertain == True):
        rel_type += ' { uncertain: true }'
    with graph.session() as session:
        if not (session.read_transaction(graph_relationship_exists, key_from, lang_from, key_to, lang_to, rel_type)):
            session.write_transaction(create_graph_relationship_tx, key_from, lang_from, key_to, lang_to, rel_type)

def create_cognate_relationship(key_from, lang_from, key_to, lang_to):
    rel_type = 'IS_COGNATE_WITH'
    with graph.session() as session:
        if (not session.read_transaction(graph_relationship_exists, key_from, lang_from, key_to, lang_to, rel_type) and 
           not session.read_transaction(graph_relationship_exists, key_to, lang_to, key_from, lang_from, rel_type)):
            session.write_transaction(create_graph_relationship_tx, key_from, lang_from, key_to, lang_to, rel_type)

def create_graph_relationship_tx(tx, key_from, lang_from, key_to, lang_to, rel_type):
    query = (
        "MATCH (w1:" + safe_language(lang_from) + " { key: $key_from }) "
        "MATCH (w2:" + safe_language(lang_to) + " { key: $key_to }) "
        "CREATE (w1)-[:" + rel_type + "]->(w2) "
        "RETURN w1, w2"
    )
    return tx.run(query, key_from=key_from, key_to=key_to)

def graph_relationship_exists(tx, key_from, lang_from, key_to, lang_to, rel_type):
    query = (
        "MATCH (w1:" + safe_language(lang_from) + " { key: $key_from }) "
        "MATCH (w2:" + safe_language(lang_to) + " { key: $key_to }) "
        "RETURN EXISTS ((w1)-[:" + rel_type + "]->(w2))"
    )
    result = tx.run(query, key_from=key_from, key_to=key_to)
    record = result.single()
    return (record != None and record[0] == True)

def safe_language(language):
    text = language
    for ch in [' ', '-', '\'', '(', ')']:
        if (ch in text):
            text = text.replace(ch, '_')
    return text


if __name__ == "__main__":
    main()


