import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = "sales_intelligence"  # Default, but should match config

if not MONGO_URL:
    print("Error: MONGO_URL not found in .env file")
    sys.exit(1)

async def clear_database():
    print("Sales Intelligence Engine - Database Cleanup Utility")
    print("====================================================")
    
    # Connect to MongoDB
    try:
        client = AsyncIOMotorClient(MONGO_URL)
        # Test connection
        await client.admin.command('ping')
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)
        
    db = client[DB_NAME]
    print(f"Target Database: {DB_NAME}")
    
    # Get collections
    collections = await db.list_collection_names()
    target_collections = ["visitor_sessions", "users"]
    
    found_collections = [c for c in collections if c in target_collections]
    
    if not found_collections:
        print("No target collections found to clear.")
        return

    print(f"\nFound collections to clear: {', '.join(found_collections)}")
    print("\nWARNING: This will PERMANENTLY DELETE all data in these collections!")
    print("   This action cannot be undone.")
    
    confirm = input("\nAre you sure you want to proceed? (type 'yes' to confirm): ")
    
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return

    print("\nClearing data...")
    
    for col_name in found_collections:
        try:
            await db[col_name].drop()
            print(f"Dropped collection: {col_name}")
        except Exception as e:
            print(f"Failed to drop {col_name}: {e}")
            
    print("\nDatabase cleanup complete!")

if __name__ == "__main__":
    # Run async main
    try:
        asyncio.run(clear_database())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
