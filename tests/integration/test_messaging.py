from support import LiveIntegrationTestCase, requires_live_integration


@requires_live_integration
class MessagingIntegrationTests(LiveIntegrationTestCase):
    def test_messaging_smoke(self):
        runner = self.new_runner()
        topic_id = runner.unique_id("topic")
        message_id = runner.unique_id("msg")

        try:
            runner.call("messaging_list_messages")
            runner.call(
                "messaging_create_topic",
                {"topic_id": topic_id, "name": "MCP Smoke Topic"},
            )
            runner.call(
                "messaging_create_email",
                {
                    "message_id": message_id,
                    "subject": "MCP Smoke",
                    "content": "hello",
                    "draft": True,
                },
            )
            runner.call("messaging_get_message", {"message_id": message_id})
        finally:
            try:
                runner.call("messaging_delete", {"message_id": message_id})
            except Exception:
                pass
            try:
                runner.call("messaging_delete_topic", {"topic_id": topic_id})
            except Exception:
                pass

        self.assert_no_unexpected_errors(runner)
