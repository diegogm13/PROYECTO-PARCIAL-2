"""Formato estándar de respuesta: {"statusCode": ..., "data": ...} o {"statusCode": ..., "error": ...}."""
from flask import jsonify


def ok(data, status=200):
    return jsonify({"statusCode": status, "data": data}), status


def fail(message, status):
    return jsonify({"statusCode": status, "error": message}), status


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status
