from fastapi import Request


def get_db(request: Request):
    return request.app.state.db


def get_gemini(request: Request):
    return request.app.state.gemini


def get_vector_search(request: Request):
    return request.app.state.vector_search


def get_livekit(request: Request):
    return request.app.state.livekit


def get_recommendations(request: Request):
    return request.app.state.recommendations


def get_reflections(request: Request):
    return request.app.state.reflections


def get_learning(request: Request):
    return request.app.state.learning
