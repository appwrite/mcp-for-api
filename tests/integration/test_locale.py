from support import LiveIntegrationTestCase, requires_live_integration


@requires_live_integration
class LocaleIntegrationTests(LiveIntegrationTestCase):
    def test_locale_smoke(self):
        runner = self.new_runner()

        runner.call("locale_get")
        runner.call("locale_list_languages")

        self.assert_no_unexpected_errors(runner)
