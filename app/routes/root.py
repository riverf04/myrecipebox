from flask import Blueprint, jsonify

root_bp = Blueprint("root", __name__)


@root_bp.get("/")
def hello():
    return jsonify({"message": "Recipe Box API", "recipes": "/recipes"})