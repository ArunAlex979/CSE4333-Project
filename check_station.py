from google.cloud import firestore

db = firestore.Client()

station_id = "kqxhEQMyv1UKJAlSHkN3"

station_doc = db.collection(u'stations').document(station_id).get()

if station_doc.exists:
    print(f"Station with ID {station_id} exists.")
    print(station_doc.to_dict())
else:
    print(f"Station with ID {station_id} does not exist.")