import random
from datetime import date, datetime, timedelta
from google.cloud import firestore

# Initialize Firestore client
db = firestore.Client()
collection = db.collection(u'stations')

def generate_labels_and_current_index(date_increment="bimonthly"):
    labels = []
    current_date = datetime.now()
    current_index = -1

    if date_increment == "daily":
        for i in range(365):  # Assuming a year for daily
            d = current_date - timedelta(days=current_date.timetuple().tm_yday - 1) + timedelta(days=i)
            labels.append(d.strftime('%b %d'))
            if d.date() == current_date.date():
                current_index = i
    elif date_increment == "weekly":
        # Generate labels for 52 weeks
        for i in range(52):
            # Start from the first day of the current year's first week
            d = datetime(current_date.year, 1, 1) + timedelta(weeks=i)
            labels.append(f"Week {i+1} ({d.strftime('%b %d')})")
            # Check if current date falls into this week
            if d.isocalendar()[1] == current_date.isocalendar()[1] and d.year == current_date.year:
                current_index = i
    elif date_increment == "monthly":
        for month in range(1, 13):
            d = date(current_date.year, month, 1)
            labels.append(d.strftime('%b'))
            if current_date.month == month:
                current_index = month - 1
    elif date_increment == "bimonthly":
        for month in range(1, 13):
            # First half of the month
            date1 = date(current_date.year, month, 1)
            labels.append(f"{date1.day} {date1.strftime('%b')})")
            if current_date.month == month and current_date.day < 15:
                current_index = len(labels) - 1

            # Second half of the month
            date2 = date(current_date.year, month, 15)
            labels.append(f"{date2.day} {date2.strftime('%b')})")
            if current_date.month == month and current_date.day >= 15:
                current_index = len(labels) - 1
    return labels, current_index

def randomize_data():
    # Fetch all sites from the collection
    sites = collection.stream()

    for site in sites:
        site_data = site.to_dict()
        date_increment = site_data.get('date_increment', 'bimonthly')
        labels, _ = generate_labels_and_current_index(date_increment)
        
        # Generate new random counts
        new_counts = [random.randint(10, 500) for _ in range(len(labels))]
        
        # Generate random battery level
        new_battery_level = random.randint(0, 100)
        
        # Update the site in the database
        site.reference.update({
            'counts': new_counts,
            'battery_level': new_battery_level
        })

    print("Data in Firestore has been randomized according to date increments.")

if __name__ == '__main__':
    randomize_data()
