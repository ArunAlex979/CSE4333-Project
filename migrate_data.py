

import json
from pymongo import MongoClient

# --- Configuration ---
# Make sure these match your settings in app.py
MONGO_URI = "mongodb+srv://trafx-user:Password@trafx.elditss.mongodb.net/?retryWrites=true&w=majority&appName=TRAFx"
DB_NAME = "TRAFX"
COLLECTION_NAME = "Station"
JSON_FILE_PATH = "data.json"

def migrate_data():
    """
    Reads data from a JSON file and migrates it to a MongoDB collection.
    """
    client = None  # Initialize client to None
    try:
        # 1. Connect to MongoDB
        print(f"Connecting to MongoDB at {MONGO_URI}...")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print("Connection successful.")

        # 2. Read data from the JSON file
        print(f"Reading data from {JSON_FILE_PATH}...")
        with open(JSON_FILE_PATH, 'r') as f:
            data = json.load(f)
        print(f"Found {len(data)} documents in the JSON file.")

        # 3. Clean up the data (remove old 'id' field if it exists)
        for site in data:
            if 'id' in site:
                del site['id']

        # 4. Clear the existing collection to prevent duplicates
        print(f"Clearing all existing documents from the '{COLLECTION_NAME}' collection...")
        delete_result = collection.delete_many({})
        print(f"Deleted {delete_result.deleted_count} documents.")

        # 5. Insert the new data into the collection
        if data:
            print(f"Inserting {len(data)} new documents into the collection...")
            insert_result = collection.insert_many(data)
            print(f"Successfully inserted {len(insert_result.inserted_ids)} documents.")
        else:
            print("No data to insert.")

        print("\nMigration complete! Your MongoDB collection is now populated.")

    except FileNotFoundError:
        print(f"ERROR: The file {JSON_FILE_PATH} was not found. Please make sure it's in the same directory.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # 6. Ensure the connection is closed
        if client:
            client.close()
            print("MongoDB connection closed.")

if __name__ == "__main__":
    migrate_data()

