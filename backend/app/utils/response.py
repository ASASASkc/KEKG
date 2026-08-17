# -*- coding: utf-8 -*-
"""
统一响应格式
"""
from flask import jsonify


def ok(data=None, message='操作成功'):
    return jsonify({
        'code': 200,
        'success': True,
        'data': data,
        'message': message
    })


def created(data=None, message='创建成功'):
    return jsonify({
        'code': 201,
        'success': True,
        'data': data,
        'message': message
    }), 201


def fail(message='操作失败', code=400):
    return jsonify({
        'code': code,
        'success': False,
        'data': None,
        'message': message
    }), code


def not_found(message='资源不存在'):
    return fail(message, 404)


def server_error(message='服务器内部错误'):
    return fail(message, 500)
