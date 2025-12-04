from google.cloud import firestore
from dateutil import parser

db = firestore.Client()

station_id = "kqxhEQMyv1UKJAlSHkH2"

data = {
    u'battery_level': 100,
    u'counts': [],
    u'date_increment': "daily",
    u'deleted': False,
    u'end_date': "2025-12-15",
    u'image1': "/static/img/image1.png",
    u'image2': "/static/img/image2.png",
    u'last_data_collection_time': parser.parse("October 28, 2025 at 1:50:27.862 PM UTC-5"),
    u'last_reboot_time': parser.parse("October 28, 2025 at 2:27:33.718 PM UTC-5"),
    u'latitude': "",
    u'longitude': "",
    u'name': "CLOUD Test55",
    u'site_comments': "TEST TEeeeeeee",
    u'start_date': "2025-01-01"
}

db.collection(u'stations').document(station_id).set(data)

print(f"Station with ID {station_id} has been added.")