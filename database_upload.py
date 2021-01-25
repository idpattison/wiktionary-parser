import sys
import json

from google.cloud import datastore
db = datastore.Client('ianpattison-sandbox')

def main():
    # forms for calling the uploader

    # firestore_upload.py <filename>
    # --> load the JSON contents of the file, then upload them to Firestore
    # --> NB Firestore needs to be in Datastore mode

    # there should only be 1 argument and it should be the filename
    if (len(sys.argv) == 2):  # NB the program name itself counts as an agrument
        
        # load the contents of the file
        with open(sys.argv[1]) as json_file:
            words = json.load(json_file) 

        for w in words:

            key = db.key('Words', w['key'])
            entity = datastore.Entity(key = key)
            entity.update(w)
            db.put(entity)

            # next add the short form of each word (core word, ancestors, descendants, cognates) to BigQuery

    # no filename specified
    else:
        print('Usage is "database_upload.py <filename>"')




if __name__ == "__main__":
    main()


