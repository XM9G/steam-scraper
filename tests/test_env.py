from pathlib import Path
import tempfile
import unittest

from main import load_env


class LoadEnvTests(unittest.TestCase):
    def load(self, text, environ=None):
        environ = {} if environ is None else environ
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_text(text, encoding="utf-8")
            load_env(path, environ)
        return environ

    def test_reads_values_and_skips_comments(self):
        env = self.load(
            "# comment\n"
            "\n"
            "KUMA_PUSH_URL=https://status.example.com/api/push/abc\n"
            'DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/1/x?a=b"\n'
            "export QUOTED='single'\n"
            "not a setting\n"
        )
        self.assertEqual(env, {
            "KUMA_PUSH_URL": "https://status.example.com/api/push/abc",
            "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/1/x?a=b",
            "QUOTED": "single",
        })

    def test_existing_environment_wins(self):
        env = self.load("KUMA_PUSH_URL=from-file\n", {"KUMA_PUSH_URL": "from-env"})
        self.assertEqual(env["KUMA_PUSH_URL"], "from-env")

    def test_missing_file_is_fine(self):
        environ = {}
        load_env(Path("/nonexistent/.env"), environ)
        self.assertEqual(environ, {})


if __name__ == "__main__":
    unittest.main()
