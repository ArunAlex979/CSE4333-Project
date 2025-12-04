from google.cloud import firestore

db = firestore.Client()

stations_ref = db.collection(u'stations').stream()

for station in stations_ref:
    print(f"ID: {station.id}, Name: {station.to_dict().get('name')}")