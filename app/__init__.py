from flask import Flask
from app.config import load_configurations, configure_logging
from .views import webhook_blueprint
from dotenv import load_dotenv
import os

load_dotenv()


def create_app():
    app = Flask(__name__)

    # Load configurations and logging settings
    load_configurations(app)
    configure_logging()

    # Import and register blueprints, if any
    app.register_blueprint(webhook_blueprint)

    # Face Cutout API settings
    app.config['FACE_CUTOUT_API_KEY'] = os.environ.get('FACE_CUTOUT_API_KEY')

    # Add a root route
    @app.route('/')
    def home():
        return 'WhatsApp Bot Service is running'

    return app
