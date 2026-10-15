"""Add or reset a CrimeGuard login.   Usage:
    python manage_users.py add <username> <police|crime_branch> "<Display Name>"
    python manage_users.py list
"""
import getpass, json, sys
from auth import USERS_FILE, hash_password, ROLES

def load():
    return json.load(open(USERS_FILE, encoding="utf-8")) if USERS_FILE.exists() else {"users": []}

if len(sys.argv) >= 2 and sys.argv[1] == "list":
    for u in load()["users"]:
        print(f'{u["username"]:<16}{u["role"]:<14}{u["name"]}')
elif len(sys.argv) >= 4 and sys.argv[1] == "add":
    username, role = sys.argv[2].lower(), sys.argv[3]
    name = sys.argv[4] if len(sys.argv) > 4 else username
    if role not in ROLES:
        sys.exit(f"role must be one of {list(ROLES)}")
    pw = getpass.getpass("Password: ")
    data = load()
    data["users"] = [u for u in data["users"] if u["username"] != username]
    data["users"].append({"username": username, "name": name, "role": role, **hash_password(pw)})
    json.dump(data, open(USERS_FILE, "w", encoding="utf-8"), indent=2)
    print("saved", username)
else:
    print(__doc__)
