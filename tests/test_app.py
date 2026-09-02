"""The app wiring: every tab must actually build, with a real Gradio import."""

import unittest

from studio import app
from studio.tools import BY_NAME, TOOLS


class TestToolSurface(unittest.TestCase):
    def test_every_tool_exposes_the_same_surface(self):
        for tool in TOOLS:
            self.assertTrue(tool.TITLE, tool.__name__)
            self.assertTrue(tool.TAGLINE, tool.__name__)
            self.assertTrue(callable(tool.run), tool.__name__)
            self.assertTrue(callable(tool.build_tab), tool.__name__)

    def test_tools_are_addressable_by_module_name(self):
        self.assertEqual(sorted(BY_NAME),
                         ["animation", "character", "cinematic", "clearance",
                          "continuity", "trailer"])


class TestBuildUI(unittest.TestCase):
    def test_the_whole_studio_builds(self):
        demo = app.build_ui()
        self.assertTrue(demo.blocks)

    def test_each_tool_builds_on_its_own(self):
        for name, tool in BY_NAME.items():
            with self.subTest(tool=name):
                self.assertTrue(app.build_ui([tool]).blocks)

    def test_an_unknown_tool_name_is_refused_clearly(self):
        with self.assertRaises(SystemExit) as caught:
            app.main(["nope"])
        self.assertIn("Unknown tool", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
