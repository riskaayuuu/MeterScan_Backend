from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.db import mongo

activity_bp = Blueprint('activity_bp', __name__)

@activity_bp.route('/activity-logs', methods=['GET'])
@jwt_required()
def get_activity_logs():

    user_id = get_jwt_identity()

    logs = mongo.db.activity_logs.find(
        {"user_id": str(user_id)}
    ).sort("created_at", -1)

    result = []

    for log in logs:
        result.append({
            "activity": log.get("activity", ""),
            "description": log.get("description", ""),
            "created_at": str(log.get("created_at", ""))
        })

    return jsonify(result), 200