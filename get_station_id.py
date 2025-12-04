from google.cloud import firestore

db = firestore.Client()

device_logs_ref = db.collection(u'DeviceLogs').limit(1).stream()

for log in device_logs_ref:
    print(log.to_dict()['station_id'])