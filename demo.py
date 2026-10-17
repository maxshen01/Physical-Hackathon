"""One HTTPS origin for recognition, image features and spoken feedback."""
from kinevoa_classifier.api import create_app
from llm.physio_coach.main import app as feedback_app


def create_demo_app(**classifier_options):
    app = create_app(**classifier_options)
    app.include_router(feedback_app.router)
    return app


app = create_demo_app()
