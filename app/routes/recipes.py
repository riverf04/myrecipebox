from flask import Blueprint, jsonify, request, g
import sys
import sqlite3
from app.services.recipe_service import (
    get_all_recipes,
    get_recipe_by_id,
    create_recipe as service_create_recipe,
    get_recipes_for_user,
)
from app.services.auth_service import token_required
from app.db import get_db


recipes_bp = Blueprint("recipes", __name__, url_prefix="/recipes")


def recipe_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "ingredients": row["ingredients"],
        "instructions": row["instructions"],
        "is_public": bool(row["is_public"]),
    }


def ensure_owner_or_admin(recipe, user_id, user_role):
    owner_id = (
        recipe["owner_id"]
        if "owner_id" in recipe.keys()
        else recipe["user_id"]
        if "user_id" in recipe.keys()
        else None
    )

    if (owner_id is None or int(owner_id) != user_id) and user_role != "admin":
        return jsonify({"error": "Forbidden"}), 403

    return None


@recipes_bp.get("")
def list_recipes():
    recipes = get_all_recipes()
    return jsonify(recipes)


@recipes_bp.get("/mine")
@token_required
def list_my_recipes():
    user_id = g.user_id
    recipes = get_recipes_for_user(user_id)
    return jsonify(recipes)


@recipes_bp.get("/<int:recipe_id>")
def get_recipe(recipe_id):
    recipe_dict = get_recipe_by_id(recipe_id)
    if recipe_dict is None:
        return jsonify({"error": "recipe not found"}), 404

    return jsonify(recipe_dict)


@recipes_bp.post("")
def create_recipe():
    data = request.get_json(silent=True)
    if not data or not data.get("title") or not data.get("ingredients"):
        return jsonify({"error": "title and ingredients are required"}), 400

    user_id = getattr(g, "user_id", None)
    print("DEBUG user_id in route:", user_id, file=sys.stderr)

    new_recipe = service_create_recipe(data, user_id)
    if new_recipe is None:
        return jsonify({"error": "a recipe with that title already exists"}), 409

    return jsonify(new_recipe), 201


@recipes_bp.patch("/<int:recipe_id>")
@token_required
def update_recipe(recipe_id):
    user_id = g.user_id
    user_role = g.user_role

    db = get_db()
    recipe = (
        db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
        .fetchone()
    )

    if recipe is None:
        return jsonify({"error": "recipe not found"}), 404

    denial = ensure_owner_or_admin(recipe, user_id, user_role)
    if denial is not None:
        return denial

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "a JSON body is required"}), 400
    fields, values = [], []
    for column in ("title", "ingredients", "instructions"):
        if column in data:
            fields.append(f"{column} = ?")
            values.append(data[column])
    if "is_public" in data:
        fields.append("is_public = ?")
        values.append(1 if data["is_public"] else 0)
    if not fields:
        return jsonify({"error": "nothing to update"}), 400
    values.append(recipe_id)

    try:
        cur = db.execute(
            f"UPDATE recipes SET {', '.join(fields)} WHERE id = ?", values
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "a recipe with that title already exists"}), 409

    row = (
        db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
        .fetchone()
    )
    return jsonify(recipe_to_dict(row))


@recipes_bp.delete("/<int:recipe_id>")
@token_required
def delete_recipe(recipe_id):
    user_id = g.user_id
    user_role = g.user_role

    db = get_db()
    recipe = (
        db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
        .fetchone()
    )

    if recipe is None:
        return jsonify({"error": "recipe not found"}), 404

    denial = ensure_owner_or_admin(recipe, user_id, user_role)
    if denial is not None:
        return denial

    db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    db.commit()
    return "", 204