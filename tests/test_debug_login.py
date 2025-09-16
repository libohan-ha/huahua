import sys
import types
import unittest


def ensure_stub_modules():
    if "flask_login" not in sys.modules:
        flask_login = types.ModuleType("flask_login")

        class DummyLoginManager:
            def __init__(self):
                self.login_view = None
                self._user_callback = None

            def init_app(self, app):
                self.app = app

            def user_loader(self, callback):
                self._user_callback = callback
                return callback

        class DummyUserMixin:
            pass

        def login_user(user):  # noqa: D401 - simple stub
            return None

        def logout_user():
            return None

        def login_required(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            wrapper.__name__ = func.__name__
            return wrapper

        flask_login.LoginManager = DummyLoginManager
        flask_login.UserMixin = DummyUserMixin
        flask_login.login_user = login_user
        flask_login.logout_user = logout_user
        flask_login.login_required = login_required
        flask_login.current_user = types.SimpleNamespace(is_authenticated=False)
        sys.modules["flask_login"] = flask_login

    if "authlib.integrations.flask_client" not in sys.modules:
        authlib = types.ModuleType("authlib")
        integrations = types.ModuleType("authlib.integrations")
        flask_client = types.ModuleType("authlib.integrations.flask_client")

        class DummyOAuth:
            def __init__(self, app):
                self.app = app

        flask_client.OAuth = DummyOAuth
        authlib.integrations = integrations
        integrations.flask_client = flask_client
        sys.modules["authlib"] = authlib
        sys.modules["authlib.integrations"] = integrations
        sys.modules["authlib.integrations.flask_client"] = flask_client

    if "supabase" not in sys.modules:
        supabase = types.ModuleType("supabase")

        class DummyQuery:
            def select(self, *args, **kwargs):
                return self

            def eq(self, *args, **kwargs):
                return self

            def insert(self, *args, **kwargs):
                return self

            def delete(self, *args, **kwargs):
                return self

            def execute(self):
                return types.SimpleNamespace(data=[])

        class DummyAuth:
            def sign_in_with_password(self, *args, **kwargs):
                return types.SimpleNamespace(user=types.SimpleNamespace(id="test-user"))

            def sign_up(self, *args, **kwargs):
                return types.SimpleNamespace(user=types.SimpleNamespace(id="test-user"))

            def sign_out(self):
                return None

            def get_user(self):
                return types.SimpleNamespace(user=types.SimpleNamespace(id="test-user"))

        class DummyClient:
            def __init__(self):
                self.auth = DummyAuth()

            def table(self, *args, **kwargs):
                return DummyQuery()

        def create_client(url, key):
            return DummyClient()

        supabase.create_client = create_client
        sys.modules["supabase"] = supabase


def _prepare_environment():
    ensure_stub_modules()


_prepare_environment()

from app import DEFAULT_SECRET_KEY, app  # noqa: E402  pylint: disable=wrong-import-position


class DebugLoginRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.original_secret = app.secret_key

    def tearDown(self):
        app.secret_key = self.original_secret

    def test_debug_login_reports_default_secret(self):
        app.secret_key = DEFAULT_SECRET_KEY
        response = self.client.get("/debug-login")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, dict)
        self.assertIn("using_default_secret_key", data)
        self.assertTrue(data["using_default_secret_key"])
        self.assertIn("session_keys", data)
        self.assertIsInstance(data["session_keys"], list)
        self.assertFalse(data["logged_in"])

    def test_debug_login_reports_custom_secret(self):
        app.secret_key = "custom-secret-value"
        response = self.client.get("/debug-login")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("using_default_secret_key", data)
        self.assertFalse(data["using_default_secret_key"])


if __name__ == "__main__":
    unittest.main()
