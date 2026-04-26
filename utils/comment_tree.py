from models import Comment
from utils.serializers import comment_to_dict

def build_comment_tree(comments: list[Comment]) -> list[dict]:
    comments_dicts = []

    for comment in comments:
        comment_data = comment_to_dict(comment)
        comment_data["replies"] = []
        comments_dicts.append(comment_data)

    comments_map = {comment["id"]: comment for comment in comments_dicts}

    root_comments = []

    for comment in comments_dicts:
        if comment["parent_id"] is None:
            root_comments.append(comment)
        else:
            parent = comments_map.get(comment["parent_id"])
            if parent:
                parent["replies"].append(comment)

    return root_comments
