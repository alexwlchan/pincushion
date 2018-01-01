# -*- encoding: utf-8

import pytest

from pincushion.flask import app


@pytest.fixture
def flask_app():
    app.testing = True
    client = app.test_client()
    yield client


def test_404_gives_custom_404_response(flask_app):
    result = flask_app.get('/login')
    assert result.status_code == 404
    assert b'404 Not Found' in result.data
