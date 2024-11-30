#pip install fastapi uvicorn
#uvicorn main:app --reload
#Visit the Swagger UI at http://127.0.0.1:8000/docs.
#for deployment uvicorn main:app --host 0.0.0.0 --port 8000
#swagger: http://127.0.0.1:8000/docs



from fastapi import FastAPI, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient #for database routes
from pydantic import BaseModel, Field, IPvAnyAddress
from bson import ObjectId
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from pymongo import ReturnDocument


# Load environment variables from .env file
load_dotenv()

MONGODB_CONNECTION_URL = os.getenv("MONGODB_CONNECTION_URL")


# Create an instance of FastAPI
app = FastAPI()

# Allow CORS for your frontend domain (e.g., http://localhost:3000)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://malcmind.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to MongoDB
client = AsyncIOMotorClient(MONGODB_CONNECTION_URL)
db = client['Next_JS_Portfolio']
collection = db['mycollection']
blogs_collection = db['AI_Blogs']

# Pydantic model for input validation
class Blog(BaseModel):
    Title: str
    BlogType: str
    MarkdownContent: str


# Define the Pydantic models

class IPRequest(BaseModel):
    ip_address: IPvAnyAddress = Field(..., description="The IP address of the requester")
    request_count: int = Field(default=0, description="Total number of requests from this IP")

class IPRequestResponse(BaseModel):
    ip_address: IPvAnyAddress
    request_count: int

# Route to retrieve all blog posts

# Route to retrieve or create an IP entry with a request_count of 0
@app.get("/requests/no-increment/{ip_address}", response_model=IPRequestResponse)
async def get_or_create_no_increment(ip_address: str):
    result = await collection.find_one_and_update(
        {"ip_address": ip_address},
        {"$setOnInsert": {"ip_address": ip_address, "request_count": 0}},  # Only set if inserting
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if result:
        return {"ip_address": result["ip_address"], "request_count": result["request_count"]}
    raise HTTPException(status_code=500, detail="Failed to retrieve or create IP entry")


# Route to retrieve or create an IP entry and increment the count
@app.get("/requests/increment/{ip_address}", response_model=IPRequestResponse)
async def get_or_create_and_increment(ip_address: str):
    result = await collection.find_one_and_update(
        {"ip_address": ip_address},
        {
            "$inc": {"request_count": 1},  # Increment the count by 1
            "$setOnInsert": {"ip_address": ip_address},  # Set on insert only
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if result:
        return {"ip_address": result["ip_address"], "request_count": result["request_count"]}
    raise HTTPException(status_code=500, detail="Failed to retrieve or increment IP entry")



# Route to reset the request count for an IP address to zero
@app.post("/requests/reset/{ip_address}", response_model=IPRequestResponse)
async def reset_request_count(ip_address: str):
    result = await collection.find_one_and_update(
        {"ip_address": ip_address},
        {"$set": {"request_count": 0}},  # Reset the count to 0
        return_document=ReturnDocument.AFTER,
    )
    if result:
        return {"ip_address": result["ip_address"], "request_count": result["request_count"]}
    raise HTTPException(
        status_code=404, detail=f"No entry found for IP address {ip_address}"
    )

@app.delete("/api/delete-blog/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blog(blog_id: str):
    """Delete a blog post by its ID."""

    result = await blogs_collection.delete_one({"_id": ObjectId(blog_id)})

    if result.deleted_count == 1:
        return  # Return 204 No Content on successful deletion
    else:
        raise HTTPException(status_code=404, detail=f"Blog with id {blog_id} not found") 


# Route to create a new blog post
@app.post("/api/add-blog")
async def add_blog(blog: Blog):
    # Create a new blog document
    new_blog = {
        "Title": blog.Title,
        "BlogType": blog.BlogType,
        "MarkdownContent": blog.MarkdownContent
    }

    # Insert the blog into the MongoDB collection
    result = await blogs_collection.insert_one(new_blog)

    # Return a success response with the blog ID
    return {"message": "Blog added", "id": str(result.inserted_id)}

class UpdateBlogContentRequest(BaseModel):
    markdown_content: str

@app.patch("/api/update-blog-content/{blog_id}")
async def update_blog_content(blog_id: str, payload: UpdateBlogContentRequest):
    # Use the markdown_content from the request body
    update_document = {
        "$set": {
            "MarkdownContent": payload.markdown_content
        }
    }

    # Update the blog in the MongoDB collection
    result = await blogs_collection.update_one({"_id": ObjectId(blog_id)}, update_document)

    # Check if a document was updated
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Blog not found")

    # Return a success response
    return {"message": "Markdown content updated successfully"}

# Define the user model for creating a new user
class UserCreate(BaseModel):
    username: str
    email: str

# POST route to create a new user
@app.post("/dbusers/", tags=["dbusers"])
async def create_dbuser(user: UserCreate):
    # Check if user with the same email already exists
    existing_user = await collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Insert the new user into the database
    new_user = await collection.insert_one(user.dict())
    # Create response with the inserted user
    return {"user_id": str(new_user.inserted_id), "username": user.username}

@app.get("/dbusers/{user_id}", tags=["dbusers"])
async def get_dbuser(user_id: str):
    user = await collection.find_one({"_id": user_id})
    if user:
        return {"user_id": user_id, "username": user["username"]}
    raise HTTPException(status_code=404, detail="User not found")

@app.get("/dbusers/username/{username}", tags=["dbusers"])
async def get_dbuser_by_username(username: str):
    user = await collection.find_one({"username": username})
    if user:
        return {"user_id": str(user["_id"]), "username": user["username"]}
    raise HTTPException(status_code=404, detail="User not found")


# Define a route to handle GET requests to "/"
@app.get("/", tags=["root"])
async def read_root():
    return {"message": "Hello, World!"}

#Query params http://127.0.0.1:8000/greet?name=Alice
@app.get("/greet", tags=["greet"])
async def greet_user(name: str = "Guest"):
    return {"message": f"Hello, {name}!"}

#Path params http://127.0.0.1:8000/users/123
@app.get("/users/{user_id}", tags=["greet"])
async def get_user(user_id: int):
    return {"user_id": user_id, "username": f"User{user_id}"}


# Define a Pydantic model for request body validation
class Item(BaseModel):
    name: str
    price: float
    description: str = None

# Define a route to handle POST requests to "/items/"
# Send a POST request to http://127.0.0.1:8000/items/ with JSON data like:
# {"name": "Foo", "price": 50.0, "description": "A very nice item"}
@app.post("/items/")
async def create_item(item: Item):
    return {"item_name": item.name, "item_price": item.price}

#Path params with error handling

from fastapi import HTTPException

@app.get("/items/{item_id}")
async def read_item(item_id: int):
    if item_id < 1:
        raise HTTPException(status_code=400, detail="Invalid item ID")
    return {"item_id": item_id}

