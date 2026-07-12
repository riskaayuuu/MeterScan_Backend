from datetime import datetime
from utils.db import mongo

def save_activity(user_id, activity, description):
    mongo.db.activity_logs.insert_one({
        "user_id": str(user_id),
        "activity": activity,
        "description": description,
        "created_at": datetime.utcnow()
    })