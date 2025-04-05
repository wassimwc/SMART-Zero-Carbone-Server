from fastapi import FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()
origins = [
    "http://127.0.0.1:5500",  
    "http://localhost:5500",
    "http://192.168.1.15:5500",
]
# Enable CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow these frontend origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# MongoDB Connection
MONGO_URI = "mongodb://localhost:27017"  # Change this if using MongoDB Atlas
DB_NAME = "sensors_data"
#COLLECTION_NAME = "Sensors_data"

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]
#collection = db[COLLECTION_NAME]

# Test Route
@app.get("/")
async def root():
    return {"message": "API is running"}

# Add a company
@app.post("/add-company/")
async def add_company(company: dict):
    result = await collection.insert_one(company)
    return {"message": "Company added", "id": str(result.inserted_id)}

# Search for a company
@app.get("/search-company/")
async def search_company(collection: str):
    company_data = await db[collection].find().to_list(length=None)  # Fetch all documents
    for data in company_data:
        data["_id"] = str(data["_id"])  # Convert ObjectId to string
    return company_data


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)