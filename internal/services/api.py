import requests

BASE_URL = "https://jsonplaceholder.typicode.com"

def get_data(resource, resource_id):
    get_response = requests.get(f"{BASE_URL}/{resource}/{resource_id}")

    if not get_response.status_code == 200:
        return None

    return get_response.json()

def create_post(user_id, title, body):

    payload = {
        "userId": user_id,
        "title": title,
        "body": body
    }

    post_response = requests.post(
        f"{BASE_URL}/posts",
        json=payload
    )

    if post_response.status_code != 201:
        return None
    return post_response.json()