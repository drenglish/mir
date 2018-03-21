#!/usr/bin/env python

"""
Shared application utility functions.
"""

import os
import importlib
from base64 import b64encode

from itsdangerous import Signer, BadSignature
import bcrypt

from eve.auth import BasicAuth
from flask import current_app as app


class UserListAuth(BasicAuth):
    # TODO: rework token refreshing, etc
    # TODO: https://pyjwt.readthedocs.io/en/latest/usage.html
    def check_auth(self, username, password, allowed_roles, resource, method):
        accounts = app.data.driver.db['accounts']
        lookup = {'username': username}
        if allowed_roles:
            lookup['roles'] = {'$in': allowed_roles}
        account = accounts.find_one(lookup)

        if account:
            try:
                s = Signer(app.config['SECRET_KEY'])
                s.unsign(password)
                if password == account["token"]:
                    return True
                else:
                    return False
            except BadSignature:
                pass

            return account and \
                bcrypt.hashpw(password.encode('utf-8'), account['password'].encode('utf-8')) == account['password']

# -----------------------------------
# Factory Meta Programming Helpers
# -----------------------------------

def is_an_attribute_name(attributes_path, filename):
    if (
            os.path.isfile(os.path.join(attributes_path, filename))
            and filename.endswith('py')
            and not filename.startswith('__init__')
    ):
        return True
    else:
        return False


def get_attribute_names(models_path):
    return [name.split('.')[0] for name in os.listdir(models_path) if is_an_attribute_name(models_path, name)]


# -----------------------------------
# Decorators
# -----------------------------------

def register_hook(*args):
    def decorate(f):
        def wrapper(app):
            for event in args:
                e = getattr(app, event) if hasattr(app, event) else None
                if e is not None:
                    e += f
        return wrapper
    return decorate


# -----------------------------------
# General Helpers
# -----------------------------------

def generate_token(SECRET_KEY, username):
    # TODO: Rework token implementation
    # TODO: Add expiration
    s = Signer(SECRET_KEY)
    random_bytes = os.urandom(32)
    uuid = b64encode(random_bytes)
    return s.sign(uuid).decode('utf-8')


def get_settings_dict():
    settings_module = importlib.import_module('settings')
    settings = {
        setting: getattr(settings_module, setting)
        for setting in dir(settings_module)
        if not setting.startswith('_')
    }

    return settings


def get_models():
    def process_auth(v):
        auth = {
            'UserListAuth': UserListAuth
        }
        for key, value in v.items():
            if key == 'authentication' and isinstance(value, basestring):
                v[key] = auth[value]
        return v

    def register_model(directory, model_name):
        name = model_name.split('.')[0]
        print '%s.%s' % (directory, name)
        model = getattr(
            importlib.import_module(
                '%s.%s' % (directory, name)
            ), 'model'
        )
        return {
            name: model
        }

    def create_domain(all_models):
        return {k: process_auth(v) for d in all_models for k, v in d.items()}

    user_model_dir = os.path.join(os.getcwd(), 'models')
    default_model_dir = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'default_models'
    )

    all_models = [
        register_model(user_model_dir.split('/')[-1], item)
        for item in os.listdir(user_model_dir)
        if not item.startswith("__")
    ] + [
        register_model('mir.lib.%s' % default_model_dir.split('/')[-1], item)
        for item in os.listdir(default_model_dir)
        if not item.startswith("__")
    ]

    return create_domain(all_models)
