from fastapi import FastAPI, Form, HTTPException
from typing import Optional, List
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime

app = FastAPI()

# MongoDB setup
client = MongoClient("mongodb://localhost:27017")
db = client["blog_app"]
users_collection = db["users"]
posts_collection = db["posts"]
comments_collection = db["comments"]
likes_collection = db["likes"]

# ----------------------- User Management -----------------------
@app.post("/signup")
def signup(username: str = Form(...), password: str = Form(...)):
    if users_collection.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="User already exists")
    users_collection.insert_one({"username": username, "password": password})
    return {"message": "Signup successful!"}

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    user = users_collection.find_one({"username": username})
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"message": "Login successful!"}

# ----------------------- Blog Post Management -----------------------
@app.post("/create-post")
def create_post(
    username: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    tags: Optional[str] = Form(""),
    is_published: Optional[bool] = Form(True)
):
    if not users_collection.find_one({"username": username}):
        raise HTTPException(status_code=404, detail="User not found")

    post = {
        "author": username,
        "title": title,
        "content": content,
        "tags": tags.split(",") if tags else [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_published": is_published,
        "likes": 0
    }
    result = posts_collection.insert_one(post)
    post["_id"] = str(result.inserted_id)
    return {"message": "Post created", "post": post}

@app.get("/posts")
def get_posts(
    author: Optional[str] = None,
    tag: Optional[str] = None,
    is_published: Optional[bool] = True,
    sort: Optional[str] = "newest"
):
    query = {}
    if author: query["author"] = author
    if tag: query["tags"] = tag
    if is_published is not None: query["is_published"] = is_published

    posts = list(posts_collection.find(query))
    for post in posts:
        post["_id"] = str(post["_id"])
        post["created_at"] = post.get("created_at", datetime.utcnow())
    posts.sort(key=lambda x: x["created_at"], reverse=(sort == "newest"))
    return {"posts": posts}

@app.put("/edit-post")
def edit_post(
    author: str = Form(...),
    title: str = Form(...),
    new_title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_published: Optional[bool] = Form(None)
):
    post = posts_collection.find_one({"author": author, "title": title})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    update_fields = {"updated_at": datetime.utcnow()}
    if new_title: update_fields["title"] = new_title
    if content: update_fields["content"] = content
    if tags: update_fields["tags"] = tags.split(",")
    if is_published is not None: update_fields["is_published"] = is_published

    posts_collection.update_one({"author": author, "title": title}, {"$set": update_fields})
    updated_post = posts_collection.find_one({"author": author, "title": update_fields.get("title", title)})
    updated_post["_id"] = str(updated_post["_id"])
    return {"message": "Post updated", "post": updated_post}

@app.delete("/delete-post")
def delete_post(author: str = Form(...), title: str = Form(...)):
    result = posts_collection.delete_one({"author": author, "title": title})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted"}

@app.post("/like-post")
def like_post(reader: str = Form(...), author: str = Form(...), title: str = Form(...)):
    post = posts_collection.find_one({"author": author, "title": title})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if likes_collection.find_one({"reader": reader, "post_id": str(post["_id"])}):
        raise HTTPException(status_code=400, detail="You already liked this post")

    likes_collection.insert_one({"reader": reader, "post_id": str(post["_id"]), "timestamp": datetime.utcnow()})
    posts_collection.update_one({"_id": post["_id"]}, {"$inc": {"likes": 1}})
    return {"message": "Post liked"}

# ----------------------- Comments -----------------------
@app.post("/add-comment")
def add_comment(author: str = Form(...), title: str = Form(...), commenter: str = Form(...), text: str = Form(...)):
    post = posts_collection.find_one({"author": author, "title": title})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comment = {
        "post_id": str(post["_id"]),
        "commenter": commenter,
        "text": text,
        "timestamp": datetime.utcnow()
    }
    result = comments_collection.insert_one(comment)
    comment["_id"] = str(result.inserted_id)
    return {"message": "Comment added", "comment": comment}

@app.get("/comments")
def get_comments(author: str, title: str):
    post = posts_collection.find_one({"author": author, "title": title})
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    comments = list(comments_collection.find({"post_id": str(post["_id"])}))
    for comment in comments:
        comment["_id"] = str(comment["_id"])
    return {"comments": comments}

@app.delete("/delete-comment")
def delete_comment(commenter: str = Form(...), text: str = Form(...)):
    result = comments_collection.delete_one({"commenter": commenter, "text": text})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Comment not found or unauthorized")
    return {"message": "Comment deleted"}
