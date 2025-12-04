import secrets
from google.cloud import firestore

db = firestore.Client()

def generate_and_store_access_codes(num_codes):
    """Generates a specified number of unique access codes and stores them in Firestore."""
    codes_ref = db.collection('access_codes')
    existing_codes = {doc.id for doc in codes_ref.stream()}
    
    new_codes = []
    for _ in range(num_codes):
        while True:
            new_code = secrets.token_hex(4)
            if new_code not in existing_codes and new_code not in new_codes:
                new_codes.append(new_code)
                break
    
    for code in new_codes:
        codes_ref.document(code).set({'used': False})
        print(f"Generated and stored access code: {code}")

if __name__ == '__main__':
    try:
        num_to_generate = int(input("Enter the number of access codes to generate: "))
        if num_to_generate > 0:
            generate_and_store_access_codes(num_to_generate)
        else:
            print("Please enter a positive number.")
    except ValueError:
        print("Invalid input. Please enter an integer.")
