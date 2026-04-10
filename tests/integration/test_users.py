from support import LiveIntegrationTestCase, requires_live_integration


@requires_live_integration
class UsersIntegrationTests(LiveIntegrationTestCase):
    def test_users_smoke(self):
        runner = self.new_runner()
        user_id = runner.unique_id("u")

        try:
            runner.call("users_list")
            runner.call(
                "users_create",
                {
                    "user_id": user_id,
                    "email": runner.make_email(user_id),
                    "password": "Passw0rd!123",
                    "name": "MCP Smoke User",
                },
            )
            runner.call("users_get", {"user_id": user_id})
            runner.call(
                "users_update_name",
                {"user_id": user_id, "name": "MCP Smoke User Updated"},
            )
        finally:
            try:
                runner.call("users_delete", {"user_id": user_id})
            except Exception:
                pass

        self.assert_no_unexpected_errors(runner)
