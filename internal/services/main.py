from api import get_data, create_post


def main_get():

    post = get_data("posts", 1)
    user = get_data("users", 1)

    if post is None:
            return "Could not retrieve data"
    if user is None:
            return "Could not retrieve data"
    print(f"""
    Title: {post["title"]}
    Body: {post["body"]}
    """)

    print(f"""
    Name: {user["name"]},
    Email: {user["email"]},
    City: {user["address"]["city"]}
    """)

def main():
        post = create_post(
            1,
            "Saturday Weekly Bible Review",
            "Reviewing the chapters 21-24 of the book of Joshua",
        )

        if post is None:
            print("Failed to create post.")
            return
        
        print(post)
        print(post["id"])
        print(post["title"])

main()
