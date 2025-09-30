import unittest
import os
import logging
from datetime import datetime
from ib_cicd.promote_build_solution import main as promote_build_main
from ib_cicd.promote_solution import main as promote_solution_main
import shutil
import json


class TestRegressionSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure logging
        logging.basicConfig(
            filename=f'regression_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )

        # Verify required environment variables
        required_vars = [
            "SOURCE_HOST_URL",
            "TARGET_HOST_URL",
            "SOURCE_TOKEN",
            "TARGET_TOKEN",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        # Create test configs directory if it doesn't exist
        os.makedirs("regression/configs", exist_ok=True)

    def setUp(self):
        """Set up test environment before each test"""
        # Backup existing config if it exists
        if os.path.exists("config.json"):
            shutil.copy("config.json", "config.json.backup")

    def tearDown(self):
        """Clean up after each test"""
        # Restore original config if it existed
        if os.path.exists("config.json.backup"):
            shutil.move("config.json.backup", "config.json")
        elif os.path.exists("config.json"):
            os.remove("config.json")

    def _setup_config(self, config_file):
        """Helper method to set up configuration for each test"""
        config_path = f"regression/configs/{config_file}"
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file {config_file} not found")

        shutil.copy(config_path, "config.json")

        with open(config_path) as f:
            return json.load(f)

    def test_build_flow_migration(self):
        """Test end-to-end migration of a build flow solution"""
        config = self._setup_config("build_solution_config.json")
        logging.info(
            f"Starting build flow migration test with config: {json.dumps(config, indent=2)}"
        )

        try:
            # Run the migration
            promote_build_main(
                [
                    "--compile_solution",
                    "--download_solution",
                    "--create_build_project",
                    "--publish_build_app",
                    "--create_deployment",
                    "--delete_app",
                    "--delete_build",
                ]
            )

            self.assertTrue(True)

        except Exception as e:
            logging.error(f"Build flow migration failed: {str(e)}")
            raise

    def test_normal_flow_migration(self):
        """Test end-to-end migration of a normal flow solution"""
        config = self._setup_config("normal_flow_config.json")
        logging.info(
            f"Starting normal flow migration test with config: {json.dumps(config, indent=2)}"
        )

        try:
            # Run the migration
            promote_solution_main(
                [
                    "--compile_solution",
                    "--promote_solution_to_target",
                    "--upload_dependencies",
                    "--download_solution",
                    "--publish_advanced_app",
                    "--create_deployment",
                    "--delete_app",
                ]
            )

            self.assertTrue(True)

        except Exception as e:
            logging.error(f"Normal flow migration failed: {str(e)}")
            raise


if __name__ == "__main__":
    unittest.main()
