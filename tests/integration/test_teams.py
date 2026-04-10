from support import LiveIntegrationTestCase, requires_live_integration


@requires_live_integration
class TeamsIntegrationTests(LiveIntegrationTestCase):
    def test_teams_smoke(self):
        runner = self.new_runner()
        user_id = runner.unique_id("u")
        team_id = runner.unique_id("team")
        membership_id: str | None = None

        try:
            runner.call(
                "users_create",
                {
                    "user_id": user_id,
                    "email": runner.make_email(user_id),
                    "password": "Passw0rd!123",
                    "name": "MCP Team Smoke User",
                },
            )
            runner.call("teams_create", {"team_id": team_id, "name": "MCP Smoke Team"})
            membership = runner.call(
                "teams_create_membership",
                {"team_id": team_id, "roles": ["owner"], "user_id": user_id},
            )
            membership_id = membership["$id"]
            runner.call(
                "teams_get_membership",
                {"team_id": team_id, "membership_id": membership_id},
            )
        finally:
            if membership_id:
                try:
                    runner.call(
                        "teams_delete_membership",
                        {"team_id": team_id, "membership_id": membership_id},
                    )
                except Exception:
                    pass
            try:
                runner.call("teams_delete", {"team_id": team_id})
            except Exception:
                pass
            try:
                runner.call("users_delete", {"user_id": user_id})
            except Exception:
                pass

        self.assert_no_unexpected_errors(runner)
