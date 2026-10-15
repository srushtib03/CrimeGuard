"""CrimeGuard authentication: two roles (police, crime_branch), hashed passwords, signed expiring tokens.
Standard library only - no extra dependencies."""
import base64, hashlib, hmac, json, os, secrets, time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
USERS_FILE = DATA_DIR / "users.json"
SECRET_FILE = DATA_DIR / ".auth_secret"
TOKEN_TTL = 8 * 3600
ROLES = {"police": "Police", "crime_branch": "Crime Branch"}

# Which API areas each role may use (enforced server-side by the middleware in main.py)
CRIME_BRANCH_ONLY = ("/api/shap", "/api/apriori", "/api/mining", "/api/olap")
PUBLIC = ("/api/health", "/api/auth/login")


def hash_password(password: str, salt: bytes | None = None, iterations: int = 200_000):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {"salt": salt.hex(), "hash": digest.hex(), "iterations": iterations}


def load_users():
    with open(USERS_FILE, encoding="utf-8") as f:
        return json.load(f)["users"]


def _secret() -> bytes:
    env = os.environ.get("CRIMEGUARD_SECRET")
    if env:
        return env.encode()
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32))
    return SECRET_FILE.read_text().strip().encode()


_failures: dict[str, list[float]] = {}


def _locked(username: str) -> bool:
    now = time.time()
    recent = [t for t in _failures.get(username, []) if now - t < 60]
    _failures[username] = recent
    return len(recent) >= 5


def authenticate(username: str, password: str, role: str):
    """Return (user, error). Wrong role is reported the same as wrong password."""
    username = (username or "").strip().lower()
    if _locked(username):
        return None, "Too many failed attempts. Please wait a minute and try again."
    for u in load_users():
        if u["username"].lower() == username:
            test = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), bytes.fromhex(u["salt"]), u["iterations"]).hex()
            if hmac.compare_digest(test, u["hash"]) and u["role"] == role:
                _failures.pop(username, None)
                return u, None
    _failures.setdefault(username, []).append(time.time())
    return None, "Invalid username, password or role."


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(user: dict) -> str:
    payload = {"u": user["username"], "name": user["name"], "role": user["role"], "exp": int(time.time()) + TOKEN_TTL}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def parse_token(token: str):
    try:
        body, sig = token.split(".", 1)
        good = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            return None
        payload = json.loads(_unb64(body))
        return payload if payload["exp"] > time.time() else None
    except Exception:
        return None


def check_access(path: str, role: str):
    """None if allowed, else an error message."""
    if role == "crime_branch":
        return None
    if path.startswith(CRIME_BRANCH_ONLY):
        return "This section is available to Crime Branch accounts only."
    return None
